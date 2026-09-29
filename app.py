"""SawitPRO Shipping Cost Estimator: pick products, origin and destination; get the cheapest vendor x fleet option."""
from __future__ import annotations

import base64
import html
import math
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

LOGO = Path(__file__).with_name("assets") / "logo.png"
st.set_page_config(page_title="Shipping Cost Estimator · SawitPRO", page_icon=str(LOGO), layout="wide")

CATEGORY_STYLE = {  # icon, accent colour
    "Pupuk": ("🌾", "#B7892F"),
    "Pupuk SawitPRO": ("🌴", "#426636"),
    "Herbisida": ("🧪", "#6B4E9B"),
    "Insektisida": ("🐛", "#A6452E"),
    "Benih": ("🌰", "#7A5230"),
    "Bibit": ("🌱", "#4E8A3A"),
    "Merchandise": ("👕", "#2F5D8A"),
    "Sembako": ("🛢️", "#C26A1B"),
}
FLEET_LABEL = {"PU_BV": "Pick-up / L300", "CDE": "CDE", "CDD": "CDD", "FUSO": "Fuso", "TRONTON": "Tronton",
               "CARGO": "Cargo", "CUSTOM": "Tanpa jenis truk"}
REGENCY_LEVEL = "Semua kecamatan (tarif tingkat kab/kota)"


def rp(x: float) -> str:
    return "Rp " + f"{x:,.0f}".replace(",", ".")


def kg(x: float) -> str:
    return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0") + " kg"


def step(n: int, title: str):
    st.markdown(f'<div class="step"><b>{n}</b><span>{title}</span></div>', unsafe_allow_html=True)


# ---------- data ----------

@st.cache_resource
def engine():
    url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    return create_engine(url.replace("postgresql://", "postgresql+psycopg2://", 1), pool_pre_ping=True)


@st.cache_data(ttl=3600, show_spinner="Memuat data dari Neon…")
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    with engine().connect() as con:
        products = pd.read_sql(
            "SELECT ir, name, category, weight_kg FROM products WHERE category_code <> '207' ORDER BY category, name",
            con)
        rates = pd.read_sql(
            "SELECT logistic_vendor, origin_regency, dest_regency, dest_district, fleet, capacity_min_kg, "
            "capacity_max_kg, pricing_model, price_per_trip, price_per_kg, note FROM shipping_rates", con)
    return products, rates


@st.cache_data
def logo_b64() -> str:
    return base64.b64encode(LOGO.read_bytes()).decode()


@st.cache_data
def thumb(ir: str) -> str | None:
    path = LOGO.parent / "products" / f"{ir}.webp"
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode() if path.exists() else None


def options(route: pd.DataFrame, total_kg: float) -> pd.DataFrame:
    """Cost of every vendor x fleet option for the shipment; trucks are repeated when the load exceeds capacity."""
    cap = route["capacity_max_kg"].astype(float)
    trips = (total_kg / cap).apply(lambda t: max(1, math.ceil(t)) if pd.notna(t) else 1)
    per_trip = route["pricing_model"].eq("PER_TRIP")
    cost = (route["price_per_trip"].where(per_trip, route["price_per_kg"] * total_kg)
            * trips.where(per_trip, 1))
    lo = route["capacity_min_kg"].astype(float).fillna(0)
    fits = (total_kg > lo) & (total_kg <= cap.fillna(float("inf"))) | ((total_kg == 0) & (lo == 0))
    out = route.assign(trips=trips, cost=cost.astype(float), fits=fits)
    return out.dropna(subset=["cost"]).sort_values(["cost", "fits"], ascending=[True, False]).reset_index(drop=True)


# ---------- style ----------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#1E2E1A;--palm:#426636;--palm-deep:#2E4A25;--sun:#FCD100;--cream:#F7F4EA;--paper:#FFFEF9;
  --line:#E0DAC6;--muted:#66705F;--radius:16px;}
