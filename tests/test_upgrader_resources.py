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
    orig_place_new = getattr(configs, "PLACE_NEW_BUILDINGS", True)
    configs.START_FROM_MENU_TOP = True
    configs.PLACE_NEW_BUILDINGS = False

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
        configs.PLACE_NEW_BUILDINGS = orig_place_new


def test_place_new_building_clicks_confirm_directly_and_retries_drag_on_red_spot():
    upg = upgrader.Upgrader()
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # Case 1: Green checkmark visible immediately -> clicks it without dragging
    with (
        patch.object(upgrader.Frame_Handler, "get_frame", return_value=fake_frame),
        patch.object(upg, "_locate_placement_button", return_value=(0.57, 0.50)),
        patch.object(upgrader.Input_Handler, "click") as mock_click,
        patch.object(upgrader.Input_Handler, "swipe") as mock_swipe,
        patch("time.sleep"),
    ):
        assert upg._place_new_building(timeout=0.3) is True

    mock_click.assert_called_once_with(0.57, 0.50)
    mock_swipe.assert_not_called()

    # Case 2: Initial drop blocked (no green check initially, red cancel visible -> drags -> green check appears)
    locate_seq = iter([
        (None, None),  # poll iter 1
        (None, None),  # poll iter 2
        (0.54, 0.50),  # place_cancel found after timeout
        (0.35, 0.42),  # place_confirm appears after first drag!
    ])
    with (
        patch.object(upgrader.Frame_Handler, "get_frame", return_value=fake_frame),
        patch.object(upg, "_locate_placement_button", side_effect=lambda *a, **kw: next(locate_seq)),
        patch.object(upgrader.Input_Handler, "click") as mock_click2,
        patch.object(upgrader.Input_Handler, "swipe") as mock_swipe2,
        patch("time.sleep"),
    ):
        assert upg._place_new_building(timeout=0.5) is True

    mock_swipe2.assert_called_once()
    mock_click2.assert_called_once_with(0.35, 0.42)


def test_row_uses_gems_and_is_new_row_on_real_capture_layout():
    upg = upgrader.Upgrader()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    h, w = frame.shape[:2]

    # Row 1 at y=0.25: New gold building (neon green text + gold coin)
    frame[int(h * 0.24):int(h * 0.26), int(w * 0.79):int(w * 0.90)] = [180, 247, 86]
    # Row 2 at y=0.35: New gem building like Builder's Hut (neon green text + bright emerald gem on right edge)
    frame[int(h * 0.34):int(h * 0.36), int(w * 0.79):int(w * 0.90)] = [180, 247, 86]
    frame[int(h * 0.34):int(h * 0.36), w - 35:w - 15] = [100, 230, 80]

    assert upg._is_new_row(frame, 0.25, 0.775, 1.0) is True
    assert upg._row_uses_gems(frame, 0.25, 0.775, 1.0) is False
    assert upg._is_new_row(frame, 0.35, 0.775, 1.0) is True
    assert upg._row_uses_gems(frame, 0.35, 0.775, 1.0) is True


def test_home_specified_upgrade_places_new_building_and_never_buys_builders_hut():
    upg = upgrader.Upgrader()
    orig_start = configs.START_FROM_MENU_TOP
    orig_place_new = getattr(configs, "PLACE_NEW_BUILDINGS", True)
    configs.START_FROM_MENU_TOP = True
    configs.PLACE_NEW_BUILDINGS = True

    try:
        # Must refuse Builder's Hut immediately before even opening menus
        with (
            patch.object(upg, "_open_home_builders_menu") as mock_open,
            patch.object(upgrader.Input_Handler, "click_exit"),
            patch.object(upgrader.Task_Handler, "excluded", return_value=False),
            patch.object(upgrader, "get_vocab", return_value={"heroes": ["Barbarian King"]}),
        ):
            assert upg.home_specified_upgrade(["Builder's Hut"]) is None
        mock_open.assert_not_called()

        # When priority includes Hero Hall marked 'New', clicks row and calls _place_new_building
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[int(1080 * 0.12):int(1080 * 0.14), int(1920 * 0.79):int(1920 * 0.90)] = [180, 247, 86]

        def fake_batch_locate(templates, frame, **kwargs):
            return [[(0.78, 0.13)] for _ in templates]

        with (
            patch.object(upg, "_open_home_builders_menu", return_value=(0.85, 0.08)),
            patch.object(upgrader.Frame_Handler, "get_frame", return_value=frame),
            patch.object(upgrader.Frame_Handler, "locate", return_value=(0.85, 0.08)),
            patch.object(upgrader.Frame_Handler, "batch_locate", side_effect=fake_batch_locate),
            patch.object(upgrader, "get_vocab", return_value={"heroes": ["Barbarian King"]}),
            patch.object(upgrader.Task_Handler, "excluded", return_value=False),
            patch.object(upg, "_place_new_building", return_value=True) as mock_place,
            patch.object(upg, "_click_home_confirm") as mock_confirm,
            patch.object(upgrader.Input_Handler, "click") as mock_click,
            patch.object(upgrader.Input_Handler, "click_exit"),
            patch("time.sleep"),
        ):
            result = upg.home_specified_upgrade(["Hero Hall"])

        assert result == "hero hall"
        mock_place.assert_called_once()
        mock_confirm.assert_not_called()
        menu_center = (0.775 + 1.0) / 2
        assert mock_click.call_args_list[0].args == (menu_center, 0.13)
    finally:
        configs.START_FROM_MENU_TOP = orig_start
        configs.PLACE_NEW_BUILDINGS = orig_place_new


