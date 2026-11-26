import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import coc_bot
import config_manager
import configs
import utils


@pytest.fixture(autouse=True)
def clean_temp_cache():
    config_manager.snapshot_base_configs(configs, force=True)
    utils.TEMP_CACHE.clear()
    yield
    config_manager.reset_base_configs(configs)
    utils.TEMP_CACHE.clear()
    utils.Task_Handler.cache_valid = False
    utils.Task_Handler.cached_exclusions = []


def test_detect_village_picks_higher_confidence_when_both_match_threshold():
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    home_asset = utils.Asset_Manager.upgrader_assets["home_gold"]
    builder_asset = utils.Asset_Manager.upgrader_assets["builder_gold"]

    def fake_locate(template, frame=None, **kwargs):
        if template is home_asset:
            return (0.9, 0.1, 0.73)  # false positive above 0.7
        if template is builder_asset:
            return (0.9, 0.1, 0.94)  # true match
        return (None, None, 0.0)

    with (
        patch.object(utils.Frame_Handler, "get_frame", return_value=fake_frame),
        patch.object(utils.Frame_Handler, "locate", side_effect=fake_locate),
    ):
        assert utils.detect_village() == "builder_base"
        assert utils.in_home_base() is False
        assert utils.in_builder_base() is True


def test_detect_village_returns_none_below_threshold():
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with (
        patch.object(utils.Frame_Handler, "get_frame", return_value=fake_frame),
        patch.object(utils.Frame_Handler, "locate", return_value=(None, None, 0.4)),
    ):
        assert utils.detect_village() is None
        assert utils.in_home_base() is False
        assert utils.in_builder_base() is False


def test_to_home_base_verifies_arrival_and_updates_cache_only_after_success():
    utils.TEMP_CACHE["location"] = "builder_base"
    # First call (initial check): False; after clicking boat: False once, then True
    home_checks = iter([False, False, True])

    with (
        patch.object(utils, "in_home_base", side_effect=lambda *a, **kw: next(home_checks)),
        patch.object(utils.Input_Handler, "zoom"),
        patch.object(utils.Input_Handler, "swipe_down"),
        patch.object(utils.Input_Handler, "swipe_left"),
        patch.object(utils.Input_Handler, "click") as mock_click,
        patch.object(utils.Frame_Handler, "batch_locate", return_value=[(0.6, 0.4)]),
        patch("time.sleep"),
    ):
        assert utils.to_home_base() is True

    mock_click.assert_called_once_with(0.6, 0.4)
    assert utils.TEMP_CACHE["location"] == "home_base"


def test_to_home_base_does_not_poison_cache_when_boat_not_found():
    utils.TEMP_CACHE["location"] = "builder_base"

    with (
        patch.object(utils, "in_home_base", return_value=False),
        patch.object(utils, "detect_village", return_value="builder_base"),
        patch.object(utils.Input_Handler, "zoom"),
        patch.object(utils.Input_Handler, "swipe_down"),
        patch.object(utils.Input_Handler, "swipe_left"),
        patch.object(utils.Input_Handler, "swipe") as mock_swipe,
        patch.object(utils.Frame_Handler, "batch_locate", return_value=[(None, None)]),
        patch("time.sleep"),
    ):
        assert utils.to_home_base() is False

    # Should have panned between retry attempts and kept actual location instead of poisoning cache
    assert mock_swipe.call_count == 5
    assert utils.TEMP_CACHE["location"] == "builder_base"


def test_coc_bot_step_does_not_run_home_tasks_if_stuck_in_builder_base():
    configs.UPGRADE_HOME_BASE = True
    configs.ATTACK_HOME_BASE = True
    configs.UPGRADE_BUILDER_BASE = False
    configs.UPGRADE_BUILDER_LAB = False
    configs.ATTACK_BUILDER_BASE = False
    configs.WEB_APP_URL = ""
    configs.LOCAL_GUI = False
    utils.Task_Handler.cache_valid = False

    bot = coc_bot.CoC_Bot()
    bot.upgrader = MagicMock()
    bot.attacker = MagicMock()

    with (
        patch.object(coc_bot, "online", return_value=True),
        patch.object(coc_bot, "running", return_value=True),
        patch.object(coc_bot, "start_coc", return_value=(True, "ok")),
        patch.object(coc_bot, "update_status"),
        patch.object(coc_bot, "to_home_base", return_value=False) as mock_to_home,
        patch.object(coc_bot, "to_builder_base", return_value=False),
        patch.object(coc_bot, "stop_coc"),
    ):
        assert bot.step() is True

    bot.upgrader.run_home_base.assert_not_called()
    bot.attacker.run_home_base.assert_not_called()
    # Still attempted to return to home base before stopping
    assert mock_to_home.call_count == 2


def test_coc_bot_step_returns_to_home_base_before_stopping_after_builder_base():
    configs.UPGRADE_HOME_BASE = True
    configs.ATTACK_HOME_BASE = False
    configs.UPGRADE_BUILDER_BASE = True
    configs.UPGRADE_BUILDER_LAB = False
    configs.ATTACK_BUILDER_BASE = False
    configs.WEB_APP_URL = ""
    configs.LOCAL_GUI = False
    utils.Task_Handler.cache_valid = False

    events = []
    bot = coc_bot.CoC_Bot()
    bot.upgrader = MagicMock()
    bot.upgrader.run_builder_base.side_effect = lambda *a, **kw: events.append("run_builder_base")
    bot.attacker = MagicMock()

    def fake_to_home(ref_cache=False):
        events.append(("to_home_base", ref_cache))
        return True

    def fake_to_builder(ref_cache=False):
        events.append(("to_builder_base", ref_cache))
        return True

    def fake_stop(**kw):
        events.append("stop_coc")

    with (
        patch.object(coc_bot, "online", return_value=True),
        patch.object(coc_bot, "running", return_value=True),
        patch.object(coc_bot, "start_coc", return_value=(True, "ok")),
        patch.object(coc_bot, "update_status"),
        patch.object(coc_bot, "to_home_base", side_effect=fake_to_home),
        patch.object(coc_bot, "to_builder_base", side_effect=fake_to_builder),
        patch.object(coc_bot, "stop_coc", side_effect=fake_stop),
    ):
        assert bot.step() is True

    assert events == [
        ("to_home_base", True),
        ("to_builder_base", True),
        "run_builder_base",
        ("to_home_base", False),
        "stop_coc",
    ]
