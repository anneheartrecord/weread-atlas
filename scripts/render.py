"""Render the 书房 page from the vault.

    python3 scripts/render.py --root <微信读书> [--out path]

Reads only the vault (see vault_read.py) and writes one self-contained
HTML file, `书房/index.html` by default: inline CSS, inline JS and the
data inlined as JSON. The only outside requests the page makes are the
font stylesheets and the book covers. The page follows the system's
light or dark preference; there are no themes to pick.

The knowledge ring is laid out here rather than in the browser, so its
geometry can be tested: domains are arcs of one circle, topics are dots on
it, and relations between topics are curves across the inside.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_read import UNSORTED, read_vault  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_TITLE = "书脉"
MAX_HIGHLIGHTS = 10
MAX_THOUGHTS = 5


# ---------------------------------------------------------------- selection


def excluded(text: str, fragments: Sequence[str]) -> bool:
    return any(f and f in text for f in fragments)


_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_END = "。！？…”」』.!?\"'"


def highlight_score(text: str, has_thought: bool) -> float:
    """Higher is better. Favors whole sentences of readable length."""
    n = len(text)
    if n < 6:
        s = 0.05
    elif n < 16:
        s = 0.35 + 0.65 * (n - 6) / 10
    elif n <= 90:
        s = 1.0
    elif n <= 200:
        s = 1.0 - 0.5 * (n - 90) / 110
    else:
        s = 0.4
    letters = len(_CJK.findall(text)) + len(re.findall(r"[A-Za-z]", text))
    if n and letters / n < 0.5:
        s *= 0.5
    if text.rstrip()[-1:] in _END:
        s += 0.1
    if has_thought:
        s += 0.5
    return s


def thought_score(text: str, has_quote: bool) -> float:
    n = len(text)
    if n < 4:
        s = 0.1
    elif n < 12:
        s = 0.5 + 0.5 * (n - 4) / 8
    elif n <= 160:
        s = 1.0
    else:
        s = 0.7
    return s + (0.2 if has_quote else 0.0)


def pick_spread(items: List[Any], scores: List[float], k: int) -> List[Any]:
    """Pick up to k items: split the list into k equal stretches and take the
    best of each, so picks cover the whole book. Keeps the original order."""
    n = len(items)
    if n <= k:
        return list(items)
    chosen = []
    for b in range(k):
        lo, hi = (b * n) // k, ((b + 1) * n) // k
        best = max(range(lo, hi), key=lambda i: (scores[i], -i))
        chosen.append(best)
    return [items[i] for i in sorted(chosen)]


def book_items(book: Dict[str, Any], fragments: Sequence[str]):
    """(highlights, thoughts) in book order with exclusions applied."""
    hls, ths = [], []
    seen = set()
    for ch in book["chapters"]:
        for h in ch["highlights"]:
            text = h["text"].strip()
            hidden = excluded(text, fragments)
            visible_thoughts = [t for t in h["thoughts"] if t.strip() and not excluded(t, fragments)]
            for t in visible_thoughts:
                # An excluded highlight never leaks through a thought's quote.
                ths.append({"text": t.strip(), "quote": "" if hidden else text})
            if not text or hidden or text in seen:
                continue
            seen.add(text)
            hls.append({"text": text, "thought": bool(visible_thoughts)})
    for o in book["orphanThoughts"]:
        t, q = o["text"].strip(), (o.get("quote") or "").strip()
        if t and not excluded(t, fragments):
            ths.append({"text": t, "quote": "" if excluded(q, fragments) else q})
    return hls, ths


# --------------------------------------------------------------------- data


def _num(v: Any, default: float = 0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def clean_stats(stats: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stats:
        return None
    out = {
        "generatedAt": str(stats.get("generatedAt") or ""),
        "since": str(stats.get("since") or ""),
        "totalHours": _num(stats.get("totalHours")),
        "readDays": _num(stats.get("readDays")),
        "readBooks": _num(stats.get("readBooks")),
        "finishedBooks": _num(stats.get("finishedBooks")),
        "notes": _num(stats.get("notes")),
        "years": [],
        "months": [],
        "hourly": [],
        "categories": [],
    }
    for y in stats.get("years") or []:
        if isinstance(y, dict) and y.get("year") is not None:
            out["years"].append({
                "year": int(_num(y.get("year"))),
                "hours": _num(y.get("hours")),
                "days": int(_num(y.get("days"))),
                "finished": int(_num(y.get("finished"))),
            })
    for m in stats.get("months") or []:
        if isinstance(m, dict) and re.match(r"^\d{4}-\d{2}$", str(m.get("month", ""))):
            out["months"].append({"month": m["month"], "hours": _num(m.get("hours"))})
    out["months"].sort(key=lambda m: m["month"])
    hourly = {int(_num(h.get("hour"), -1)): _num(h.get("hours")) for h in stats.get("hourly") or [] if isinstance(h, dict)}
    if hourly:
        out["hourly"] = [{"hour": h, "hours": hourly.get(h, 0.0)} for h in range(24)]
    for c in stats.get("categories") or []:
        if isinstance(c, dict) and c.get("name"):
            out["categories"].append({"name": str(c["name"]), "hours": _num(c.get("hours")), "count": int(_num(c.get("count")))})
    out["categories"].sort(key=lambda c: -c["hours"])
    out["years"].sort(key=lambda y: y["year"])
    return out


def build_page_data(vault: Dict[str, Any]) -> Dict[str, Any]:
    fragments = vault["config"]["exclude"]
    hidden = set(vault["config"].get("hideBooks") or [])
    books = [b for b in vault["books"] if b["file"] not in hidden]
    # A topic whose books are all hidden would only describe them, so it leaves the page;
    # the others keep only their shown books, and their hours are recounted over those.
    topics = []
    for t in vault["topics"]:
        if t["books"] and all(f in hidden for f in t["books"]):
            continue
        if any(f in hidden for f in t["books"]):
            t = dict(t, books=[f for f in t["books"] if f not in hidden],
                     hours=round(sum(b["hours"] for b in books if b["file"] in t["books"]), 1))
        topics.append(t)
    # Domain totals are recounted over the shown books and topics, so a hidden book leaves
    # no trace in a domain's count or hours.
    domains = []
    for d in vault["domains"]:
        dbooks = [b for b in books if d["name"] in b["domains"]]
        dtopics = sum(1 for t in topics if t["domain"] == d["name"])
        if dbooks or dtopics:
            domains.append(dict(d, books=len(dbooks), hours=round(sum(b["hours"] for b in dbooks), 1), topics=dtopics))
    book_idx = {b["file"]: i for i, b in enumerate(books)}
    title_idx = {b["title"]: i for i, b in enumerate(books)}
    topic_idx = {t["name"]: i for i, t in enumerate(topics)}

    def ref(name: str) -> Optional[int]:
        i = book_idx.get(name)
        return title_idx.get(name) if i is None else i

    page_books = []
    for b in books:
        hls, ths = book_items(b, fragments)
        hl_pick = pick_spread(hls, [highlight_score(h["text"], h["thought"]) for h in hls], MAX_HIGHLIGHTS)
        th_pick = pick_spread(ths, [thought_score(t["text"], bool(t["quote"])) for t in ths], MAX_THOUGHTS)
        card = th_pick[0]["text"] if th_pick else (hl_pick[0]["text"] if hl_pick else "")
        page_books.append({
            "title": b["title"],
            "author": b["author"],
            "category": b["category"],
            "cover": b["cover"] if re.match(r"^https?://", b["cover"]) else "",
            # Imported books (bookId CB_…) only open for their owner, so their links are left off.
            "link": b["link"] if b["link"] and re.match(r"^(https?|weread)://", b["link"]) and not b.get("bookId", "").startswith("CB_") else None,
            "progress": b["progress"],
            "finished": b["finished"],
            "readAt": b["readAt"],
            "hours": b["hours"],
            "marks": b["marks"],
            "thoughtCount": b["thoughtCount"],
            "domains": b["domains"],
            "topics": [topic_idx[n] for n in b["topics"] if n in topic_idx],
            "card": card,
            "cardIsQuote": not th_pick and bool(hl_pick),
            "thoughts": [{"text": t["text"], "quote": t["quote"]} for t in th_pick],
            "highlights": [h["text"] for h in hl_pick],
        })

    def src(name: str) -> Dict[str, Any]:
        return {"title": name, "idx": ref(name)}

    # A hidden book leaves the topic cards too: its title as a viewpoint source, and its
    # thoughts and highlights picked for a card. Cards name books by file name, or by
    # title when written by hand; a title shared with a shown book stays visible.
    shown_names = set(book_idx) | set(title_idx)
    hidden_names = set(hidden) | {b["title"] for b in vault["books"]
                                  if b["file"] in hidden and b["title"] not in shown_names}

    def shown(name: str) -> bool:
        return name not in hidden_names

    page_topics = []
    for t in topics:
        viewpoints = []
        for v in t["viewpoints"]:
            sources = [s["title"] for s in v["books"]]
            kept = [n for n in sources if shown(n)]
            if sources and not kept:
                continue  # drawn only from hidden books, so it would describe them
            viewpoints.append({"claim": v["claim"], "text": v["text"], "books": [src(n) for n in kept]})
        page_topics.append({
            "name": t["name"],
            "domain": t["domain"],
            "oneLiner": t["oneLiner"],
            "hours": t["hours"],
            "books": [book_idx[f] for f in t["books"] if f in book_idx],
            "viewpoints": viewpoints,
            "thoughts": [
                {"text": x["text"], "quote": "" if excluded(x["quote"], fragments) else x["quote"], **_ref_or_none(x["book"], ref)}
                for x in t["thoughts"]
                if x["text"] and not excluded(x["text"], fragments) and shown(x["book"])
            ],
            "highlights": [
                {"text": x["text"], **_ref_or_none(x["book"], ref)}
                for x in t["highlights"]
                if x["text"] and not excluded(x["text"], fragments) and shown(x["book"])
            ],
        })

    relations = build_relations(page_topics, [t.get("related") or [] for t in topics], page_books)
    stats = clean_stats(vault["stats"])
    return {
        "title": str(vault["config"].get("title") or DEFAULT_TITLE),
        "generatedAt": (stats or {}).get("generatedAt", ""),
        "stats": stats,
        "domains": domains,
        "topics": page_topics,
        "books": page_books,
        "relations": relations,
        "veins": veins_overview(relations),
        "ring": ring_layout(page_topics, domains, relations),
    }


def _ref_or_none(name: str, ref) -> Dict[str, Any]:
    return {"title": name, "idx": ref(name) if name else None}


# ---------------------------------------------------------------- relations


def build_relations(topics: List[Dict[str, Any]], related: List[List[Dict[str, str]]],
                    books: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Relations between topics, undirected, by page-topic index.

    Two sources: the cards' own 相关主题 (kind "concept", with the card's
    reason), and pairs of topics that share two or more books (kind "books").
    A concept pair that also shares books carries the count and titles. Cross
    domain relations come first, then concept before books, then most shared.
    """
    index = {t["name"]: i for i, t in enumerate(topics)}
    rels: Dict[Any, Dict[str, Any]] = {}
    for i, items in enumerate(related):
        for r in items:
            j = index.get(r.get("topic"))
            if j is None or j == i:
                continue
            key = (min(i, j), max(i, j))
            if key not in rels:
                rels[key] = {"a": key[0], "b": key[1], "why": str(r.get("why") or ""), "kind": "concept"}
    for a in range(len(topics)):
        for b in range(a + 1, len(topics)):
            shared = [k for k in topics[a]["books"] if k in topics[b]["books"]]
            if not shared:
                continue
            names = "、".join("《%s》" % books[k]["title"] for k in shared[:2]) + ("等" if len(shared) > 2 else "")
            if (a, b) in rels:
                rels[(a, b)].update(shared=len(shared), sharedBooks=names)
            elif len(shared) >= 2:
                rels[(a, b)] = {"a": a, "b": b, "why": "共读 %d 本书：%s" % (len(shared), names),
                                "kind": "books", "shared": len(shared), "sharedBooks": names}
    out = list(rels.values())
    for r in out:
        r["cross"] = topics[r["a"]]["domain"] != topics[r["b"]]["domain"]
        r.setdefault("shared", 0)
    out.sort(key=lambda r: (not r["cross"], r["kind"] != "concept", -r["shared"]))
    return out


