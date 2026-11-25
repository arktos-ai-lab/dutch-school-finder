#!/usr/bin/env python3
"""Education routes: validation and the Mermaid generator for data/routes.json.

data/routes.json is the one source for every route the guide shows: the arrows in the system diagram,
the "Other ways through" cards and the flowchart. build/prerender.py and site/app.js read it;
build/check_site.py runs `validate` and `check_page`. Stdlib only.

Run standalone:  python -I build/routes_lib.py   (validates data/routes.json, prints counts)
"""
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("standard", "right", "school_decides", "conditional")
SHOWN = ("diagram", "card")
TRACKS = ("bo", "pro", "vbk", "vgt", "havo", "vwo", "ib", "mbo", "hbo", "wo", "phd")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load(path=None):
    return json.loads(Path(path or ROOT / "data" / "routes.json").read_text(encoding="utf8"))


def src_urls_from_js(js):
    m = re.search(r"var SRC_URL=\{(.*?)\n\};", js, re.S)
    return dict(re.findall(r"(\w+):'([^']+)'", m.group(1)))


def validate(R, en, src_url, today=None):
    """list of problems (empty = fine). en is site/i18n/en.json, src_url the SRC_URL map of app.js."""
    P = []
    today = today or date.today().isoformat()
    stage_ids = [s["id"] for s in R.get("stages", [])]
    nodes = {}
    for n in R.get("nodes", []):
        for k in ("id", "label", "stage", "rank", "track"):
            if k not in n:
                P.append(f"node {n.get('id', '?')}: missing {k}")
        if n.get("id") in nodes:
            P.append(f"node {n['id']}: duplicate id")
        nodes[n.get("id")] = n
        if n.get("stage") not in stage_ids:
            P.append(f"node {n.get('id')}: unknown stage {n.get('stage')}")
        if n.get("track") not in TRACKS:
            P.append(f"node {n.get('id')}: unknown track {n.get('track')}")
        if not isinstance(n.get("rank"), int):
            P.append(f"node {n.get('id')}: rank must be an integer")
    for n in nodes.values():
        for ref in ("parent", "box"):
            if n.get(ref) and n[ref] not in nodes:
                P.append(f"node {n['id']}: {ref} {n[ref]} is not a node")
    groups = {g["id"] for g in en["sys"]["moves"]["groups"]}
    ids = set()
    for ed in R.get("edges", []):
        i = ed.get("id", "?")
        if i in ids:
            P.append(f"edge {i}: duplicate id")
        ids.add(i)
        for k in ("id", "from", "to", "kind", "shown", "condition", "sources", "checked"):
            if not ed.get(k):
                P.append(f"edge {i}: missing {k}")
        if ed.get("kind") not in KINDS:
            P.append(f"edge {i}: unknown kind {ed.get('kind')}")
        if ed.get("shown") not in SHOWN:
            P.append(f"edge {i}: unknown shown {ed.get('shown')}")
        for k in [ed.get("from"), ed.get("to")] + list(ed.get("via", [])):
            if k not in nodes:
                P.append(f"edge {i}: node {k} does not exist")
        srcs = ed.get("sources") or []
        if not srcs:
            P.append(f"edge {i}: no source")
        for k in srcs:
            if k not in en.get("src", {}):
                P.append(f"edge {i}: source {k} has no title in en.json src")
            if k not in src_url:
                P.append(f"edge {i}: source {k} has no URL in app.js SRC_URL")
        c = ed.get("checked", "")
        if not ISO.match(c):
            P.append(f"edge {i}: checked date {c!r} is not YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(c)
            except ValueError:
                P.append(f"edge {i}: checked date {c} is not a real date")
            if c > today:
                P.append(f"edge {i}: checked date {c} is in the future")
        if (ed.get("kind") == "standard") != (ed.get("shown") == "diagram"):
            P.append(f"edge {i}: kind standard and shown diagram must go together")
        if ed.get("shown") == "diagram":
            dg = ed.get("diagram") or {}
            if not dg.get("path") or "dashed" not in dg:
                P.append(f"edge {i}: diagram edge needs diagram.path and diagram.dashed")
            if ed.get("from") in nodes and ed.get("to") in nodes and not nodes[ed["to"]]["rank"] > nodes[ed["from"]]["rank"]:
                P.append(f"edge {i}: standard edge {ed['from']} -> {ed['to']} does not point forward in time (rank {nodes[ed['from']]['rank']} -> {nodes[ed['to']]['rank']})")
        else:
            if ed.get("group") not in groups:
                P.append(f"edge {i}: card group {ed.get('group')} is not in en.json sys.moves.groups")
    return P


def counts(R):
    return len(R["nodes"]), len(R["edges"]), dict(Counter(e["kind"] for e in R["edges"]))


def cards(R):
    return [e for e in R["edges"] if e["shown"] == "card"]


def diagram_edges(R):
    return [e for e in R["edges"] if e["shown"] == "diagram"]


def chip_nodes(R, ed):
    nd = {n["id"]: n for n in R["nodes"]}
    return [nd[k] for k in [ed["from"]] + list(ed.get("via", [])) + [ed["to"]]]


def check_page(html_text, R, en):
    """the built /system/ page must show exactly the cards and arrows of the data file"""
    P = []
    import html as H
    texts = [H.unescape(t) for t in re.findall(r'<p class="mtext">(.*?)</p>', html_text, re.S)]
    want = [e["condition"] for e in cards(R)]
    if sorted(texts) != sorted(want):
        P.append(f"system page: {len(texts)} cards on the page, {len(want)} card edges in routes.json (texts differ)")
    arrows = re.findall(r'<path class="ar(?: d)?" data-edge="([^"]+)"', html_text)
    wantA = [e["id"] for e in diagram_edges(R)]
    if sorted(arrows) != sorted(wantA):
        P.append(f"system page: diagram arrows {sorted(set(wantA) ^ set(arrows))} differ from the standard edges")
    cardids = re.findall(r'<li class="mcard" data-edge="([^"]+)"', html_text)
    if sorted(cardids) != sorted(e["id"] for e in cards(R)):
        P.append("system page: card edge ids differ from routes.json")
    return P


# ---------------------------------------------------------------- Mermaid

MM_FILL = {"bo": "#4A5A78", "pro": "#15857C", "vbk": "#CF4A1C", "vgt": "#B36B00", "havo": "#2D8A45", "vwo": "#2A62C9",
           "ib": "#5B6B86", "mbo": "#B8286F", "hbo": "#8A6100", "wo": "#6A3DB3", "phd": "#14161F"}
MM_ARROW = {"standard": "-->", "right": "==>", "school_decides": "-.->", "conditional": "-.->"}
MM_STYLE = {"standard": "stroke:#050B1F,stroke-width:2px", "right": "stroke:#1B7F3B,stroke-width:3px",
            "school_decides": "stroke:#C2570C,stroke-width:2px,stroke-dasharray:2 4", "conditional": "stroke:#6A3DB3,stroke-width:2px,stroke-dasharray:8 4"}


def _mid(i):
    return "n_" + i.replace("-", "_")


def _lab(s):
    return s.replace('"', "'")


def mermaid(R, en):
    """flowchart TB of every edge, one subgraph per stage. No leading spaces (the page shows it in a <pre>)."""
    kind_t = en["sys"]["kind"]
    nd = {n["id"]: n for n in R["nodes"]}
    used = []
    for ed in R["edges"]:
        for k in [ed["from"]] + list(ed.get("via", [])) + [ed["to"]]:
            if k not in used:
                used.append(k)
    o = ["%% Dutch School Guide: all education routes. Generated from data/routes.json, do not edit.", "flowchart TB"]
    for st in R["stages"]:
        mem = [k for k in used if nd[k]["stage"] == st["id"]]
        if not mem:
            continue
        o.append(f'subgraph s_{st["id"]}["{_lab(st["label"])}"]')
        o.append("direction TB")
        for k in mem:
            o.append(f'{_mid(k)}["{_lab(nd[k]["label"])}"]')
        o.append("end")
    styles = []
    for idx, ed in enumerate(R["edges"]):
        chain = [ed["from"]] + list(ed.get("via", [])) + [ed["to"]]
        o.append(f"%% {ed['id']}")
        for a, b in zip(chain, chain[1:]):
            o.append(f'{_mid(a)} {MM_ARROW[ed["kind"]]}|{_lab(kind_t[ed["kind"]])}| {_mid(b)}')
            styles.append(ed["kind"])
    for i, k in enumerate(styles):
        o.append(f"linkStyle {i} {MM_STYLE[k]}")
    # invisible links stack the nodes of one diagram box in a column, so the chart stays narrow
    # (added after the styled links, so the linkStyle numbers above are unaffected)
    groups = {}
    for k in used:
        groups.setdefault(nd[k].get("box") or nd[k].get("parent") or k, []).append(k)
    o.append("%% layout only")
    for mem in groups.values():
        for a, b in zip(mem, mem[1:]):
            o.append(f"{_mid(a)} ~~~ {_mid(b)}")
    for tr, col in MM_FILL.items():
        mem = [_mid(k) for k in used if nd[k]["track"] == tr]
        if mem:
            o.append(f"classDef t_{tr} fill:{col},stroke:{col},color:#FFFFFF")
            o.append(f"class {','.join(mem)} t_{tr}")
    return "\n".join(o) + "\n"


def main():
    R = load()
    en = json.loads((ROOT / "site" / "i18n" / "en.json").read_text(encoding="utf8"))
    su = src_urls_from_js((ROOT / "site" / "app.js").read_text(encoding="utf8"))
    P = validate(R, en, su)
    n, e, k = counts(R)
    print(f"routes.json: {n} nodes, {e} edges {k}")
    for p in P:
        print("PROBLEM:", p)
    return 1 if P else 0


if __name__ == "__main__":
    sys.exit(main())
