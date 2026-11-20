"""Step 9: sanity checks and coverage report (prints; no files written)."""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT

SPOT = [  # (file, name substring, city substring) - eyeball coordinates and tracks
    ("vo", "Vossius", "Amsterdam"), ("vo", "Stedelijk Gymnasium", "Utrecht"),
    ("vo", "Praedinius", "Groningen"), ("vo", "Bonnefanten", "Maastricht"),
    ("vo", "Maartens", "Maastricht"), ("po", "Maasparel", "Stevensweert"),
]


def load(n):
    with open(os.path.join(OUT, n), encoding="utf-8") as f:
        return json.load(f)


def rec(d, r):
    return dict(zip(d["cols"], r))


def km(a, b, c, d):
    return math.hypot((a - c) * 111.2, (b - d) * 68.0)


def pct(a, b):
    return "%d/%d (%.1f%%)" % (a, b, 100.0 * a / b) if b else "0/0"


def check_detail():
    """Coverage and consistency checks for detail_po / detail_vo / inspection. Raises SystemExit on a hard failure."""
    errs = []
    po, vo = load("schools_po.json"), load("schools_vo.json")
    ids_po, ids_vo = {r[0] for r in po["rows"]}, {r[0] for r in vo["rows"]}
    dp, dv, ins = load("detail_po.json"), load("detail_vo.json"), load("inspection.json")
    so = load("schools_so.json")
    rs = [rec(so, r) for r in so["rows"]]
    ids_so = {r["id"] for r in rs}
    print("\n==== schools_so.json: %d rows | type %s | cluster %s" % (
        len(rs), dict(collections.Counter(r["so_type"] for r in rs)), dict(collections.Counter(r["cl"] for r in rs))))
    print("  geo %s | with pupils %s | with website %s" % (
        dict(collections.Counter(r["g"] for r in rs)), pct(sum(1 for r in rs if r["pupils"] is not None), len(rs)),
        pct(sum(1 for r in rs if r["web"]), len(rs))))
    if len(ids_so) != len(rs) or ids_so & ids_po:
        errs.append("schools_so ids not unique / overlap with schools_po")
    for r in rs:
        if r["so_type"] not in ("SO", "VSO", "SO/VSO") or r["cl"] not in (1, 2, 3, 4, None):
            errs.append("so invalid type/cluster " + r["id"])
        if r["lat"] is not None and not (50.7 < r["lat"] < 53.7 and 3.2 < r["lon"] < 7.3):
            errs.append("so outside NL " + r["id"])
        if r["pupils"] is not None and r["pupils"] < 0:
            errs.append("so pupils invalid " + r["id"])
    print("\n==== detail_po.json (%d schools with data of %d)" % (len(dp["schools"]), len(ids_po)))
    S = dp["schools"]
    for f in ("pt", "es", "dm", "at", "lj", "rn", "hv"):
        print("  %-3s %s" % (f, pct(sum(1 for d in S.values() if f in d), len(ids_po))))
    print("  pt with a 2025 value: %s" % pct(sum(1 for d in S.values() if any(x[0] == 2025 and x[1] is not None for x in d.get("pt", []))), len(ids_po)))
    for i, d in S.items():
        if i not in ids_po:
            errs.append("detail_po id not in schools_po: " + i)
        for t, avg, n in d.get("es", []):
            if n is None or n < 5 or avg is None:
                errs.append("es below 5 or null " + i)
        if "dm" in d and (d["dm"][2] < 5 or d["dm"][0] < 0):
            errs.append("dm invalid " + i)
        for y, n, s_, sh in d.get("at", []):
            if sh is not None and abs(sum(x for x in sh if x is not None) - 100) > 0.6:
                errs.append("advice shares not 100 %s %s" % (i, y))
        for k, (p1, p2, n) in d.get("rn", {}).items():
            if n < 5 or any(x is not None and not 0 <= x <= 100 for x in (p1, p2)) or (p1 is not None and p2 is not None and p2 > p1 + 0.05):
                errs.append("rn invalid %s %s" % (i, k))
        if "hv" in d and (d["hv"][2] < 5 or any(x is not None and x < 0 for x in d["hv"])):
            errs.append("hv invalid " + i)
        if "lj" in d and (len(d["lj"]) != 8 or any(x is not None and (x < 0 or 1 <= x <= 4) for x in d["lj"])):
            errs.append("lj invalid " + i)
    print("\n==== detail_vo.json (%d schools with data of %d)" % (len(dv["schools"]), len(ids_vo)))
    V = dv["schools"]
    for f in ("pt", "tp", "pr", "cm", "ce", "zb", "ov", "op"):
        print("  %-3s %s" % (f, pct(sum(1 for d in V.values() if f in d), len(ids_vo))))
    for i, d in V.items():
        if i not in ids_vo:
            errs.append("detail_vo id not in schools_vo: " + i)
        for lab, lst in d.get("pr", {}).items():
            for pr_ in lst:
                if (pr_[1] is None) != (pr_[2] is None) or (pr_[1] is not None and (pr_[1] < 5 or not 0 <= pr_[2] <= 100)):
                    errs.append("pr invalid %s %s %s" % (i, lab, pr_))
        for lab, lst in d.get("ce", {}).items():
            for y, m_, n, *_ in lst:
                if n < 5 or not 1.0 <= m_ <= 10.0:
                    errs.append("ce invalid %s %s %s" % (i, lab, [y, m_, n]))
        if "zb" in d and (d["zb"][0] is None or d["zb"][0] < 5):
            errs.append("zb invalid " + i)
        for pc4_, n, *_ in d.get("cm", []):
            if n < 5:
                errs.append("cm below 5 " + i)
    print("\n==== inspection.json: %d schools, as_of %s, licence %s" % (len(ins["schools"]), ins["as_of"], ins["licence"]))
    RATED = ("Goed", "Voldoende", "Onvoldoende", "Zwak", "Zeer zwak")
    allids = len(ids_po) + len(ids_so) + len(ids_vo)
    print("  listed schools: %s | counts %s" % (pct(len(ins["schools"]), allids), ins["counts"]))
    rated = {i: s for i, s in ins["schools"].items() if s["o"] in RATED}
    print("  rated: %s | with standards st/xs: %s | with bestuur b: %s" % (
        pct(len(rated), allids), pct(sum(1 for s in rated.values() if "st" in s or "xs" in s), len(rated)),
        pct(sum(1 for s in ins["schools"].values() if "b" in s), len(ins["schools"]))))
    if ins["counts"]["rated"] != len(rated):
        errs.append("inspection counts.rated does not match")
    for i, s in ins["schools"].items():
        if i not in ids_po and i not in ids_vo and i not in ids_so:
            errs.append("inspection id unknown " + i)
        if s["o"] in RATED and not s.get("d"):
            errs.append("rated without date " + i)
        if s["o"] not in RATED and s["o"] not in ("Geen eindoordeel", "Basistoezicht"):
            errs.append("inspection unknown o %s %s" % (i, s["o"]))
        if s["o"] == "Geen eindoordeel" and ("d" in s or "st" in s):
            errs.append("unrated school with details " + i)
        for code in list(s.get("st", {})) + [c for v_ in s.get("xs", {}).values() for c in v_]:
            if code in ("OP0", "OP1", "OP2", "OP3", "OP4", "OP5", "OP6", "VS1", "VS2", "OR1", "OR2", "SKA1", "SKA2", "SKA3") and code not in ins["labels"]:
                errs.append("no label for " + code)
    print("\n---- detail spot checks")
    for f, nm, city in (("vo", "Vossius", "Amsterdam"), ("vo", "Stedelijk Gymnasium", "Utrecht"), ("po", "Maasparel", "Stevensweert")):
        d = load("schools_%s.json" % f)
        D = S if f == "po" else V
        hit = [rec(d, r) for r in d["rows"] if nm.lower() in r[1].lower() and city.lower() in (r[4] + r[5]).lower()]
        if not hit:
            errs.append("spot check school not found: " + nm)
        for r in hit[:1]:
            x = D.get(r["id"])
            print(" ", f, r["id"], r["name"], "->", json.dumps(x, separators=(",", ":"))[:700] if x else "NO DETAIL")
            if not x or "pt" not in x:
                errs.append("spot check without pt: " + nm)
            if f == "vo" and x and "pr" not in x:
                errs.append("spot check VO without pass rates: " + nm)
            if ins["schools"].get(r["id"]):
                print("    inspection:", ins["schools"][r["id"]])
    if len(S) < 0.9 * len(ids_po) or len(V) < 0.85 * len(ids_vo):
        errs.append("detail coverage too low")
    if errs:
        print("\nDETAIL CHECK FAILURES:", len(errs))
        for e in errs[:30]:
            print("  ", e)
        raise SystemExit(1)
    print("\ndetail checks OK")


