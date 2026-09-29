"""Match product photos (named after the Odoo product) to IR codes and write small square thumbnails to assets/products/<ir>.webp.

Usage: python build_thumbs.py "C:\\Users\\denaf\\Downloads\\SawitPRO Foto Produk"
"""
import re
import sys
import tomllib
from pathlib import Path

import pandas as pd
from PIL import Image
from sqlalchemy import create_engine

SIZE = 160
PAD = 8
HERE = Path(__file__).parent
OUT = HERE / "assets" / "products"
VARIANT = re.compile(r"\s*\((grosir|toko keliling|khusus petani)\)\s*$", re.I)
MANUAL = {  # product name -> photo name, when Odoo and the photo folder name the product differently
    "Topzone 276 SL 20 Liter - Herbisida Penyiang Pembasmi Gulma Berdaun Lebar": "Topzone 276 SL - 20 Liter",
    "Pupuk SawitPRO 20kg + Abu Janjang 40kg": "Pupuk SawitPRO 20kg",
    "Pupuk SawitPRO 50kg + Abu Janjang 40kg": "Pupuk SawitPRO 50kg",
}


def crop_product(img: Image.Image) -> Image.Image:
    """Drop the TokoSawit footer strip (social icons below a white gap near the bottom) and surrounding white space."""
    flat = Image.new("RGB", img.size, "white")
    flat.paste(img, mask=img.getchannel("A"))
    ink = flat.convert("L").point(lambda v: 255 if v < 235 else 0)
    w, h = ink.size
    has_ink = [ink.crop((0, y, w, y + 1)).getbbox() is not None for y in range(h)]
    for y in range(int(h * 0.93), int(h * 0.78), -1):
        if not has_ink[y] and any(has_ink[y:]):
            img, ink = img.crop((0, 0, w, y)), ink.crop((0, 0, w, y))
            break
    box = ink.getbbox()
    return img.crop(box) if box else img


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main(src: Path):
    url = tomllib.loads((HERE / ".streamlit" / "secrets.toml").read_text())["DATABASE_URL"]
    products = pd.read_sql("SELECT ir, name FROM products WHERE category_code <> '207'",
                           create_engine(url.replace("postgresql://", "postgresql+psycopg2://", 1)))
    exact, base = {}, {}
    for f in sorted(src.iterdir()):
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            exact[norm(f.stem)] = f
            base.setdefault(norm(VARIANT.sub("", f.stem)), f)

    OUT.mkdir(parents=True, exist_ok=True)
    missing = []
    for ir, name in products.itertuples(index=False):
        key = norm(MANUAL.get(name, name))
        photo = exact.get(key) or base.get(key)
        if photo is None:
            missing.append(name)
            continue
        img = crop_product(Image.open(photo).convert("RGBA"))
        img.thumbnail((SIZE - 2 * PAD, SIZE - 2 * PAD), Image.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
        canvas.alpha_composite(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2))
        canvas.convert("RGB").save(OUT / f"{ir}.webp", "WEBP", quality=82, method=6)
    print(f"{len(products) - len(missing)} thumbnails, {len(missing)} without photo:")
    for name in sorted(missing):
        print("  -", name)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
