"""Load the product master (Odoo export) and the final trucking tariff master into Neon Postgres.

Usage:
    $env:DATABASE_URL = "postgresql://..."
    python load_neon.py
"""
from __future__ import annotations

import os
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


def products() -> pd.DataFrame:
    p = pd.read_excel(PRODUCTS)
    ir = p["Internal Reference"].astype(str).str.zfill(8)
    return pd.DataFrame({
        "ir": ir, "ir_base": ir.str[:6], "category_code": ir.str[:3], "category": ir.str[:3].map(CATEGORY),
        "name": p["Name"].str.strip(), "weight_kg": p["Weight"].astype(float),
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
