"""Step 22: build out/inspectie_extra.json (extra Inspectie van het Onderwijs open data, per BRIN6).

All four sources carry DCTERMS.rights = "CC0 1.0 Universal" in the page metadata (checked 2026-11-20). These numbers are
context for a profile or the compare view only: no sort key, no filter, no ranking.

Per BRIN6 (all keys optional):
  lr  PO leerresultaten, doorstroomtoets 2024, 2025 and 2026 pooled by the Inspectie:
      [avg 1F %, avg 1S/2F %, pupils over 3 years, signaleringswaarde 1F, signaleringswaarde 1S/2F, outcome 1F, outcome 1S/2F]
      outcome: 1 above the signaleringswaarde, 0 below it, 2 small school (judged over five years), 3 too little data.
      The Inspectie file holds one row per object van toezicht (OVT = cluster of one or more locations); every location of
      the OVT gets the row. The signaleringswaarde depends on the schoolweging (below).
  sw  PO schoolweging, 3-year mean of the CBS values 2022/23 to 2024/25 (higher = more pupils whose parents have little
      education or other CBS risk factors). Same OVT rule.
  sv  schorsingen en verwijderingen 2025/26 (1 Aug 2025 to 31 Jul 2026), counts reported to the Inspectie:
      [suspensions longer than a day, removals | null, locations in the unit]. Removals are only reported for VO (null for
      PO and SO). The unit is the OVT: PO cluster, SO onderwijskundige eenheid, VO onderwijssoort within a vestiging (summed
      per vestiging here). Not listed = nothing in the Inspectie file.
  ex  Excellente school predicaat: [year the predicaat ran until, school year range, (VO: afdelingen)], the latest entry in the
      Inspectie PDF "Excellente scholen 2020 tot 1 juli 2026". VO: the predicaat is per afdeling (listed). PO and SO rows
      apply to the OVT. The predicaat is no longer awarded; the last round ended on 1 July 2026.
"""
import datetime, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, RAW, write_json_atomic
from xlsx import read_ods

OORDELEN = "inspectie_oordelen_po_so_vo.ods"
LR_FILE = "inspectie_leerresultaten_po_2026.ods"
SW_FILE = "inspectie_schoolweging_po_2022-2025.ods"
SV_FILE = "inspectie_schorsingen_2025-2026.ods"
EX_PDF, EX_TXT = "inspectie_excellente_scholen_2026.pdf", "inspectie_excellente_scholen_2026.txt"
OUTCOME = {"boven de signaleringswaarde": 1, "onder de signaleringswaarde": 0,
           "kleine school - beoordeling over 5 jaar": 2, "te weinig gegevens": 3}


def fl(v):
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def to_int(v):
    v = str(v).strip()
    return int(v) if v.isdigit() else None


def ovt_key(s):
    return re.sub(r"\s+", "", s or "").upper().replace("-", "|", 1) if "|" not in (s or "") else re.sub(r"\s+", "", s).upper()


