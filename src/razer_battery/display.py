"""Text, colors and pixel helpers for showing a reading; pure functions shared by the CLI and tray."""

from collections.abc import Sequence

from .device import Reading

LOW_BATTERY = 20
TOOLTIP_LIMIT = 127  # NOTIFYICONDATAW.szTip holds 128 characters including the terminator.

RED = (0xE8, 0x11, 0x23)
GREEN = (0x16, 0xC6, 0x0C)
WHITE = (0xFF, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00)


def describe(reading: Reading) -> str:
    state = "充电中" if reading.charging else "未充电"
    return f"Razer {reading.model}: {reading.percent}%（{state}）"


def tooltip(reading: Reading | None, error: str | None = None) -> str:
    text = describe(reading) if reading is not None else f"Razer 鼠标电量：{error or '未知'}"
    return text[:TOOLTIP_LIMIT]


def icon_text(reading: Reading | None) -> str:
    return "?" if reading is None else str(reading.percent)


def icon_color(reading: Reading | None, light_theme: bool) -> tuple[int, int, int]:
    if reading is not None and reading.charging:
        return GREEN
    if reading is not None and reading.percent <= LOW_BATTERY:
        return RED
    return BLACK if light_theme else WHITE


def font_size(text: str, size: int) -> tuple[int, int]:
    """Return (height, average width) for CreateFontW so the text fills a size x size icon.

    The height is negative (character height without leading); a width of 0 keeps the
    font's own proportions, otherwise characters are narrowed so three digits still fit.
    """
    height = -(size * 5 // 4)
    if len(text) <= 1:
        return height, 0
    return height, max(1, size * 9 // (10 * len(text)))


def center_glyphs(pixels: Sequence[int], canvas: int, size: int) -> list[int]:
    """Cut the lit pixels of a canvas x canvas image and center them in a size x size image.

    Font metrics (leading, descent) differ between fonts and DPI, so the drawn glyphs are
    measured instead of trusting DrawText's vertical centering.
    """
    lit = [(i % canvas, i // canvas) for i, pixel in enumerate(pixels) if pixel & 0xFFFFFF]
    result = [0] * (size * size)
    if not lit:
        return result
    left = min(x for x, _ in lit)
    top = min(y for _, y in lit)
    width = max(x for x, _ in lit) - left + 1
    height = max(y for _, y in lit) - top + 1
    # Glyphs wider than the icon are cropped evenly on both sides.
    shift_x = (size - width) // 2 - left
    shift_y = (size - height) // 2 - top
    for x, y in lit:
        tx, ty = x + shift_x, y + shift_y
        if 0 <= tx < size and 0 <= ty < size:
            result[ty * size + tx] = pixels[y * canvas + x]
    return result


def colorize(gray: Sequence[int], rgb: tuple[int, int, int]) -> list[int]:
    """Turn white-on-black 0x00RRGGBB pixels into 0xAARRGGBB pixels of one color.

    Text is drawn white with grayscale antialiasing, so the brightest channel of each
    pixel is its coverage and becomes the alpha of the icon.
    """
    red, green, blue = rgb
    color = (red << 16) | (green << 8) | blue
    pixels = []
    for pixel in gray:
        alpha = max((pixel >> 16) & 0xFF, (pixel >> 8) & 0xFF, pixel & 0xFF)
        pixels.append((alpha << 24) | color if alpha else 0)
    return pixels
