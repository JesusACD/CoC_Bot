import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import configs
import upgrader
import utils


def test_get_sufficient_resources_detects_red_price_with_tolerance():
    upg = upgrader.Upgrader()

    white_section = np.full((30, 100, 3), [255, 255, 255], dtype=np.uint8)
    assert upg._get_sufficient_resources(white_section) is True

    # Exact red cost text color
    red_section = np.full((30, 100, 3), [50, 50, 50], dtype=np.uint8)
    red_section[10:20, 40:60] = [255, 123, 114]
    assert upg._get_sufficient_resources(red_section) is False

    # Slightly shifted/compressed red cost text color (within tol=25)
    compressed_red_section = np.full((30, 100, 3), [50, 50, 50], dtype=np.uint8)
    compressed_red_section[10:20, 40:60] = [242, 110, 102]
    assert upg._get_sufficient_resources(compressed_red_section) is False


def test_click_home_confirm_skips_when_confirm_button_has_red_cost():
    upg = upgrader.Upgrader()
    frame = np.full((1080, 1920, 3), [40, 40, 40], dtype=np.uint8)
    # Place red insufficient-resource text inside confirm button centered at (0.5, 0.8)
    frame[850:880, 940:980] = [255, 123, 114]

    with (
        patch.object(upgrader.Frame_Handler, "get_frame", return_value=frame),
        patch.object(upgrader.Frame_Handler, "locate", return_value=(0.5, 0.8)),
        patch.object(upgrader.Input_Handler, "click") as mock_click,
    ):
        assert upg._click_home_confirm(timeout=1) is False

    mock_click.assert_not_called()


def test_click_home_confirm_clicks_when_resources_are_sufficient():
    upg = upgrader.Upgrader()
    frame = np.full((1080, 1920, 3), [40, 40, 40], dtype=np.uint8)
    # White affordable price text inside confirm button
    frame[850:880, 940:980] = [255, 255, 255]

    with (
        patch.object(upgrader.Frame_Handler, "get_frame", return_value=frame),
        patch.object(upgrader.Frame_Handler, "locate", return_value=(0.5, 0.8)),
        patch.object(upgrader.Input_Handler, "click") as mock_click,
    ):
        assert upg._click_home_confirm(timeout=1) is True

    mock_click.assert_called_once_with(0.5, 0.8)


def test_open_home_builders_menu_tries_primary_then_fallback_and_handles_one_tab():
    upg = upgrader.Upgrader()

    # Case 1: Tries primary (0.77, -0.05) first, falls back to (0.80, -0.05) when primary misses
    locate_results = iter([
        (None, None),  # right after _click_build_button (not 1-tab)
        (None, None),  # after clicking primary 0.77
        (0.85, 0.12),  # found after clicking fallback 0.80
    ])
    with (
        patch.object(upg, "_click_build_button"),
        patch.object(upgrader.Frame_Handler, "locate", side_effect=lambda *a, **kw: next(locate_results)),
        patch.object(upgrader.Input_Handler, "click") as mock_click,
        patch("time.sleep"),
    ):
        assert upg._open_home_builders_menu() == (0.85, 0.12)

    assert [c.args for c in mock_click.call_args_list] == [(0.77, -0.05), (0.80, -0.05)]

    # Case 2: 1-tab menu (TH1-TH2) -> "Suggested upgrades" already visible immediately
    with (
        patch.object(upg, "_click_build_button"),
        patch.object(upgrader.Frame_Handler, "locate", return_value=(0.85, 0.12)),
        patch.object(upgrader.Input_Handler, "click") as mock_click_1tab,
        patch("time.sleep"),
    ):
        assert upg._open_home_builders_menu() == (0.85, 0.12)

    mock_click_1tab.assert_not_called()


def test_open_home_lab_menu_tries_primary_then_two_tab_fallback():
    upg = upgrader.Upgrader()

    # Tries primary (0.84, -0.05) first, falls back to 2-tab coordinate (0.94, -0.05)
    locate_results = iter([
        (None, None),  # after clicking primary 0.84
        (0.85, 0.12),  # found after clicking fallback 0.94
    ])
    with (
        patch.object(upg, "_click_build_button"),
        patch.object(upgrader.Frame_Handler, "locate", side_effect=lambda *a, **kw: next(locate_results)),
        patch.object(upgrader.Input_Handler, "click") as mock_click,
        patch("time.sleep"),
    ):
        assert upg._open_home_lab_menu() == (0.85, 0.12)

    assert [c.args for c in mock_click.call_args_list] == [(0.84, -0.05), (0.94, -0.05)]


def test_dismiss_reward_popups_clicks_continue_button():
    fake_hc_frame = np.zeros((1080, 1920), dtype=np.uint8)
    locate_calls = iter([
        [(0.49, 0.85)],  # cont_templates iter 1
        [(None, None)],  # cont_templates iter 2
        [(None, None)],  # skip_templates iter 2
    ])

    with (
        patch.object(utils.Frame_Handler, "get_frame", return_value=fake_hc_frame),
        patch.object(utils.Frame_Handler, "batch_locate", side_effect=lambda *a, **kw: next(locate_calls)),
        patch.object(utils.Input_Handler, "click") as mock_click,
        patch.object(utils.Input_Handler, "click_exit") as mock_exit,
        patch("time.sleep"),
    ):
        assert utils.dismiss_reward_popups() is True

    mock_click.assert_called_once_with(0.49, 0.85)
    mock_exit.assert_called_once()