def veins_overview(relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What the side panel lists before a topic is picked: indices into `relations`.

    Only relations with a written reason (kind "concept") are listed: cross-domain
    ones when there are any, otherwise all of them. Pairs that merely share books
    stay as dashed lines on the ring; "共读 2 本书" is not a reason and would only
    pad the panel.
    """
    concept = [k for k, r in enumerate(relations) if r["kind"] == "concept"]
    cross = [k for k in concept if relations[k]["cross"]]
    if cross:
        return {"kicker": "跨领域的脉络", "items": cross}
    return {"kicker": "主题之间的脉络", "items": concept}


# --------------------------------------------------------------------- ring

RING_GAP = 0.2  # radians left empty between two domains
RING_MAX_R = 210
RING_MIN_R = 150
RING_MIN_SIZE = 600
RING_MARGIN = 12
LABEL_CHARS = 14


def measure(text: str, px: float) -> float:
    """Rough text width: CJK and full-width glyphs are 1em, the rest about 0.58em."""
    w = 0.0
    for ch in text:
        c = ord(ch)
        w += 1 if c > 0x2E7F else 0.68 if 65 <= c <= 90 else 0.56
    return w * px


def ring_label(name: str) -> str:
    return name if len(name) <= LABEL_CHARS else name[: LABEL_CHARS - 1] + "…"


def _f1(v: float) -> float:
    return round(v, 1)


def _boxes_overlap(a, b, pad: float = 2) -> bool:
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


def ring_layout(topics: List[Dict[str, Any]], domains: List[Dict[str, Any]],
                relations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Geometry of the knowledge ring, in the coordinates of a square viewBox.

    Label size shrinks a little as topics get more numerous (13px at about 30);
    the radius is whatever leaves room for the longest radial label, and when
    the topics are too many for that radius the whole viewBox grows instead, so
    neighbouring labels never collide. Returns None when there are no topics.
    """
    n = len(topics)
    if not n:
        return None
    names = [d["name"] for d in domains if any(t["domain"] == d["name"] for t in topics)]
    for t in topics:
        if t["domain"] not in names:
            names.append(t["domain"])
    m = len(names)
    label_px = max(11.0, min(15.0, 13 + (31 - n) * 0.1))
    scale = label_px / 13
    max_hours = max([t["hours"] for t in topics] + [1])
    dots = [(3.2 + 6 * math.sqrt(max(t["hours"], 0) / max_hours)) * scale for t in topics]
    labels = [ring_label(t["name"]) for t in topics]
    room = RING_MARGIN + max(dots) + 8 + max(measure(s, label_px) for s in labels)
    gap = RING_GAP
    step = (2 * math.pi - gap * m) / n
    r = max(min(RING_MAX_R, 380 - room), RING_MIN_R, 1.3 * label_px / step)
    size = max(RING_MIN_SIZE, math.ceil(2 * (r + room)))
    c = size / 2

    angles = [0.0] * n
    arcs = []
    ang = -math.pi / 2 + gap / 2
    for d in names:
        members = sorted((i for i, t in enumerate(topics) if t["domain"] == d), key=lambda i: -topics[i]["hours"])
        a0 = ang
        for i in members:
            angles[i] = ang + step / 2
            ang += step
        arcs.append({"name": d, "a0": a0, "a1": ang})
        ang += gap

    def point(a: float, rad: float):
        return c + rad * math.cos(a), c + rad * math.sin(a)

    def arc_path(a0: float, a1: float) -> str:
        x0, y0 = point(a0, r)
        x1, y1 = point(a1, r)
        return "M%.1f,%.1fA%.1f,%.1f 0 %d 1 %.1f,%.1f" % (x0, y0, r, r, 1 if a1 - a0 > math.pi else 0, x1, y1)

    # Domain names sit inside the ring at the middle of their arc. When they
    # crowd each other, shrink them, then put every other one further in.
    def domain_boxes(px: float, radii):
        out = []
        for g, rad in zip(arcs, radii):
            x, y = point((g["a0"] + g["a1"]) / 2, rad)
            w = measure(g["name"], px) * 1.14 + 4  # letter-spacing 0.14em
            out.append((x - w / 2, y - px * 0.7, x + w / 2, y + px * 0.7, x, y))
        return out

    def crowded(boxes) -> bool:
        return any(_boxes_overlap(boxes[i], boxes[j]) for i in range(len(boxes)) for j in range(i + 1, len(boxes)))

    domain_px, boxes = 15.0, []
    for px, radii in [(15.0, [0.66] * m), (13.0, [0.66] * m), (12.0, [0.66] * m), (12.0, [0.7, 0.42] * m), (11.0, [0.72, 0.4] * m)]:
        domain_px, boxes = px, domain_boxes(px, [k * r for k in radii[:m]])
        if not crowded(boxes):
            break
    for g, b in zip(arcs, boxes):
        g["x"], g["y"] = _f1(b[4]), _f1(b[5])
        g["d"] = arc_path(g.pop("a0"), g.pop("a1"))

    nodes = []
    for i, t in enumerate(topics):
        a = angles[i]
        x, y = point(a, r)
        right = math.cos(a) >= -1e-9
        lx, ly = point(a, r + dots[i] + 8)
        deg = math.degrees(a)
        nodes.append({"x": _f1(x), "y": _f1(y), "a": round(a, 4), "dot": _f1(dots[i]), "label": labels[i],
                      "lx": _f1(lx), "ly": _f1(ly), "rot": _f1(deg if right else deg + 180),
                      "anchor": "start" if right else "end"})

    roads = []
    for rel in relations:
        p, q = nodes[rel["a"]], nodes[rel["b"]]
        d = abs(angles[rel["a"]] - angles[rel["b"]])
        if d > math.pi:
            d = 2 * math.pi - d
        # Neighbours bow gently near the rim; distant topics pass close to the centre.
        k = 0.82 * (1 - d / math.pi)
        mx, my = c + ((p["x"] + q["x"]) / 2 - c) * k, c + ((p["y"] + q["y"]) / 2 - c) * k
        roads.append({"d": "M%.1f,%.1fQ%.1f,%.1f %.1f,%.1f" % (p["x"], p["y"], mx, my, q["x"], q["y"]),
                      "w": round((1.3 if rel["kind"] == "concept" else 0.9) + min(rel["shared"], 4) * 0.3, 2)})

    return {"size": size, "r": _f1(r), "labelPx": round(label_px, 1), "domainPx": domain_px,
            "arcs": arcs, "nodes": nodes, "roads": roads}


# --------------------------------------------------------------------- html


def inline_json(data: Any) -> str:
    """JSON that is safe inside <script type="application/json">."""
    s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        s.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def render_html(data: Dict[str, Any]) -> str:
    page = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    css = (TEMPLATES / "page.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "page.js").read_text(encoding="utf-8")
    parts = {
        "@@ATLAS_TITLE@@": html.escape(data["title"]),
        "/*@@ATLAS_CSS@@*/": css,
        "/*@@ATLAS_JS@@*/": js.replace("</script", "<\\/script"),
        "@@ATLAS_DATA@@": inline_json(data),
    }
    # One pass, so text inside the data can never be mistaken for a placeholder.
    pattern = re.compile("|".join(re.escape(k) for k in parts))
    return pattern.sub(lambda m: parts[m.group(0)], page)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="从库里渲染书房页")
    ap.add_argument("--root", required=True, help="微信读书 根目录")
    ap.add_argument("--out", help="输出路径，默认 <root>/书房/index.html")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    try:
        vault = read_vault(root)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    warnings = vault["warnings"]

    data = build_page_data(vault)
    out = Path(args.out).expanduser() if args.out else root / "书房" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render_html(data)
    out.write_text(text, encoding="utf-8")

    size_kb = len(text.encode("utf-8")) / 1024
    # 未归类 holds the books with no domain; it is not one of the user's domains, so the
    # count matches what topics.py printed.
    real = [d for d in data["domains"] if d["name"] != UNSORTED]
    unsorted = sum(d["books"] for d in data["domains"] if d["name"] == UNSORTED)
    mapped = sum(1 for d in real if d["topics"] > 0)
    domains_note = f"领域 {len(real)} 个" if mapped == len(real) else \
        f"领域 {len(real)} 个，其中 {mapped} 个有主题画在环上"
    if unsorted:
        domains_note += f"，另有 {unsorted} 本书没有分到领域"
    print(f"书房页：{out}")
    reasoned = [r for r in data["relations"] if r["kind"] == "concept"]
    cross = sum(1 for r in reasoned if r["cross"])
    co_read = len(data["relations"]) - len(reasoned)
    print(f"书 {len(data['books'])} 本｜主题 {len(data['topics'])} 个｜{domains_note}｜{size_kb:.0f} KB")
    # Mirrors veins_overview: cross-domain relations when there are any, else every reasoned one.
    if cross:
        panel = f"其中跨领域 {cross} 条，脉络栏列出这些"
    elif reasoned:
        panel = "没有跨领域的，脉络栏列出这些同领域的关系"
    else:
        panel = "脉络栏是空的"
    print(f"写了理由的关系 {len(reasoned)} 条，{panel}"
          + (f"；另有只是共读的 {co_read} 条，只在环上画虚线" if co_read else ""))
    if warnings:
        print(f"警告 {len(warnings)} 条：")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("警告 0 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
