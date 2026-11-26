import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import upgrader


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