def check_extra():
    """Coverage and consistency checks for the gap-closing files (detail_so, extra, inspectie_extra, context and the new
    detail_po / detail_vo keys). Raises SystemExit on a hard failure."""
    import re
    errs = []
    po, so, vo = load("schools_po.json"), load("schools_so.json"), load("schools_vo.json")
    ids_po, ids_so, ids_vo = ({r[0] for r in d["rows"]} for d in (po, so, vo))
    allids = ids_po | ids_so | ids_vo
    dvo_all = load("detail_vo.json")
    dp, dv, dso = load("detail_po.json")["schools"], dvo_all["schools"], load("detail_so.json")["schools"]
    ex, ie, cx = load("extra.json"), load("inspectie_extra.json"), load("context.json")
    PROF = dvo_all["years"]["profiles"]

    def ok_cell(c):
        if c is None:
            return True
        if isinstance(c, list):
            return len(c) == 2 and isinstance(c[0], int) and c[0] > 0 and c[1] == 1
        return isinstance(c, int) and c >= 0

    def ok_series(a):
        return (isinstance(a, list) and len(a) == 2 and isinstance(a[0], int) and 0 <= a[0] <= 22 and isinstance(a[1], list)
                and a[0] + len(a[1]) <= 23 and a[1] and a[1][0] != 0 and a[1][-1] != 0
                and all(c is None or (isinstance(c, int) and (c == 0 or c >= 5)) for c in a[1]))

    print("\n==== gap-closing files")
    print("  detail_po ag      %s" % pct(sum(1 for d in dp.values() if "ag" in d), len(ids_po)))
    print("  detail_so ag      %s" % pct(sum(1 for d in dso.values() if "ag" in d), len(ids_so)))
    for f in ("tj", "pf", "pp", "se", "cl"):
        print("  detail_vo %-2s     %s" % (f, pct(sum(1 for d in dv.values() if f in d), len(ids_vo))))
    for i, d in dp.items():
        if "ag" in d and not ok_series(d["ag"]):
            errs.append("po ag invalid " + i)
    for i, d in dso.items():
        if i not in ids_so:
            errs.append("detail_so id unknown " + i)
        for k, a in d.get("ag", {}).items():
            if k not in ("So", "Vso") or not ok_series(a):
                errs.append("so ag invalid %s %s" % (i, k))
    for i, d in dv.items():
        for lab, (first, cells) in d.get("tj", {}).items():
            if not 1 <= first <= 6 or first - 1 + len(cells) > 6 or not all(ok_cell(c) for c in cells):
                errs.append("tj invalid %s %s" % (i, lab))
        for lab, lst in d.get("pf", {}).items():
            for y, cells in lst:
                if len(cells) != len(PROF) or not all(ok_cell(c) for c in cells):
                    errs.append("pf invalid %s %s %s" % (i, lab, y))
        for lab, m in d.get("pp", {}).items():
            for pk, lst in m.items():
                for y, n, p_ in lst:
                    if pk not in PROF or n < 5 or not 0 <= p_ <= 100:
                        errs.append("pp invalid %s %s %s" % (i, lab, pk))
        for key in ("se", "cl"):
            for lab, lst in d.get(key, {}).items():
                for y, m_, n, *_ in lst:
                    if n < 5 or not 1.0 <= m_ <= 10.0:
                        errs.append("%s invalid %s %s" % (key, i, lab))

    S = ex["schools"]
    print("  extra schools     %s | tel %s | board %s | swv %s | vakantieregio %s" % (
        pct(len(S), len(allids)), pct(sum(1 for v in S.values() if v[0]), len(allids)), pct(sum(1 for v in S.values() if v[1]), len(allids)),
        pct(sum(1 for v in S.values() if v[2]), len(allids)), pct(sum(1 for v in S.values() if v[4] >= 0), len(allids))))
    tel_re = re.compile(r"^\+?[0-9][0-9 ()\-]{5,18}[0-9]$")
    for i, (tel, bg, sw, sx, vr) in S.items():
        if i not in allids:
            errs.append("extra id unknown " + i)
        if tel and not tel_re.match(tel):
            errs.append("tel invalid " + i)
        if bg and bg not in ex["boards"]:
            errs.append("board missing " + i)
        if sw and sw not in ex["swv"]:
            errs.append("swv missing " + i)
        if sx and (i not in ids_so or not sw or not sw.startswith("VO")):
            errs.append("derived swv only for VSO with a VO code " + i)
        if vr not in (-1, 0, 1, 2):
            errs.append("vr invalid " + i)
    nb = collections.Counter(v[1] for v in S.values() if v[1])
    for b, (nm, n) in ex["boards"].items():
        if not nm or n < nb.get(b, 0) or n < 1:
            errs.append("board size invalid " + b)
    for code, (nm, us) in ex["swv"].items():
        if us is not None and (len(us) != 4 or any(c is not None and (not isinstance(c, int) or 0 < c < 5) for c in us)):
            errs.append("uitstroom invalid " + code)
    for b, v in ex["fm"].items():
        if len(v) != 6 or v[1] <= 0 or any(x is not None and x < 0 for x in v[1:]) or v[3] > v[1] + 0.2:
            errs.append("fm invalid " + b)
    print("  extra fm          %d institutions (BRIN4) | uitstroom for %d swv | derived VSO swv %d | boards %d" % (
        len(ex["fm"]), sum(1 for v in ex["swv"].values() if v[1]), sum(1 for v in S.values() if v[3]), len(ex["boards"])))
    if len(S) < 0.95 * len(allids) or sum(1 for v in S.values() if v[4] >= 0) < 0.99 * len(allids):
        errs.append("extra coverage too low")
    if ex.get("holidays_licence") != "CC0 1.0 Universal":
        errs.append("holiday licence")
    for y, rows in ex["holidays"].items():
        for key, comp, rng in rows:
            for a, b in rng:
                if not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", a) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", b) and a <= b):
                    errs.append("holiday dates invalid %s %s" % (y, key))
        if {r[0] for r in rows} != {"autumn", "christmas", "spring", "may", "summer"}:
            errs.append("holiday set incomplete " + y)

    I = ie["schools"]
    c = collections.Counter(k for d in I.values() for k in d)
    print("  inspectie_extra   lr %s | sw %s | sv %d | ex %d (of %d listed)" % (
        pct(c["lr"], len(ids_po)), pct(c["sw"], len(ids_po)), c["sv"], c["ex"], ie["counts"]["ex_listed"]))
    for i, d in I.items():
        if i not in allids:
            errs.append("inspectie_extra id unknown " + i)
        if "lr" in d:
            a1, a2, n3, s1, s2, o1, o2 = d["lr"]
            if i not in ids_po or o1 not in (0, 1, 2, 3) or o2 not in (0, 1, 2, 3):
                errs.append("lr invalid " + i)
            for av, o in ((a1, o1), (a2, o2)):
                if o in (0, 1) and av is None:
                    errs.append("lr outcome without average " + i)
                if av is not None and not 0 <= av <= 100:
                    errs.append("lr range " + i)
            if n3 is not None and n3 < 5 and (o1 in (0, 1) or o2 in (0, 1)):
                errs.append("lr judged on fewer than 5 pupils " + i)
        if "sw" in d and not 0 < d["sw"] < 100:
            errs.append("sw range " + i)
        if "sv" in d:
            s_, v_, k = d["sv"]
            if s_ < 0 or (v_ is not None and v_ < 0) or k < 1 or (v_ is not None and i not in ids_vo):
                errs.append("sv invalid " + i)
        if "ex" in d and not (isinstance(d["ex"][0], int) and 2020 <= d["ex"][0] <= 2026):
            errs.append("ex invalid " + i)
    if c["lr"] < 0.85 * len(ids_po):
        errs.append("leerresultaten coverage too low")

    for grp, g in cx["pupils"].items():
        if not g["nat"] or g["nat"][2] < cx["min_n"] or len(g["prov"]) != len(cx["provinces"]):
            errs.append("context pupils " + grp)
        for pv in g["prov"]:
            if pv is not None and pv[2] < cx["min_n"]:
                errs.append("context province below min_n " + grp)
    a = cx["advice"]["nat"]
    if not a or abs(sum(a[2]) - 100) > 5:
        errs.append("context advice shares")
    for tr, g in cx["pass"].items():
        if not 0 <= g["nat"][1] <= 100:
            errs.append("context pass " + tr)
    for key, m in cx["grades"].items():
        for tr, g in m.items():
            if not 1 <= g["nat"][0] <= 10:
                errs.append("context grade %s %s" % (key, tr))
    if errs:
        print("\nGAP-CLOSING CHECK FAILURES:", len(errs))
        for e in errs[:30]:
            print("  ", e)
        raise SystemExit(1)
    print("\ngap-closing checks OK")


