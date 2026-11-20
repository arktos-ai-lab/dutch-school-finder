"""Step 20: build out/extra.json (contact, board, samenwerkingsverband, holiday region, staff at institution level,
VSO leavers per SWV, school holidays). One lazily loaded file for every profile and compare view.

  schools[BRIN6] = [tel, bg, swv, swvx, vr]
      tel  telephone number of the vestiging (DUO address file TELEFOONNUMMER; public institutional data), or null
      bg   bevoegd gezag number (DUO), or null; boards[bg] = [name, number of locations in this site's school files]
      swv  samenwerkingsverband code. BO/SBO: DUO "leerlingen bo per vestiging" (SWV_VESTIGING, PO codes); VO: DUO pupils per
           vestiging (VO codes). VSO locations: the VO SWV that all VO schools in the same municipality share (null when the
           municipality is split between SWVs or has no VO school), swvx = 1 marks this derived value. SO-only: null.
      vr   vakantieregio index into `regions` (DUO address file VAKANTIEREGIO), or -1
  swv[code] = [name | null, uitstroom | null]
      name: only VO SWVs have a name in the open files (from the DUO VSO uitstroom file); PO SWV codes have none.
      uitstroom (VSO leavers 2025/26, regional): [dagbesteding, arbeidsmarkt, vervolgonderwijs, onbekend] with null = "<5".
      The DUO total column is not used (it would let a reader recover a suppressed cell by subtraction).
  fm[BRIN4] = [year, fte_total, fte_management, fte_teaching, fte_support, pupils_per_teacher_fte | null]
      DUO functiemix instellingen, latest year per institution; school group level, not per location.
  holidays[schoolyear] = [[key, compulsory(0/1), [[start, end] noord, midden, zuid]]] (Rijksoverheid open data, CC0)
"""
import datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, RAW, write_json_atomic
import duo

REGIONS = ["noord", "midden", "zuid"]
HOL_KEYS = {"herfstvakantie": "autumn", "kerstvakantie": "christmas", "voorjaarsvakantie": "spring",
            "meivakantie": "may", "zomervakantie": "summer"}
HOL_YEARS = ["2025-2026", "2026-2027", "2027-2028"]
TEL_RE = re.compile(r"^\+?[0-9][0-9 ()\-]{5,18}[0-9]$")


