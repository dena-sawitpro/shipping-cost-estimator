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


def total_kg(at) -> str:
    return re.search(r'Total berat</div><div class="v">([^<]+)', " ".join(m.value for m in at.markdown)).group(1)


at = AppTest.from_file("app.py", default_timeout=60)
at.session_state["cart"] = ["10101600", "10300100"]
at.run()
assert total_kg(at) == "51 kg", total_kg(at)
at.number_input(key="q_10101600").increment().run()
assert total_kg(at) == "101 kg", total_kg(at)
at.button(key="del_10101600").click().run()
assert at.session_state["cart"] == ["10300100"] and total_kg(at) == "1 kg", total_kg(at)
assert not at.exception, at.exception
print("\nstepper + delete: ok")

at = AppTest.from_file("app.py", default_timeout=60).run()
everything = len(at.selectbox(key="add").options)
at.session_state["cats"] = ["Herbisida"]
at.run()
herbicides = len(at.selectbox(key="add").options)
at.session_state["cats"] = []
at.run()
assert 0 < herbicides < everything == len(at.selectbox(key="add").options), (herbicides, everything)
print(f"category filter: all {everything} -> Herbisida {herbicides} -> reset {everything}: ok")

at = AppTest.from_file("app.py", default_timeout=60)
at.session_state["calc_mode"] = "berat"
at.session_state["direct_kg"] = 2500.0
at.run()
assert not at.exception, at.exception
assert total_kg(at) == "2.500 kg", total_kg(at)
assert "Langsung" in " ".join(m.value for m in at.markdown)
at.selectbox(key="origin").select("Kota Dumai").run()
at.selectbox(key="dest_pick").select("Kab. Kampar · Bangkinang").run()
priced = re.search(r'class="price">([^<]+)', " ".join(m.value for m in at.markdown))
assert priced, "direct weight produced no estimate"
print(f"direct weight 2.500 kg -> {priced.group(1)}: ok")

