"""SawitPRO Shipping Cost Estimator: pick products, origin and destination; get the cheapest vendor x fleet option."""
from __future__ import annotations

import html
import math
import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Shipping Cost Estimator · SawitPRO", page_icon="🚚", layout="wide")

CATEGORY_STYLE = {  # icon, accent colour
    "Pupuk": ("🌾", "#B7892F"),
    "Pupuk SawitPRO": ("🌴", "#1F4D36"),
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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Inter:wght@400;500;600&display=swap');
:root{--ink:#16261D;--palm:#1F4D36;--gold:#C8A24A;--cream:#F6F2E8;--paper:#FFFDF7;--line:#DCD3BC;--muted:#6B7466;}
html,body,[class*="css"],.stMarkdown,.stTextInput,.stSelectbox,.stNumberInput{font-family:'Inter',system-ui,sans-serif;}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,#E7DDC2 0%,transparent 60%),var(--cream);}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2.2rem;max-width:1180px;}
h1,h2,h3,.display{font-family:'Fraunces',Georgia,serif!important;color:var(--ink);letter-spacing:-.01em;}
.eyebrow{font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;color:var(--palm);font-weight:600;}
.hero h1{font-size:3rem;line-height:1.02;margin:.35rem 0 .5rem;}
.hero p{color:var(--muted);max-width:620px;font-size:1.02rem;margin:0;}
.step{display:flex;align-items:center;gap:.6rem;margin:1.6rem 0 .6rem;}
.step b{display:inline-grid;place-items:center;width:1.7rem;height:1.7rem;border-radius:50%;background:var(--palm);color:var(--cream);font-size:.8rem;}
.step span{font-family:'Fraunces',serif;font-size:1.35rem;color:var(--ink);}
.pcard{background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:12px;padding:.65rem .8rem .2rem;margin-bottom:.2rem;}
.pcard .t{font-weight:600;font-size:.9rem;color:var(--ink);line-height:1.25;}
.pcard .m{font-size:.75rem;color:var(--muted);}
.chip{display:inline-block;padding:.1rem .5rem;border-radius:99px;font-size:.7rem;font-weight:600;color:#fff;background:var(--c);}
.total{display:flex;gap:2.2rem;align-items:baseline;background:var(--palm);color:var(--cream);border-radius:14px;padding:1rem 1.4rem;margin-top:.8rem;}
.total .v{font-family:'Fraunces',serif;font-size:2rem;}
.total .l{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;opacity:.75;}
.waybill{position:relative;background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:1.5rem 1.7rem;
  box-shadow:0 18px 40px -24px rgba(22,38,29,.45);animation:rise .45s ease-out;}
.waybill:before{content:"";position:absolute;left:0;right:0;top:92px;border-top:2px dashed var(--line);}
.waybill .route{font-family:'Fraunces',serif;font-size:1.45rem;color:var(--ink);}
.waybill .route em{color:var(--gold);font-style:normal;padding:0 .4rem;}
.waybill .price{font-family:'Fraunces',serif;font-size:2.6rem;color:var(--palm);margin-top:1.5rem;line-height:1;}
.waybill .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:1.1rem;}
.waybill .grid div{font-size:.95rem;color:var(--ink);font-weight:600;}
.waybill .grid small{display:block;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:500;}
.stamp{position:absolute;right:1.4rem;top:1.2rem;border:2px solid var(--gold);color:var(--gold);border-radius:8px;padding:.2rem .6rem;
  font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;font-weight:700;transform:rotate(4deg);}
.note{margin-top:1rem;font-size:.82rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.7rem;}
table.alt{width:100%;border-collapse:collapse;margin-top:.4rem;font-size:.88rem;}
table.alt th{text-align:left;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:.5rem .6rem;border-bottom:1px solid var(--line);}
table.alt td{padding:.55rem .6rem;border-bottom:1px solid #EAE3D0;color:var(--ink);vertical-align:top;}
table.alt tr.best td{background:#EEF3E8;font-weight:600;}
table.alt td.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
.tag{font-size:.7rem;padding:.08rem .45rem;border-radius:99px;border:1px solid var(--line);color:var(--muted);white-space:nowrap;}
.tag.fit{border-color:var(--palm);color:var(--palm);}
.empty{background:var(--paper);border:1px dashed var(--line);border-radius:14px;padding:1.4rem;color:var(--muted);text-align:center;}
@keyframes rise{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
@media (prefers-reduced-motion:reduce){.waybill{animation:none;}}
@media (max-width:760px){.hero h1{font-size:2.2rem;}.waybill .grid{grid-template-columns:repeat(2,1fr);}.total{flex-wrap:wrap;gap:1rem;}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="eyebrow">SawitPRO · Logistik</div>
  <h1>Shipping Cost Estimator</h1>
  <p>Pilih produk, tentukan asal dan tujuan. Estimator menghitung total berat, mencari armada yang sesuai,
  lalu membandingkan tarif per trip dan per kg dari semua vendor.</p>
</div>
""", unsafe_allow_html=True)

products, rates = load()
pmap = products.set_index("ir")


def label(ir: str) -> str:
    p = pmap.loc[ir]
    return f"{CATEGORY_STYLE.get(p['category'], ('📦',))[0]}  {p['name']}"


# ---------- step 1: products ----------

st.markdown('<div class="step"><b>1</b><span>Pilih produk</span></div>', unsafe_allow_html=True)
cats = list(CATEGORY_STYLE)
picked_cats = st.pills("Kategori", [f"{CATEGORY_STYLE[c][0]} {c}" for c in cats], selection_mode="multi",
                       label_visibility="collapsed")
shown = products
if picked_cats:
    names = [p.split(" ", 1)[1] for p in picked_cats]
    shown = products[products["category"].isin(names)]
chosen = st.multiselect("Produk", shown["ir"].tolist(), format_func=label, placeholder="Cari nama produk…",
                        key="chosen", label_visibility="collapsed")
chosen = list(dict.fromkeys(chosen))

total_kg, missing = 0.0, []
if chosen:
    cols = st.columns(3)
    for i, ir in enumerate(chosen):
        p = pmap.loc[ir]
        icon, color = CATEGORY_STYLE.get(p["category"], ("📦", "#6B7466"))
        with cols[i % 3]:
            weight = float(p["weight_kg"] or 0)
            st.markdown(
                f'<div class="pcard" style="--c:{color}"><span class="chip" style="--c:{color}">{icon} {p["category"]}</span>'
                f'<div class="t">{html.escape(p["name"])}</div>'
                f'<div class="m">IR {ir} · {kg(weight) if weight else "berat belum ada di Odoo"} per unit</div></div>',
                unsafe_allow_html=True)
            qty = st.number_input("Jumlah unit", min_value=0, value=1, step=1, key=f"q_{ir}")
            if not weight:
                weight = st.number_input("Berat per unit (kg)", min_value=0.0, value=0.0, step=0.5, key=f"w_{ir}")
                if not weight:
                    missing.append(p["name"])
            total_kg += qty * weight

units = sum(st.session_state.get(f"q_{ir}", 1) for ir in chosen)
st.markdown(
    f'<div class="total"><div><div class="l">Total berat</div><div class="v">{kg(total_kg)}</div></div>'
    f'<div><div class="l">Produk</div><div class="v">{len(chosen)}</div></div>'
    f'<div><div class="l">Unit</div><div class="v">{units:,}</div></div></div>'.replace(f"{units:,}", f"{units:,}".replace(",", ".")),
    unsafe_allow_html=True)
if missing:
    st.caption("Isi berat per unit untuk: " + ", ".join(missing))

# ---------- step 2: route ----------

st.markdown('<div class="step"><b>2</b><span>Tentukan rute</span></div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
origin = c1.selectbox("Asal (kab/kota)", sorted(rates["origin_regency"].dropna().unique()), index=None,
                      placeholder="Pilih asal", key="origin")
from_origin = rates[rates["origin_regency"] == origin]
dest = c2.selectbox("Tujuan (kab/kota)", sorted(from_origin["dest_regency"].dropna().unique()), index=None,
                    placeholder="Pilih tujuan", disabled=origin is None, key="dest")
to_dest = from_origin[from_origin["dest_regency"] == dest]
districts = sorted(to_dest["dest_district"].dropna().unique())
district_opts = districts or ([REGENCY_LEVEL] if dest else [])
district = c3.selectbox("Kecamatan tujuan", district_opts, index=None if districts else 0,
                        placeholder="Pilih kecamatan", disabled=dest is None, key="district")

# ---------- step 3: result ----------

st.markdown('<div class="step"><b>3</b><span>Rekomendasi</span></div>', unsafe_allow_html=True)
if not (origin and dest and district) or total_kg <= 0:
    todo = "pilih produk" if total_kg <= 0 else "lengkapi rute"
    st.markdown(f'<div class="empty">Silakan {todo} untuk melihat estimasi ongkos kirim.</div>', unsafe_allow_html=True)
    st.stop()

route = to_dest[to_dest["dest_district"].isna() | (to_dest["dest_district"] == district)]
opts = options(route, total_kg)
if opts.empty:
    st.markdown('<div class="empty">Belum ada tarif untuk rute ini.</div>', unsafe_allow_html=True)
    st.stop()

best = opts.iloc[0]
fit = opts[opts["fits"]]
fleet = FLEET_LABEL.get(best["fleet"], best["fleet"])
model = "Per trip" if best["pricing_model"] == "PER_TRIP" else f"Per kg · {rp(best['price_per_kg'])}/kg"
trip_txt = f"{int(best['trips'])}× trip" if best["pricing_model"] == "PER_TRIP" else "—"
place = dest if district == REGENCY_LEVEL else f"{district}, {dest}"
note = f'<div class="note">{html.escape(best["note"])}</div>' if isinstance(best["note"], str) else ""
st.markdown(f"""
<div class="waybill">
  <div class="stamp">Termurah</div>
  <div class="eyebrow">Surat jalan estimasi · {kg(total_kg)}</div>
  <div class="route">{html.escape(origin)}<em>→</em>{html.escape(place)}</div>
  <div class="price">{rp(best['cost'])}</div>
  <div class="grid">
    <div><small>Vendor</small>{html.escape(best['logistic_vendor'])}</div>
    <div><small>Armada</small>{fleet}</div>
    <div><small>Skema</small>{model}</div>
    <div><small>Trip · per kg efektif</small>{trip_txt} · {rp(best['cost'] / total_kg)}/kg</div>
  </div>
  {note}
</div>
""", unsafe_allow_html=True)

if not fit.empty and fit.iloc[0]["cost"] != best["cost"]:
    f = fit.iloc[0]
    st.caption(f"Armada yang pas dengan berat ini: {FLEET_LABEL.get(f['fleet'], f['fleet'])} "
               f"({f['logistic_vendor']}) {rp(f['cost'])}.")

rows = []
for i, o in opts.iterrows():
    lo = 0 if pd.isna(o["capacity_min_kg"]) else o["capacity_min_kg"]
    rng = f"{kg(lo)}–{kg(o['capacity_max_kg'])}" if pd.notna(o["capacity_max_kg"]) else "—"
    tariff = rp(o["price_per_trip"]) + "/trip" if o["pricing_model"] == "PER_TRIP" else rp(o["price_per_kg"]) + "/kg"
    tags = '<span class="tag fit">sesuai berat</span>' if o["fits"] else ""
    if o["pricing_model"] == "PER_TRIP" and o["trips"] > 1:
        tags += f' <span class="tag">{int(o["trips"])}× trip</span>'
    note = html.escape(o["note"]) if isinstance(o["note"], str) else ""
    rows.append(f'<tr class="{"best" if i == 0 else ""}"><td>{html.escape(o["logistic_vendor"])}</td>'
                f'<td>{FLEET_LABEL.get(o["fleet"], o["fleet"])}<br><span class="tag">{rng}</span></td>'
                f'<td class="r">{tariff}</td><td>{tags}</td><td class="r">{rp(o["cost"])}</td>'
                f'<td style="font-size:.78rem;color:#6B7466">{note}</td></tr>')
st.markdown('<div class="step"><b>4</b><span>Semua opsi</span></div>', unsafe_allow_html=True)
st.markdown('<table class="alt"><thead><tr><th>Vendor</th><th>Armada · kapasitas</th><th style="text-align:right">Tarif</th>'
            '<th></th><th style="text-align:right">Estimasi</th><th>Catatan</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>", unsafe_allow_html=True)
st.caption("Sumber: Master Tarif Logistik (PKS + ODOO Current Vendor Cost), 29 Sep 2026. Estimasi belum termasuk "
           "biaya inap, bongkar muat, atau multi drop.")
