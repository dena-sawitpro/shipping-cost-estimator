"""Headless end-to-end check: python test_app.py"""
import re

from streamlit.testing.v1 import AppTest


def scenario(product: str, qty: int, origin: str, dest: str, district: str):
    at = AppTest.from_file("app.py", default_timeout=60).run()
    ms = at.multiselect(key="chosen")
    ir = next(v for v, lab in zip(ms.options, ms.options) if product in lab)
    at.multiselect(key="chosen").select(ir).run()
    at.number_input[0].set_value(qty).run()
    at.selectbox[0].select(origin).run()
    at.selectbox[1].select(dest).run()
    at.selectbox[2].select(district).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    total = re.search(r'Total berat</div><div class="v">([^<]+)', text).group(1)
    best = re.search(r'class="price">([^<]+)', text)
    rows = re.findall(r"<tr class=\"(best)?\">(.*?)</tr>", text)
    print(f"\n{product} x{qty} | {origin} -> {district}, {dest} | total {total} | best {best and best.group(1)}")
    for _, r in rows[:6]:
        print("  ", re.sub(r"<[^>]+>", " | ", r).replace(" |  | ", " | ")[:170])


scenario("Canada Cap Mahkota", 200, "Kota Dumai", "Kab. Kampar", "Bangkinang")
scenario("Bablass 490 SL - 1 Liter", 40, "Kota Pekanbaru", "Kab. Siak", "Siak")
scenario("Canada Cap Mahkota", 700, "Kota Dumai", "Kab. Batanghari", "Semua kecamatan (tarif tingkat kab/kota)")
