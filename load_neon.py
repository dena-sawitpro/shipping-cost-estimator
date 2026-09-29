"""Load the product master (Odoo export) and the final trucking tariff master into Neon Postgres.

Usage:
    $env:DATABASE_URL = "postgresql://..."
    python load_neon.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DL = Path(r"c:\Users\denaf\Downloads")
PRODUCTS = DL / "ODOO Product Info.xlsx"
RATES = DL / "Master Tarif Logistik - Final 29 Sep 2026 v3.xlsx"

CATEGORY = {"101": "Pupuk", "102": "Pupuk SawitPRO", "103": "Herbisida", "104": "Insektisida", "105": "Benih",
            "106": "Bibit", "108": "Merchandise", "109": "Sembako", "207": "Pulsa"}


def engine():
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?"))


UNIT_KG = {"kg": 1, "gr": 0.001, "gram": 0.001, "g": 0.001, "liter": 1, "l": 1, "ml": 0.001}  # liquids at ~1 kg/L
QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|gram|gr|g|liter|l|ml)\b", re.I)


def weight_from_name(name: str) -> float | None:
    """Estimate unit weight from the package size in the product title; bundles ('20kg + ... 40kg') are summed."""
    hits = QTY.findall(name)
    return sum(float(n.replace(",", ".")) * UNIT_KG[u.lower()] for n, u in hits) if hits else None


def products() -> pd.DataFrame:
    p = pd.read_excel(PRODUCTS)
    ir = p["Internal Reference"].astype(str).str.zfill(8)
    name = p["Name"].str.strip()
    odoo = p["Weight"].astype(float)
    guess = name.map(weight_from_name)
    missing = odoo.isna() | (odoo <= 0)
    return pd.DataFrame({
        "ir": ir, "ir_base": ir.str[:6], "category_code": ir.str[:3], "category": ir.str[:3].map(CATEGORY),
        "name": name, "weight_kg": odoo.where(~missing, guess),
        "weight_source": pd.Series("odoo", index=p.index).where(~missing, guess.notna().map({True: "judul", False: None})),
        "sales_price": p["Sales Price"].astype(float), "tags": p["Tags"],
    })


def rates() -> pd.DataFrame:
    r = pd.read_excel(RATES, sheet_name="Master Tarif")
    for col in ["rate_id", "dest_zone", "capacity_min_kg", "capacity_max_kg", "source_page"]:
        r[col] = r[col].astype("Int64")
    return r


def main():
    eng = engine()
    p, r = products(), rates()
    with eng.begin() as con:
        p.to_sql("products", con, if_exists="replace", index=False)
        r.to_sql("shipping_rates", con, if_exists="replace", index=False)
        con.execute(text("ALTER TABLE products ADD PRIMARY KEY (ir)"))
        con.execute(text("ALTER TABLE shipping_rates ADD PRIMARY KEY (rate_id)"))
        con.execute(text("CREATE INDEX ON shipping_rates (origin_key, dest_key)"))
    with eng.connect() as con:
        for t in ["products", "shipping_rates"]:
            print(t, con.execute(text(f"SELECT count(*) FROM {t}")).scalar())


if __name__ == "__main__":
    main()
