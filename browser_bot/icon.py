"""Generation deterministe de l'icone Windows du bot Cemanty."""
from pathlib import Path

from PIL import Image, ImageDraw


ICON_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def create_icon(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    scale = 4
    size = 256 * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = 18 * scale
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=(238, 82, 23, 255),
        outline=(166, 52, 14, 255),
        width=8 * scale,
    )

    # Flamme blanche volontairement simple pour rester lisible a 16 px.
    flame = [
        (128, 49),
        (151, 89),
        (147, 119),
        (174, 102),
        (185, 139),
        (180, 171),
        (157, 197),
        (126, 208),
        (94, 198),
        (71, 174),
        (67, 143),
        (78, 117),
        (93, 96),
        (100, 128),
        (117, 108),
    ]
    draw.polygon([(x * scale, y * scale) for x, y in flame], fill=(255, 249, 235, 255))
    draw.ellipse((105 * scale, 139 * scale, 151 * scale, 190 * scale), fill=(238, 82, 23, 255))

    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(target, format="ICO", sizes=[(side, side) for side in ICON_SIZES])
    return target