def main():
    pc4 = load("pc4.json")
    for name in ("po", "vo"):
        d = load("schools_%s.json" % name)
        recs = [rec(d, r) for r in d["rows"]]
        print("\n==== %s: %d rows" % (name.upper(), len(recs)))
        print("per province:", dict(sorted(collections.Counter(d["prov"][r["prov"]] if r["prov"] >= 0 else "?" for r in recs).items())))
        print("geo quality:", dict(collections.Counter(r["g"] for r in recs)))
        bad = [r for r in recs if r["lat"] is not None and not (50.7 < r["lat"] < 53.7 and 3.2 < r["lon"] < 7.3)]
        print("outside NL bbox:", len(bad), [(r["id"], r["name"]) for r in bad[:5]])
        far = []
        for r in recs:
            c = pc4.get(r["pc"][:4])
            if r["lat"] is not None and r["g"] == 0 and c and km(r["lat"], r["lon"], c[0], c[1]) > 12:
                far.append((r["id"], r["name"], r["pc"], round(km(r["lat"], r["lon"], c[0], c[1]), 1)))
        print("address hit >12 km from its PC4 centroid:", len(far), far[:6])
        print("without pupils:", sum(1 for r in recs if r["pupils"] is None), "| with website:", sum(1 for r in recs if r["web"]))
        if name == "po":
            n_adv = sum(1 for r in recs if r["adv"] and r["adv"][0] > 0)
            full = sum(1 for r in recs if r["adv"] and r["adv"][0] > 0 and r["adv"][1] == 0)
            print("with advice data (n>0): %d (%.1f%%); with no suppressed cell: %d (%.1f%%); sbo: %d" % (
                n_adv, 100 * n_adv / len(recs), full, 100 * full / len(recs), sum(r["sbo"] for r in recs)))
        else:
            n_ex = sum(1 for r in recs if r["exam"] and any(x[1] for x in r["exam"]))
            print("with exam data (>=1 track): %d (%.1f%%)" % (n_ex, 100 * n_ex / len(recs)))
            print("with tracks known:", sum(1 for r in recs if r["tracks"]))
    print("\n==== spot checks")
    for f, nm, city in SPOT:
        d = load("schools_%s.json" % f)
        hits = [rec(d, r) for r in d["rows"] if nm.lower() in r[1].lower() and city.lower() in (r[4] + r[5]).lower()]
        for r in hits[:3]:
            tr = ""
            if f == "vo":
                tr = [k for k, b in d["bits"].items() if r["tracks"] & b]
            print(f, r["id"], r["name"], "|", r["addr"], r["pc"], r["city"], "|", r["lat"], r["lon"], "g=%d" % r["g"],
                  "|", "pupils", r["pupils"], tr, (r.get("exam") or ""))
        if not hits:
            print(f, nm, city, "-> NO MATCH")
    check_detail()
    check_extra()


if __name__ == "__main__":
    main()
