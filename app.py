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
LOADING_FEE_PER_TON = 35_000

def rp(x: float) -> str:
    return "Rp " + f"{x:,.0f}".replace(",", ".")


def kg(x: float) -> str:
    whole, frac = f"{x:,.2f}".split(".")
    frac = frac.rstrip("0")
    return whole.replace(",", ".") + (f",{frac}" if frac else "") + " kg"


def num(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


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
            "SELECT ir, name, category, weight_kg, weight_source FROM products "
            "WHERE category_code <> '207' AND weight_kg > 0 ORDER BY category, name",
            con)
        rates = pd.read_sql(
            "SELECT logistic_vendor, origin_regency, dest_regency, dest_district, fleet, capacity_min_kg, "
            "capacity_max_kg, pricing_model, price_per_trip, price_per_kg FROM shipping_rates", con)
    return products, rates


@st.cache_data
def logo_b64() -> str:
    return base64.b64encode(LOGO.read_bytes()).decode()


@st.cache_data
def thumb(ir: str, category: str) -> str:
    path = LOGO.parent / "products" / f"{ir}.webp"
    if path.exists():
        return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode()
    icon, color = CATEGORY_STYLE.get(category, ("📦", "#66705F"))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" rx="14" '
           f'fill="{color}" fill-opacity=".16"/><text x="40" y="52" font-size="36" text-anchor="middle">{icon}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def options(route: pd.DataFrame, total_kg: float) -> pd.DataFrame:
    """Price every vendor x fleet option for the shipment.

    Per-trip tariffs are shown as a join-route share (trip price / max capacity x shipment kg); the full charter
    (trip price x trucks needed) is kept alongside. An option is eligible once the shipment reaches its minimum load.
    """
    lo = route["capacity_min_kg"].astype(float).fillna(0)
    cap = route["capacity_max_kg"].astype(float)
    per_trip = route["pricing_model"].eq("PER_TRIP")
    trips = (total_kg / cap).apply(lambda t: max(1, math.ceil(t)) if pd.notna(t) else 1)
    charter = (route["price_per_trip"] * trips).where(per_trip)
    join = (route["price_per_trip"] / cap * total_kg).where(cap.notna(), route["price_per_trip"])
    estimate = join.where(per_trip, route["price_per_kg"] * total_kg)
    minimum = route["price_per_trip"].where(per_trip, route["price_per_kg"] * lo)
    out = route.assign(lo=lo, trips=trips, charter=charter, estimate=estimate.astype(float), minimum=minimum,
                       join_route=per_trip & cap.notna() & (join < charter - 0.5), eligible=total_kg >= lo,
                       fits=(total_kg >= lo) & ((total_kg <= cap) | cap.isna()))
    return out.dropna(subset=["estimate"]).sort_values(["estimate", "fits"], ascending=[True, False]).reset_index(drop=True)


def capacity(o) -> str:
    return f"{num(o['lo'])}–{num(o['capacity_max_kg'])} kg" if pd.notna(o["capacity_max_kg"]) else "tanpa batas"


def tariff(o) -> str:
    return f"{rp(o['price_per_trip'])}/trip" if o["pricing_model"] == "PER_TRIP" else f"{rp(o['price_per_kg'])}/kg"


# ---------- style ----------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#1E2E1A;--palm:#426636;--palm-deep:#2E4A25;--leaf:#E6EEDC;--sun:#FCD100;--sun-soft:#FFF4C2;--cream:#F7F4EA;
  --paper:#FFFEF9;--line:#E0DAC6;--muted:#66705F;--alert:#C63D2F;--radius:16px;}