def excellent():
    """{OVT key or BRIN|vestiging: (valid until year, schoolyear range)} from the PDF text (pdftotext, poppler)."""
    txt = os.path.join(RAW, EX_TXT)
    pdf = os.path.join(RAW, EX_PDF)
    if not os.path.exists(txt):
        exe = shutil.which("pdftotext")
        if not exe or not os.path.exists(pdf):
            print("excellent schools: pdftotext or PDF missing, skipped")
            return {}
        subprocess.run([exe, "-layout", "-enc", "UTF-8", pdf, txt], check=True)
    out, cur = {}, None
    for line in open(txt, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*Predicaat Excellente School geldig tot 1 juli (\d{4}) \(schooljaar (\d{4}/\d{2,4})\)", line)
        if m:
            cur = (int(m.group(1)), m.group(2))
            continue
        m = re.match(r"\s*([0-9][0-9A-Z]{3})\s*[|-]\s*([0-9A-Z]+(?:\s?[0-9]+)?(?:\|[A-Z]+)?)\s{2,}", line)
        if m and cur:
            key = ovt_key(m.group(1) + "|" + m.group(2))
            afd = line.split()[-1].lower() if re.fullmatch(r"[0-9A-Z]{4}\|[0-9]{2}", key) else None
            if key not in out or out[key][0] < cur[0]:
                out[key] = [cur[0], cur[1], [afd] if afd else []]
            elif out[key][0] == cur[0] and afd and afd not in out[key][2]:
                out[key][2].append(afd)
    return out


def main():
    ids = set()
    for n in ("schools_po.json", "schools_so.json", "schools_vo.json"):
        ids |= {r[0] for r in json.load(open(os.path.join(OUT, n), encoding="utf-8"))["rows"]}
    # OVT -> locations (Inspectie oordelen file, BetrokkenVestigingen)
    rows = next(iter(read_ods(os.path.join(RAW, OORDELEN)).values()))
    hdr = rows[0]
    members = {}
    for raw in rows[1:]:
        r = dict(zip(hdr, raw + [""] * (len(hdr) - len(raw))))
        if r["Sector"] not in ("PO", "SO", "VO"):
            continue
        vs = [v.strip().replace("|", "") for v in r["BetrokkenVestigingen"].split(",") if v.strip()]
        members.setdefault(ovt_key(r["OVT"]), set()).update(v for v in vs if v in ids)
    sch = {}

    def put(i, k, v):
        sch.setdefault(i, {})[k] = v

    # leerresultaten PO
    lr = next(r for n, r in read_ods(os.path.join(RAW, LR_FILE)).items() if n == "Data")
    h = lr[0]
    col = {n: k for k, n in enumerate(h)}
    n_lr = 0
    for r in lr[1:]:
        r = r + [""] * (len(h) - len(r))
        mem = members.get(ovt_key(r[0]), set())
        if not mem:
            continue
        rec = [fl(r[col["Gewogen driejaarsgemiddelde %1F"]]), fl(r[col["Gewogen driejaarsgemiddelde %1S/2F"]]),
               to_int(r[col["Totaal aantal leerlingen 3 jaar"]]), fl(r[col["Signaleringswaarde 1F"]]),
               fl(r[col["Signaleringswaarde 1S/2F"]]), OUTCOME.get(r[col["Uitkomst indicator 1F"]].strip().lower()),
               OUTCOME.get(r[col["Uitkomst indicator 1S/2F"]].strip().lower())]
        if rec[5] is None and rec[6] is None:
            continue
        n_lr += 1
        for i in mem:
            put(i, "lr", rec)
    # schoolweging PO (3-year mean)
    sw = read_ods(os.path.join(RAW, SW_FILE))["Driejaarsgemiddelde"]
    n_sw = 0
    for r in sw[1:]:
        v = fl(r[3]) if len(r) > 3 else None
        mem = members.get(ovt_key(r[0]), set()) if r else set()
        if v is not None and mem and 0 < v < 100:
            n_sw += 1
            for i in mem:
                put(i, "sw", round(v, 2))
    # schorsingen en verwijderingen
    sv = read_ods(os.path.join(RAW, SV_FILE))["Sheet2"]
    unit = {}
    for r in sv[1:]:
        if len(r) < 9:
            continue
        s_, v_ = to_int(r[6]), to_int(r[7])
        if s_ is None or v_ is None:
            continue
        sector = r[2].strip()
        key = ovt_key(r[4])
        mem = members.get(key, set())
        if sector == "VO":                    # vestiging + onderwijssoort: sum per vestiging
            mem = {key.replace("|", "")} & ids
        a = unit.setdefault((sector, key), [0, 0, mem])
        a[0] += s_
        a[1] += v_
    n_sv = 0
    for (sector, key), (s_, v_, mem) in unit.items():
        for i in mem:
            if sector == "VO":
                cur = sch.get(i, {}).get("sv")
                if cur:
                    cur[0] += s_
                    cur[1] += v_
                else:
                    put(i, "sv", [s_, v_, 1])
            else:
                put(i, "sv", [s_, None, len(mem)])
        n_sv += 1 if mem else 0
    # excellent schools
    ex = excellent()
    n_ex = 0
    for key, (until, rng, afd) in ex.items():
        mem = members.get(key, set())
        if not mem and re.fullmatch(r"[0-9A-Z]{4}\|[0-9]{2}", key):
            mem = {key.replace("|", "")} & ids
        for i in mem:
            put(i, "ex", [until, rng] + ([sorted(afd)] if afd else []))
        n_ex += 1 if mem else 0
    out = {"v": 1, "generated": datetime.date.today().isoformat(),
           "years": {"lr": "2023/24, 2024/25 and 2025/26 (doorstroomtoets 2024, 2025, 2026)", "sw": "2022/23 to 2024/25",
                     "sv": "2025-2026", "ex": "round 2023 to 2026, valid until 1 July 2026"},
           "counts": {"lr_ovt": n_lr, "sw_ovt": n_sw, "sv_units": n_sv, "ex_units": n_ex, "ex_listed": len(ex)},
           "schools": dict(sorted(sch.items()))}
    write_json_atomic(os.path.join(OUT, "inspectie_extra.json"), out)
    print("inspectie_extra.json schools:", len(sch), "|", out["counts"])


if __name__ == "__main__":
    main()
