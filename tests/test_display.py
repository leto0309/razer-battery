import pytest

from razer_battery import display
from razer_battery.device import Reading


def reading(percent=67, charging=False):
    return Reading("DeathAdder V3 Pro (wireless)", percent, charging)


def test_describe_and_tooltip():
    assert display.describe(reading()) == "Razer DeathAdder V3 Pro (wireless): 67%（未充电）"
    assert display.tooltip(reading(charging=True)).endswith("（充电中）")
    assert display.tooltip(None, "未找到") == "Razer 鼠标电量：未找到"
    assert display.tooltip(None) == "Razer 鼠标电量：未知"


def test_tooltip_fits_notify_icon_limit():
    assert len(display.tooltip(None, "x" * 500)) == 127


def test_icon_text():
    assert display.icon_text(reading(100)) == "100"
    assert display.icon_text(None) == "?"


@pytest.mark.parametrize("value, light, expected", [
    (reading(67), False, display.WHITE),
    (reading(67), True, display.BLACK),
    (reading(20), False, display.RED),
    (reading(21), True, display.BLACK),
    (reading(5, charging=True), False, display.GREEN),
    (None, False, display.WHITE),
    (None, True, display.BLACK),
])
def test_icon_color(value, light, expected):
    assert display.icon_color(value, light) == expected


def test_font_narrows_for_more_digits():
    one, two, three = (display.font_size(t, 16) for t in ("5", "67", "100"))
    assert one == (-20, 0)
    assert one[0] == two[0] == three[0]
    assert two[1] > three[1] > 0


def test_center_glyphs_moves_lit_pixels_to_the_middle():
    canvas, size = 8, 4
    pixels = [0] * (canvas * canvas)
    pixels[0] = pixels[1] = 0xFFFFFF  # a 2x1 glyph in the top-left corner
    result = display.center_glyphs(pixels, canvas, size)
    lit = [i for i, p in enumerate(result) if p]
    assert lit == [1 * size + 1, 1 * size + 2]


def test_center_glyphs_crops_wide_glyphs_evenly():
    canvas, size = 8, 4
    pixels = [0] * (canvas * canvas)
    for x in range(6):
        pixels[x] = 0x010101 * (x + 1)
    row = display.center_glyphs(pixels, canvas, size)[size:2 * size]
    assert row == [0x020202, 0x030303, 0x040404, 0x050505]


def test_center_glyphs_of_empty_canvas_is_empty():
    assert display.center_glyphs([0] * 16, 4, 2) == [0, 0, 0, 0]


def test_colorize_uses_brightest_channel_as_alpha():
    assert display.colorize([0x000000, 0x808080, 0xFFFFFF, 0x004000], display.RED) == [
        0, 0x80E81123, 0xFFE81123, 0x40E81123,
    ]
