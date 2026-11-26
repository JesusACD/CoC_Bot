import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure gui_server can be imported cleanly
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import configs
import config_manager
import utils
from gui_server import gui_server


@pytest.fixture(autouse=True)
def restore_configs_after_test():
    """Ensure global configs module and snapshot state are restored after each test."""
    orig_ids = list(configs.INSTANCE_IDS)
    orig_instance_configs = getattr(configs, "INSTANCE_CONFIGS", None)
    had_instance_configs = hasattr(configs, "INSTANCE_CONFIGS")
    config_manager.snapshot_base_configs(configs, force=True)

    yield

    config_manager.reset_base_configs(configs)
    configs.INSTANCE_IDS = orig_ids
    if had_instance_configs:
        configs.INSTANCE_CONFIGS = orig_instance_configs
    elif hasattr(configs, "INSTANCE_CONFIGS"):
        delattr(configs, "INSTANCE_CONFIGS")
    config_manager.snapshot_base_configs(configs, force=True)
    utils.Task_Handler.cache_valid = False
    utils.Task_Handler.cached_exclusions = []
    gui_server.instances.clear()


def test_init_instance_applies_per_instance_overrides_and_task_handler_respects_them():
    configs.INSTANCE_IDS = ["main", "alt_th9"]
    configs.INSTANCE_CONFIGS = {
        "alt_th9": {
            "OPEN_HOME_BUILDERS": 2,
            "UPGRADE_PETS": False,
            "PRIORITY_PET_UPGRADES": False,
            "ATTACK_HOME_BASE": False,
            "HOME_BASE_UPGRADE_PRIORITY": [["Laboratory", "Clan Castle"]],
            "AUTO_START_EMULATOR": False,
            "WEB_APP_URL": "",
            "LOCAL_GUI": False,
        }
    }
    config_manager.snapshot_base_configs(configs, force=True)

    with (
        patch.object(utils, "request_perms"),
        patch.object(utils._Emulator_Manager, "adb_address", new="127.0.0.1:5555"),
    ):
        utils.init_instance("alt_th9")

    assert utils.INSTANCE_ID == "alt_th9"
    assert configs.OPEN_HOME_BUILDERS == 2
    assert configs.UPGRADE_PETS is False
    assert configs.HOME_BASE_UPGRADE_PRIORITY == [["Laboratory", "Clan Castle"]]

    # Task_Handler fallback (when no web app / GUI) should reflect per-instance overrides
    utils.Task_Handler.cache_valid = False
    assert utils.Task_Handler.excluded("pet_house") is True
    assert utils.Task_Handler.excluded("pet_house_priority") is True
    assert utils.Task_Handler.excluded("home_attacks") is True
    assert utils.Task_Handler.excluded("home_base") is False


def test_init_instance_switches_emulator_type_per_instance():
    configs.INSTANCE_IDS = ["main", "alt_mumu"]
    configs.EMULATOR_TYPE = "bluestacks"
    configs.AUTO_START_EMULATOR = False
    configs.WEB_APP_URL = ""
    configs.INSTANCE_CONFIGS = {
        "alt_mumu": {"EMULATOR_TYPE": "mumu"},
    }
    config_manager.snapshot_base_configs(configs, force=True)

    with (
        patch.object(utils, "request_perms"),
        patch.object(utils._Emulator_Manager, "adb_address", new="127.0.0.1:16384"),
    ):
        utils.init_instance("alt_mumu")
        assert utils.Emulator_Manager is utils.MuMu_Manager

        utils.init_instance("main")
        assert utils.Emulator_Manager is utils.BlueStacks_Manager


def test_gui_server_instance_uses_per_instance_overrides_and_hides_rotate_from_ids():
    configs.INSTANCE_IDS = ["main", "alt_th9"]
    configs.UPGRADE_PETS = True
    configs.ATTACK_HOME_BASE = True
    configs.PRIORITY_HOME_BASE_UPGRADES = True
    configs.INSTANCE_CONFIGS = {
        "alt_th9": {
            "UPGRADE_PETS": False,
            "ATTACK_HOME_BASE": False,
            "PRIORITY_HOME_BASE_UPGRADES": False,
        }
    }
    config_manager.snapshot_base_configs(configs, force=True)

    inst_main = gui_server.Instance("main")
    inst_alt = gui_server.Instance("alt_th9")

    assert "pet_house" not in inst_main.exclusions
    assert "home_attacks" not in inst_main.exclusions
    assert "home_base_priority" not in inst_main.exclusions

    assert "pet_house" in inst_alt.exclusions
    assert "home_attacks" in inst_alt.exclusions
    assert "home_base_priority" in inst_alt.exclusions

    # Verify Flask endpoints return per-instance exclusions and hide "rotate" from home page IDs
    gui_server.bot_pipe = MagicMock()
    client = gui_server.app.test_client()

    res_alt = client.get("/instances/alt_th9/exclude")
    assert res_alt.status_code == 200
    assert "pet_house" in res_alt.get_json()["exclusions"]
    assert "home_attacks" in res_alt.get_json()["exclusions"]

    res_main = client.get("/instances/main/exclude")
    assert res_main.status_code == 200
    assert "pet_house" not in res_main.get_json()["exclusions"]

    # Starting rotation must not list "rotate" as an instance card on home page
    res_start = client.post("/instance_action", json={"action": "start", "id": "rotate"})
    assert res_start.status_code == 200
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"/instances/rotate" not in res_home.data
