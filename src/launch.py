try:
    from configs import *
except:
    from configs_build import *

def gui_disable_sleep():
    import time, utils
    utils.disable_sleep()
    while True: time.sleep(1)

def launch_proc(args):
    from log import enable_logging, logger
    import configs
    from utils import parse_args, init_instance, Emulator_Manager
    from coc_bot import CoC_Bot
    
    once = getattr(args, "once", False)
    parse_args(args.debug, args.id, args.gui, args.gui_port, once=once)
    init_instance(args.id)
    enable_logging(args.id)
    bot = CoC_Bot()
    try:
        bot.run(once=once)
    finally:
        if once and getattr(configs, "AUTO_START_EMULATOR", True):
            try:
                logger.info(f"Shutting down emulator for instance '{args.id}'...")
                Emulator_Manager.stop()
            except Exception:
                logger.exception(f"Error stopping emulator for '{args.id}':")

def cmd_rotate(args):
    import time
    from multiprocessing import Process
    from copy import deepcopy
    from log import logger
    import configs
    import utils

    if DISABLE_DEVICE_SLEEP: utils.disable_sleep()
    
    gui_port = getattr(args, "gui_port", None)
    def report_rotation(payload):
        if gui_port is None:
            return
        try:
            import requests
            requests.post(
                f"http://127.0.0.1:{gui_port}/rotation_status",
                json=payload,
                timeout=(1, 2),
            )
        except Exception:
            pass

    logger.info(f"Starting sequential rotation mode for instances: {configs.INSTANCE_IDS}")
    logger.info(f"Interval between rotation rounds: {configs.CHECK_INTERVAL} minutes")
    
    current_child = None
    def cleanup_child():
        nonlocal current_child
        report_rotation({
            "active": False,
            "current_id": None,
            "status": "idle",
            "next_round_at": 0,
        })
        if current_child and current_child.is_alive():
            try:
                current_child.terminate()
                current_child.join()
            except: pass
    
    import atexit
    atexit.register(cleanup_child)
    
    try:
        round_num = 1
        while True:
            logger.info("==================================================")
            logger.info(f"--- Starting Rotation Round #{round_num} ---")
            logger.info("==================================================")
            
            for instance_id in configs.INSTANCE_IDS:
                logger.info(f"[{instance_id}] Starting turn...")
                report_rotation({
                    "active": True,
                    "current_id": instance_id,
                    "round": round_num,
                    "status": "running",
                    "next_round_at": 0,
                })
                args_copy = deepcopy(args)
                args_copy.id = instance_id
                args_copy.once = True
                
                current_child = Process(target=launch_proc, args=(args_copy,))
                current_child.start()
                try:
                    current_child.join()
                except (KeyboardInterrupt, SystemExit):
                    if current_child and current_child.is_alive():
                        current_child.terminate()
                        current_child.join()
                    raise
                finally:
                    current_child = None
                
                logger.info(f"[{instance_id}] Turn finished.")
                time.sleep(5)
            
            logger.info(f"Round #{round_num} complete for all instances.")
            logger.info(f"All emulators stopped. Waiting {configs.CHECK_INTERVAL} minutes before next round...")
            wait_seconds = int(60 * configs.CHECK_INTERVAL)
            report_rotation({
                "active": True,
                "current_id": None,
                "round": round_num,
                "status": "waiting",
                "next_round_at": time.time() + wait_seconds,
            })
            round_num += 1
            
            for _ in range(wait_seconds):
                time.sleep(1)
                
    except (KeyboardInterrupt, SystemExit):
        report_rotation({
            "active": False,
            "current_id": None,
            "status": "idle",
            "next_round_at": 0,
        })
        logger.info("Sequential rotation stopped by user.")

def cmd_launch(args):
    import utils
    if DISABLE_DEVICE_SLEEP: utils.disable_sleep()
    if getattr(args, "rotate", False) and (args.id is None or args.id == "rotate"):
        cmd_rotate(args)
    else:
        launch_proc(args)

def gui_launch(args):
    from multiprocessing import Process
    from gui import init_gui, get_gui
    from copy import deepcopy
    
    procs = {}
    pipe = init_gui(args.id)
    args.gui_port = get_gui().server_port
    
    sleep_proc = None
    if DISABLE_DEVICE_SLEEP:
        sleep_proc = Process(target=gui_disable_sleep, daemon=True)
        sleep_proc.start()

    if getattr(args, "rotate", False) and args.id is None:
        p = Process(target=cmd_rotate, args=(args,))
        p.start()
        procs["rotate"] = p
    elif args.id is not None:
        p = Process(target=launch_proc, args=(args,))
        p.start()
        procs[args.id] = p

    try:
        while True:
            data = pipe.recv()
            if data == -1: raise SystemExit
            action, id = data.get("action"), data.get("id")
            if action == "start":
                if id == "rotate":
                    if "rotate" not in procs or not procs["rotate"].is_alive():
                        args_copy = deepcopy(args)
                        args_copy.rotate = True
                        p = Process(target=cmd_rotate, args=(args_copy,))
                        p.start()
                        procs["rotate"] = p
                else:
                    args_copy = deepcopy(args)
                    args_copy.id = data.get("id")
                    p = Process(target=launch_proc, args=(args_copy,))
                    p.start()
                    procs[id] = p
            elif action == "stop":
                p = procs.pop(id, None)
                if p and p.is_alive():
                    p.terminate()
                    p.join()
    except (EOFError, KeyboardInterrupt, SystemExit):
        get_gui().stop()
        pipe.close()
        if sleep_proc is not None: sleep_proc.terminate()
        for p in procs.values():
            if p and p.is_alive():
                p.terminate()
                p.join()

def launch():
    import utils
    args = utils.parse_args()
    if args.gui: gui_launch(args)
    else: cmd_launch(args)