html,body,[class*="css"],.stMarkdown,.stSelectbox,.stTextInput{font-family:'Inter',system-ui,sans-serif;}
.stApp{background:radial-gradient(1200px 500px at 110% -10%,#E9F0DD 0%,transparent 60%),var(--cream);}
header[data-testid="stHeader"]{background:transparent;height:0;}
.block-container{padding:1.4rem 2rem 3rem;max-width:1280px;}
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
.help{font-size:.78rem;color:var(--muted);margin:-.2rem 0 .5rem;}
.st-key-add div:has(>input),.st-key-origin div:has(>input),.st-key-dest_pick div:has(>input){
  background:#fff;border:1px solid var(--line);border-radius:12px;min-height:46px;
  box-shadow:0 1px 2px rgba(30,46,26,.04),0 6px 16px -12px rgba(30,46,26,.35);transition:border-color .15s,box-shadow .15s;}
.st-key-add div:has(>input):hover,.st-key-origin div:has(>input):hover,.st-key-dest_pick div:has(>input):hover{border-color:#B9C9A6;}
.st-key-add div:has(>input):focus-within,.st-key-origin div:has(>input):focus-within,
.st-key-dest_pick div:has(>input):focus-within{border-color:var(--palm);box-shadow:0 0 0 3px rgba(66,102,54,.14);}
.st-key-add input::placeholder,.st-key-origin input::placeholder,.st-key-dest_pick input::placeholder{color:#8B917F;}
.st-key-add div:has(>input){padding-left:2.3rem;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23426636' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E") no-repeat .85rem center/17px;}
.st-key-dest_pick div:has(>input:disabled){background:#FAF8F2;box-shadow:none;}
[data-testid="stPopover"] button{background:#fff;border:1px solid var(--line);border-radius:12px;min-height:46px;color:var(--ink);
  box-shadow:0 1px 2px rgba(30,46,26,.04),0 6px 16px -12px rgba(30,46,26,.35);}
[data-testid="stPopover"] button:hover{border-color:#B9C9A6;color:var(--palm);}
.st-key-route{gap:.45rem;}
.st-key-route [data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
.st-key-route label p{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700;}
.st-key-route label [data-testid="stIconMaterial"]{color:var(--palm);font-size:1rem;}
.route-arrow{display:grid;place-items:center;width:30px;height:30px;margin:0 auto 8px;border-radius:50%;background:var(--leaf);
  color:var(--palm);font-weight:700;border:1px solid #C9D6B8;}
.route-meta{font-size:.74rem;color:var(--muted);}
.st-key-cart{gap:.5rem;margin-top:.2rem;}
[class*="st-key-line_"]{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:.5rem .6rem .5rem .5rem;
  box-shadow:0 10px 24px -22px rgba(30,46,26,.6);transition:border-color .15s;}
[class*="st-key-line_"]:hover{border-color:#C9D6B8;}
[class*="st-key-line_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:.7rem;align-items:center;}
[class*="st-key-line_"] [data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
[class*="st-key-line_"] [data-testid="stColumn"]{min-width:0 !important;width:auto !important;}
[class*="st-key-line_"] [data-testid="stColumn"]:nth-child(1){flex:0 0 34px !important;}
[class*="st-key-line_"] [data-testid="stColumn"]:nth-child(2){flex:0 0 132px !important;}
[class*="st-key-line_"] [data-testid="stColumn"]:nth-child(3){flex:0 0 56px !important;}
[class*="st-key-line_"] [data-testid="stColumn"]:nth-child(4){flex:1 1 auto !important;}
.pthumb{display:block;width:56px;height:56px;padding:4px;box-sizing:border-box;border-radius:12px;object-fit:contain;
  background:#fff;border:1px solid #EEE8D6;box-shadow:0 4px 10px -6px rgba(30,46,26,.35);}
.pname{font-size:.9rem;font-weight:600;color:var(--ink);line-height:1.25;overflow:hidden;display:-webkit-box;
  -webkit-line-clamp:2;-webkit-box-orient:vertical;}
.pmeta{font-size:.74rem;color:var(--muted);margin-top:.15rem;font-variant-numeric:tabular-nums;}
.pmeta b{color:var(--palm);}
[class*="st-key-q_"] [data-testid="stNumberInputContainer"]{border-radius:10px;border:1.5px solid var(--palm) !important;
  background:#fff;overflow:hidden;}
[class*="st-key-q_"] input{text-align:center;font-weight:700;font-size:1rem;color:var(--ink);padding-left:.3rem;padding-right:0;}
[class*="st-key-q_"] button{background:var(--leaf);color:var(--palm);border:none;width:2rem;height:100%;}
[class*="st-key-q_"] button:hover{background:var(--palm);color:#fff;}
[class*="st-key-del_"] button{color:#9AA08F;min-height:2rem;padding:.2rem;}
[class*="st-key-del_"] button:hover{color:var(--alert);background:#FBE9E6;}
.st-key-summary{position:sticky;top:1rem;}
.total{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:.6rem;background:linear-gradient(135deg,#FFFEF9 0%,#F3F7EC 100%);
  border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.2rem;}
.total .v{font-family:'Fraunces',Georgia,serif;font-size:1.7rem;color:var(--palm);line-height:1.1;}
.total .l{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;}
.waybill{position:relative;margin-top:.9rem;background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;box-shadow:0 20px 40px -28px rgba(30,46,26,.55);animation:rise .4s ease-out;}
.waybill .head{background:var(--palm);color:#F4F1E4;padding:1rem 1.3rem;}
.waybill .head .eyebrow{font-size:.66rem;letter-spacing:.2em;text-transform:uppercase;color:var(--sun);font-weight:700;}
.waybill .route{font-family:'Fraunces',Georgia,serif;font-size:1.2rem;margin-top:.2rem;line-height:1.3;}
.waybill .route em{color:var(--sun);font-style:normal;padding:0 .35rem;}
.waybill .body{padding:1.1rem 1.3rem 1.2rem;border-top:2px dashed var(--line);}
.waybill .price{font-family:'Fraunces',Georgia,serif;font-size:2.3rem;color:var(--ink);line-height:1;}
.badges{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.6rem;}
.badge{display:inline-flex;align-items:center;border-radius:99px;padding:.22rem .7rem;font-size:.7rem;font-weight:700;letter-spacing:.04em;}
.badge.best{background:var(--sun);color:var(--palm-deep);}
.badge.join{background:var(--alert);color:#fff;}
.waybill .grid{display:grid;grid-template-columns:1fr 1fr;gap:.8rem 1rem;margin-top:1rem;}
.waybill .grid div{font-size:.9rem;color:var(--ink);font-weight:600;}
.waybill .grid small{display:block;font-size:.64rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:500;}
.fee{margin-top:1rem;padding:.55rem .75rem;border-radius:10px;background:var(--sun-soft);font-size:.76rem;color:#5A4B00;line-height:1.55;
  display:flex;flex-direction:column;font-variant-numeric:tabular-nums;}
.fee b{color:var(--ink);}
.fine{margin-top:.55rem;font-size:.72rem;color:var(--muted);line-height:1.45;}
.empty{margin-top:.9rem;background:var(--paper);border:1px dashed var(--line);border-radius:var(--radius);padding:1.6rem 1.2rem;
  color:var(--muted);text-align:center;font-size:.92rem;}
.empty.slim{margin-top:.6rem;padding:1rem;font-size:.85rem;}
.help{margin-top:.5rem;}
.empty b{display:block;font-family:'Fraunces',Georgia,serif;font-size:1.1rem;color:var(--ink);margin-bottom:.25rem;}
table.alt{width:100%;border-collapse:separate;border-spacing:0;font-size:.88rem;background:var(--paper);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden;box-shadow:0 14px 30px -24px rgba(30,46,26,.6);}
table.alt th{text-align:left;font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:#EAF0E0;font-weight:600;
  padding:.75rem .85rem;background:var(--palm);}
table.alt td{padding:.65rem .85rem;border-bottom:1px solid #EEE8D6;color:var(--ink);vertical-align:middle;}
table.alt tr:last-child td{border-bottom:none;}
table.alt tbody tr:nth-child(even) td{background:#FBF9F2;}
table.alt tr.best td{background:var(--sun-soft) !important;font-weight:600;}
table.alt tr.best td:first-child{box-shadow:inset 4px 0 0 var(--sun);}
table.alt td.r,table.alt th.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
table.alt td small{display:block;font-size:.7rem;font-weight:500;color:var(--muted);margin-top:.1rem;}
.tags{display:flex;flex-direction:column;align-items:flex-start;gap:.3rem;color:var(--muted);}
.tag{display:inline-block;font-size:.68rem;line-height:1.35;padding:.12rem .55rem;border-radius:99px;border:1px solid var(--line);
  color:var(--muted);white-space:nowrap;}
.tag.fit{border-color:#C9D6B8;color:var(--palm);background:var(--leaf);}
.tag.join{border-color:var(--alert);color:#fff;background:var(--alert);font-weight:600;}
[data-testid="stExpander"] details{background:var(--paper);border:1px solid var(--line);border-radius:14px;}
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
  .route-arrow{transform:rotate(90deg);margin:0 auto;width:26px;height:26px;}
  [class*="st-key-line_"] [data-testid="stHorizontalBlock"]{gap:.5rem;}
  [class*="st-key-line_"] [data-testid="stColumn"]:nth-child(1){flex:0 0 28px !important;}
  [class*="st-key-line_"] [data-testid="stColumn"]:nth-child(2){flex:0 0 124px !important;}
  [class*="st-key-line_"] [data-testid="stColumn"]:nth-child(3){flex:0 0 46px !important;}
  [class*="st-key-q_"] button{width:1.7rem;}
  .pthumb{width:46px;height:46px;padding:3px;border-radius:10px;}
  .pname{font-size:.84rem;}
  table.alt thead{display:none;}
  table.alt,table.alt tbody,table.alt tr,table.alt td{display:block;width:100%;}
  table.alt{border:none;background:transparent;box-shadow:none;}
  table.alt tr{background:var(--paper);border:1px solid var(--line);border-radius:14px;margin-bottom:.6rem;padding:.5rem .2rem;}
  table.alt tr.best{border-color:var(--sun);background:var(--sun-soft);}
  table.alt tbody tr td,table.alt tr.best td{background:transparent !important;box-shadow:none !important;}
  table.alt td{border:none;padding:.22rem .8rem;display:flex;justify-content:space-between;gap:1rem;}
  table.alt td:before{content:attr(data-l);font-size:.64rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600;padding-top:.15rem;}
  table.alt td>span{text-align:right;}
  .tags{align-items:flex-end;}
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
  <img src="data:image/png;base64,{logo_b64()}" alt="SawitPRO">
  <div>
    <div class="eyebrow">SawitPRO · Logistik</div>
    <h1>Shipping Cost Estimator</h1>
    <p>Isi jumlah produk dan pilih rute. Estimator menghitung total berat lalu membandingkan tarif
    per trip dan per kg dari semua vendor.</p>
  </div>
</div>
""", unsafe_allow_html=True)

products, rates = load()
products = products.sort_values("category", key=lambda c: c.map({k: i for i, k in enumerate(CATEGORY_STYLE)}).fillna(99),
                                kind="stable")
pmap = products.set_index("ir")
CATEGORIES = [c for c in CATEGORY_STYLE if c in set(products["category"])]


def product_label(ir: str) -> str:
    return f"{CATEGORY_STYLE.get(pmap.at[ir, 'category'], ('📦',))[0]}  {pmap.at[ir, 'name']}"


def add_product():
    ir = st.session_state.get("add")
    if ir and ir not in st.session_state.setdefault("cart", []):
        st.session_state["cart"].append(ir)
    st.session_state["add"] = None


def remove_product(ir: str):
    st.session_state["cart"] = [i for i in st.session_state.get("cart", []) if i != ir]
    st.session_state.pop(f"q_{ir}", None)


left, right = st.columns([1.5, 1], gap="large")

# ---------- step 1: products ----------

with left:
    step(1, "Pilih produk")
    picked = st.session_state.get("cats") or CATEGORIES
    c_filter, c_search = st.columns([1, 2.8], vertical_alignment="bottom")
    with c_filter.popover("Semua kategori" if len(picked) == len(CATEGORIES) else f"{len(picked)} kategori",
                          icon=":material/filter_list:", width="stretch"):
        st.pills("Kategori", CATEGORIES, format_func=lambda c: f"{CATEGORY_STYLE[c][0]} {c}", selection_mode="multi",
                 default=CATEGORIES, key="cats")
        st.caption("Semua kategori aktif secara default. Klik untuk menyaring.")
    chosen = [ir for ir in dict.fromkeys(st.session_state.get("cart", [])) if ir in pmap.index]
    pool = products[products["category"].isin(picked) & ~products["ir"].isin(chosen)]
    c_search.selectbox("Cari produk", pool["ir"].tolist(), format_func=product_label, index=None, key="add",
                       on_change=add_product, placeholder="Cari & tambah produk…", label_visibility="collapsed")
    saved = st.session_state.get("qty", {})
    qty = {}

    if chosen:
        with st.container(key="cart"):
            for ir in chosen:
                st.session_state.setdefault(f"q_{ir}", saved.get(ir, 1))
                unit_kg = float(pmap.at[ir, "weight_kg"])
                with st.container(key=f"line_{ir}"):
                    c_del, c_qty, c_img, c_name = st.columns([1, 3, 1, 6], vertical_alignment="center", gap="small")
                    c_img.markdown(f'<img class="pthumb" src="{thumb(ir, pmap.at[ir, "category"])}" alt="">',
                                   unsafe_allow_html=True)
                    n = c_qty.number_input("Jumlah", min_value=0, step=1, key=f"q_{ir}", label_visibility="collapsed")
                    c_name.markdown(f'<div class="pname">{html.escape(pmap.at[ir, "name"])}</div>'
                                    f'<div class="pmeta">{kg(unit_kg)} × {num(n)} = <b>{kg(unit_kg * n)}</b></div>',
                                    unsafe_allow_html=True)
                    c_del.button("", icon=":material/delete:", key=f"del_{ir}", type="tertiary",
                                 help="Keluarkan produk", on_click=remove_product, args=(ir,))
                qty[ir] = int(n)
        st.markdown('<div class="help">Atur jumlah dengan tombol <b>−</b> / <b>+</b> atau ketik langsung.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty slim">Cari produk di atas, lalu atur jumlahnya di daftar yang muncul.</div>',
                    unsafe_allow_html=True)
    st.session_state["qty"] = qty
    total_kg = sum(n * float(pmap.at[ir, "weight_kg"]) for ir, n in qty.items())

    # ---------- step 2: route ----------

    step(2, "Tentukan rute")
    with st.container(key="route"):
        c1, c_arrow, c2 = st.columns([10, 1, 10], vertical_alignment="bottom", gap="small")
        origin = c1.selectbox(":material/warehouse: Asal · kab/kota", sorted(rates["origin_regency"].dropna().unique()),
                              index=None, placeholder="Pilih kota asal", key="origin")
        c_arrow.markdown('<div class="route-arrow">→</div>', unsafe_allow_html=True)
        from_origin = rates[rates["origin_regency"] == origin]
        destinations = {}
        for regency, g in from_origin.groupby("dest_regency"):
            districts = sorted(g["dest_district"].dropna().unique())
            for d in districts:
                destinations[f"{regency} · {d}"] = (regency, d)
            if not districts:
                destinations[f"{regency} · semua kecamatan"] = (regency, REGENCY_LEVEL)
        pick = c2.selectbox(":material/location_on: Tujuan · kab/kota & kecamatan", sorted(destinations), index=None,
                            disabled=origin is None, placeholder="Ketik kabupaten atau kecamatan", key="dest_pick")
        dest, district = destinations.get(pick, (None, None))
        to_dest = from_origin[from_origin["dest_regency"] == dest]
        if origin:
            st.markdown(f'<div class="route-meta">{num(len(destinations))} tujuan tersedia dari {html.escape(origin)}'
                        f' · {from_origin["logistic_vendor"].nunique()} vendor</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="route-meta">Pilih kota asal dulu, lalu ketik kabupaten atau kecamatan tujuan.</div>',
                        unsafe_allow_html=True)

# ---------- step 3: summary & recommendation ----------

opts = pd.DataFrame()
ready = bool(origin and dest and district) and total_kg > 0
if ready:
    route = to_dest[to_dest["dest_district"].isna() | (to_dest["dest_district"] == district)]
    opts = options(route, total_kg)
eligible = opts[opts["eligible"]] if not opts.empty else opts
loading_tons = math.ceil(total_kg / 1000) if total_kg > 0 else 0
loading_fee = loading_tons * LOADING_FEE_PER_TON

with right:
    with st.container(key="summary"):
        step(3, "Estimasi")
        st.markdown(
            f'<div class="total"><div><div class="l">Total berat</div><div class="v">{kg(total_kg)}</div></div>'
            f'<div><div class="l">Produk</div><div class="v">{len(qty)}</div></div>'
            f'<div><div class="l">Unit</div><div class="v">{num(sum(qty.values()))}</div></div></div>',
            unsafe_allow_html=True)

        if not ready:
            todo = "Cari dan pilih produk" if total_kg <= 0 else "Lengkapi kota asal dan tujuan"
            st.markdown(f'<div class="empty"><b>Belum ada estimasi</b>{todo} untuk melihat ongkos kirim termurah.</div>',
                        unsafe_allow_html=True)
        elif eligible.empty:
            st.markdown('<div class="empty"><b>Tarif belum tersedia</b>Belum ada armada di rute ini yang minimum '
                        'muatannya terpenuhi. Lihat opsi lain di bawah.</div>', unsafe_allow_html=True)
        else:
            best = eligible.iloc[0]
            place = dest if district == REGENCY_LEVEL else f"{district}, {dest}"
            if best["pricing_model"] == "PER_TRIP":
                scheme = f"Per trip · {rp(best['price_per_trip'])}"
                extra = f"<div><small>Sewa penuh</small>{rp(best['charter'])} · {int(best['trips'])}× trip</div>"
            else:
                scheme = f"Per kg · {rp(best['price_per_kg'])}"
                extra = f"<div><small>Per kg efektif</small>{rp(best['estimate'] / total_kg)}/kg</div>"
            flag = '<span class="badge join">*join route · bersyarat</span>' if best["join_route"] else ""
            join_note = (f'<div class="fine">*Join route: {rp(best["price_per_trip"])} ÷ {num(best["capacity_max_kg"])} kg × '
                         f'{kg(total_kg)}. Berlaku bila muatan digabung dengan kiriman lain di rute yang sama; '
                         f'kalau sewa satu truk penuh {rp(best["charter"])}.</div>') if best["join_route"] else ""
            st.markdown(f"""
<div class="waybill">
  <div class="head">
    <div class="eyebrow">Surat jalan estimasi · {kg(total_kg)}</div>
    <div class="route">{html.escape(origin)}<em>→</em>{html.escape(place)}</div>
  </div>
  <div class="body">
    <div class="badges"><span class="badge best">★ Termurah</span>{flag}</div>
    <div class="price">{rp(best['estimate'])}</div>
    <div class="grid">
      <div><small>Vendor</small>{html.escape(best['logistic_vendor'])}</div>
      <div><small>Armada</small>{FLEET_LABEL.get(best['fleet'], best['fleet'])} · {capacity(best)}</div>
      <div><small>Skema</small>{scheme}</div>
      {extra}
    </div>
    <div class="fee"><span>+ Biaya muat: {loading_tons} ton × {rp(LOADING_FEE_PER_TON)} = <b>{rp(loading_fee)}</b></span>
      <span>Total: {rp(best['estimate'])} + {rp(loading_fee)} = <b>{rp(best['estimate'] + loading_fee)}</b></span></div>
    {join_note}
  </div>
</div>
""", unsafe_allow_html=True)

# ---------- step 4: all options ----------

if not opts.empty:
    if not eligible.empty:
        rows = []
        for i, o in eligible.reset_index(drop=True).iterrows():
            tags = '<span class="tag join">*join route</span>' if o["join_route"] else ""
            if o["fits"]:
                tags += '<span class="tag fit">sesuai kapasitas</span>'
            charter = f"{rp(o['charter'])}<small>{int(o['trips'])}× trip</small>" if pd.notna(o["charter"]) else "—"
            rows.append(
                f'<tr class="{"best" if i == 0 else ""}"><td data-l="Vendor">{html.escape(o["logistic_vendor"])}</td>'
                f'<td data-l="Armada"><span>{FLEET_LABEL.get(o["fleet"], o["fleet"])}<small>{capacity(o)}</small></span></td>'
                f'<td data-l="Tarif" class="r">{tariff(o)}</td>'
                f'<td data-l="Estimasi" class="r"><span>{rp(o["estimate"])}<small>+ muat {rp(o["estimate"] + loading_fee)}</small></span></td>'
                f'<td data-l="Sewa penuh" class="r"><span>{charter}</span></td>'
                f'<td data-l="Catatan"><span class="tags">{tags or "—"}</span></td></tr>')
        step(4, f"Semua opsi ({len(eligible)})")
        st.markdown('<table class="alt"><thead><tr><th>Vendor</th><th>Armada · kapasitas</th><th class="r">Tarif</th>'
                    '<th class="r">Estimasi</th><th class="r">Sewa penuh</th><th>Catatan</th></tr></thead><tbody>'
                    + "".join(rows) + "</tbody></table>", unsafe_allow_html=True)
        st.markdown(f'<div class="fine">*Join route = tarif per trip ÷ kapasitas maksimum × berat kiriman (muatan digabung '
                    f'dengan kiriman lain). "+ muat" menambahkan potensi biaya muat {rp(LOADING_FEE_PER_TON)} per ton '
                    f'(dibulatkan ke atas).</div>', unsafe_allow_html=True)

    below = opts[~opts["eligible"]].sort_values(["lo", "minimum"])
    if not below.empty:
        with st.expander(f"Lihat {len(below)} opsi lain · minimum muatan belum terpenuhi", icon=":material/visibility:"):
            rows = "".join(
                f'<tr><td data-l="Vendor">{html.escape(o["logistic_vendor"])}</td>'
                f'<td data-l="Armada"><span>{FLEET_LABEL.get(o["fleet"], o["fleet"])}<small>{capacity(o)}</small></span></td>'
                f'<td data-l="Tarif" class="r">{tariff(o)}</td>'
                f'<td data-l="Min. muatan" class="r"><span>{num(o["lo"])} kg<small>kurang {kg(o["lo"] - total_kg)}</small></span></td>'
                f'<td data-l="Biaya minimum" class="r">{rp(o["minimum"])}</td></tr>'
                for _, o in below.iterrows())
            st.markdown('<table class="alt"><thead><tr><th>Vendor</th><th>Armada · kapasitas</th><th class="r">Tarif</th>'
                        '<th class="r">Min. muatan</th><th class="r">Biaya minimum</th></tr></thead><tbody>'
                        + rows + "</tbody></table>", unsafe_allow_html=True)

st.markdown('<div class="foot">Sumber: Master Tarif Logistik (PKS + ODOO Current Vendor Cost), 29 Sep 2026. '
            'Estimasi belum termasuk biaya inap atau multi drop.</div>', unsafe_allow_html=True)
