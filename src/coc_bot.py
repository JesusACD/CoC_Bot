from utils import *
try:
    import configs
    from configs import *
except:
    import configs_build as configs
    from configs_build import *
from upgrader import Upgrader
from attacker import Attacker

class CoC_Bot:
    def __init__(self):
        self.upgrader = Upgrader()
        self.attacker = Attacker()
    
    def step(self):
        import time

        if not online():
            logger.warning("Device offline.")
            return False

        if not running():
            logger.info("Bot paused.")
            return False
        
        started, res = start_coc(detailed=True)
        if started:
            update_status("now")
            
            Task_Handler.get_exclusions()
            exclude_home_base = Task_Handler.excluded("home_base", use_cached=True)
            exclude_home_lab = Task_Handler.excluded("home_lab", use_cached=True)
            exclude_pets = Task_Handler.excluded("pet_house", use_cached=True)
            skip_home_base_upgrades = exclude_home_base and exclude_home_lab and exclude_pets
            exclude_home_attacks = Task_Handler.excluded("home_attacks", use_cached=True)
            
            exclude_builder_base = Task_Handler.excluded("builder_base", use_cached=True)
            exclude_builder_lab = Task_Handler.excluded("builder_lab", use_cached=True)
            skip_builder_base_upgrades = exclude_builder_base and exclude_builder_lab
            exclude_builder_attacks = Task_Handler.excluded("builder_attacks", use_cached=True)
            
            # Check home base
            in_home = True
            if not skip_home_base_upgrades or not exclude_home_attacks:
                in_home = to_home_base(ref_cache=True)
            
            if in_home:
                if not skip_home_base_upgrades:
                    logger.info("Upgrading home base")
                    self.upgrader.run_home_base(exclude_home_base, exclude_home_lab, exclude_pets)
                if not exclude_home_attacks:
                    logger.info("Attacking home base")
                    self.attacker.run_home_base(restart=not skip_home_base_upgrades or not skip_builder_base_upgrades)
            else:
                logger.error("Could not confirm home base; skipping home base tasks to avoid acting on builder base.")
            
            # Check builder base
            in_builder = False
            if not skip_builder_base_upgrades or not exclude_builder_attacks:
                in_builder = to_builder_base(ref_cache=True)
            
            if in_builder:
                if not skip_builder_base_upgrades:
                    logger.info("Upgrading builder base")
                    self.upgrader.collect_builder_attack_elixir()
                    self.upgrader.run_builder_base(exclude_builder_base, exclude_builder_lab)
                if not exclude_builder_attacks:
                    logger.info("Attacking builder base")
                    self.attacker.run_builder_base()
            elif not skip_builder_base_upgrades or not exclude_builder_attacks:
                logger.error("Could not confirm builder base; skipping builder base tasks.")
            
            to_home_base()
            stop_coc(sleep=configs.SUSPEND_EMULATOR_ON_IDLE)
            update_status(time.time())
            return True
        elif res == "error":
            update_status("error")
            return False
        return False

    def run(self, once=False):
        import time
        
        while True:
            try:
                self.step()
                if once:
                    break
                time.sleep(60 * configs.CHECK_INTERVAL)
            except (KeyboardInterrupt, SystemExit): raise
            except Exception:
                logger.exception("CoC_Bot.run:")
                stop_coc()
                update_status("error")
                if once:
                    break
                time.sleep(60 * configs.CHECK_INTERVAL)
