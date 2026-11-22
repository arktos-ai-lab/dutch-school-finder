#!/usr/bin/env python3
"""Prerender Dutch School Guide into _site/: real paths, static HTML in <main> for every page.

Run from anywhere:  python -I build/prerender.py [--out DIR] [--seo FILE]

Inputs : site/index.html (shell), site/app.js + app.css + i18n/*.json + seo.json + og.png,
         pipeline/out/*.json (open data).
Output : _site/ = the deployable site (pages, sitemaps, robots.txt, 404.html, copied assets, data/).
Stdlib only. The slug rule (slugify) is the same as in site/app.js.
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import struct
import sys
import unicodedata
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "pipeline" / "out"

# per-school files that the build splits into small shards (data/s/<first 3 chars of the BRIN6 id>.json)
SHARDED = {"detail_po.json", "detail_vo.json", "detail_so.json", "extra.json", "inspectie_extra.json", "inspection.json"}

# ---------------------------------------------------------------- small helpers


def e(s):
    return html.escape(str(s), quote=True)


def jload(p):
    with open(p, encoding="utf8") as f:
        return json.load(f)


_SPECIAL = [("ß", "ss"), ("æ", "ae"), ("œ", "oe"), ("ø", "o"), ("đ", "d"), ("ð", "d"), ("ł", "l"), ("ı", "i"), ("þ", "th")]


def slugify(s):
    """Same rule as slugify() in site/app.js."""
    s = unicodedata.normalize("NFKD", "" if s is None else str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    for a, b in _SPECIAL:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def school_slug(s):
    n = slugify(s["name"])[:60].rstrip("-")
    c = slugify(s["city"])
    return s["id"].lower() + ("-" + n if n else "") + ("-" + c if c else "")


def nf(n):
    return f"{n:,}"


def jr(x):
    """Math.round"""
    return int(math.floor(x + 0.5))


def nf1(x):
    return f"{x:,.1f}"


def num(x):
    """number the way JS prints it in an attribute"""
    if isinstance(x, float) and x == int(x):
        x = int(x)
    return str(x)


# ---------------------------------------------------------------- i18n like app.js


class Tr:
    def __init__(self, d):
        self.d = d

    def raw(self, key):
        o = self.d
        for p in key.split("."):
            if not isinstance(o, dict) or p not in o:
                raise KeyError(key)
            o = o[p]
        return o

    def has(self, key):
        try:
            self.raw(key)
            return True
        except KeyError:
            return False

    def __call__(self, key, **v):
        o = self.raw(key)
        if isinstance(o, dict):
            n = v.get("n")
            o = o["one"] if n == 1 and "one" in o else o["other"]
        if not isinstance(o, str):
            raise TypeError(key)

        def fill(m):
            k = m.group(1)
            if k in v and v[k] is not None:
                x = v[k]
                return nf(x) if isinstance(x, int) and not isinstance(x, bool) else str(x)
            if k == "brand":
                return self.d["brand"]["name"]
            return m.group(0)

        return re.sub(r"\{(\w+)\}", fill, o)


def rich(s):
    """only <b>..</b> survives, everything else is text (like rich() in app.js)"""
    parts = re.split(r"(</?b>)", str(s))
    out = []
    for p in parts:
        if p in ("<b>", "</b>"):
            out.append(p)
        else:
            out.append(e(p))
    return "".join(out)


# ---------------------------------------------------------------- constants read from app.js (single source of truth)


def read_app_consts(js):
    m = re.search(r"var SRC_URL=\{(.*?)\n\};", js, re.S)
    src_url = dict(re.findall(r"(\w+):'([^']+)'", m.group(1)))
    m = re.search(r"var SRC_ORDER=\[(.*?)\];", js, re.S)
    src_order = re.findall(r"'([^']+)'", m.group(1))
    m = re.search(r"var LAST_CHECKED='([^']+)'", js)
    last_checked = m.group(1)
    m = re.search(r"var FEAT_ATTR=\[(.*?)\];\nfunction renderFooter", js, re.S)
    feat_attr = re.findall(r"\['(\w+)','([^']+)','([^']*)'\]", m.group(1))
    assert src_url and src_order and feat_attr
    return src_url, src_order, last_checked, feat_attr


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def fmt_day(iso):
    y, mo, d = (int(x) for x in iso.split("-"))
    return f"{d} {MONTHS[mo - 1]} {y}"


# ---------------------------------------------------------------- data


def load_schools():
    out = []
    for fname, sec_of in (("schools_po", lambda r: "sbo" if r["sbo"] else "po"), ("schools_vo", lambda r: "vo"), ("schools_so", lambda r: "so")):
        j = jload(DATA / f"{fname}.json")
        cols = j["cols"]
        for row in j["rows"]:
            r = dict(zip(cols, row))
            r["_raw"] = dict(r)
            r["sec"] = sec_of(r)
            r["denNl"] = j["den"][r["den"]] if r.get("den") is not None and r["den"] >= 0 else ""
            r["provN"] = j["prov"][r["prov"]] if r.get("prov") is not None and 0 <= r["prov"] < len(j["prov"]) else ""
            r["_levels"] = j.get("levels")
            r["_clusters"] = j.get("clusters")
            r["name"] = r["name"] or ""
            r["city"] = r["city"] or ""
            r["mun"] = r["mun"] or ""
            out.append(r)
    return out


def hav(lat1, lon1, lat2, lon2):
    la1 = lat1 * math.pi / 180
    la2 = lat2 * math.pi / 180
    dl = (la2 - la1) / 2
    dn = (lon2 - lon1) * math.pi / 360
    a = math.sin(dl) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dn) ** 2
    return 12742 * math.asin(min(1, math.sqrt(a)))


def nearest_same_type(schools, k=5):
    """id -> [(school, km)] the k nearest schools of the same sec (same rule as nearbySection in app.js)"""
    res = {}
    CELL = 0.05
    for sec in ("po", "sbo", "vo", "so"):
        grp = [s for s in schools if s["sec"] == sec and s["g"] != 3 and s["lat"] is not None]
        grid = {}
        for s in grp:
            grid.setdefault((int(s["lat"] / CELL), int(s["lon"] / CELL)), []).append(s)
        brute = len(grp) < 1200
        for s in grp:
            if brute:
                cand = [(hav(s["lat"], s["lon"], o["lat"], o["lon"]), o) for o in grp if o is not s]
                cand.sort(key=lambda x: (x[0], x[1]["id"]))
                res[s["id"]] = [(o, d) for d, o in cand[:k]]
                continue
            cy, cx = int(s["lat"] / CELL), int(s["lon"] / CELL)
            found = []
            r = 0
            while r < 400:
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if max(abs(dy), abs(dx)) != r:
                            continue
                        for o in grid.get((cy + dy, cx + dx), ()):
                            if o is not s:
                                found.append((hav(s["lat"], s["lon"], o["lat"], o["lon"]), o))
                found.sort(key=lambda x: (x[0], x[1]["id"]))
                # a cell is at least ~3.3 km wide at 53 degrees north; anything unseen is farther than r*3.3 km
                if len(found) >= k and found[k - 1][0] <= r * 3.3:
                    break
                r += 1
            res[s["id"]] = [(o, d) for d, o in found[:k]]
    return res


# ---------------------------------------------------------------- the build


class Build:
    def __init__(self, out_dir, seo_path):
        self.out = Path(out_dir)
        self.seo = jload(seo_path)
        self.site_url = self.seo["site_url"].rstrip("/")
        self.base = self.seo["base_path"]
        assert self.base.startswith("/") and self.base.endswith("/")
        self.indexable = bool(self.seo["indexable"])
        self.langs = self.seo["lang"]
        self.en = jload(SITE / "i18n" / "en.json")
        self.t = Tr(self.en)
        self.brand = self.en["brand"]["name"]
        self.js = (SITE / "app.js").read_text(encoding="utf8")
        self.src_url, self.src_order, self.last_checked, self.feat_attr = read_app_consts(self.js)
        self.shell = (SITE / "index.html").read_text(encoding="utf8")
        self.meta = jload(DATA / "meta.json")
        self.insp = jload(DATA / "inspection.json")
        self.feat = jload(DATA / "features.json")
        self.det_vo = jload(DATA / "detail_vo.json")
        self.det_po = jload(DATA / "detail_po.json")
        self.det_so = jload(DATA / "detail_so.json")
        self.extra = jload(DATA / "extra.json")
        self.ixd = jload(DATA / "inspectie_extra.json")
        self.pc4 = jload(DATA / "pc4.json")
        self.schools = load_schools()
        self.tcount = {}
        for s in self.schools:
            k = (s["name"], s["city"], s["sec"])
            self.tcount[k] = self.tcount.get(k, 0) + 1
            k = k + (s["addr"],)
            self.tcount[k] = self.tcount.get(k, 0) + 1
        self.intl = jload(ROOT / "build" / "international_schools.json")
        self.faq_q = {x["id"]: x["q"] for g in self.en["faq"]["groups"] for x in g["items"]}
        self.faq_page_ids = {p["id"] for p in self.en["faq"]["pages"]}
        self.guides = self.load_guides()
        self.pages = 0
        self.sitemap = {"pages": [], "schools": [], "municipalities": []}
        self.ver = {}
        for f in ("app.js", "app.css"):
            self.ver[f] = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        # translations and icons change without app.js changing: their own version, so browsers never keep an old copy
        self.ver["i18n"] = hashlib.sha1(b"".join(f.read_bytes() for f in sorted((SITE / "i18n").glob("*.json")))).hexdigest()[:8]
        self.ver["icon"] = hashlib.sha1((SITE / "favicon.svg").read_bytes() + (ROOT / "build" / "prerender.py").read_bytes()).hexdigest()[:8]
        # date of the open data behind school and municipality pages: the newest generation date of the pipeline files
        gens = [str(j.get("generated", ""))[:10] for j in (self.meta, self.insp, self.det_vo, self.det_po, self.det_so, self.extra, self.ixd, self.feat)]
        self.generated = max(g for g in gens if re.fullmatch(r"\d{4}-\d{2}-\d{2}", g))
        self.hashes = {}

    # ------------------------------------------------------------ url helpers
    def href(self, rel):
        return self.base + rel

    def canon(self, rel):
        return self.site_url + "/" + rel

    def out_path(self, rel):
        return self.out / rel / "index.html" if rel else self.out / "index.html"

    # ------------------------------------------------------------ data helpers
    def data_year(self, key):
        m = (self.meta.get("data_years") or {}).get(key)
        if not m:
            return "", ""
        a = re.match(r"(\d{4}-\d{4})", m)
        d = re.search(r"(\d{4}-\d{2}-\d{2})", m)
        return (a.group(1) if a else ""), (d.group(1) if d else "")

    def den_label(self, nl):
        m = self.en["den"]
        return m.get(nl, self.en["den"]["other"])

    def feat_list(self, sid):
        f = self.feat["schools"].get(sid)
        out = []
        if not f or not isinstance(f.get("flags"), list):
            return out
        for k in ["tto", "ib", "technasium", "international", "montessori", "dalton", "jenaplan", "vrije_school", "newcomer"]:
            if k not in f["flags"]:
                continue
            c = (f.get("confidence") or {}).get(k)
            if c not in ("high", "medium"):
                continue
            out.append((k, c, (f.get("evidence") or {}).get(k)))
        return out

    def safe_url(self, u):
        return u if isinstance(u, str) and re.match(r"^https?://[^\s\"'<>]+$", u, re.I) else None

    def safe_web(self, w):
        return "https://" + w if w and re.match(r"^[a-z0-9][a-z0-9.\-/_%?=&:~#+@]*$", w, re.I) else None

    def feat_src_name(self, url, kind):
        t = self.t
        if kind != "list":
            return t("feat.src.site")
        host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
        for dom, key in [("nuffic.nl", "nuffic"), ("technasium.nl", "technasium"), ("montessori.nl", "montessori"), ("dalton.nl", "dalton"), ("jenaplan.nl", "jenaplan"), ("vrijescholen.nl", "vrije"), ("dutchinternationalschools.nl", "dis"), ("sio.nl", "sio"), ("duo.nl", "duo")]:
            if host.endswith(dom):
                return t("feat.src." + key)
        return t("feat.src.other")

    def feat_chips(self, sid):
        t = self.t
        lst = self.feat_list(sid)
        if not lst:
            return ""
        out = ['<div class="fts">']
        for k, c, ev in lst:
            src = self.feat_src_name(ev[0], ev[2]) if ev else t("feat.src.site")
            tip = t("feat.tip", label=t("ft." + k), src=src, checked=t("feat.checked", date=ev[3]) if ev and ev[3] else "", less=t("feat.less") if c == "medium" else "")
            cls = "ft" + (" md" if c == "medium" else "")
            url = self.safe_url(ev[0]) if ev else None
            if url:
                out.append(f'<a class="{cls}" href="{e(url)}" target="_blank" rel="noopener" title="{e(tip)}">{e(t("ft." + k))}</a>')
            else:
                out.append(f'<span class="{cls}" title="{e(tip)}">{e(t("ft." + k))}</span>')
        out.append("</div>")
        return "".join(out)

    # ------------------------------------------------------------ html shell
    def head(self, p):
        t = self.t
        rel = p.get("rel")
        title = p["title"]
        desc = p["desc"]
        robots_idx = p.get("index", True) and self.indexable
        robots = ("index, follow" if robots_idx else ("noindex, follow" if self.indexable else "noindex, nofollow"))
        h = ['<meta charset="utf-8">', '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">']
        h.append(f"<title>{e(title)}</title>")
        h.append(f'<meta name="description" content="{e(desc)}">')
        h.append(f'<meta name="robots" content="{robots}">')
        h.append(f'<meta name="theme-color" content="#E8DCC3">')
        h.append(f'<meta name="sp-base" content="{e(self.base)}">')
        h.append(f'<meta name="sp-ver" content="{self.ver['i18n']}">')
        if p.get("canonical", True):
            url = self.canon(rel)
            h.append(f'<link rel="canonical" href="{e(url)}">')
            first = self.langs[0]
            for lg in self.langs:
                u = url if lg == first else url + ("&" if "?" in url else "?") + "lang=" + lg
                h.append(f'<link rel="alternate" hreflang="{e(lg)}" href="{e(u)}">')
            h.append(f'<link rel="alternate" hreflang="x-default" href="{e(url)}">')
            h.append(f'<meta property="og:url" content="{e(url)}">')
        img = self.site_url + "/og.png"
        h.append('<meta property="og:type" content="website">')
        h.append(f'<meta property="og:site_name" content="{e(self.brand)}">')
        h.append(f'<meta property="og:title" content="{e(p.get("og_title", title))}">')
        h.append(f'<meta property="og:description" content="{e(desc)}">')
        h.append(f'<meta property="og:locale" content="en_GB">')
        h.append(f'<meta property="og:image" content="{e(img)}">')
        h.append('<meta property="og:image:width" content="1200">')
        h.append('<meta property="og:image:height" content="630">')
        h.append(f'<meta property="og:image:alt" content="{e(self.brand)}: {e(self.en["brand"]["tagline"])}">')
        h.append('<meta name="twitter:card" content="summary_large_image">')
        h.append(f'<meta name="twitter:title" content="{e(p.get("og_title", title))}">')
        h.append(f'<meta name="twitter:description" content="{e(desc)}">')
        h.append(f'<meta name="twitter:image" content="{e(img)}">')
        h.append(f'<link rel="icon" type="image/svg+xml" href="{self.base}favicon.svg?v={self.ver['icon']}">')
        h.append(f'<link rel="icon" type="image/x-icon" sizes="32x32" href="{self.base}favicon.ico?v={self.ver['icon']}">')
        h.append(f'<link rel="preload" href="{self.base}fonts/atkinson-hyperlegible-latin-400.woff2" as="font" type="font/woff2" crossorigin>')
        h.append(f'<link rel="stylesheet" href="{self.base}app.css?v={self.ver["app.css"]}">')
        for ld in p.get("jsonld", []):
            h.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>")
        return "\n".join(h)

    def fill_i18n(self, s):
        t = self.t

        def el(m):
            tag, attrs, key = m.group(1), m.group(2), m.group(3)
            return f"<{tag}{attrs}>{e(t(key))}</{tag}>"

        s = re.sub(r'<(\w+)([^<>]*\bdata-i18n="([^"]+)"[^<>]*)></\1>', el, s)

        def at(m):
            tag, attrs, spec = m.group(1), m.group(2), m.group(3)
            extra = ""
            for pair in spec.split(";"):
                k, _, v = pair.partition(":")
                extra += f' {k.strip()}="{e(t(v.strip()))}"'
            return f"<{tag}{extra}{attrs}>"

        s = re.sub(r'<(\w+)([^<>]*\bdata-i18n-attr="([^"]+)"[^<>]*)>', at, s)

        route_rel = {"route": "", "find": "find/", "map": "map/", "system": "system/", "faq": "questions/", "sources": "sources/"}

        def rt(m):
            tag, attrs, name = m.group(1), m.group(2), m.group(3)
            return f'<{tag} href="{self.href(route_rel[name])}"{attrs}>'

        s = re.sub(r'<(a)([^<>]*\bdata-route="(\w+)"[^<>]*)>', rt, s)
        return s

    def fill_links(self, s):
        """text and href for empty <a data-i18n> links only; the rest of a hidden section is left to app.js"""
        s = re.sub(r'<a([^<>]*\bdata-i18n="([^"]+)"[^<>]*)></a>', lambda m: f"<a{m.group(1)}>{e(self.t(m.group(2)))}</a>", s)
        route_rel = {"route": "", "find": "find/", "map": "map/", "system": "system/", "faq": "questions/", "sources": "sources/"}
        return re.sub(r'<a((?![^<>]*\bhref=)[^<>]*\bdata-route="(\w+)"[^<>]*)>',
                      lambda m: f'<a href="{self.href(route_rel[m.group(2)])}"{m.group(1)}>', s)

    def page(self, p):
        """p: rel, view, title, desc, slots (dict), jsonld, index, tab, schoolid"""
        t = self.t
        view = p["view"]
        s = self.shell
        s = s.replace("<!--@head-->", self.head(p))
        s = s.replace("<!--@bodyattrs-->", f' data-view="{view}"')
        s = s.replace("<!--@appjs-->", f'{self.base}app.js?v={self.ver["app.js"]}')
        # hidden sections; the active one carries the h1
        for v in ("route", "find", "map", "school", "compare", "system", "faq", "sources", "static"):
            s = s.replace(f"<!--@hide:{v}-->", "" if v == view else " hidden")
        if view not in ("route", "school", "static"):
            m = re.search(rf'<section id="p-{view}".*?</section>', s, re.S)
            blk = m.group(0)
            nb = blk.replace('<h2 class="vh"', '<h1 class="vh"', 1)
            nb = nb.replace("</h2>", "</h1>", 1)
            assert nb != blk
            s = s.replace(blk, nb)
        # hero title: h1 on the start page, a plain paragraph elsewhere
        hero = e(t("hero.title"))
        s = s.replace("<!--@h1-->", f'<h1 id="h1" class="h1" data-i18n="hero.title">{hero}</h1>' if view == "route" else f'<p id="h1" class="h1" data-i18n="hero.title">{hero}</p>')
        # text is filled in only where it is visible; hidden sections and the hero (off the start page) are left to app.js
        stash = []

        def keep(m):
            stash.append(m.group(0))
            return f"@@{len(stash) - 1}@@"

        s = re.sub(r'<section id="p-\w+" hidden>.*?</section>', keep, s, flags=re.S)
        if view != "route":
            # hidden off the start page (app.js toggles it); its text is filled by app.js when shown
            s = s.replace('<section class="hero" aria-labelledby="h1">', '<section class="hero" aria-labelledby="h1" hidden>', 1)
            s = re.sub(r'<section class="hero".*?</section>', keep, s, flags=re.S)
        s = self.fill_i18n(s)
        # links inside hidden sections still get their text and href, so no page carries an empty link
        s = re.sub(r"@@(\d+)@@", lambda m: self.fill_links(stash[int(m.group(1))]), s)
        # current tab
        tab = p.get("tab", view if view != "faq" else "faq")
        if tab:
            s = s.replace(f'class="tab" id="t-{tab}"', f'class="tab" id="t-{tab}" aria-current="page"', 1)
        slots = p.get("slots", {})
        home = view == "route"
        defaults = {
            "ageopts": self.age_options() if home else "",
            "exrow": self.ex_row() if home else "",
            "gloss": self.gloss() if home else "",
            "footchecked": e(t("foot.checked", date=fmt_day(self.last_checked))),
            "schoolattrs": "",
            "homelinks": "",
            "footlinks": self.foot_links(),
        }
        defaults.update(slots)
        for k, v in defaults.items():
            s = s.replace(f"<!--@{k}-->", v)
        s = re.sub(r"<!--@\w+-->", "", s)
        assert "<!--@" not in s
        s = re.sub(r"\n\s*", "\n", s)
        return s

    def foot_links(self):
        """site-wide links in the footer, so every content page is one click from every page"""
        t = self.t
        ks = [("guides/", "foot.guides"), ("questions/", "foot.questions"), ("international/", "foot.intl"), ("municipalities/", "foot.munis"), ("system/", "foot.system")]
        if not self.guides:
            ks = ks[1:]
        li = "".join(f'<li><a href="{self.href(r)}">{e(t(k))}</a></li>' for r, k in ks)
        return f'<nav class="footnav" aria-label="{e(t("foot.navAria"))}"><ul>{li}</ul></nav>'

    def write(self, rel, content):
        if not rel.startswith(("school/", "municipality/")):
            # fingerprint of a content page (the asset version query is left out), for its sitemap lastmod
            self.hashes[rel] = hashlib.sha1(re.sub(r"\?v=[0-9a-f]{8}", "", content).encode("utf8")).hexdigest()[:16]
        path = self.out_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf8", newline="\n")
        self.pages += 1

    # ------------------------------------------------------------ static fragments shared with the shell
    def age_options(self):
        t = self.t
        o = [f'<option value="">{e(t("form.agePlaceholder"))}</option>', f'<option value="u4">{e(t("form.ageU4"))}</option>']
        for a in range(4, 18):
            o.append(f'<option value="{a}">{e(t("form.ageN", age=str(a)))}</option>')
        o.append(f'<option value="18">{e(t("form.age18"))}</option>')
        return "".join(o)

    def ex_row(self):
        t = self.t
        o = [f'<span class="exlbl">{e(t("form.tryExample"))}</span>']
        for pc, k in (("1077", "amsterdam"), ("2517", "hague"), ("5611", "eindhoven")):
            o.append(f'<button class="chip exbtn" type="button">{e(t("ex." + k))}</button>')
        return "".join(o)

    def gloss(self):
        return "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in self.en["glossary"])

    def crumbs(self, items):
        t = self.t
        li = []
        for i, (label, href) in enumerate(items):
            if href and i < len(items) - 1:
                li.append(f'<li><a href="{e(href)}">{e(label)}</a></li>')
            else:
                li.append(f'<li><span aria-current="page">{e(label)}</span></li>')
        return f'<nav class="crumbs" aria-label="{e(t("crumb.aria"))}"><ol>{"".join(li)}</ol></nav>'

    def src_line(self, keys, cls="src"):
        t = self.t
        parts = []
        for k in keys:
            u = self.src_url.get(k)
            if not u:
                continue
            parts.append(f'<a href="{e(u)}" target="_blank" rel="noopener">{e(t("src." + k))}</a>')
        return f'<p class="{cls}">{e(t("src.label"))} ' + " · ".join(parts) + "</p>"

    # ------------------------------------------------------------ description fitting
    @staticmethod
    def fit(base, opts, tails, lo=150, hi=160):
        """base + a subset of opts (kept in order) + up to two tails, 150 to 160 characters; most complete text first"""
        from itertools import combinations
        best = None
        n = len(opts)
        for k in range(n, -1, -1):
            for pick in combinations(range(n), k):
                head = [base] + [opts[i] for i in pick]
                cands = [[]] + [[x] for x in tails] + [[x, y] for x, y in combinations(tails, 2)]
                for tl in cands:
                    txt = " ".join(head + tl)
                    L = len(txt)
                    if lo <= L <= hi:
                        return txt
                    if L <= hi and (best is None or L > len(best)):
                        best = txt
        if best is None:
            best = base[: hi - 3].rsplit(" ", 1)[0] + "..."
        return best

    # ------------------------------------------------------------ system svg (port of buildSystem in app.js)
    def system_svg(self):
        t = self.t
        W, H = 360, 700
        o = []

        def rect(x, y, w, hh, cls, txt=None, tcls="on"):
            o.append(f'<rect class="cell {cls}" x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(hh)}"/>')
            if txt not in (None, ""):
                o.append(f'<text class="{tcls}" x="{num(x + w / 2)}" y="{num(y + hh / 2 + 4)}" text-anchor="middle">{e(txt)}</text>')

        def text(x, y, tx, cls="ax", anchor=None):
            a = f' text-anchor="{anchor}"' if anchor else ""
            o.append(f'<text class="{cls}" x="{num(x)}" y="{num(y)}"{a}>{e(tx)}</text>')

        def path(d, dash=False, both=False):
            o.append(f'<path class="arh" d="{d}"/>')
            ms = ' marker-start="url(#ah)"' if both else ""
            o.append(f'<path class="ar{" d" if dash else ""}" d="{d}" marker-end="url(#ah)"{ms}/>')

        def mk(cx, y, tx):
            o.append(f'<rect class="mkb" x="{num(cx - 7)}" y="{num(y)}" width="14" height="14"/>')
            o.append(f'<text class="mkt" x="{num(cx)}" y="{num(y + 10.5)}" text-anchor="middle">{e(tx)}</text>')

        def bar(x, y, w, n, cls, labels=None):
            for i in range(n):
                rect(x, y + i * 20, w, 20, cls, labels[i] if labels else str(i + 1))

        o.append(f'<svg class="sys-svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="sysT sysD" style="direction:ltr">')
        o.append(f'<title id="sysT">{e(t("sys.title"))}</title><desc id="sysD">{e(t("sys.desc"))}</desc>')
        o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path class="ah" d="M0 0L10 5L0 10z"/></marker></defs>')
        LX = [40, 120, 200, 280]
        LW = 60
        C = [70, 150, 230, 310]
        # ages: one left-hand column for primary and secondary alike, one age per row (same as app.js)
        text(40, 14, t("sys.primary"), "ax")
        text(34, 14, t("sys.ageAxis"), "ax", "end")
        for g in range(1, 9):
            y = 22 + (g - 1) * 20
            rect(40, y, 308, 20, "f-bo")
            o.append(f'<text class="on" x="48" y="{num(y + 14.5)}">{e(t("sys.yearGroup", n=str(g)))}</text>')
            text(34, y + 14.5, str(g + 3), "ax", "end")
        for x in C:
            path(f"M{x} 184V230")
        o.append('<rect class="lbl" x="36" y="196" width="288" height="24"/>')
        mk(50, 201, "1")
        text(64, 213, t("sys.adviceLabel"), "ax")
        names = ["pro", "vmbo", "havo", "vwo"]
        cls = ["f-pro", "f-vbk", "f-havo", "f-vwo"]
        yrs = [5, 4, 5, 6]
        text(34, 246, t("sys.ageAxis"), "ax", "end")
        for i in range(4):
            rect(LX[i], 232, LW, 18, cls[i], t("sys.lane." + names[i]), "hd")
            bar(LX[i], 250, LW, yrs[i], cls[i])
        for k, a in enumerate([12, 13, 14, 15, 16, 17]):
            text(34, 250 + k * 20 + 14.5, str(a), "ax", "end")
        path("M181 278H199", True, True)
        path("M261 278H279", True, True)
        mk(190, 284, "2")
        mk(270, 284, "2")
        path("M181 314H199", True)
        mk(190, 320, "3")
        path("M261 334H279")
        mk(270, 340, "4")
        path("M70 352V424", True)
        mk(70, 380, "5")
        path("M150 332V424")
        mk(150, 380, "6")
        path("M230 352V424")
        mk(230, 396, "7")
        path("M214 352V392H166V424")
        mk(190, 385, "7")
        path("M310 372V424")
        mk(310, 396, "8")
        path("M296 372V404H258V424")
        mk(277, 397, "8")
        rect(40, 424, 132, 18, "f-mbo", "mbo", "hd")
        rect(200, 424, 62, 18, "f-hbo", "hbo", "hd")
        rect(280, 424, 68, 18, "f-wo", "wo", "hd")
        for k, l in enumerate([1, 2, 3, 4]):
            lb = [str(l) if q == 0 else "" for q in range(l)]
            bar(40 + k * 34, 442, 30, l, "f-mbo", lb)
        text(106, 540, t("sys.mboLevels"), "ax", "middle")
        bar(200, 442, 22, 2, "f-hbo", ["AD", ""])
        bar(226, 442, 36, 4, "f-hbo")
        path("M244 523V543", True)
        bar(226, 544, 36, 2, "f-hbo", ["M", ""])
        bar(280, 442, 68, 3, "f-wo")
        path("M314 503V525", True)
        bar(280, 526, 68, 2, "f-wo", ["M", ""])
        path("M314 567V589", True)
        bar(280, 590, 68, 4, "f-wo", ["PhD", "", "", ""])
        path("M173 470H199")
        mk(186, 477, "a")
        path("M263 452H279", True)
        mk(271, 458, "b")
        path("M263 512H271V536H279", True)
        mk(271, 519, "d")
        text(36, 692, t("sys.legend"), "ax")
        o.append("</svg>")
        return "".join(o)

    def system_slots(self):
        t = self.t
        keys = "".join(f'<li><i style="background:var(--c-{x})"></i>{e(t("sys.key." + x))}</li>' for x in ["bo", "pro", "vbk", "havo", "vwo", "mbo", "hbo", "wo"])
        xf = "".join(f'<li><b>{e(x["k"])}</b><span>{e(x["text"])}</span></li>' for x in self.en["sys"]["xfers"])
        xf += f'<li><b>+</b><span>{e(t("sys.xfersExtra"))}</span></li>'
        links = []
        for key in ["schema", "nuf", "loket", "gov", "mboRijks", "sk123", "vo_raad_moving_from_vmbo_to_havo_and_fro", "rijksoverheid_which_diplomas_give_access"]:
            links.append(f'<a href="{e(self.src_url[key])}" target="_blank" rel="noopener">{e(t("src." + key))}</a>')
        syssrc = e(t("src.label")) + " " + " · ".join(links)
        return {"sysfig": self.system_svg(), "syskeys": keys, "xfers": xf, "syssrc": syssrc}

    # ------------------------------------------------------------ faq
    def faq_html(self):
        t = self.t
        groups = self.en["faq"]["groups"]
        o = ['<div class="faqtools"><nav class="faqnav" aria-label="%s">' % e(t("faq.navAria"))]
        for g in groups:
            o.append(f'<a class="chip" href="#faqg-{e(g["id"])}" style="text-decoration:none">{e(g["title"])}</a>')
        o.append("</nav>")
        o.append(f'<div class="faqall"><button class="btn sec" type="button">{e(t("faq.expand"))}</button> <button class="btn sec" type="button">{e(t("faq.collapse"))}</button></div></div>')
        for g in groups:
            o.append(f'<section class="faqgrp" aria-labelledby="faqg-{e(g["id"])}"><h2 id="faqg-{e(g["id"])}">{e(g["title"])}</h2>')
            for x in g["items"]:
                o.append(f'<details id="{e(x["id"])}"><summary>{e(x["q"])}</summary><div class="ans">')
                for b in x["blocks"]:
                    if "p" in b:
                        o.append(f"<p>{rich(b['p'])}</p>")
                    elif "say" in b:
                        o.append(f'<p class="say">{rich(b["say"])}</p>')
                    elif "ul" in b:
                        o.append("<ul>" + "".join(f"<li>{rich(li)}</li>" for li in b["ul"]) + "</ul>")
                o.append(self.src_line(x.get("src", [])))
                pl = f' &middot; <a href="{self.href("questions/" + x["id"] + "/")}">{e(t("faq.pageLink"))}</a>' if x["id"] in self.faq_page_ids else ""
                o.append(f'<p class="faqlink"><a href="{self.href("questions/#" + x["id"])}">{e(t("faq.link"))}</a>{pl}</p></div></details>')
            o.append("</section>")
        return "".join(o)

    @staticmethod
    def answer_ld(x):
        parts = []
        for b in x["blocks"]:
            if "p" in b:
                parts.append("<p>" + e(re.sub(r"</?b>", "", b["p"])) + "</p>")
            elif "say" in b:
                parts.append("<p>" + e(re.sub(r"</?b>", "", b["say"])) + "</p>")
            elif "ul" in b:
                parts.append("<ul>" + "".join("<li>" + e(re.sub(r"</?b>", "", li)) + "</li>" for li in b["ul"]) + "</ul>")
        return {"@type": "Question", "name": x["q"], "acceptedAnswer": {"@type": "Answer", "text": "".join(parts)}}

    def faq_jsonld(self):
        qs = [self.answer_ld(x) for g in self.en["faq"]["groups"] for x in g["items"]]
        return {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": self.langs[0], "mainEntity": qs}

    # ------------------------------------------------------------ one page per frequent question
    SITE_LINKS = {"route": "", "find": "find/", "system": "system/", "munis": "municipalities/", "intl": "international/", "sources": "sources/", "guides": "guides/", "map": "map/", "questions": "questions/"}

    def question_pages(self):
        """/questions/<id>/ for the questions listed in en.json faq.pages: the answer from en.json, related links, FAQPage with one question.
        FAQPage (not QAPage): Google documents QAPage only for pages where users can submit answers; a single answer written by the site
        itself is FAQPage."""
        t = self.t
        qmap = {x["id"]: x for g in self.en["faq"]["groups"] for x in g["items"]}
        for pg in self.en["faq"]["pages"]:
            x = qmap[pg["id"]]
            rel = f"questions/{x['id']}/"
            cr = [(t("crumb.home"), self.href("")), (t("faq.page.crumb"), self.href("questions/")), (x["q"], None)]
            o = [f'<div class="phead" data-tab="faq">{self.crumbs(cr)}<h1 class="vh" id="h-static" tabindex="-1">{e(x["q"])}</h1></div>']
            ans = []
            for b in x["blocks"]:
                if "p" in b:
                    ans.append(f"<p>{rich(b['p'])}</p>")
                elif "say" in b:
                    ans.append(f'<p class="say">{rich(b["say"])}</p>')
                elif "ul" in b:
                    ans.append("<ul>" + "".join(f"<li>{rich(li)}</li>" for li in b["ul"]) + "</ul>")
            o.append(f'<section class="psec qa"><div class="ans">{"".join(ans)}</div>{self.src_line(x.get("src", []))}</section>')
            li = []
            for rid in pg["related"]:
                href = self.href(f"questions/{rid}/") if rid in self.faq_page_ids else self.href(f"questions/#{rid}")
                li.append(f'<li><a href="{e(href)}">{e(qmap[rid]["q"])}</a></li>')
            o.append(f'<section class="psec"><h2>{e(t("faq.page.relatedQ"))}</h2><ul class="muni-list">{"".join(li)}</ul></section>')
            li = [f'<li><a href="{e(self.href(self.SITE_LINKS[k]))}">{e(t("faq.page.l." + k))}</a></li>' for k in pg["links"]]
            li.append(f'<li><a href="{e(self.href("questions/#" + x["id"]))}">{e(t("faq.page.all"))}</a></li>')
            o.append(f'<section class="psec"><h2>{e(t("faq.page.next"))}</h2><ul class="muni-list">{"".join(li)}</ul></section>')
            bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
                  {"@type": "ListItem", "position": 2, "name": t("faq.page.crumb"), "item": self.canon("questions/")},
                  {"@type": "ListItem", "position": 3, "name": x["q"], "item": self.canon(rel)}]
            ld = {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": self.langs[0], "mainEntity": [self.answer_ld(x)]}
            page = {"rel": rel, "view": "static", "tab": None, "title": pg["title"], "desc": pg["desc"],
                    "jsonld": [ld, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}],
                    "slots": {"static": "".join(o)}}
            self.write(rel, self.page(page))
            self.sitemap["pages"].append(rel)

    # ------------------------------------------------------------ guides: longer pages, one file per guide
    GUIDE_DIR = SITE / "i18n" / "guides"

    def load_guides(self):
        """site/i18n/guides/<lang>/<slug>.json, one per guide (see site/i18n/guides/README.md for the format)"""
        d = self.GUIDE_DIR / self.langs[0]
        out = {}
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            g = json.loads(f.read_text(encoding="utf8"))
            assert g["slug"] == f.stem, ("guide slug must match file name", f.name)
            for k in ("title", "desc", "h1", "lede", "group", "checked", "sections", "sources"):
                assert g.get(k), ("guide field missing", f.name, k)
            assert g["group"] in {x["id"] for x in self.en["guides"]["groups"]}, ("unknown guide group", f.name, g["group"])
            out[g["slug"]] = g
        return out

    def grich(self, s):
        """guide text: <b>..</b> and [label](/site/path/ or https://...) links; everything else is text"""
        out = []
        for part in re.split(r"(\[[^\]]+\]\([^)\s]+\))", str(s)):
            m = re.fullmatch(r"\[([^\]]+)\]\(([^)\s]+)\)", part)
            if not m:
                out.append(rich(part))
                continue
            label, url = m.groups()
            if url.startswith("/"):
                path, _, frag = url[1:].partition("#")
                href = self.href(path) + ("#" + frag if frag else "")
                out.append(f'<a href="{e(href)}">{rich(label)}</a>')
            else:
                assert url.startswith("https://"), ("guide link must be /path/ or https://", url)
                out.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{rich(label)}</a>')
        return "".join(out)

    def guide_blocks(self, blocks):
        o = []
        for b in blocks:
            if "p" in b:
                o.append(f"<p>{self.grich(b['p'])}</p>")
            elif "say" in b:
                o.append(f'<p class="say">{self.grich(b["say"])}</p>')
            elif "ul" in b:
                o.append("<ul>" + "".join(f"<li>{self.grich(li)}</li>" for li in b["ul"]) + "</ul>")
            elif "steps" in b:
                o.append('<ol class="gsteps">' + "".join(f"<li>{self.grich(li)}</li>" for li in b["steps"]) + "</ol>")
            elif "note" in b:
                o.append(f'<p class="note">{self.grich(b["note"])}</p>')
            elif "table" in b:
                tb = b["table"]
                cap = f'<caption>{e(tb["caption"])}</caption>' if tb.get("caption") else ""
                head = "".join(f'<th scope="col">{e(h)}</th>' for h in tb["head"])
                rows = "".join("<tr>" + "".join((f'<th scope="row">{self.grich(c)}</th>' if i == 0 else f"<td>{self.grich(c)}</td>") for i, c in enumerate(r)) + "</tr>" for r in tb["rows"])
                o.append(f'<div class="gtable"><table>{cap}<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>')
            else:
                raise AssertionError(("unknown guide block", b))
        return "".join(o)

    def guide_pages(self):
        t = self.t
        G = self.en["guides"]
        guides = self.guides
        qmap = {x["id"]: x for g in self.en["faq"]["groups"] for x in g["items"]}
        crumb_home = (t("crumb.home"), self.href(""))
        crumb_idx = (G["crumb"], self.href("guides/"))
        # index
        o = [f'<div class="phead">{self.crumbs([crumb_home, (G["crumb"], None)])}<h1 class="vh" id="h-static" tabindex="-1">{e(G["indexH1"])}</h1><p>{e(G["indexIntro"])}</p></div>']
        for grp in G["groups"]:
            items = [g for g in guides.values() if g["group"] == grp["id"]]
            if not items:
                continue
            li = "".join(f'<li><a href="{self.href("guides/" + g["slug"] + "/")}">{e(g["h1"])}</a><br><span class="note">{e(g["lede"])}</span></li>' for g in sorted(items, key=lambda g: g.get("order", 99)))
            o.append(f'<section class="psec"><h2>{e(grp["h"])}</h2><ul class="muni-list">{li}</ul></section>')
        o.append(f'<section class="psec"><h2>{e(G["moreH"])}</h2><ul class="muni-list"><li><a href="{self.href("questions/")}">{e(G["toQuestions"])}</a></li><li><a href="{self.href("")}">{e(G["toRoute"])}</a></li><li><a href="{self.href("system/")}">{e(G["toSystem"])}</a></li></ul></section>')
        bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
              {"@type": "ListItem", "position": 2, "name": G["crumb"], "item": self.canon("guides/")}]
        page = {"rel": "guides/", "view": "static", "tab": None, "title": G["indexTitle"], "desc": G["indexDesc"],
                "jsonld": [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}], "slots": {"static": "".join(o)}}
        self.write("guides/", self.page(page))
        self.sitemap["pages"].append("guides/")
        # one page per guide
        for g in guides.values():
            rel = f"guides/{g['slug']}/"
            o = [f'<div class="phead">{self.crumbs([crumb_home, crumb_idx, (g["h1"], None)])}<h1 class="vh" id="h-static" tabindex="-1">{e(g["h1"])}</h1>'
                 f'<p class="lede">{self.grich(g["lede"])}</p><p class="note">{e(G["checked"].format(date=fmt_day(g["checked"])))}</p></div>']
            secs = g["sections"]
            if len(secs) >= 4:
                toc = "".join(f'<li><a href="#{e(s["id"])}">{e(s["h"])}</a></li>' for s in secs)
                o.append(f'<nav class="psec gtoc" aria-label="{e(G["toc"])}"><h2>{e(G["toc"])}</h2><ol>{toc}</ol></nav>')
            for s in secs:
                assert re.fullmatch(r"[a-z0-9-]+", s["id"]), ("section id", g["slug"], s["id"])
                o.append(f'<section class="psec qa" id="{e(s["id"])}"><h2>{e(s["h"])}</h2>{self.guide_blocks(s["blocks"])}</section>')
            src = "".join(f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["label"])}</a></li>' for x in g["sources"])
            o.append(f'<section class="psec"><h2>{e(G["sourcesH"])}</h2><p class="note">{e(G["sourcesNote"])}</p><ul class="srclist">{src}</ul></section>')
            rel_li = [f'<li><a href="{self.href("guides/" + r + "/")}">{e(guides[r]["h1"])}</a></li>' for r in g.get("related_guides", []) if r in guides]
            for q in g.get("related_questions", []):
                href = self.href(f"questions/{q}/") if q in self.faq_page_ids else self.href(f"questions/#{q}")
                rel_li.append(f'<li><a href="{e(href)}">{e(qmap[q]["q"])}</a></li>')
            for k in g.get("links", []):
                rel_li.append(f'<li><a href="{e(self.href(self.SITE_LINKS[k]))}">{e(t("faq.page.l." + k))}</a></li>')
            rel_li.append(f'<li><a href="{self.href("guides/")}">{e(G["all"])}</a></li>')
            o.append(f'<section class="psec"><h2>{e(G["next"])}</h2><ul class="muni-list">{"".join(rel_li)}</ul></section>')
            bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
                  {"@type": "ListItem", "position": 2, "name": G["crumb"], "item": self.canon("guides/")},
                  {"@type": "ListItem", "position": 3, "name": g["h1"], "item": self.canon(rel)}]
            art = {"@context": "https://schema.org", "@type": "Article", "headline": g["h1"], "description": g["desc"], "inLanguage": self.langs[0],
                   "dateModified": g["checked"], "mainEntityOfPage": self.canon(rel),
                   "publisher": {"@type": "Organization", "name": self.brand, "url": self.canon("")}}
            page = {"rel": rel, "view": "static", "tab": None, "title": g["title"], "desc": g["desc"],
                    "jsonld": [art, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}], "slots": {"static": "".join(o)}}
            self.write(rel, self.page(page))
            self.sitemap["pages"].append(rel)

    # ------------------------------------------------------------ sources (port of renderSources)
    def sources_html(self):
        t = self.t
        m = self.meta
        o = []
        o.append(f'<div class="psec"><h2>{e(t("sources.check.title"))}</h2><p>{e(t("sources.check.text", date=fmt_day(self.last_checked)))}</p></div>')
        o.append(f'<div class="psec"><h2>{e(t("sources.read.title"))}</h2>' + "".join(f"<p>{e(x)}</p>" for x in self.en["sources"]["read"]["items"]) + "</div>")
        d = [f'<div class="psec"><h2>{e(t("sources.data.title"))}</h2>']
        att = m.get("attribution")
        if att:
            d.append(f'<p>{e(t("sources.dataline", built=m.get("generated", ""), pupils=self.data_year("po_pupils")[1], advice=self.data_year("po_advice")[0], exams=self.data_year("vo_exams")[0]))}</p>')
        d.append('<ul class="srclist">')
        li = [e(t("attr.feat.lead")) + " "]
        for i, (k, url, lic) in enumerate(self.feat_attr):
            if i:
                li.append(", ")
            li.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{e(t("attr.l." + k))}</a>')
            if lic:
                li.append(e(" (" + lic + ")"))
        li.append(" " + e(t("attr.feat.tail")))
        d.append("<li>" + "".join(li) + "</li>")
        if att:
            for a in att:
                d.append(f'<li>{e(a["text"] + " " + t("attr.licence", licence=a["licence"]) + " ")}<a href="{e(a["licence_url"])}" target="_blank" rel="noopener">{e(t("attr.licenceLink"))}</a> · <a href="{e(a["url"])}" target="_blank" rel="noopener">{e(t("attr.sourceLink"))}</a></li>')
            d.append("</ul>")
            if m.get("disclaimer"):
                d.append(f'<p>{e(m["disclaimer"])}</p>')
        else:
            d.append(f'<li>{e(t("attr.fallback"))}</li></ul><p>{e(t("attr.fallbackDisc"))}</p>')
        d.append(f'<p>{e(t("sources.sodk"))}</p></div>')
        o.append("".join(d))
        # blocks
        b = [f'<div class="psec"><h2>{e(t("sources.blocks.title"))}</h2><p>{e(t("sources.blocks.intro"))}</p><ul class="srclist">' + "".join(f"<li>{e(x)}</li>" for x in self.en["sources"]["blocks"]["items"]) + "</ul>"]
        c = m.get("counts") or {}
        if isinstance(c.get("schools_po"), int):
            b.append(f'<p>{e(t("sources.counts.schools", po=c["schools_po"] - (c.get("schools_po_sbo") or 0), sbo=c.get("schools_po_sbo") or 0, so=c.get("schools_so") or 0, vo=c.get("schools_vo") or 0))}</p>')
        I = self.insp
        k = I.get("counts") or {}
        if isinstance(k.get("listed"), int):
            by = ""
            bo = k.get("by_o")
            if isinstance(bo, dict):
                by = ", ".join(f"{j} {nf(bo[j])}" for j in ["Goed", "Voldoende", "Onvoldoende", "Zwak", "Zeer zwak"] if isinstance(bo.get(j), int))
            txt = t("sources.counts.insp", listed=k["listed"], rated=k["rated"], none=k["geen_eindoordeel"], basic=k["basistoezicht"], asof=I.get("as_of", "")) + (" " + t("sources.counts.by", by=by) if by else "")
            b.append(f"<p>{e(txt)}</p>")
            links = []
            if self.safe_url(I.get("source_url")):
                links.append(f'<a href="{e(I["source_url"])}" target="_blank" rel="noopener">{e(t("sources.insp.file"))}</a>')
            if self.safe_url(I.get("notes_url")):
                links.append(f'<a href="{e(I["notes_url"])}" target="_blank" rel="noopener">{e(t("sources.insp.notes"))}</a>')
            if links:
                b.append('<p class="dsrc">' + " · ".join(links) + "</p>")
        b.append("</div>")
        o.append("".join(b))
        lst = "".join(f'<li><a href="{e(self.src_url[k])}" target="_blank" rel="noopener">{e(t("src." + k))}</a></li>' for k in self.src_order)
        o.append(f'<div class="psec"><h2>{e(t("sources.list.title"))}</h2><ul class="srclist">{lst}</ul></div>')
        return "".join(o)

    # ------------------------------------------------------------ home links
    def province_tops(self):
        by = {}
        for s in self.schools:
            if not s["mun"] or not s["provN"]:
                continue
            by.setdefault((s["provN"], s["mun"]), []).append(s)
        best = {}
        for (prov, mun), lst in by.items():
            n = len(lst)
            if prov not in best or n > best[prov][1] or (n == best[prov][1] and mun < best[prov][0]):
                best[prov] = (mun, n)
        return sorted((p, m, n) for p, (m, n) in best.items())

    def home_links(self, tops):
        t = self.t
        o = [f'<h3>{e(t("home.linksTitle"))}</h3><p>{e(t("home.linksIntro"))}</p><ul class="provs">']
        for prov, mun, n in tops:
            o.append(f'<li><a href="{self.href("municipality/" + self.mslug[mun] + "/")}">{e(mun)}<small>{e(prov)}</small></a></li>')
        o.append("</ul>")
        il = " &middot; ".join(f'<a href="{self.href("international/" + k + "/")}">{e(c["name"])}</a>' for k, c in self.intl["cities"].items())
        o.append(f'<h3>{e(t("home.intlTitle"))}</h3><p>{e(t("home.intlIntro"))} {il}</p>')
        if self.guides:
            gl = " &middot; ".join(f'<a href="{self.href("guides/" + k + "/")}">{e(g["h1"])}</a>' for k, g in sorted(self.guides.items(), key=lambda kv: kv[1].get("home", 99)) if g.get("home"))
            o.append(f'<h3>{e(t("home.guidesTitle"))}</h3><p>{gl}{" &middot; " if gl else ""}<a href="{self.href("guides/")}">{e(t("home.guidesAll"))}</a></p>')
        o.append(f'<p><a href="{self.href("municipalities/")}">{e(t("home.linksAll"))}</a> &middot; <a href="{self.href("find/")}">{e(t("home.linksFind"))}</a> &middot; <a href="{self.href("questions/")}">{e(t("home.linksQuestions"))}</a></p>')
        return "".join(o)

    # ------------------------------------------------------------ school page
    def school_page(self, s, near):
        t = self.t
        sec = s["sec"]
        grp = "vo" if sec == "vo" else "so" if sec == "so" else "po"
        den = self.den_label(s["denNl"])
        slug = school_slug(s)
        rel = f"school/{slug}/"
        pc = s["pc"]
        pc_fmt = (pc[:4] + " " + pc[4:]) if pc and len(pc) == 6 else (pc or "")
        typ = t("seo.type." + sec)
        k1 = (s["name"], s["city"], s["sec"])
        dup = self.tcount[k1] > 1 and bool(s["addr"])
        addr_t = self.title_addr(s)
        title, og_title = self.title_pre[s["id"]]
        det = (self.det_vo if grp == "vo" else self.det_po)["schools"].get(s["id"]) if grp != "so" else None
        pur = {"po": "po_pupils", "sbo": "po_pupils", "vo": "vo_pupils", "so": "so_pupils"}[sec]
        pup_range, pup_date = self.data_year(pur)
        # --- description
        if s["pupils"] is None or (s["pupils"] == 0 and s["pupils_lb"]):
            pup_txt = None
        else:
            ptxt = t("pupils.atLeast" if s["pupils_lb"] else "pupils.about", n=s["pupils"])
            pup_txt = ptxt[0].upper() + ptxt[1:] + "."
        opts = []
        if pup_txt:
            opts.append(pup_txt)
        opts.append(t("seo.desc.den", den=den))
        if sec == "vo":
            names = self.track_names(s)
            if names:
                opts.insert(1, t("seo.desc.tracks", tracks=", ".join(names)))
        if sec == "so":
            cl = s.get("cls") or ([s["cl"]] if s.get("cl") is not None else [])
            if cl:
                opts.insert(1, t("seo.desc.cluster", cluster=" and ".join(t(f"so.cl.{c}.chip") for c in cl)))
        base = t("seo.desc.school" if s["city"] else "seo.desc.schoolNoCity", name=s["name"], type=typ, city=s["city"], prov=s["provN"])
        if not s["provN"]:
            base = base.replace(" ()", "").replace("()", "")
        if dup:
            # same name in the same town: the address tells the pages apart, so it is never dropped;
            # two school codes at one address also get the code, as the title does
            base += " " + t("seo.desc.addr", addr=s["addr"])
            if self.tcount[k1 + (s["addr"],)] > 1:
                base += " " + t("seo.desc.code", code=s["id"])
        if len(base) > 156:
            nm = s["name"]
            cut = nm[: max(20, len(nm) - (len(base) - 150))].rsplit(" ", 1)[0] + "..."
            base = base.replace(nm, cut)
        desc = self.fit(base, opts, self.en["seo"]["desc"]["tail"])

        # --- phead
        mrel = f"municipality/{self.mslug[s['mun']]}/" if s["mun"] else None
        crumbs = [(t("crumb.home"), self.href(""))]
        if mrel:
            crumbs.append((s["mun"], self.href(mrel)))
        crumbs.append((s["name"], None))
        ph = ['<div class="phead">', self.crumbs(crumbs)]
        ph.append(f'<a class="back" href="{self.href("find/")}">{e(t("school.back"))}</a>')
        ph.append(f'<div class="when">{e(t("sec.long." + sec))}</div>')
        ph.append(f'<h1 id="h-school" tabindex="-1">{e(s["name"])}</h1>')
        if sec == "so":
            tg = ""
            if s.get("so_type"):
                tg += f'<span class="tr t-so">{e(s["so_type"])}</span>'
            for c in (s.get("cls") or ([s["cl"]] if s.get("cl") is not None else [])):
                tg += f'<span class="tr t-socl">{e(t(f"so.cl.{c}.chip"))}</span>'
            ph.append(f'<div style="margin:0 0 6px">{tg}</div>')
        addr = ", ".join(x for x in [s["addr"], " ".join(x for x in [pc_fmt, s["city"]] if x), t("school.municipality", mun=s["mun"]) if s["mun"] and s["mun"] != s["city"] else None] if x)
        ph.append(f'<p class="addr">{e(addr)}</p>')
        isk = bool(sec == "vo" and (re.search(r"\bISK\b|schakelklas|internationale schakel", s["name"], re.I) or s.get("st") == "BRUGJAAR"))
        ph.append(f'<p style="margin:0 0 6px">{e(t("school.denom", den=den) + (t("school.isk") if isk else ""))}</p>')
        ph.append(self.feat_chips(s["id"]))
        lk = ['<div class="lk">']
        if sec != "so":
            q = re.sub(r"\s+", " ", (s["name"] + " " + s["city"])).strip()
            from urllib.parse import quote
            lk.append(f'<a href="https://scholenopdekaart.nl/zoeken/{"basisscholen" if grp == "po" else "middelbare-scholen"}?zoektermen={quote(q, safe="")}&amp;weergave=Lijst" target="_blank" rel="noopener">{e(t("link.sodk"))}</a>')
        w = self.safe_web(s["web"])
        if w:
            lk.append(f'<a href="{e(w)}" target="_blank" rel="noopener">{e(t("link.site"))}</a>')
        if s["g"] != 3 and s["lat"] is not None:
            lk.append(f'<a href="{self.href("map/?s=" + s["id"])}">{e(t("school.showMap"))}</a>')
        lk.append("</div>")
        ph.append("".join(lk))
        if 0 < s["g"] < 3:
            ph.append(f'<p class="note">{e(t("school.approx"))}</p>')
        ph.append("</div>")

        def psec(title, expl, kids, src=None):
            o = [f'<section class="psec"><h2>{e(title)}</h2>']
            if expl:
                o.append(f'<p class="expl"><b>{e(t("prof.whatMeans"))}</b>{e(expl)}</p>')
            o.extend(kids)
            if src:
                o.append(f'<p class="dsrc">{e(src)}</p>')
            o.append("</section>")
            return "".join(o)

        def duo_src(what_key, rng, date):
            return t("prof.duoSrc", what=t(what_key)) + ((": " + (rng or "") + ((" " + t("prof.counted", date=date)) if date else "")) if (rng or date) else "") + "."

        secs = []
        # pupils
        small = s["pupils"] == 0 and bool(s["pupils_lb"])  # every cell suppressed: no total exists
        big = t("prof.pupils.notShown") if s["pupils"] is None else t("prof.pupils.bigSmall") if small else (t("prof.pupils.bigAtLeast", n=s["pupils"]) if s["pupils_lb"] else nf(s["pupils"]))
        pk = [f'<div class="big">{e(big)}</div>']
        note = t("prof.pupils.noCount") if s["pupils"] is None else t("prof.pupils.smallNote") if small else t("prof.pupils.total") + ((" " + t("prof.pupils.hiddenNote")) if s["pupils_lb"] else "")
        pk.append(f'<p class="note" style="margin-top:4px">{e(note)}</p>')
        secs.append(psec(t("prof.pupils.title"), t("prof.pupils.expl"), pk, duo_src("prof.pupils.srcWhat", pup_range, pup_date)))
        if sec == "vo":
            kids = []
            tb = self.track_badges(s)
            kids.append(f"<div>{tb or '<span class=\"note\">' + e(t('prof.levels.none')) + '</span>'}</div>")
            if s.get("st"):
                kids.append(f'<p class="note">{e(t("prof.levels.st", st=s["st"]))}</p>')
            rng, date = self.data_year("vo_pupils")
            secs.append(psec(t("prof.levels.title"), t("prof.levels.expl"), kids, duo_src("prof.levels.srcWhat", rng, date) + " " + t("prof.levels.fromPupilFile")))
            # latest pass rate per track
            kids = []
            pr = (det or {}).get("pr") if det else None
            order = ["PRO", "VMBO-B", "VMBO-K", "VMBO-GL/TL", "HAVO", "VWO", "BRUGJAAR"]
            tkmap = {"PRO": ("pro", "pro"), "VMBO-B": ("bb", "bb"), "VMBO-K": ("kb", "kb"), "VMBO-GL/TL": ("gt", "tl"), "HAVO": ("havo", "havo"), "VWO": ("vwo", "vwo"), "BRUGJAAR": ("bridge", "ib")}
            passrows = []
            if pr:
                for k in order:
                    arr = pr.get(k)
                    if not arr:
                        continue
                    row = sorted(arr, key=lambda r: str(r[0]))[-1]
                    nm, cl = tkmap[k]
                    passrows.append((nm, cl, row))
                for nm, cl, row in passrows:
                    if row[2] is None:
                        txt = t("prof.pass.few")
                    else:
                        txt = t("exam.rowPass", pct=jr(row[2]), n=row[1]) + ((" " + t("prof.pass.partial")) if len(row) > 3 and row[3] else "") + ((" " + t("prof.pass.small")) if row[1] is not None and row[1] < 30 else "")
                    kids.append(f'<div><span class="tr t-{cl}">{e(t("tk." + nm))}</span> {e(t("prof.pass.year", y=str(row[0])))}: {e(txt)}</div>')
            elif s.get("exam"):
                for ex in s["exam"]:
                    if ex[1] is None:
                        rest = t("exam.hidden")
                    elif ex[1] < 30:
                        rest = t("exam.few", n=ex[1]) + (t("exam.partial") if ex[3] else "")
                    else:
                        rest = t("exam.pass", pct=jr(ex[2]), n=ex[1]) + (t("exam.partial") if ex[3] else "")
                    bd = t("badge." + ex[0]) if self.t.has("badge." + ex[0]) else ex[0]
                    kids.append(f'<div><span class="tr t-{ex[0]}">{e(bd)}</span> {e(rest)}</div>')
            rng, date = self.data_year("vo_exams")
            if kids:
                secs.append(psec(t("prof.pass.title"), t("prof.pass.expl"), kids, duo_src("prof.pass.srcWhat", rng, date)))
            else:
                secs.append(psec(t("prof.pass.title"), t("prof.pass.explShort"), [f'<p class="note">{e(t("prof.pass.none"))}</p>'], duo_src("prof.pass.srcWhat", rng, date)))
        elif sec in ("po", "sbo"):
            if sec == "po":
                rng, date = self.data_year("po_advice")
                secs.append(psec(t("prof.advice.title"), t("prof.advice.expl"), [self.advice_block(s["adv"])], duo_src("prof.advice.srcWhat", rng, date)))
            else:
                secs.append(psec(t("prof.sbo.title"), t("prof.sbo.text"), [], None))
        else:
            kv = []
            cls = s.get("cls") or ([s["cl"]] if s.get("cl") is not None else [])
            sot = s.get("so_type")
            kv.append((t("prof.so.type"), t("so.type." + ("both" if sot == "SO/VSO" else "vso" if sot == "VSO" else "so"))))
            kv.append((t("prof.so.cluster"), " · ".join(t(f"so.cl.{c}.name") for c in cls) if cls else t("prof.so.clusterNone")))
            kvh = '<div class="kv stack">' + "".join(f'<div class="r"><span>{e(a)}</span><span>{e(b)}</span></div>' for a, b in kv) + "</div>"
            dl = ""
            if cls:
                dl = '<dl class="dl">' + "".join(f'<dt>{e(t(f"so.cl.{c}.name"))}</dt><dd>{e(t(f"so.cl.{c}.desc"))}</dd>' for c in cls) + "</dl>"
            secs.append(psec(t("prof.so.title"), t("prof.so.expl"), [kvh, dl], None))
        # inspection
        secs.append(self.insp_section(s, psec))
        # nearby
        if near:
            li = []
            for o, d in near:
                sub = " · ".join(x for x in [o["city"], self.den_label(o["denNl"])] if x)
                dist = t("unit.lessThanOne") if d < 1 else (nf1(d) if d < 10 else nf(jr(d)))
                li.append(f'<li><div class="nbn"><a href="{self.href("school/" + school_slug(o) + "/")}">{e(o["name"])}</a><div class="note" style="margin:0">{e(sub)}</div></div><span class="d">{e(t("unit.km", n=dist))}</span></li>')
            secs.append(psec(t("prof.nb.title." + sec), t("prof.nb.expl"), ['<ul class="nb-list">' + "".join(li) + "</ul>"], t("prof.nb.src")))
        main = "".join(ph) + '<div class="pgrid">' + "".join(secs) + "</div>" + f'<p class="note">{e(t("school.note"))}</p>'

        # --- json-ld
        ldtype = {"po": "ElementarySchool", "sbo": "ElementarySchool", "vo": "HighSchool", "so": "School"}[sec]
        ld = {"@context": "https://schema.org", "@type": ldtype, "name": s["name"], "url": self.canon(rel)}
        adr = {"@type": "PostalAddress", "addressCountry": "NL"}
        if s["addr"]:
            adr["streetAddress"] = s["addr"]
        if pc_fmt:
            adr["postalCode"] = pc_fmt
        if s["city"]:
            adr["addressLocality"] = s["city"]
        if s["provN"]:
            adr["addressRegion"] = s["provN"]
        ld["address"] = adr
        if s["g"] is not None and s["g"] < 2 and s["lat"] is not None:
            ld["geo"] = {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]}
        if w:
            ld["sameAs"] = [w]
        bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")}]
        pos = 2
        if mrel:
            bl.append({"@type": "ListItem", "position": pos, "name": s["mun"], "item": self.canon(mrel)})
            pos += 1
        bl.append({"@type": "ListItem", "position": pos, "name": s["name"], "item": self.canon(rel)})
        bcl = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}
        return {
            "rel": rel, "view": "school", "tab": "find", "title": title, "og_title": og_title, "desc": desc, "jsonld": [ld, bcl],
            "slots": {"school": main, "schoolattrs": f' data-static="{e(s["id"])}"'},
        }

    TITLE_MAX = 65

    def title_addr(self, s):
        k1 = (s["name"], s["city"], s["sec"])
        if self.tcount[k1] > 1 and s["addr"]:
            return s["addr"] + (f" ({s['id']})" if self.tcount[k1 + (s["addr"],)] > 1 else "")
        return ""

    def precompute_titles(self):
        """<title> of every school page; titles that came out equal after shortening get the school code added."""
        self.title_pre = {}
        seen = {}
        for s in self.schools:
            self.title_pre[s["id"]] = self.school_titles(s["name"], self.t("seo.type." + s["sec"]), s["city"], self.title_addr(s))
            seen.setdefault(self.title_pre[s["id"]][0], []).append(s)
        for lst in seen.values():
            if len(lst) > 1:
                for s in lst:
                    a = self.title_addr(s)
                    a = a if f"({s['id']})" in a else (a + " " if a else "") + f"({s['id']})"
                    self.title_pre[s["id"]] = self.school_titles(s["name"], self.t("seo.type." + s["sec"]), s["city"], a)

    def school_titles(self, name, typ, city, addr):
        """(<title>, og:title). og:title is the long form with the brand. <title> drops the brand when the long form is
        longer than TITLE_MAX, then the 'school in' wording, then shortens the name at a word boundary (same rule as schoolTitle in app.js)."""
        t = self.t
        suffix = "Addr" if addr else ("" if city else "NoCity")
        v = {"name": name, "type": typ, "city": city, "addr": addr}
        long = t("title.school" + suffix, **v)
        if len(long) <= self.TITLE_MAX:
            return long, long
        plain = t("title.school" + suffix + "Plain", **v)
        if len(plain) <= self.TITLE_MAX:
            return plain, long
        short = t("title.school" + suffix + "Short", **v)
        if len(short) > self.TITLE_MAX:
            over = len(short) - self.TITLE_MAX
            keep = max(20, len(name) - over - 3)
            if keep < len(name):
                v["name"] = name[:keep].rsplit(" ", 1)[0].rstrip(",;: ") + "..."
                short = t("title.school" + suffix + "Short", **v)
        return short, long

    def track_names(self, s):
        tr = s.get("tracks") or 0
        names = []
        if tr & 1:
            names.append(self.t("tk.pro"))
        if tr & 2:
            names.append(self.t("tk.bb"))
        if tr & 4:
            names.append(self.t("tk.kb"))
        if tr & 24:
            names.append(self.t("tk.gt"))
        if tr & 32:
            names.append(self.t("tk.havo"))
        if tr & 64:
            names.append(self.t("tk.vwo"))
        return names

    def track_badges(self, s):
        t = self.t
        tr = s.get("tracks") or 0
        defs = [("pro", 1), ("bb", 2), ("kb", 4), ("gl", 8), ("tl", 16), ("havo", 32), ("vwo", 64), ("gym", 128), ("ib", 512), ("ess", 1024)]
        out = "".join(f'<span class="tr t-{k}">{e(t("badge." + k))}</span>' for k, b in defs if tr & b)
        groups = (1 if tr & 30 else 0) + (1 if tr & 32 else 0) + (1 if tr & 64 else 0)
        if groups >= 2:
            out += f'<span class="broad">{e(t("broad", n=groups))}</span>'
        return out

    def advice_block(self, a):
        t = self.t
        if not a or not a[2] or a[0] < 15 or a[1] > 6:
            txt = t("adv.hidden", n=a[0], hidden=a[1]) if a and a[0] > 0 else t("adv.none")
            return f'<div class="adv"><p class="advn">{e(txt)}</p></div>'
        sh = a[2]
        # Same segments as SEG in app.js. Shares are of the pupils DUO shows, so they add up to 100%.
        seg = [("vso", [0]), ("pro", [1]), ("vbk", [2, 3, 4]), ("vgt", [5, 6]), ("havo", [7, 8]), ("vwo", [9, 10]), ("nap", [11])]
        parts = []
        bar = []
        for k, idx in seg:
            v = sum((sh[i] or 0) for i in idx)
            if v > 0:
                bar.append(f'<i class="a-{k}" style="width:{num(round(v, 6))}%"></i>')
                parts.append((k, t("adv.part", label=t("seg." + k), pct=jr(v))))
        summ = t("sep.list").join(p for _, p in parts)
        leg = "".join(f'<li><i class="sw a-{k}"></i>{e(p)}</li>' for k, p in parts)
        note = f'<p class="advn">{e(t("adv.smallNote"))}</p>' if a[1] > 0 else ""
        return (f'<div class="adv"><div class="advh">{e(t("adv.head", n=a[0]))}</div>'
                f'<div class="bar" role="img" aria-label="{e(t("adv.aria", list=summ))}">{"".join(bar)}</div>'
                f'<ul class="advleg" aria-hidden="true">{leg}</ul>{note}</div>')

    def insp_section(self, s, psec):
        t = self.t
        I = self.insp
        r = I["schools"].get(s["id"])
        sector = "VO" if s["sec"] == "vo" else "SO" if s["sec"] == "so" else "PO"
        brin = s["id"][:4]
        tpl = I.get("deeplink") or ""
        link = tpl.replace("{BRIN4}", brin).replace("{SECTOR}", sector)
        if not link.startswith("https://toezichtresultaten.onderwijsinspectie.nl/"):
            link = f"https://toezichtresultaten.onderwijsinspectie.nl/extern?code={brin}&sector={sector}"
        btn = (f'<div style="margin-top:12px"><a class="btn lnk" href="{e(link)}" target="_blank" rel="noopener">{e(t("insp.btn"))}<span class="sr"> {e(t("insp.btnNew"))}</span></a>'
               f'<p class="note">{e(t("insp.btnNote", brin=brin))}</p></div>')
        rated = ["Goed", "Voldoende", "Onvoldoende", "Zwak", "Zeer zwak"]
        warn = ["Onvoldoende", "Zeer zwak", "Zwak", "Voldoet niet"]
        kids = []
        if r and r.get("o") in rated:
            w = " warn" if r["o"] in warn else ""
            box = f'<div class="insp{w}"><b>{e(r["o"])}</b>'
            gl = (I.get("scale") or {}).get(r["o"])
            if gl:
                box += f'<div class="note" style="margin:2px 0 0">{e(gl)}</div>'
            xk = [k for k, v in (r.get("x") or {}).items() if isinstance(v, str)]
            if xk:
                box += f'<div class="note" style="margin:2px 0 0">{e(t("prof.insp.lowest"))}</div>'
            if r.get("d"):
                box += f'<div class="note" style="margin:2px 0 0">{e(t("prof.insp.dated", date=r["d"]))}</div>'
            box += "</div>"
            kids.append(box)
            if xk:
                lis = ""
                for k in xk:
                    key = re.sub(r"[^A-Za-z]", "", k)
                    nm = t("insp.prog." + key) if t.has("insp.prog." + key) else k
                    lis += f"<li><span>{e(nm)}</span><span>{e(r['x'][k])}</span></li>"
                kids.append(f'<div><b>{e(t("insp.perProg"))}</b><ul class="progs">{lis}</ul></div>')
            kids.append(btn)
            src = I.get("source", "")
            kids.append(f'<p class="dsrc">{e(t("prof.insp.source"))} {e(src)}' + (". " + e(t("prof.insp.asOf", date=I.get("as_of", ""))) if I.get("as_of") else "") + ".</p>")
        elif r and r.get("o") in ("Geen eindoordeel", "Basistoezicht"):
            gk = "basic" if r["o"] == "Basistoezicht" else "none"
            kids.append(f'<div class="insp nofinal"><b>{e(t("insp.nf." + gk + ".title"))}</b><div class="note" style="margin:4px 0 0">{e(t("insp.nf." + gk + ".expl"))}</div></div>')
            kids.append(btn)
        else:
            kids.append(f'<p>{e(t("prof.insp.none"))} <a href="https://www.onderwijsinspectie.nl/" target="_blank" rel="noopener">{e(t("prof.insp.linkText"))}</a>.</p>')
            kids.append(btn)
        return psec(t("prof.insp.title"), t("prof.insp.expl"), kids, None)

    # ------------------------------------------------------------ municipality pages
    def muni_pages(self, by_mun):
        t = self.t
        for mun, lst in sorted(by_mun.items()):
            slug = self.mslug[mun]
            rel = f"municipality/{slug}/"
            prov = max(set(s["provN"] for s in lst), key=lambda p: sum(1 for s in lst if s["provN"] == p))
            counts = {k: sum(1 for s in lst if s["sec"] == k) for k in ("po", "sbo", "vo", "so")}
            tot = sum((s["pupils"] or 0) for s in lst)
            parts = [t(f"muni.parts.{k}", n=counts[k]) for k in ("po", "sbo", "vo", "so") if counts[k]]
            plist = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
            intro = t("muni.intro", name=mun, prov=prov, n=len(lst), parts=plist)
            intro2 = t("muni.introPupils", n=tot) if tot else ""
            pcs = {}
            for s in lst:
                if s["pc"] and len(s["pc"]) >= 4:
                    pcs[s["pc"][:4]] = pcs.get(s["pc"][:4], 0) + 1
            top_pc = sorted(pcs.items(), key=lambda x: (-x[1], x[0]))[0][0] if pcs else None
            h1 = t("muni.h1", name=mun)
            cr = [(t("crumb.home"), self.href("")), (t("muni.crumbList"), self.href("municipalities/")), (mun, None)]
            o = [f'<div class="phead">{self.crumbs(cr)}<h1 class="vh" id="h-static" tabindex="-1">{e(h1)}</h1><p>{e(intro)} {e(intro2)}</p>']
            if top_pc:
                o.append(f'<p><a class="btn lnk" href="{self.href("?pc=" + top_pc)}">{e(t("muni.routeLink", pc=top_pc))}</a></p><p class="note">{e(t("muni.routeText"))}</p>')
            ik = self.intl_slug_of_mun().get(mun)
            if ik:
                o.append(f'<p><a href="{self.href("international/" + ik + "/")}">{e(t("muni.intlLink", name=self.intl["cities"][ik]["name"]))}</a></p>')
            o.append("</div>")
            for k in ("po", "sbo", "vo", "so"):
                grp = sorted((s for s in lst if s["sec"] == k), key=lambda s: (s["name"].lower(), s["id"]))
                if not grp:
                    continue
                li = []
                for s in grp:
                    if s["pupils"] is None:
                        pu = t("muni.noCount")
                    elif s["pupils"] == 0 and s["pupils_lb"]:
                        pu = t("muni.pupilsSmall")
                    else:
                        pu = t("muni.pupilsAtLeast" if s["pupils_lb"] else "muni.pupilsAbout", n=s["pupils"])
                    facts = [s["city"] + (", " + s["addr"] if s["addr"] else "") if s["city"] else s["addr"], pu]
                    if k == "vo":
                        names = self.track_names(s)
                        if names:
                            facts.append(", ".join(names))
                    if k == "so" and s.get("so_type"):
                        facts.append(s["so_type"])
                    li.append(f'<li><a href="{self.href("school/" + school_slug(s) + "/")}">{e(s["name"])}</a><span class="mt">{e(" · ".join(x for x in facts if x))}</span></li>')
                o.append(f'<section class="psec"><h2>{e(t("muni.group." + k, name=mun))}</h2><p class="expl">{e(t("muni.groupNote." + k))}</p><ul class="muni-list">{"".join(li)}</ul></section>')
            o.append(f'<p class="note">{e(t("muni.src"))}</p>')
            title = t("title.municipality", name=mun)
            base = t("seo.desc.municipality", name=mun, prov=prov, n=len(lst), parts=plist)
            desc = self.fit(base, [t("seo.desc.municipalityPad")], self.en["seo"]["desc"]["tail"])
            bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
                  {"@type": "ListItem", "position": 2, "name": t("muni.crumbList"), "item": self.canon("municipalities/")},
                  {"@type": "ListItem", "position": 3, "name": mun, "item": self.canon(rel)}]
            page = {"rel": rel, "view": "static", "tab": None, "title": title, "desc": desc,
                    "jsonld": [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}],
                    "slots": {"static": "".join(o)}}
            self.write(rel, self.page(page))
            self.sitemap["municipalities"].append(rel)

    # ------------------------------------------------------------ per-school data shards
    def write_shards(self, near, titles):
        """data/common.json (what every profile needs once) and data/s/<id[:3]>.json (all per-school data of up to ~60 schools).

        A school page or a compare view fetches common.json and the shards of the schools it shows, nothing else.
        Same per-school shapes as the pipeline files: d detail (po/vo/so), n inspection, x extra row, i inspectie_extra,
        f features, r the index row, nb the five nearest schools of the same type."""
        def top(j, drop=("schools",)):
            return {k: v for k, v in j.items() if k not in drop}

        det_of = {"po": self.det_po, "vo": self.det_vo, "so": self.det_so}
        common = {
            "v": 1,
            "det": {g: top(j) for g, j in det_of.items()},
            "extra": top(self.extra, ("schools", "boards", "swv", "fm")),
            "ix": top(self.ixd),
            "insp": top(self.insp),
            "feat": {"generated": self.feat.get("generated")},
        }
        self.write_text("data/common.json", json.dumps(common, ensure_ascii=False, separators=(",", ":")))
        shards = {}
        for s in self.schools:
            sid = s["id"]
            grp = "vo" if s["sec"] == "vo" else "so" if s["sec"] == "so" else "po"
            r = {k: v for k, v in s["_raw"].items() if v is not None and k != "den"}
            r["sec"] = s["sec"]
            r["denNl"] = s["denNl"]
            r["tt"] = titles[sid]
            o = {"r": r}
            d = det_of[grp]["schools"].get(sid)
            if d is not None:
                o["d"] = d
            for key, src in (("n", self.insp["schools"]), ("x", self.extra["schools"]), ("i", self.ixd["schools"]), ("f", self.feat["schools"])):
                if sid in src:
                    o[key] = src[sid]
            nb = near.get(sid)
            if nb:
                o["nb"] = [[x["id"], x["name"], x["city"], x["denNl"], round(d_, 3)] for x, d_ in nb]
            sh = shards.setdefault(sid[:3].lower(), {"v": 1, "s": {}, "b": {}, "w": {}, "m": {}, "p": {}})
            sh["s"][sid] = o
            for e_ in (d or {}).get("cm") or []:
                if isinstance(e_, list) and str(e_[0]) in self.pc4 and len(sh["p"]) < 100000:
                    sh["p"][str(e_[0])] = self.pc4[str(e_[0])][2]
            x = o.get("x")
            if x:
                if x[1] and x[1] in self.extra["boards"]:
                    sh["b"][x[1]] = self.extra["boards"][x[1]]
                if x[2] and x[2] in self.extra["swv"]:
                    sh["w"][x[2]] = self.extra["swv"][x[2]]
            if sid[:4] in self.extra["fm"]:
                sh["m"][sid[:4]] = self.extra["fm"][sid[:4]]
        for k, sh in sorted(shards.items()):
            for a in ("b", "w", "m", "p"):
                if not sh[a]:
                    del sh[a]
            self.write_text(f"data/s/{k}.json", json.dumps(sh, ensure_ascii=False, separators=(",", ":")))
        self.n_shards = len(shards)

    # ------------------------------------------------------------ international pages
    def intl_slug_of_mun(self):
        return {c["mun"]: k for k, c in self.intl["cities"].items()}

    def intl_pages(self, by_mun):
        t = self.t
        I = self.intl
        cities = I["cities"]
        li = "".join(f'<li><a href="{self.href("international/" + k + "/")}">{e(c["name"])}</a></li>' for k, c in cities.items())
        cr = [(t("crumb.home"), self.href("")), (t("intl.crumb"), None)]
        o = [f'<div class="phead">{self.crumbs(cr)}<h1 class="vh" id="h-static" tabindex="-1">{e(t("intl.indexH1"))}</h1><p>{e(t("intl.indexIntro"))}</p></div>',
             f'<section class="psec"><h2>{e(t("intl.indexCities"))}</h2><ul class="muni-list">{li}</ul></section>']
        bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
              {"@type": "ListItem", "position": 2, "name": t("intl.crumb"), "item": self.canon("international/")}]
        page = {"rel": "international/", "view": "static", "tab": None, "title": t("intl.indexTitle"), "desc": t("intl.indexDesc"),
                "jsonld": [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}], "slots": {"static": "".join(o)}}
        self.write("international/", self.page(page))
        self.sitemap["pages"].append("international/")
        checked = fmt_day(I["checked"])
        src_html = (f'<p class="src">{e(t("intl.source"))} <a href="{e(I["source"])}" target="_blank" rel="noopener">{e(I["source"])}</a>, {e(t("intl.checked", date=I["checked"]))}.</p>')
        for key, c in cities.items():
            name = c["name"]
            mun = c["mun"]
            rel = f"international/{key}/"
            lst = by_mun.get(mun, [])
            groups = {"tto": [], "ib": [], "international": [], "newcomer": []}
            for s in sorted(lst, key=lambda x: (x["name"].lower(), x["id"])):
                if s["sec"] == "so":
                    continue
                fl = {k for k, cf, ev in self.feat_list(s["id"])}
                tr = s.get("tracks") or 0
                isk = bool(s["sec"] == "vo" and (re.search(r"\bISK\b|schakelklas|internationale schakel", s["name"], re.I) or s.get("st") == "BRUGJAAR"))
                if s["sec"] == "vo" and "tto" in fl:
                    groups["tto"].append(s)
                if "ib" in fl or (s["sec"] == "vo" and tr & 512):
                    groups["ib"].append(s)
                if "international" in fl or (s["sec"] == "vo" and tr & 1024):
                    groups["international"].append(s)
                if "newcomer" in fl or isk:
                    groups["newcomer"].append(s)
            cr = [(t("crumb.home"), self.href("")), (t("intl.crumb"), self.href("international/")), (name, None)]
            o = [f'<div class="phead">{self.crumbs(cr)}<h1 class="vh" id="h-static" tabindex="-1">{e(t("intl.cityH1", city=name))}</h1><p>{e(t("intl.cityIntro", city=name))}</p></div>']
            opts = "".join(f'<li><b>{e(x["k"])}</b> {e(x["text"])}</li>' for x in self.en["intl"]["opt"])
            qlinks = " &middot; ".join(f'<a href="{self.href("questions/" + q + "/")}">{e(self.faq_q[q])}</a>' for q in ("dutch-international-bilingual", "without-dutch", "international-school-costs"))
            o.append(f'<section class="psec"><h2>{e(t("intl.optH"))}</h2><ul class="intl-opts">{opts}</ul><p class="note">{e(t("intl.optMore"))}: {qlinks}</p></section>')
            body = []
            for g in ("tto", "ib", "international", "newcomer"):
                if not groups[g]:
                    continue
                items = []
                for s in groups[g]:
                    lvl = t("intl.levelSecondary") if s["sec"] == "vo" else t("intl.levelPrimary")
                    facts = " · ".join(x for x in [lvl, s["addr"]] if x)
                    items.append(f'<li><a href="{self.href("school/" + school_slug(s) + "/")}">{e(s["name"])}</a><span class="mt">{e(facts)}</span></li>')
                body.append(f'<h3>{e(t("intl.grp." + g))}</h3><ul class="muni-list">{"".join(items)}</ul>')
            if not body:
                body.append(f'<p>{e(t("intl.dataEmpty", city=name))}</p>')
            o.append(f'<section class="psec"><h2>{e(t("intl.dataH", city=name))}</h2><p class="expl">{e(t("intl.dataIntro"))}</p>{"".join(body)}</section>')
            has_assoc = any(x["kind"] == "associated" for x in c["schools"])
            for kind, hk, ik in (("funded", "intl.fundedH", "intl.fundedIntro"), ("associated", "intl.assocH", "intl.assocIntro")):
                sch = [x for x in c["schools"] if x["kind"] == kind]
                if not sch:
                    continue
                items = "".join(f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["name"])}</a></li>' for x in sch)
                extra = f'<p class="note">{e(t("intl.harenNote"))}</p>' if key == "groningen" else ""
                adm = f' <a href="{e(I["source_admissions"])}" target="_blank" rel="noopener">{e(t("intl.admissions"))}</a>.' if kind == "funded" else ""
                tail = f'<p class="note">{e(t("intl.noOthers", city=name))}</p>' if kind == "funded" and not has_assoc else ""
                o.append(f'<section class="psec"><h2>{e(t(hk, city=name))}</h2><p>{e(t(ik))}{adm}</p><ul class="muni-list">{items}</ul>{extra}{src_html}{tail}</section>')
            more = [f'<li><a href="{self.href("municipality/" + self.mslug[mun] + "/")}">{e(t("intl.muniLink", name=name))}</a></li>',
                    f'<li><a href="{self.href("international/")}">{e(t("intl.allCities"))}</a></li>',
                    f'<li><a href="{self.href("find/")}">{e(t("intl.findLink"))}</a></li>',
                    f'<li><a href="{self.href("questions/")}">{e(t("intl.q"))}</a></li>']
            o.append(f'<section class="psec"><h2>{e(t("intl.moreH"))}</h2><ul class="muni-list">{"".join(more)}</ul></section>')
            title = t("intl.cityTitle", city=name)
            desc = t("intl.cityDesc", city=name)
            bl = [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")},
                  {"@type": "ListItem", "position": 2, "name": t("intl.crumb"), "item": self.canon("international/")},
                  {"@type": "ListItem", "position": 3, "name": name, "item": self.canon(rel)}]
            page = {"rel": rel, "view": "static", "tab": None, "title": title, "desc": desc,
                    "jsonld": [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": bl}], "slots": {"static": "".join(o)}}
            self.write(rel, self.page(page))
            self.sitemap["pages"].append(rel)

    # ------------------------------------------------------------ misc files
    def write_text(self, rel, txt):
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf8", newline="\n")

    def content_dates(self, rels):
        """rel -> lastmod for the content pages. build/content_dates.json (committed) holds a fingerprint and a date per page;
        a page whose fingerprint changed gets today's date and the file is rewritten (commit it with the change)."""
        import datetime
        f = ROOT / "build" / "content_dates.json"
        old = json.loads(f.read_text(encoding="utf8")) if f.is_file() else {}
        today = datetime.date.today().isoformat()
        new, out = {}, {}
        for r in rels:
            h = self.hashes[r]
            o = old.get(r)
            d = o["date"] if o and o["hash"] == h else today
            new[r] = {"hash": h, "date": d}
            out[r] = d
        if new != old and not getattr(self, "no_dates_write", False):
            f.write_text(json.dumps(new, indent=1, sort_keys=True) + chr(10), encoding="utf8", newline=chr(10))
        return out

    def sitemaps(self):
        def urlset(rels, lastmod):
            u = "".join(f"<url><loc>{e(self.canon(r))}</loc><lastmod>{lastmod[r] if isinstance(lastmod, dict) else lastmod}</lastmod></url>" for r in rels)
            return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + u + "</urlset>\n"

        pages_lm = self.content_dates(self.sitemap["pages"])
        self.write_text("sitemap-pages.xml", urlset(self.sitemap["pages"], pages_lm))
        self.write_text("sitemap-schools.xml", urlset(self.sitemap["schools"], self.generated))
        self.write_text("sitemap-municipalities.xml", urlset(self.sitemap["municipalities"], self.generated))
        idx = "".join(f"<sitemap><loc>{e(self.site_url + '/' + n)}</loc><lastmod>{lm}</lastmod></sitemap>" for n, lm in [("sitemap-pages.xml", max(pages_lm.values())), ("sitemap-schools.xml", self.generated), ("sitemap-municipalities.xml", self.generated)])
        self.write_text("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + idx + "</sitemapindex>\n")
        robots = "User-agent: *\nAllow: /\n"
        if self.indexable:
            robots += f"\nSitemap: {self.site_url}/sitemap.xml\n"
        self.write_text("robots.txt", robots)

    def favicon_ico(self):
        """32x32 route-line mark as a PNG inside an .ico (stdlib only)"""
        n = 32
        navy, yel, clear_ = (29, 78, 137, 255), (232, 220, 195, 255), (0, 0, 0, 0)
        px = [[clear_] * n for _ in range(n)]
        sc = n / 28.0

        def fill(x0, y0, x1, y1, col):
            for y in range(max(0, int(round(y0 * sc))), min(n, int(round(y1 * sc)))):
                for x in range(max(0, int(round(x0 * sc))), min(n, int(round(x1 * sc)))):
                    px[y][x] = col

        # schoolhouse with flag, roof, clock, windows and door, as in favicon.svg (rectangles only)
        red, white = (168, 131, 79, 255), (255, 255, 255, 255)
        for x0, y0, x1, y1 in ((13.4, 1, 14.6, 9), (2, 13, 26, 27), (0.5, 12, 27.5, 14), (7, 11.5, 21, 13), (9.5, 10, 18.5, 11.5), (11.5, 8.5, 16.5, 10)):
            fill(x0, y0, x1, y1, navy)
        fill(14.6, 1.5, 20, 4.7, red)
        for x0, y0, x1, y1 in ((12.5, 15, 15.5, 18), (4.5, 16, 8, 19.5), (20, 16, 23.5, 19.5), (4.5, 21.5, 8, 25), (20, 21.5, 23.5, 25), (11.5, 21.5, 16.5, 27)):
            fill(x0, y0, x1, y1, white)
        raw = b"".join(b"\x00" + b"".join(bytes(c) for c in row) for row in px)

        def chunk(tp, data):
            c = struct.pack(">I", len(data)) + tp + data
            return c + struct.pack(">I", zlib.crc32(tp + data) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
        ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", n, n, 0, 0, 1, 32, len(png), 22) + png
        (self.out / "favicon.ico").write_bytes(ico)

    # ------------------------------------------------------------ main
    def run(self):
        t = self.t
        out = self.out
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        # assets
        for f in ("app.js", "app.css", "og.png", "favicon.svg"):
            shutil.copy2(SITE / f, out / f)
        shutil.copytree(SITE / "fonts", out / "fonts")
        (out / "i18n").mkdir()
        for f in (SITE / "i18n").glob("*.json"):
            shutil.copy2(f, out / "i18n" / f.name)
        (out / "data").mkdir()
        for f in DATA.glob("*.json"):
            if f.name in SHARDED:
                continue
            shutil.copy2(f, out / "data" / f.name)
        (out / ".nojekyll").write_text("", encoding="utf8")
        if (SITE / "CNAME").is_file():
            shutil.copy2(SITE / "CNAME", out / "CNAME")
        self.favicon_ico()

        # municipalities
        by_mun = {}
        for s in self.schools:
            if s["mun"]:
                by_mun.setdefault(s["mun"], []).append(s)
        self.mslug = {}
        seen = {}
        for mun in sorted(by_mun):
            sl = slugify(mun)
            assert sl and sl not in seen, ("municipality slug clash", mun, seen.get(sl))
            seen[sl] = mun
            self.mslug[mun] = sl
        tops = self.province_tops()
        assert len(tops) == 12, tops

        D = self.en["seo"]["desc"]

        def simple(rel, view, title_key, desc, slots=None, jsonld=None, **kw):
            page = {"rel": rel, "view": view, "title": t(title_key), "desc": desc, "jsonld": jsonld or [], "slots": slots or {}}
            page.update(kw)
            self.write(rel, self.page(page))
            if kw.get("index", True) and kw.get("sitemap", True):
                self.sitemap["pages"].append(rel)

        # home
        ws = {"@context": "https://schema.org", "@type": "WebSite", "name": self.brand, "url": self.canon(""), "inLanguage": self.langs[0], "description": t("meta.description")}
        simple("", "route", "title.route", t("meta.description"), {"homelinks": self.home_links(tops)}, [ws], tab="route")
        simple("find/", "find", "title.find", D["find"], {"findout": f'<noscript><p class="note">{e(t("findStatic.noscript"))}</p></noscript><p><a href="{self.href("municipalities/")}">{e(t("home.linksAll"))}</a></p>'}, tab="find")
        simple("map/", "map", "title.map", D["map"], {"mapout": f'<noscript><p class="note">{e(t("mapStatic.noscript"))}</p></noscript><p><a href="{self.href("municipalities/")}">{e(t("home.linksAll"))}</a></p>'}, tab="map")
        simple("system/", "system", "title.system", D["system"], self.system_slots(), tab="system")
        simple("questions/", "faq", "title.faq", D["faq"], {"faq": self.faq_html()}, [self.faq_jsonld()], tab="faq")
        simple("sources/", "sources", "title.sources", D["sources"], {"sourcesout": self.sources_html()}, tab="sources")
        self.question_pages()
        if self.guides:
            self.guide_pages()
        # compare: client side, never indexed
        simple("compare/", "compare", "title.compare", D["compare"], {"compareout": f'<p>{e(t("compareStatic.text"))}</p><noscript><p class="note">{e(t("compareStatic.noscript"))}</p></noscript><p><a href="{self.href("find/")}">{e(t("home.linksFind"))}</a></p>'}, tab="find", index=False, sitemap=False)

        # municipalities index
        provs = {}
        for mun, lst in by_mun.items():
            pv = max(set(s["provN"] for s in lst), key=lambda p: sum(1 for s in lst if s["provN"] == p))
            provs.setdefault(pv, []).append((mun, len(lst)))
        o = [f'<div class="phead">{self.crumbs([(t("crumb.home"), self.href("")), (t("munis.h1"), None)])}<h1 class="vh" id="h-static" tabindex="-1">{e(t("munis.h1"))}</h1><p>{e(t("munis.intro", n=len(by_mun)))}</p></div>']
        for pv in sorted(provs):
            li = "".join(f'<li><a href="{self.href("municipality/" + self.mslug[m] + "/")}">{e(m)}</a> <span class="note">({e(t("munis.count", n=n))})</span></li>' for m, n in sorted(provs[pv], key=lambda x: x[0].lower()))
            o.append(f'<section class="psec azgrp"><h2>{e(pv)}</h2><ul class="az">{li}</ul></section>')
        pg = {"rel": "municipalities/", "view": "static", "tab": None, "title": t("title.municipalities"), "desc": D["municipalities"],
              "jsonld": [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": t("crumb.home"), "item": self.canon("")}, {"@type": "ListItem", "position": 2, "name": t("munis.h1"), "item": self.canon("municipalities/")}]}],
              "slots": {"static": "".join(o)}}
        self.write("municipalities/", self.page(pg))
        self.sitemap["pages"].append("municipalities/")

        # 404
        nf_html = (f'<div class="phead nf404"><h1 class="vh" id="h-static" tabindex="-1">{e(t("notfound.h1"))}</h1><p>{e(t("notfound.text"))}</p>'
                   f'<p id="nf-lookup">{e(t("notfound.lookup"))}</p><ul>'
                   f'<li><a href="{self.href("find/")}">{e(t("notfound.tryFind"))}</a></li><li><a href="{self.href("")}">{e(t("notfound.tryHome"))}</a></li><li><a href="{self.href("system/")}">{e(t("notfound.trySystem"))}</a></li></ul></div>')
        pg = {"rel": "404.html", "view": "static", "tab": None, "title": t("title.notFound"), "desc": D["notFound"], "canonical": False, "index": False, "jsonld": [], "slots": {"static": nf_html}}
        s404 = self.page(pg)
        self.write_text("404.html", s404)
        self.pages += 1

        # municipality pages, schools
        self.muni_pages(by_mun)
        self.intl_pages(by_mun)
        self.precompute_titles()
        near = nearest_same_type(self.schools)
        titles = {}
        for s in self.schools:
            p = self.school_page(s, near.get(s["id"], []))
            self.write(p["rel"], self.page(p))
            self.sitemap["schools"].append(p["rel"])
            titles[s["id"]] = p["title"]
        self.write_shards(near, titles)
        self.sitemaps()
        return self.pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--seo", default=str(SITE / "seo.json"))
    ap.add_argument("--no-dates", action="store_true", help="do not rewrite build/content_dates.json (for test builds)")
    a = ap.parse_args()
    b = Build(a.out, a.seo)
    b.no_dates_write = a.no_dates
    n = b.run()
    total = sum(f.stat().st_size for f in Path(a.out).rglob("*") if f.is_file())
    print(f"pages: {n}  (schools {len(b.sitemap['schools'])}, municipalities {len(b.sitemap['municipalities'])}, other {len(b.sitemap['pages'])} indexable + compare + 404)")
    print(f"_site size: {total / 1e6:.1f} MB   indexable: {b.indexable}")


if __name__ == "__main__":
    main()
