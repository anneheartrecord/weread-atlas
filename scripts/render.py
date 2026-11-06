"""Render the 书房 page from the vault.

    python3 scripts/render.py --root <微信读书> [--theme 舆图|羊皮纸|星空] [--out path]

Reads only the vault (see vault_read.py) and writes one self-contained
HTML file, `书房/index.html` by default: inline CSS, inline JS and the
data inlined as JSON. The only outside requests the page makes are the
font stylesheet and the book covers.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_read import read_vault  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
THEMES = {"舆图": "yutu", "羊皮纸": "kami", "星空": "stars"}
DEFAULT_THEME = "舆图"
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
    topics = vault["topics"]
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

    page_topics = []
    for t in topics:
        page_topics.append({
            "name": t["name"],
            "domain": t["domain"],
            "oneLiner": t["oneLiner"],
            "hours": t["hours"],
            "books": [book_idx[f] for f in t["books"] if f in book_idx],
            "viewpoints": [
                {"claim": v["claim"], "text": v["text"], "books": [src(s["title"]) for s in v["books"]]}
                for v in t["viewpoints"]
            ],
            "thoughts": [
                {"text": x["text"], "quote": "" if excluded(x["quote"], fragments) else x["quote"], **_ref_or_none(x["book"], ref)}
                for x in t["thoughts"]
                if x["text"] and not excluded(x["text"], fragments)
            ],
            "highlights": [
                {"text": x["text"], **_ref_or_none(x["book"], ref)}
                for x in t["highlights"]
                if x["text"] and not excluded(x["text"], fragments)
            ],
        })

    stats = clean_stats(vault["stats"])
    return {
        "title": str(vault["config"].get("title") or "书房"),
        "generatedAt": (stats or {}).get("generatedAt", ""),
        "stats": stats,
        "domains": vault["domains"],
        "topics": page_topics,
        "books": page_books,
    }


def _ref_or_none(name: str, ref) -> Dict[str, Any]:
    return {"title": name, "idx": ref(name) if name else None}


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


def render_html(data: Dict[str, Any], theme: str) -> str:
    page = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    css = (TEMPLATES / "page.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "page.js").read_text(encoding="utf-8")
    parts = {
        "@@ATLAS_TITLE@@": html.escape(data["title"]),
        "@@ATLAS_THEME@@": THEMES[theme],
        "@@ATLAS_SCHEME@@": "dark" if theme == "星空" else "light dark",
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
    ap.add_argument("--theme", choices=list(THEMES), help="风格，默认取 config.json 的 theme")
    ap.add_argument("--out", help="输出路径，默认 <root>/书房/index.html")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    try:
        vault = read_vault(root)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    warnings = vault["warnings"]
    theme = args.theme or str(vault["config"].get("theme") or DEFAULT_THEME)
    if theme not in THEMES:
        warnings.append(f"config.json 的 theme「{theme}」不认识，改用{DEFAULT_THEME}")
        theme = DEFAULT_THEME

    data = build_page_data(vault)
    out = Path(args.out).expanduser() if args.out else root / "书房" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render_html(data, theme)
    out.write_text(text, encoding="utf-8")

    size_kb = len(text.encode("utf-8")) / 1024
    mapped = sum(1 for d in data["domains"] if d["topics"] > 0)
    print(f"书房页：{out}")
    print(f"风格 {theme}｜书 {len(data['books'])} 本｜主题 {len(data['topics'])} 个｜领域 {mapped} 个｜{size_kb:.0f} KB")
    if warnings:
        print(f"警告 {len(warnings)} 条：")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("警告 0 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
