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


def test_coc_bot_step_skips_builder_base_when_overridden_for_instance():
    import coc_bot

    configs.INSTANCE_IDS = ["main", "cuenta1"]
    configs.UPGRADE_BUILDER_BASE = True
    configs.UPGRADE_BUILDER_LAB = True
    configs.ATTACK_BUILDER_BASE = True
    configs.UPGRADE_HOME_BASE = True
    configs.ATTACK_HOME_BASE = True
    configs.AUTO_START_EMULATOR = False
    configs.WEB_APP_URL = ""
    configs.LOCAL_GUI = False
    configs.INSTANCE_CONFIGS = {
        "cuenta1": {
            "UPGRADE_BUILDER_BASE": False,
            "UPGRADE_BUILDER_LAB": False,
            "ATTACK_BUILDER_BASE": False,
        }
    }
    config_manager.snapshot_base_configs(configs, force=True)

    with (
        patch.object(utils, "request_perms"),
        patch.object(utils._Emulator_Manager, "adb_address", new="127.0.0.1:5555"),
    ):
        utils.init_instance("cuenta1")

    utils.Task_Handler.cache_valid = False
    bot = coc_bot.CoC_Bot()
    bot.upgrader = MagicMock()
    bot.attacker = MagicMock()

    with (
        patch.object(coc_bot, "online", return_value=True),
        patch.object(coc_bot, "running", return_value=True),
        patch.object(coc_bot, "start_coc", return_value=(True, "ok")),
        patch.object(coc_bot, "update_status"),
        patch.object(coc_bot, "to_home_base"),
        patch.object(coc_bot, "to_builder_base") as mock_to_builder,
        patch.object(coc_bot, "stop_coc"),
    ):
        assert bot.step() is True

    bot.upgrader.run_home_base.assert_called_once()
    bot.attacker.run_home_base.assert_called_once()
    mock_to_builder.assert_not_called()
    bot.upgrader.run_builder_base.assert_not_called()
    bot.attacker.run_builder_base.assert_not_called()


def test_attacker_start_normal_attack_handles_none_tuples_without_type_error():
    import attacker

    atk = attacker.Attacker()

    def fake_locate(template, frame, thresh=0.7, return_all=False, **kwargs):
        if return_all:
            return [(None, None)]
        return (0.47, 0.5)

    def immediate_click_with_timeout(locator_func, timeout=5):
        x, y = locator_func()
        return x is not None and y is not None

    with (
        patch.object(attacker.Input_Handler, "click"),
        patch.object(attacker, "render_text", return_value=MagicMock()),
        patch.object(attacker.Frame_Handler, "get_frame", return_value=MagicMock()),
        patch.object(attacker.Frame_Handler, "locate", side_effect=fake_locate),
        patch.object(attacker, "click_with_timeout", side_effect=immediate_click_with_timeout),
    ):
        assert atk.start_normal_attack(timeout=1) is False


def test_launch_proc_enables_logging_before_init_instance():
    import types
    import launch
    import log
    import coc_bot

    call_order = []

    def fake_enable_logging(inst_id):
        call_order.append(("enable_logging", inst_id))

    def fake_init_instance(inst_id):
        call_order.append(("init_instance", inst_id))

    fake_args = types.SimpleNamespace(debug=False, id="main", gui=False, gui_port=None, once=True)

    with (
        patch.object(utils, "parse_args", return_value=fake_args),
        patch.object(log, "enable_logging", side_effect=fake_enable_logging),
        patch.object(utils, "init_instance", side_effect=fake_init_instance),
        patch.object(coc_bot, "CoC_Bot", return_value=MagicMock()),
        patch.object(utils.Emulator_Manager, "stop"),
    ):
        launch.launch_proc(fake_args)

    assert call_order == [("enable_logging", "main"), ("init_instance", "main")]


def test_upgrader_run_home_base_does_not_rescan_exhausted_priority_levels():
    import upgrader

    configs.MAX_UPGRADES_PER_CHECK = 3
    configs.OPEN_HOME_BUILDERS = 0
    configs.HOME_BASE_UPGRADE_PRIORITY = [
        ["Laboratory"],
        ["Army Camp"],
        ["Wall"],
    ]

    upg = upgrader.Upgrader()
    checked_levels = []

    def fake_specified(level):
        checked_levels.append(list(level))
        if level == ["Wall"]:
            return "Wall"
        return None

    with (
        patch.object(upgrader.Input_Handler, "zoom"),
        patch.object(upgrader.Input_Handler, "swipe_down"),
        patch.object(upgrader.Input_Handler, "click"),
        patch.object(upgrader, "in_home_base", return_value=True),
        patch.object(upgrader.Task_Handler, "excluded", side_effect=lambda name, **kw: name != "home_base_priority" and True),
        patch.object(upg, "get_home_builders", return_value=1),
        patch.object(upg, "home_specified_upgrade", side_effect=fake_specified),
        patch.object(upg, "home_random_upgrade", return_value=None),
        patch.object(upgrader, "send_notification") as mock_notify,
        patch("time.sleep"),
    ):
        upg.run_home_base(exclude_base=False, exclude_lab=True, exclude_pet=True)

    # Priority 1 & 2 checked ONCE on attempt 1; attempts 2 and 3 jump straight to Priority 3 (["Wall"])
    assert checked_levels == [
        ["Laboratory"],
        ["Army Camp"],
        ["Wall"],
        ["Wall"],
        ["Wall"],
    ]
    assert mock_notify.call_count == 3


def test_cmd_rotate_terminates_stalled_instance_and_stops_at_max_rounds():
    import types
    import launch

    configs.INSTANCE_IDS = ["main", "cuenta1"]
    configs.MAX_ROTATION_TURN_MINUTES = 0.01  # 0.6s timeout
    configs.CHECK_INTERVAL = 1

    started_ids = []
    terminated_ids = []

    class FakeProcess:
        def __init__(self, target=None, args=()):
            self.inst_id = args[0].id
            self._alive = False

        def start(self):
            started_ids.append(self.inst_id)
            self._alive = True

        def join(self, timeout=None):
            # Simulate "main" hanging past timeout, while "cuenta1" finishes cleanly
            if self.inst_id != "main":
                self._alive = False

        def is_alive(self):
            return self._alive

        def terminate(self):
            terminated_ids.append(self.inst_id)
            self._alive = False

    fake_args = types.SimpleNamespace(
        debug=False, id=None, gui=False, gui_port=None, rotate=True, once=False, rounds=1
    )

    with (
        patch("multiprocessing.Process", side_effect=FakeProcess),
        patch.object(utils, "disable_sleep"),
        patch("time.sleep"),
    ):
        launch.cmd_rotate(fake_args)

    assert started_ids == ["main", "cuenta1"]
    assert terminated_ids == ["main"]
