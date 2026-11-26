import sys
from pathlib import Path

if hasattr(sys, "_MEIPASS"):
    path = Path(sys._MEIPASS) / "gui_server"
else:
    path = Path(__file__).parent.resolve()
    sys.path.append(str(path.parent))

sys.path.append(str(path))

import os
import time
from flask import Flask, render_template, jsonify, abort, request
try:
    import configs
    from configs import *
except:
    import configs_build as configs
    from configs_build import *
from config_manager import get_instance_config

app = Flask(__name__)
bot_pipe = None

class Instance:
    def __init__(self, id=None):
        self.id = id if id is not None else ""
        self.run_status = ""
        self.end_time = 0
        task_settings = {
            "home_base_priority": not get_instance_config(self.id, "PRIORITY_HOME_BASE_UPGRADES", True, cfg=configs),
            "home_lab_priority": not get_instance_config(self.id, "PRIORITY_HOME_LAB_UPGRADES", True, cfg=configs),
            "pet_house_priority": not get_instance_config(self.id, "PRIORITY_PET_UPGRADES", True, cfg=configs),
            "builder_base_priority": not get_instance_config(self.id, "PRIORITY_BUILDER_BASE_UPGRADES", True, cfg=configs),
            "builder_lab_priority": not get_instance_config(self.id, "PRIORITY_BUILDER_LAB_UPGRADES", True, cfg=configs),
            "heroes": not get_instance_config(self.id, "UPGRADE_HEROES", True, cfg=configs),
            "home_base": not get_instance_config(self.id, "UPGRADE_HOME_BASE", True, cfg=configs),
            "builder_base": not get_instance_config(self.id, "UPGRADE_BUILDER_BASE", True, cfg=configs),
            "home_lab": not get_instance_config(self.id, "UPGRADE_HOME_LAB", True, cfg=configs),
            "builder_lab": not get_instance_config(self.id, "UPGRADE_BUILDER_LAB", True, cfg=configs),
            "pet_house": not get_instance_config(self.id, "UPGRADE_PETS", True, cfg=configs),
            "home_attacks": not get_instance_config(self.id, "ATTACK_HOME_BASE", True, cfg=configs),
            "builder_attacks": not get_instance_config(self.id, "ATTACK_BUILDER_BASE", True, cfg=configs),
            "lab_assistant": not get_instance_config(self.id, "ASSIGN_LAB_ASSISTANT", True, cfg=configs),
            "builder_apprentice": not get_instance_config(self.id, "ASSIGN_BUILDER_APPRENTICE", True, cfg=configs),
            "remove_obstacles": not get_instance_config(self.id, "REMOVE_OBSTACLES", True, cfg=configs),
        }
        self.exclusions = set(k for k, v in task_settings.items() if v)

instances = {}
rotation_state = {
    "active": False,
    "current_id": None,
    "round": 0,
    "status": "idle",  # "idle" | "running" | "waiting"
    "next_round_at": 0,
}

@app.route("/", methods=["GET"])
def home():
    active_ids = [inst_id for inst_id in instances.keys() if inst_id != "rotate"]
    all_ids = sorted(list(set(active_ids + list(configs.INSTANCE_IDS))))
    return render_template(
        "home.html",
        ids=all_ids,
        rotating="rotate" in instances,
        rotation_state=rotation_state,
    )

@app.route("/rotation_status", methods=["GET", "POST"])
def handle_rotation_status():
    global rotation_state
    if request.method == "POST":
        data = request.json or {}
        if "active" in data:
            rotation_state["active"] = bool(data["active"])
        if "current_id" in data:
            rotation_state["current_id"] = data["current_id"]
        if "round" in data:
            rotation_state["round"] = data["round"]
        if "status" in data:
            rotation_state["status"] = data["status"]
        if "next_round_at" in data:
            rotation_state["next_round_at"] = data["next_round_at"]
    return jsonify({
        **rotation_state,
        "rotating": "rotate" in instances or rotation_state["active"],
        "current_time": time.time(),
    })

@app.route("/instances/<id>", methods=["GET"])
def handle_instance(id):
    instance = instances.get(id)
    if not instance: abort(404)
    return render_template(
        "instance.html",
        id=id,
        web_app_url=WEB_APP_URL,
        end_time=instance.end_time,
        current_time=time.time(),
        run_status=instance.run_status,
        exclusions=list(instance.exclusions),
    )

@app.route("/instance_action", methods=["POST"])
def handle_instance_start_stop():
    data = request.json
    action = data.get("action", "")
    id = data.get("id", "")
    if action == "start":
        if id != "rotate" and id not in INSTANCE_IDS:
            return jsonify(0)
        if id not in instances:
            instances[id] = Instance(id)
            bot_pipe.send({"action": "start", "id": id})
        return jsonify(1)
    elif action == "stop":
        instance = instances.pop(id, None)
        if id == "rotate":
            rotation_state["active"] = False
            rotation_state["current_id"] = None
            rotation_state["status"] = "idle"
            rotation_state["next_round_at"] = 0
        if instance or id == "rotate":
            bot_pipe.send({"action": "stop", "id": id})
        return jsonify(1)
    return jsonify(0)

@app.route("/current_time", methods=["GET"])
def handle_current_time():
    return {"current_time": time.time()}

@app.route("/instances/<id>/end_time", methods=["GET", "POST"])
def handle_end_time(id):
    instance = instances.get(id)
    if not instance: abort(404)
    if request.method == "POST":
        data = request.json.get("time", 0)
        instance.end_time = int(data) * 60 + time.time()
    return {"end_time": instance.end_time}

@app.route("/instances/<id>/running", methods=["GET"])
def handle_running(id):
    instance = instances.get(id)
    if not instance: abort(404)
    return {"running": instance.end_time == 0 or instance.end_time < time.time()}

@app.route("/instances/<id>/status", methods=["GET", "POST"])
def handle_status(id):
    instance = instances.get(id)
    if not instance: abort(404)
    if request.method == "POST":
        data = request.json
        instance.run_status = data.get("status", "")
    return {"status": instance.run_status}

@app.route("/instances/<id>/exclude", methods=["GET", "POST"])
def handle_exclude(id):
    if id not in instances:
        instances[id] = Instance(id)
    instance = instances.get(id)
    if not instance: abort(404)
    if request.method == "POST":
        data = request.json
        action = data.get("action", "")
        item = data.get("item", "")
        if action == "add":
            instance.exclusions.add(item)
        elif action == "remove":
            instance.exclusions.discard(item)
    return {"exclusions": sorted(list(instance.exclusions))}

def start_server(pipe, port, id=None, debug=False):
    global bot_pipe
    bot_pipe = pipe
    
    if not debug:
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    if id is not None:
        instances[id] = Instance(id)
    
    app.run(port=port, debug=debug)

if __name__ == "__main__":
    from multiprocessing import Pipe
    parent_conn, child_conn = Pipe()
    start_server(child_conn, port=1234)