def test_home_random_upgrade_places_affordable_non_gem_new_building_before_town_hall():
    upg = upgrader.Upgrader()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Paint bright green text at y_px=150 in menu (y_norm = 150/1080 + 0.06 ≈ 0.199)
    y_abs = int(1080 * 0.06 + 150)
    frame[y_abs - 10:y_abs + 10, int(1920 * 0.79):int(1920 * 0.90)] = [180, 247, 86]

    orig_start = configs.START_FROM_MENU_TOP
    orig_place_new = getattr(configs, "PLACE_NEW_BUILDINGS", True)
    configs.START_FROM_MENU_TOP = True
    configs.PLACE_NEW_BUILDINGS = True

    def fake_potential_locs(menu, exclude_new=False):
        if exclude_new:
            return np.array([300.0])  # only Town Hall
        return np.array([150.0, 300.0])  # Elixir Collector (New) + Town Hall

    def fake_batch_locate(templates, frame, **kwargs):
        # Town Hall at y_menu=300, no heroes/crafting/builders hut matched
        res = [[(40, 300)]]
        res.extend([[(-1, -1)] for _ in range(len(templates) - 1)])
        return res

    try:
        with (
            patch.object(upg, "_open_home_builders_menu", return_value=(0.85, 0.09)),
            patch.object(upgrader.Frame_Handler, "get_frame", return_value=frame),
            patch.object(upgrader.Input_Handler, "click") as mock_click,
            patch.object(upgrader.Input_Handler, "click_exit"),
            patch.object(upgrader, "get_vocab", return_value={"heroes": ["Barbarian King"]}),
            patch.object(upgrader.Task_Handler, "excluded", return_value=True),
            patch.object(upg, "_get_potential_upgrade_locs", side_effect=fake_potential_locs),
            patch.object(upgrader.Frame_Handler, "batch_locate", side_effect=fake_batch_locate),
            patch.object(upg, "_identify_home_row_name", return_value="elixir collector"),
            patch.object(upg, "_place_new_building", return_value=True) as mock_place,
            patch.object(upg, "_click_home_confirm") as mock_confirm,
            patch("time.sleep"),
        ):
            result = upg.home_random_upgrade()

        assert result == "elixir collector"
        mock_place.assert_called_once()
        mock_confirm.assert_not_called()
        menu_center = (0.775 + 1.0) / 2
        assert abs(mock_click.call_args_list[0].args[0] - menu_center) < 1e-6
        assert abs(mock_click.call_args_list[0].args[1] - (150.0 / 1080 + 0.06)) < 1e-6
    finally:
        configs.START_FROM_MENU_TOP = orig_start
        configs.PLACE_NEW_BUILDINGS = orig_place_new


def test_adb_connect_once_cleans_up_stale_minitouch_before_starting():
    mock_old_mnt = MagicMock()
    mock_adbutils_dev = MagicMock()
    mock_new_mnt = MagicMock()
    mock_u2_dev = MagicMock()

    orig_mnt = utils.ADB_Manager._minitouch_device
    orig_adb = utils.ADB_Manager._adbutils_device
    orig_u2 = utils.ADB_Manager._uiautomator_device
    utils.ADB_Manager._minitouch_device = mock_old_mnt

    try:
        with (
            patch("shutil.which", return_value="adb"),
            patch("subprocess.run"),
            patch("adbutils.adb.connect", return_value="connected to 127.0.0.1:5575"),
            patch("adbutils.device", return_value=mock_adbutils_dev),
            patch("pyminitouch.MNTDevice", return_value=mock_new_mnt) as mock_mnt_cls,
            patch("uiautomator2.connect", return_value=mock_u2_dev),
            patch.object(utils.Exit_Handler, "register"),
            patch("time.sleep"),
        ):
            utils.ADB_Manager.connect_once("127.0.0.1:5575")

        mock_old_mnt.stop.assert_called_once()
        mock_adbutils_dev.shell.assert_called_once_with("pkill -f minitouch")
        mock_mnt_cls.assert_called_once_with("127.0.0.1:5575")
        assert utils.ADB_Manager._minitouch_device is mock_new_mnt
    finally:
        utils.ADB_Manager._minitouch_device = orig_mnt
        utils.ADB_Manager._adbutils_device = orig_adb
        utils.ADB_Manager._uiautomator_device = orig_u2


def test_locate_placement_button_matches_zoomed_in_scale():
    import cv2

    upg = upgrader.Upgrader()
    tmpl = upg.assets["place_confirm"]
    scaled = cv2.resize(tmpl, (0, 0), fx=2.9, fy=2.9, interpolation=cv2.INTER_LINEAR)
    sh, sw = scaled.shape[:2]

    frame = np.full((1080, 1920, 3), [120, 170, 60], dtype=np.uint8)
    y0, x0 = 350, 600
    frame[y0:y0 + sh, x0:x0 + sw] = scaled

    x, y = upg._locate_placement_button("place_confirm", frame)
    assert x is not None and y is not None
    expected_x = (x0 + sw / 2) / 1920
    expected_y = (y0 + sh / 2) / 1080
    assert abs(x - expected_x) < 0.02
    assert abs(y - expected_y) < 0.02

    empty_frame = np.full((1080, 1920, 3), [120, 170, 60], dtype=np.uint8)
    assert upg._locate_placement_button("place_confirm", empty_frame) == (None, None)
