from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


OUTPUT = Path(__file__).with_name("clipoteca.ico")
SOURCE_SIZE = 48
RENDER_SIZE = 512
BACKGROUND = (16, 11, 13, 255)
ACCENT = (197, 59, 82, 255)


def build_icon() -> Image.Image:
    scale = RENDER_SIZE / SOURCE_SIZE
    image = Image.new("RGBA", (RENDER_SIZE, RENDER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, RENDER_SIZE - 1, RENDER_SIZE - 1),
        radius=round(14 * scale),
        fill=BACKGROUND,
    )

    line_width = round(3.4 * scale)
    # The open C-frame and index tab follow Clipoteca's existing vector mark.
    draw.arc(
        (round(9 * scale), round(11.5 * scale), round(36 * scale), round(38.5 * scale)),
        start=90,
        end=270,
        fill=ACCENT,
        width=line_width,
    )
    draw.line(
        (round(22.5 * scale), round(11.5 * scale), round(33 * scale), round(11.5 * scale)),
        fill=ACCENT,
        width=line_width,
    )
    draw.line(
        (round(22.5 * scale), round(38.5 * scale), round(33 * scale), round(38.5 * scale)),
        fill=ACCENT,
        width=line_width,
    )
    draw.line(
        (
            (round(26 * scale), round(18.5 * scale)),
            (round(36 * scale), round(18.5 * scale)),
            (round(36 * scale), round(31.5 * scale)),
            (round(26 * scale), round(31.5 * scale)),
        ),
        fill=ACCENT,
        width=round(2.4 * scale),
        joint="curve",
    )
    draw.line(
        (round(30.5 * scale), round(18.5 * scale), round(30.5 * scale), round(22.5 * scale)),
        fill=ACCENT,
        width=round(2.4 * scale),
    )
    return image.resize((256, 256), Image.Resampling.LANCZOS)


def main() -> None:
    icon = build_icon()
    icon.save(
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Icono de Windows generado: {OUTPUT}")


if __name__ == "__main__":
    main()