html,body,[class*="css"],.stMarkdown,.stSelectbox,.stNumberInput,.stMultiSelect{font-family:'Inter',system-ui,sans-serif;}
.stApp{background:var(--cream);}
header[data-testid="stHeader"]{background:transparent;height:0;}
.block-container{padding:1.4rem 2rem 3rem;max-width:1240px;}
.hero{position:relative;overflow:hidden;display:flex;align-items:center;gap:1.4rem;padding:1.6rem 2rem;border-radius:22px;
  background:radial-gradient(900px 300px at 100% 0%,#5B8448 0%,transparent 55%),linear-gradient(135deg,var(--palm) 0%,var(--palm-deep) 100%);
  color:#F4F1E4;box-shadow:0 24px 50px -30px rgba(30,46,26,.7);}
.hero:after{content:"";position:absolute;left:2rem;bottom:0;width:120px;height:4px;border-radius:4px 4px 0 0;background:var(--sun);}
.hero img{width:78px;height:78px;flex:none;border-radius:50%;object-fit:cover;filter:drop-shadow(0 6px 14px rgba(0,0,0,.25));}
.hero .eyebrow{font-size:.7rem;letter-spacing:.24em;text-transform:uppercase;color:var(--sun);font-weight:700;}
.hero h1{font-family:'Fraunces',Georgia,serif;font-size:2.5rem;line-height:1.05;margin:.2rem 0 .35rem;color:#fff;letter-spacing:-.01em;padding:0;}
.hero p{margin:0;max-width:640px;font-size:.95rem;color:#DDE5D2;}
.step{display:flex;align-items:center;gap:.6rem;margin:1.5rem 0 .55rem;}
.step b{display:inline-grid;place-items:center;width:1.65rem;height:1.65rem;border-radius:50%;background:var(--palm);color:var(--sun);font-size:.8rem;}
.step span{font-family:'Fraunces',Georgia,serif;font-size:1.3rem;color:var(--ink);}
.pcard{display:flex;gap:.75rem;align-items:center;background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:12px;padding:.6rem .75rem;}
.pcard .ph{width:64px;height:64px;flex:none;border-radius:10px;border:1px solid var(--line);background:#fff;object-fit:contain;}
.pcard .ph.ico{display:grid;place-items:center;font-size:1.7rem;background:color-mix(in srgb,var(--c) 10%,#fff);}
.pcard .pt{min-width:0;}
.pcard .t{font-weight:600;font-size:.9rem;color:var(--ink);line-height:1.25;margin-top:.3rem;}
.pcard .m{font-size:.74rem;color:var(--muted);margin-top:.15rem;}
.chip{display:inline-block;padding:.08rem .5rem;border-radius:99px;font-size:.68rem;font-weight:600;color:#fff;background:var(--c);}
.st-key-summary{position:sticky;top:1rem;}
.total{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:.6rem;background:var(--paper);border:1px solid var(--line);
  border-radius:var(--radius);padding:1rem 1.2rem;}
.total .v{font-family:'Fraunces',Georgia,serif;font-size:1.7rem;color:var(--palm);line-height:1.1;}
.total .l{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;}
.waybill{position:relative;margin-top:.9rem;background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;box-shadow:0 20px 40px -28px rgba(30,46,26,.55);animation:rise .4s ease-out;}
.waybill .head{background:var(--palm);color:#F4F1E4;padding:1rem 1.3rem;}
.waybill .head .eyebrow{padding-right:6.5rem;font-size:.66rem;letter-spacing:.2em;text-transform:uppercase;color:var(--sun);font-weight:700;}
.waybill .route{font-family:'Fraunces',Georgia,serif;font-size:1.2rem;margin-top:.2rem;line-height:1.3;}
.waybill .route em{color:var(--sun);font-style:normal;padding:0 .35rem;}
.waybill .body{padding:1.1rem 1.3rem 1.2rem;border-top:2px dashed var(--line);}
.waybill .price{font-family:'Fraunces',Georgia,serif;font-size:2.3rem;color:var(--ink);line-height:1;}
.waybill .grid{display:grid;grid-template-columns:1fr 1fr;gap:.8rem 1rem;margin-top:1rem;}
.waybill .grid div{font-size:.9rem;color:var(--ink);font-weight:600;}
.waybill .grid small{display:block;font-size:.64rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:500;}
.stamp{position:absolute;right:1rem;top:1rem;background:var(--sun);color:var(--palm-deep);border-radius:99px;padding:.2rem .65rem;
  font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;font-weight:700;}
.note{margin-top:.9rem;font-size:.8rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.6rem;}
.hint{margin-top:.6rem;font-size:.8rem;color:var(--muted);}
.empty{margin-top:.9rem;background:var(--paper);border:1px dashed var(--line);border-radius:var(--radius);padding:1.6rem 1.2rem;
  color:var(--muted);text-align:center;font-size:.92rem;}
.empty b{display:block;font-family:'Fraunces',Georgia,serif;font-size:1.1rem;color:var(--ink);margin-bottom:.25rem;}
table.alt{width:100%;border-collapse:separate;border-spacing:0;font-size:.88rem;background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;}
table.alt th{text-align:left;font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:.7rem .8rem;border-bottom:1px solid var(--line);background:#F1EDDF;}
table.alt td{padding:.65rem .8rem;border-bottom:1px solid #EEE8D6;color:var(--ink);vertical-align:top;}
table.alt tr:last-child td{border-bottom:none;}
table.alt tr.best td{background:#EFF4E6;font-weight:600;}
table.alt td.r,table.alt th.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
table.alt td.n{font-size:.78rem;color:var(--muted);}
.tag{display:inline-block;font-size:.68rem;padding:.06rem .45rem;border-radius:99px;border:1px solid var(--line);color:var(--muted);white-space:nowrap;margin:.1rem .15rem 0 0;}
.tag.fit{border-color:var(--palm);color:var(--palm);background:#EFF4E6;}
.foot{margin-top:1rem;font-size:.75rem;color:var(--muted);}
@keyframes rise{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
@media (prefers-reduced-motion:reduce){.waybill{animation:none;}}
@media (max-width:900px){.st-key-summary{position:static;}}
@media (max-width:640px){
  .block-container{padding:.8rem .9rem 2.5rem;}
  .hero{padding:1.1rem 1.1rem 1.3rem;gap:.9rem;border-radius:18px;}
  .hero:after{left:1.1rem;width:80px;}
  .hero img{width:52px;height:52px;}
  .hero h1{font-size:1.6rem;}
  .hero p{font-size:.84rem;}
  .step{margin:1.2rem 0 .45rem;}
  .step span{font-size:1.15rem;}
  .total .v{font-size:1.35rem;}
  .waybill .price{font-size:1.9rem;}
  table.alt thead{display:none;}
  table.alt,table.alt tbody,table.alt tr,table.alt td{display:block;width:100%;}
  table.alt{border:none;background:transparent;}
  table.alt tr{background:var(--paper);border:1px solid var(--line);border-radius:14px;margin-bottom:.6rem;padding:.5rem .2rem;}
  table.alt tr.best{border-color:var(--palm);}
  table.alt tr.best td{background:transparent;}
  table.alt td{border:none;padding:.2rem .8rem;display:flex;justify-content:space-between;gap:1rem;}
  table.alt td:before{content:attr(data-l);font-size:.64rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600;padding-top:.15rem;}
  table.alt td.r,table.alt td>span{text-align:right;}
  table.alt td.n:empty,table.alt td.g:empty{display:none;}
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
  <img src="data:image/png;base64,{logo_b64()}" alt="SawitPRO">
  <div>
    <div class="eyebrow">SawitPRO · Logistik</div>
    <h1>Shipping Cost Estimator</h1>
    <p>Pilih produk dan rute. Estimator menghitung total berat, mencari armada yang sesuai,
    lalu membandingkan tarif per trip dan per kg dari semua vendor.</p>
  </div>
</div>
""", unsafe_allow_html=True)

products, rates = load()
pmap = products.set_index("ir")


def label(ir: str) -> str:
    p = pmap.loc[ir]
    return f"{CATEGORY_STYLE.get(p['category'], ('📦',))[0]}  {p['name']}"


left, right = st.columns([1.45, 1], gap="large")

# ---------- step 1: products ----------

with left:
    step(1, "Pilih produk")
    picked_cats = st.pills("Kategori", [f"{CATEGORY_STYLE[c][0]} {c}" for c in CATEGORY_STYLE],
                           selection_mode="multi", label_visibility="collapsed")
    shown = products
    if picked_cats:
        shown = products[products["category"].isin([p.split(" ", 1)[1] for p in picked_cats])]
    chosen = st.multiselect("Produk", shown["ir"].tolist(), format_func=label, placeholder="Cari nama produk…",
                            key="chosen", label_visibility="collapsed")
    chosen = list(dict.fromkeys(chosen))

    total_kg, missing = 0.0, []
    if chosen:
        cols = st.columns(2)
        for i, ir in enumerate(chosen):
            p = pmap.loc[ir]
            icon, color = CATEGORY_STYLE.get(p["category"], ("📦", "#66705F"))
            with cols[i % 2]:
                weight = float(p["weight_kg"] or 0)
                src = thumb(ir)
                pic = (f'<img class="ph" src="{src}" alt="">' if src
                       else f'<div class="ph ico" style="--c:{color}">{icon}</div>')
                st.markdown(
                    f'<div class="pcard" style="--c:{color}">{pic}<div class="pt">'
                    f'<span class="chip" style="--c:{color}">{icon} {p["category"]}</span>'
                    f'<div class="t">{html.escape(p["name"])}</div>'
                    f'<div class="m">IR {ir} · {kg(weight) if weight else "berat belum ada di Odoo"} per unit</div></div></div>',
                    unsafe_allow_html=True)
                qty = st.number_input("Jumlah unit", min_value=0, value=1, step=1, key=f"q_{ir}")
                if not weight:
                    weight = st.number_input("Berat per unit (kg)", min_value=0.0, value=0.0, step=0.5, key=f"w_{ir}")
                    if not weight:
                        missing.append(p["name"])
                total_kg += qty * weight
    if missing:
        st.caption("Isi berat per unit untuk: " + ", ".join(missing))

    # ---------- step 2: route ----------

    step(2, "Tentukan rute")
    origin = st.selectbox("Asal (kab/kota)", sorted(rates["origin_regency"].dropna().unique()), index=None,
                          placeholder="Pilih asal", key="origin")
    from_origin = rates[rates["origin_regency"] == origin]
    c1, c2 = st.columns(2)
    dest = c1.selectbox("Tujuan (kab/kota)", sorted(from_origin["dest_regency"].dropna().unique()), index=None,
                        placeholder="Pilih tujuan", disabled=origin is None, key="dest")
    to_dest = from_origin[from_origin["dest_regency"] == dest]
    districts = sorted(to_dest["dest_district"].dropna().unique())
    district_opts = districts or ([REGENCY_LEVEL] if dest else [])
    district = c2.selectbox("Kecamatan tujuan", district_opts, index=None if districts else 0,
                            placeholder="Pilih kecamatan", disabled=dest is None, key="district")

# ---------- step 3: summary & recommendation ----------

opts = pd.DataFrame()
ready = bool(origin and dest and district) and total_kg > 0
if ready:
    route = to_dest[to_dest["dest_district"].isna() | (to_dest["dest_district"] == district)]
    opts = options(route, total_kg)

with right:
    summary = st.container(key="summary")
    with summary:
        step(3, "Estimasi")
        units = sum(st.session_state.get(f"q_{ir}", 1) for ir in chosen)
        st.markdown(
            f'<div class="total"><div><div class="l">Total berat</div><div class="v">{kg(total_kg)}</div></div>'
            f'<div><div class="l">Produk</div><div class="v">{len(chosen)}</div></div>'
            f'<div><div class="l">Unit</div><div class="v">{units:,}</div></div></div>'.replace(
                f"{units:,}", f"{units:,}".replace(",", ".")),
            unsafe_allow_html=True)

        if not ready:
            todo = "Pilih produk dan isi jumlahnya" if total_kg <= 0 else "Lengkapi asal, tujuan, dan kecamatan"
            st.markdown(f'<div class="empty"><b>Belum ada estimasi</b>{todo} untuk melihat ongkos kirim termurah.</div>',
                        unsafe_allow_html=True)
        elif opts.empty:
            st.markdown('<div class="empty"><b>Tarif belum tersedia</b>Belum ada tarif untuk rute ini.</div>',
                        unsafe_allow_html=True)
        else:
            best = opts.iloc[0]
            fit = opts[opts["fits"]]
            model = "Per trip" if best["pricing_model"] == "PER_TRIP" else f"Per kg · {rp(best['price_per_kg'])}"
            trip_txt = f"{int(best['trips'])}× trip" if best["pricing_model"] == "PER_TRIP" else "—"
            place = dest if district == REGENCY_LEVEL else f"{district}, {dest}"
            note = f'<div class="note">{html.escape(best["note"])}</div>' if isinstance(best["note"], str) else ""
            hint = ""
            if not fit.empty and fit.iloc[0]["cost"] != best["cost"]:
                f = fit.iloc[0]
                hint = (f'<div class="hint">Armada yang pas dengan berat ini: <b>{FLEET_LABEL.get(f["fleet"], f["fleet"])}</b> '
                        f'({html.escape(f["logistic_vendor"])}) {rp(f["cost"])}.</div>')
            st.markdown(f"""
<div class="waybill">
  <div class="head">
    <div class="stamp">Termurah</div>
    <div class="eyebrow">Surat jalan estimasi · {kg(total_kg)}</div>
    <div class="route">{html.escape(origin)}<em>→</em>{html.escape(place)}</div>
  </div>
  <div class="body">
    <div class="price">{rp(best['cost'])}</div>
    <div class="grid">
      <div><small>Vendor</small>{html.escape(best['logistic_vendor'])}</div>
      <div><small>Armada</small>{FLEET_LABEL.get(best['fleet'], best['fleet'])}</div>
      <div><small>Skema</small>{model}</div>
      <div><small>Trip · per kg efektif</small>{trip_txt} · {rp(best['cost'] / total_kg)}/kg</div>
    </div>
    {note}
  </div>
</div>
{hint}
""", unsafe_allow_html=True)

# ---------- step 4: all options ----------

if not opts.empty:
    rows = []
    for i, o in opts.iterrows():
        lo = 0 if pd.isna(o["capacity_min_kg"]) else o["capacity_min_kg"]
        rng = f"{kg(lo)}–{kg(o['capacity_max_kg'])}" if pd.notna(o["capacity_max_kg"]) else "—"
        tariff = rp(o["price_per_trip"]) + "/trip" if o["pricing_model"] == "PER_TRIP" else rp(o["price_per_kg"]) + "/kg"
        tags = '<span class="tag fit">sesuai berat</span>' if o["fits"] else ""
        if o["pricing_model"] == "PER_TRIP" and o["trips"] > 1:
            tags += f'<span class="tag">{int(o["trips"])}× trip</span>'
        note = html.escape(o["note"]) if isinstance(o["note"], str) else ""
        rows.append(
            f'<tr class="{"best" if i == 0 else ""}"><td data-l="Vendor">{html.escape(o["logistic_vendor"])}</td>'
            f'<td data-l="Armada"><span>{FLEET_LABEL.get(o["fleet"], o["fleet"])} <span class="tag">{rng}</span></span></td>'
            f'<td data-l="Tarif" class="r">{tariff}</td><td data-l="Info" class="g">{f"<span>{tags}</span>" if tags else ""}</td>'
            f'<td data-l="Estimasi" class="r">{rp(o["cost"])}</td><td data-l="Catatan" class="n">{f"<span>{note}</span>" if note else ""}</td></tr>')
    step(4, f"Semua opsi ({len(opts)})")
    st.markdown('<table class="alt"><thead><tr><th>Vendor</th><th>Armada · kapasitas</th><th class="r">Tarif</th>'
                '<th></th><th class="r">Estimasi</th><th>Catatan</th></tr></thead><tbody>'
                + "".join(rows) + "</tbody></table>", unsafe_allow_html=True)

st.markdown('<div class="foot">Sumber: Master Tarif Logistik (PKS + ODOO Current Vendor Cost), 29 Sep 2026. '
            'Estimasi belum termasuk biaya inap, bongkar muat, atau multi drop.</div>', unsafe_allow_html=True)
