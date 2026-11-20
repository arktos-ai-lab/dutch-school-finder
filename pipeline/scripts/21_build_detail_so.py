"""Step 21: build out/detail_so.json (per-school detail for special education SO/VSO, keyed by BRIN6).

Fields per BRIN6:
  ag  pupils per age, 1 October 2025, per type: {"So": [first index, [cells]], "Vso": [...]}; index 0 = "under 4",
      1..21 = age 4..24, 22 = "over 24" (duo.AGE_LABELS); null cell = suppressed (<5); leading and trailing zeros cut.
      Source: DUO "leerlingen po naar soort po, cluster en leeftijd" 2025-2026 (raw/so_leerlingen_2025-2026.csv).
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, SO_PUPIL_FILE, write_json_atomic
import duo


def main():
    so = json.load(open(os.path.join(OUT, "schools_so.json"), encoding="utf-8"))
    ids = {r[0] for r in so["rows"]}
    det = {}
    for r in duo.read_csv_auto(SO_PUPIL_FILE):
        kind = r["SOORT_PO"].strip()
        i = r["INSTELLINGSCODE"].strip() + r["VESTIGINGSCODE"].strip()
        if kind not in ("So", "Vso") or i not in ids:
            continue
        a = duo.age_series(r)
        if a:
            det.setdefault(i, {}).setdefault("ag", {})[kind] = a
    out = {"v": 1, "generated": datetime.date.today().isoformat(),
           "years": {"pupils": "2025-2026", "ages": "2025-2026"}, "schools": dict(sorted(det.items()))}
    write_json_atomic(os.path.join(OUT, "detail_so.json"), out)
    print("detail_so.json schools:", len(det), "of", len(ids))


if __name__ == "__main__":
    main()
