"""Step 23: build out/context.json: national and province averages, shown as context next to a school's own numbers.

Context only: the front-end prints them as "all schools in the Netherlands" and "all schools in <province>" next to a school's
own figure and never as a rank, a better/worse label, a sort key or a filter. Computed here from this pipeline's own output (no
new source). Rules: only exact (shown) data goes in, computed the same way as the school's own figure so the two compare like for like:
suppressed cells stay out and are never recovered by subtraction; a province figure is published only when at least MIN_N
schools contribute (otherwise null).

  provinces   the 12 provinces (index = `prov` of the school files)
  pupils      {group: {nat: [mean, median, n schools, n with a lower bound], prov: [12 x same | null]}} for po (BO), sbo, so, vo.
              Pupil totals as shown on the school pages (sum of exact cells), so hidden small groups count as zero and the
              true averages are a little higher; n with a lower bound says how many of the schools are affected.
  advice      {nat: [n schools, n leavers, [12 shares %]], prov: [...]} schooladvies of leavers 2024/25, pooled over all BO schools
              with a school advice row: shares of the leavers in the shown cells, as in a school's own bar (hidden small groups are
              left out, so rare levels look rarer than they are)
  pass        {track: {year, nat: [candidates, pass %, n schools], prov: [...]}} latest exam year, pooled over schools with a
              pass rate (candidates >= 5) for the track, computed from the disclosed rows like a school's own figure
  grades      {ce|se|cl: {track: {year, nat: [mean, candidates, n schools], prov: [...]}}} candidate-weighted mean grade, latest
              exam year, over the same kind of disclosed rows
  sw          {nat: [mean, median, n locations]} schoolweging of PO locations (Inspectie, 3-year mean)
  rn          {subject: {nat: [pct low, pct high, n pupils, n schools], prov: [...]}} doorstroomtoets reference levels pooled
              over schools (weighted by tested pupils)
"""
import datetime, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, write_json_atomic

MIN_N = 5
TRACKS = ["VMBO-B", "VMBO-K", "VMBO-GL/TL", "HAVO", "VWO"]


def load(n):
    with open(os.path.join(OUT, n), encoding="utf-8") as f:
        return json.load(f)


def recs(d):
    return [dict(zip(d["cols"], r)) for r in d["rows"]]


def by_prov(items, fn, nprov):
    """items: list of (prov idx, payload); fn(payloads) -> value or None. Returns (national, [per province])."""
    nat = fn([p for _, p in items])
    prov = []
    for k in range(nprov):
        sub = [p for g, p in items if g == k]
        prov.append(fn(sub) if len(sub) >= MIN_N else None)
    return nat, prov


def main():
    po, so, vo = load("schools_po.json"), load("schools_so.json"), load("schools_vo.json")
    dpo, dvo = load("detail_po.json"), load("detail_vo.json")
    P = po["prov"]
    n = len(P)
    out = {"v": 1, "generated": datetime.date.today().isoformat(), "provinces": P, "min_n": MIN_N}

    # pupils per school
    def pup(items):
        v = [p[0] for p in items]
        return [round(statistics.mean(v)), round(statistics.median(v)), len(v), sum(p[1] for p in items)] if len(v) >= MIN_N else None
    groups = {}
    for key, d, flt in (("po", po, lambda r: not r["sbo"]), ("sbo", po, lambda r: r["sbo"]), ("so", so, lambda r: True), ("vo", vo, lambda r: True)):
        items = [(r["prov"], (r["pupils"], r["pupils_lb"])) for r in recs(d) if flt(r) and r["pupils"] is not None]
        nat, prov = by_prov(items, pup, n)
        groups[key] = {"nat": nat, "prov": prov}
    out["pupils"] = groups

    # schooladvies mix
    items = []
    for r in recs(po):
        a = r["adv"]
        if not r["sbo"] and a and a[0] > 0 and a[2]:
            items.append((r["prov"], (a[0], a[2])))

    def adv(v):
        if len(v) < MIN_N:
            return None
        tot = sum(x[0] for x in v)
        sh = [round(sum(x[0] * (x[1][k] or 0) for x in v) / tot, 1) for k in range(len(v[0][1]))]
        return [len(v), tot, sh]
    nat, prov = by_prov(items, adv, n)
    out["advice"] = {"nat": nat, "prov": prov, "levels": po["levels"]}

    # pass rates and grades from detail_vo, latest exam year
    prov_of = {r["id"]: r["prov"] for r in recs(vo)}
    D = dvo["schools"]
    exam_year = dvo["years"]["exams"][-1]
    out["pass"] = {}
    for tr in TRACKS:
        items = []
        for i, d in D.items():
            for e in (d.get("pr") or {}).get(tr, []):
                if e[0] == exam_year and e[1] is not None:
                    items.append((prov_of.get(i, -1), (e[1], round(e[1] * e[2] / 100.0))))

        def pas(v):
            if len(v) < MIN_N:
                return None
            c = sum(x[0] for x in v)
            return [c, round(100.0 * sum(x[1] for x in v) / c, 1), len(v)]
        nat, prov = by_prov(items, pas, n)
        if nat:
            out["pass"][tr] = {"year": exam_year, "nat": nat, "prov": prov}
    out["grades"] = {}
    for key in ("ce", "se", "cl"):
        out["grades"][key] = {}
        for tr in TRACKS:
            items = []
            for i, d in D.items():
                for e in (d.get(key) or {}).get(tr, []):
                    if e[0] == exam_year:
                        items.append((prov_of.get(i, -1), (e[1], e[2])))

            def gr(v):
                if len(v) < MIN_N:
                    return None
                c = sum(x[1] for x in v)
                return [round(sum(x[0] * x[1] for x in v) / c, 2), c, len(v)]
            nat, prov = by_prov(items, gr, n)
            if nat:
                out["grades"][key][tr] = {"year": exam_year, "nat": nat, "prov": prov}

    # reference levels (doorstroomtoets), weighted by tested pupils
    prov_po = {r["id"]: r["prov"] for r in recs(po)}
    out["rn"] = {}
    for subj in ("lezen", "taal", "rekenen"):
        items = []
        for i, d in dpo["schools"].items():
            a = (d.get("rn") or {}).get(subj)
            if a and a[0] is not None and a[1] is not None:
                items.append((prov_po.get(i, -1), (a[0], a[1], a[2])))

        def rn(v):
            if len(v) < MIN_N:
                return None
            t = sum(x[2] for x in v)
            return [round(sum(x[0] * x[2] for x in v) / t, 1), round(sum(x[1] * x[2] for x in v) / t, 1), t, len(v)]
        nat, prov = by_prov(items, rn, n)
        out["rn"][subj] = {"nat": nat, "prov": prov}
    # schoolweging (Inspectie, PO): mean and median over the school locations that have one
    ie = load("inspectie_extra.json")["schools"]
    sw = [d["sw"] for d in ie.values() if "sw" in d]
    if len(sw) >= MIN_N:
        out["sw"] = {"nat": [round(statistics.mean(sw), 1), round(statistics.median(sw), 1), len(sw)]}
    write_json_atomic(os.path.join(OUT, "context.json"), out)
    print("context.json written; pupils", {k: v["nat"] for k, v in groups.items()}, "| advice schools", out["advice"]["nat"][0],
          "| pass tracks", list(out["pass"]))


if __name__ == "__main__":
    main()
