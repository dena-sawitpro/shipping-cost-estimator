"""Headless end-to-end check: python test_app.py"""
import re

from streamlit.testing.v1 import AppTest


def scenario(label: str, qty: dict, origin: str, dest: str):
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["cart"] = list(qty)
    at.session_state["qty"] = dict(qty)
    at.run()
    at.selectbox(key="origin").select(origin).run()
    at.selectbox(key="dest_pick").select(dest).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    total = re.search(r'Total berat</div><div class="v">([^<]+)', text).group(1)
    best = re.search(r'class="price">([^<]+)', text)
    fee = re.search(r'class="fee">(.*?)</div>', text, re.S)
    print(f"\n{label} | {origin} -> {dest} | total {total} | best {best and best.group(1)}")
    print("   fee:", fee and re.sub(r"<[^>]+>|\s+", " ", fee.group(1)).strip())
    for r in re.findall(r"<tr class=\"(?:best)?\">(.*?)</tr>", text)[:4]:
        print("  ", re.sub(r"<[^>]+>", " | ", r).replace(" |  | ", " | ")[:170])


scenario("MOP Canada x200", {"10101600": 200}, "Kota Dumai", "Kab. Kampar · Bangkinang")
scenario("MOP Canada x2 (100 kg)", {"10101600": 2}, "Kota Dumai", "Kab. Kampar · Bangkinang")
scenario("Bablass 1L x40", {"10300100": 40}, "Kota Pekanbaru", "Kab. Siak · Siak")
scenario("MOP Canada x700", {"10101600": 700}, "Kota Dumai", "Kab. Batanghari · semua kecamatan")