def num(v, kind=float):
    try:
        return kind(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def cell(v):
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


def holidays():
    out, lic = {}, None
    for y in HOL_YEARS:
        p = os.path.join(RAW, "schoolvakanties_%s.json" % y)
        if not os.path.exists(p):
            continue
        j = json.load(open(p, encoding="utf-8"))
        lic = j.get("license")
        if lic != "CC0 1.0 Universal":
            raise SystemExit("school holidays licence field changed: %r" % lic)
        rows = []
        for v in j["content"][0]["vacations"]:
            key = HOL_KEYS.get(re.sub(r"\s+", " ", v["type"]).strip().lower())
            if not key:
                continue
            by = {}
            for r in v["regions"]:
                # UTC timestamps: start 00:00Z and end 21:59Z or 22:59Z are the Dutch calendar dates of the UTC date
                rng = [r["startdate"][:10], r["enddate"][:10]]
                if r["region"].strip().lower() == "heel nederland":
                    by = {g: rng for g in REGIONS}
                else:
                    by[r["region"].strip().lower()] = rng
            if all(g in by for g in REGIONS):
                rows.append([key, 1 if v.get("compulsorydates") == "true" else 0, [by[g] for g in REGIONS]])
        if rows:
            out[y] = rows
    return out, lic


def main():
    po, so, vo = duo.load_po_schools(), duo.load_so_schools(), duo.load_vo_schools()
    allsch = po + so + vo
    ids = {s["id"] for s in allsch}

    # boards: name from the DUO besturen files, size = locations in our school files
    names = {}
    for f in ("duo_besturen_bo.csv", "duo_besturen_so.csv", "duo_besturen_vo.csv"):
        for r in duo.read_csv_auto(f, ","):
            n, nm = r["BEVOEGD GEZAG NUMMER"].strip(), r["BEVOEGD GEZAG NAAM"].strip()
            if n and nm:
                names.setdefault(n, nm)
    size = {}
    for s in allsch:
        if s["bg"]:
            size[s["bg"]] = size.get(s["bg"], 0) + 1
    boards = {b: [names.get(b), n] for b, n in sorted(size.items()) if names.get(b)}

    # samenwerkingsverband per vestiging
    swv_of = {}
    for r in duo.read_csv_auto("bo_leerlingen_2025-2026.csv"):
        c = r["SWV_VESTIGING"].strip()
        if c:
            swv_of[r["INSTELLINGSCODE"].strip() + r["VESTIGINGSCODE"].strip()] = c
    vo_swv = {}
    for r in duo.read_csv_auto("vo_leerlingen_2025.csv"):
        c = r["SAMENWERKINGSVERBAND PASSEND ONDERWIJS VO"].strip()
        if c:
            vo_swv[r["INSTELLINGSCODE"].strip() + r["VESTIGINGSCODE"].strip()] = c
    swv_of.update(vo_swv)
    muni = {}
    for s in vo:
        if s["id"] in vo_swv and s["gemnr"]:
            muni.setdefault(s["gemnr"], set()).add(vo_swv[s["id"]])
    derived = {}
    for s in so:
        if s["so_type"] != "SO" and s["gemnr"] and len(muni.get(s["gemnr"], ())) == 1:
            derived[s["id"]] = next(iter(muni[s["gemnr"]]))

    # VSO leavers per SWV (regional) and the VO SWV names
    swv = {}
    for r in duo.read_csv_auto("vso_uitstroom_2025-2026.csv"):
        c = r["SWV_VESTIGING"].strip()
        if c:
            swv[c] = [r["NAAM_SAMENWERKINGSVERBAND"].strip() or None,
                      [cell(r["UITSTROOM_" + k]) for k in ("DAGBESTEDING", "ARBEIDSMARKT", "VERVOLGONDERWIJS", "ONBEKEND")]]

    schools = {}
    for s in allsch:
        tel = s["tel"] if TEL_RE.match(s["tel"]) else None
        sw, sx = swv_of.get(s["id"]), 0
        if sw is None and s["id"] in derived:
            sw, sx = derived[s["id"]], 1
        vr = REGIONS.index(s["vr"]) if s["vr"] in REGIONS else -1
        bg = s["bg"] if s["bg"] in boards else None
        if sw and sw not in swv:
            swv[sw] = [None, None]
        if tel or bg or sw or vr >= 0:
            schools[s["id"]] = [tel, bg, sw, sx, vr]
    used = {v[2] for v in schools.values() if v[2]}
    swv = {k: v for k, v in sorted(swv.items()) if k in used}

    # staff composition per institution (functiemix), latest year per BRIN4
    fm, years = {}, {}
    inst = {i[:4] for i in ids}
    for r in duo.read_csv_auto("duo_functiemix_instellingen.csv", ","):
        b = r["BRIN_NUMMER"].strip()
        y = num(r["JAAR"], int)
        if b not in inst or y is None or y < years.get(b, 0):
            continue
        tot = num(r["OMVANG_FORMATIE_TOTAAL"])
        if tot is None or tot <= 0:
            continue
        ratio = num(r["LEERLING_LERAAR_RATIO"])
        fm[b] = [y, round(tot, 1), round(num(r["OMVANG_FORMATIE_MANAGER"]) or 0, 1), round(num(r["OMVANG_FORMATIE_OP"]) or 0, 1),
                 round(num(r["OMVANG_FORMATIE_OOP_OBP"]) or 0, 1), round(ratio, 1) if ratio and ratio > 0 else None]
        years[b] = y
    hol, lic = holidays()
    out = {"v": 1, "generated": datetime.date.today().isoformat(),
           "years": {"swv_uitstroom": "2025-2026", "fm": sorted(set(years.values()))[-1] if years else None, "holidays": sorted(hol)},
           "regions": REGIONS, "schools": dict(sorted(schools.items())), "boards": boards, "swv": swv, "fm": dict(sorted(fm.items())),
           "holidays": hol, "holidays_licence": lic}
    write_json_atomic(os.path.join(OUT, "extra.json"), out)
    print("extra.json schools:", len(schools), "of", len(ids), "| boards", len(boards), "| swv", len(swv),
          "| derived VSO swv", sum(1 for v in schools.values() if v[3]), "| fm", len(fm), "| holiday years", sorted(hol))


if __name__ == "__main__":
    main()