def test_get_potential_upgrade_locs_detects_slightly_off_white_rows():
    upg = upgrader.Upgrader()
    menu = np.zeros((300, 400, 3), dtype=np.uint8)
    # Two horizontal white-ish bands ([252, 252, 252]) 25px apart (Building Name + Cost)
    menu[50:60, 40:200] = [252, 252, 252]
    menu[75:85, 250:350] = [252, 252, 252]

    locs = upg._get_potential_upgrade_locs(menu, exclude_new=True)
    assert len(locs) >= 1


def test_home_random_upgrade_skips_swipe_when_all_builders_free_and_normalizes_town_hall_y():
    upg = upgrader.Upgrader()
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    orig_start = configs.START_FROM_MENU_TOP
    configs.START_FROM_MENU_TOP = True

    try:
        # town_hall_loc is in menu pixel coords: y=108 -> normalized y = 108/1080 + 0.06 = 0.16
        # Set potential_y_locs = np.array([108.0]) so normalized potential_y_locs = [0.16]
        def fake_batch_locate(templates, frame, **kwargs):
            # 1 town hall + N heroes + 1 seasonal defense
            res = [[(40, 108)]]
            res.extend([[(-1, -1)] for _ in range(len(templates) - 1)])
            return res

        with (
            patch.object(upg, "_open_home_builders_menu", return_value=(0.85, 0.09)),
            patch.object(upgrader.Frame_Handler, "get_frame", return_value=fake_frame),
            patch.object(upgrader.Input_Handler, "swipe_up") as mock_swipe_up,
            patch.object(upgrader.Input_Handler, "click") as mock_click,
            patch.object(upgrader, "get_vocab", return_value={"heroes": ["Barbarian King"]}),
            patch.object(upgrader.Task_Handler, "excluded", return_value=True),
            patch.object(upg, "_get_potential_upgrade_locs", return_value=np.array([108.0])),
            patch.object(upgrader.Frame_Handler, "batch_locate", side_effect=fake_batch_locate),
            patch.object(upg, "_click_upgrade", return_value=False),
            patch.object(upg, "_get_upgrade_name", return_value="town hall"),
            patch.object(upg, "_click_home_confirm", return_value=True),
            patch("time.sleep"),
        ):
            result = upg.home_random_upgrade()

        assert result == "town hall"
        mock_swipe_up.assert_not_called()
        menu_center = (0.775 + 1.0) / 2
        assert mock_click.call_args_list[0].args == (menu_center, 0.16)
    finally:
        configs.START_FROM_MENU_TOP = orig_start


def test_input_handler_publish_reconnects_on_connection_reset():
    fake_conn = MagicMock()
    fake_device = MagicMock(connection=fake_conn)
    builder = MagicMock()
    builder.publish.side_effect = [ConnectionResetError("lost"), None]

    with (
        patch.object(utils.ADB_Manager, "_minitouch_device", fake_device),
        patch.object(utils.ADB_Manager, "connect", return_value=True) as mock_connect,
    ):
        utils.Input_Handler._publish(builder)

    mock_connect.assert_called_once()
    assert builder.publish.call_count == 2


def test_home_random_upgrade_logs_warning_when_blocked_by_unplaced_new_buildings():
    upg = upgrader.Upgrader()
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    orig_start = configs.START_FROM_MENU_TOP
    configs.START_FROM_MENU_TOP = True

    def fake_potential_locs(menu, exclude_new=False):
        if exclude_new:
            return np.array([108.0])  # only Town Hall
        return np.array([40.0, 74.0, 108.0])  # unplaced New buildings + Town Hall

    def fake_batch_locate(templates, frame, **kwargs):
        res = [[(40, 108)]]
        res.extend([[(-1, -1)] for _ in range(len(templates) - 1)])
        return res

    try:
        with (
            patch.object(upg, "_open_home_builders_menu", return_value=(0.85, 0.09)),
            patch.object(upgrader.Frame_Handler, "get_frame", return_value=fake_frame),
            patch.object(upgrader.Input_Handler, "click"),
            patch.object(upgrader, "get_vocab", return_value={"heroes": ["Barbarian King"]}),
            patch.object(upgrader.Task_Handler, "excluded", return_value=True),
            patch.object(upg, "_get_potential_upgrade_locs", side_effect=fake_potential_locs),
            patch.object(upgrader.Frame_Handler, "batch_locate", side_effect=fake_batch_locate),
            patch.object(upg, "_click_upgrade", return_value=False),
            patch.object(upg, "_get_upgrade_name", return_value="town hall"),
            patch.object(upg, "_click_home_confirm", return_value=False),
            patch.object(upgrader.logger, "warning") as mock_warn,
            patch("time.sleep"),
        ):
            assert upg.home_random_upgrade() is None

        assert any("Only unplaced 'New' shop buildings remain" in str(c.args[0]) for c in mock_warn.call_args_list)
    finally:
        configs.START_FROM_MENU_TOP = orig_start
