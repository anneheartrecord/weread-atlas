"""Read a 书脉 vault into one data dict for the page renderer.

The vault is the single source of truth: this module reads only
`书/*.md`, `主题/*.md`, `.atlas/stats.json` and `.atlas/config.json`
under the root folder (see references/vault-format.md). A note it cannot
make sense of is skipped and recorded in `warnings`; it never raises on
user content.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib  # noqa: E402

BEGIN = atlas_lib.BEGIN
END = atlas_lib.END
UNSORTED = "未归类"
THOUGHT_MARK = "💭"
ORPHAN_HEADING = getattr(atlas_lib, "ORPHAN_SECTION", "没有对应划线的想法")
SOURCE_SEP = " —— "


class MalformedNote(ValueError):
    pass


# ---------------------------------------------------------------- frontmatter


def parse_frontmatter(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """(fields, body) via atlas_lib; fields is None when there is no frontmatter.

    Raises MalformedNote for an opening `---` that is never closed, so the
    caller can say why the note was skipped.
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    fm, body = atlas_lib.parse_frontmatter(text)
    if fm is None:
        if text.startswith("---\n") or text.strip() == "---":
            raise MalformedNote("frontmatter 没有结束的 ---")
        return None, text
    if not isinstance(fm, dict):
        fm = fm.to_dict()
    return fm, body


def generated_block(body: str) -> str:
    """The text between the markers, or the whole body when they were removed."""
    split = getattr(atlas_lib, "split_block", None)
    if split is not None:
        parts = split(body)
        return body if parts is None else parts[1]
    inner = atlas_lib.read_block(body)
    if inner is not None:
        return inner
    start = body.find(BEGIN)
    return body if start < 0 else body[start + len(BEGIN) :]


def vault_paths(root: Path) -> Dict[str, Path]:
    p = atlas_lib.paths(str(root)) if hasattr(atlas_lib, "paths") else atlas_lib.Paths(str(root))
    get = (lambda k: p[k]) if isinstance(p, dict) else (lambda k: getattr(p, k))
    return {k: Path(get(k)) for k in ("books_dir", "topics_dir", "stats_json", "config")}


# ------------------------------------------------------------------ helpers

_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_TITLE = re.compile(r"《([^》]+)》")


def link_target(s: Any) -> str:
    """`"[[书名|别名]]"` → `书名`; plain strings come back stripped."""
    s = str(s if s is not None else "").strip()
    m = _LINK.search(s)
    if m:
        return m.group(1).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s.strip("[]").split("|")[0]
    return s.strip()


def as_list(v: Any) -> List[str]:
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    return [str(v).strip()]


def as_text(v: Any) -> str:
    return "" if v is None or isinstance(v, bool) else str(v).strip()


def as_number(v: Any, field: str, where: str, warnings: List[str]) -> float:
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        warnings.append(f"{where}：{field} 不是数字（{v}），按 0 处理")
        return 0.0


def parse_sources(s: str) -> List[Dict[str, Any]]:
    """`[[书A]] · 《书B》` → [{"title": "书A", "linked": True}, ...]."""
    out = []
    for part in re.split(r"\s*·\s*", s.strip()):
        part = part.strip()
        if not part:
            continue
        m = _LINK.search(part)
        if m:
            out.append({"title": m.group(1).strip(), "linked": True})
            continue
        m = _TITLE.search(part)
        out.append({"title": (m.group(1) if m else part).strip(), "linked": False})
    return out


def split_source(line: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Split `正文 —— [[书]]` on the last separator."""
    for sep in (SOURCE_SEP, " ——", "——"):
        idx = line.rfind(sep)
        if idx > 0:
            tail = line[idx + len(sep) :]
            if _LINK.search(tail) or _TITLE.search(tail):
                return line[:idx].strip(), parse_sources(tail)
    return line.strip(), []


def _sections(block: str) -> Dict[str, List[str]]:
    secs: Dict[str, List[str]] = {}
    cur = None
    for line in block.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if m:
            cur = m.group(1).strip()
            secs.setdefault(cur, [])
        elif cur is not None:
            secs[cur].append(line)
    return secs


def _section(secs: Dict[str, List[str]], name: str) -> List[str]:
    if name in secs:
        return secs[name]
    for k, v in secs.items():
        if name in k:
            return v
    return []


# -------------------------------------------------------------------- books


def parse_book_block(block: str) -> Dict[str, Any]:
    chapters: List[Dict[str, Any]] = []
    orphans: List[Dict[str, str]] = []
    topic_line: List[str] = []
    cur: Optional[Dict[str, Any]] = None
    in_orphans = False
    last = None
    for raw in block.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote and last is not None and "quote" in last:
            # `  > 原文` under a thought that has no highlight of its own.
            last["quote"] = (last["quote"] + " " + quote.group(1).strip()).strip()
            continue
        if quote and not chapters and not in_orphans:
            text = line.lstrip("> ").strip()
            if text.startswith("主题"):
                topic_line = [s["title"] for s in parse_sources(re.sub(r"^主题[：:]\s*", "", text))]
            continue
        if quote:
            continue  # a stray blockquote the user added; not part of the notes
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            title = m.group(1).strip()
            in_orphans = title == ORPHAN_HEADING
            cur = None if in_orphans else {"title": title, "highlights": []}
            if cur is not None:
                chapters.append(cur)
            last = None
            continue
        item = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if not item:
            # Continuation of the previous bullet (user wrapped a line by hand).
            if last is not None:
                last["text"] = (last["text"] + " " + line.strip()).strip()
            continue
        indent, text = len(item.group(1).expandtabs(4)), item.group(2).strip()
        is_thought = text.startswith(THOUGHT_MARK)
        if is_thought:
            text = text[len(THOUGHT_MARK) :].strip()
        if not text:
            continue
        if is_thought and indent > 0 and not in_orphans and cur and cur["highlights"]:
            hl = cur["highlights"][-1]
            hl["thoughts"].append(text)
            last = None
        elif is_thought:
            entry = {"text": text, "quote": ""}
            orphans.append(entry)
            last = entry
        else:
            if cur is None:
                cur = {"title": "", "highlights": []}
                chapters.append(cur)
            entry = {"text": text, "thoughts": []}
            cur["highlights"].append(entry)
            last = entry
    return {"chapters": chapters, "orphanThoughts": orphans, "topicLine": topic_line}


def read_book(path: Path, warnings: List[str]) -> Optional[Dict[str, Any]]:
    where = f"书/{path.name}"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        warnings.append(f"{where}：读不出来，已跳过（{type(e).__name__}）")
        return None
    try:
        fm, body = parse_frontmatter(text)
        if fm is None:
            warnings.append(f"{where}：没有 frontmatter，不是书脉生成的笔记，已跳过")
            return None
        parsed = parse_book_block(generated_block(body))
    except MalformedNote as e:
        warnings.append(f"{where}：{e}，已跳过")
        return None
    except Exception as e:  # never let one odd note stop the page
        warnings.append(f"{where}：解析出错，已跳过（{type(e).__name__}: {e}）")
        return None
    title = as_text(fm.get("书名")) or path.stem
    progress = as_number(fm.get("进度"), "进度", where, warnings)
    return {
        "file": path.stem,
        "title": title,
        "author": as_text(fm.get("作者")),
        "bookId": as_text(fm.get("bookId")),
        "category": as_text(fm.get("分类")),
        "progress": int(max(0, min(100, progress))),
        "finished": as_text(fm.get("读完")) or None,
        "readAt": as_text(fm.get("最近阅读")) or None,
        "hours": round(as_number(fm.get("时长"), "时长", where, warnings), 1),
        "marks": int(as_number(fm.get("划线数"), "划线数", where, warnings)),
        "thoughtCount": int(as_number(fm.get("想法数"), "想法数", where, warnings)),
        "domains": as_list(fm.get("领域")),
        "topics": [link_target(t) for t in as_list(fm.get("主题"))] or parsed["topicLine"],
        "cover": as_text(fm.get("封面")),
        "link": as_text(fm.get("链接")) or None,
        "chapters": parsed["chapters"],
        "orphanThoughts": parsed["orphanThoughts"],
    }


# ------------------------------------------------------------------- topics


def parse_topic_block(block: str) -> Dict[str, Any]:
    secs = _sections(block)

    one = " ".join(l.strip() for l in _section(secs, "一句话结论") if l.strip() and not l.strip().startswith("<!--"))
    one = one.lstrip("> ").strip()

    viewpoints: List[Dict[str, Any]] = []
    for line in _section(secs, "核心观点"):
        if not line.strip():
            continue
        m = re.match(r"^\s*(?:\d+[.)、]|[-*])\s+(.*)$", line)
        if not m:
            if viewpoints:
                viewpoints[-1]["text"] = (viewpoints[-1]["text"] + " " + line.strip()).strip()
            continue
        body, books = split_source(m.group(1))
        b = re.match(r"^\*\*(.+?)\*\*\s*[：:]?\s*(.*)$", body)
        if b:
            claim, text = b.group(1).strip(), b.group(2).strip()
        else:
            parts = re.split(r"[：:]", body, maxsplit=1)
            claim, text = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
        viewpoints.append({"claim": claim, "text": text, "books": books})

    thoughts: List[Dict[str, Any]] = []
    for line in _section(secs, "我的想法"):
        if not line.strip():
            continue
        q = re.match(r"^\s*>\s?(.*)$", line)
        if q:
            if thoughts:
                thoughts[-1]["quote"] = (thoughts[-1]["quote"] + " " + q.group(1).strip()).strip()
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            text, src = split_source(m.group(1))
            text = text.lstrip(THOUGHT_MARK).strip()
            thoughts.append({"text": text, "quote": "", "book": src[0]["title"] if src else ""})

    highlights: List[Dict[str, Any]] = []
    for line in _section(secs, "代表划线"):
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            text, src = split_source(m.group(1))
            highlights.append({"text": text, "book": src[0]["title"] if src else ""})

    return {"oneLiner": one, "viewpoints": viewpoints, "thoughts": thoughts, "highlights": highlights}


def read_topic(path: Path, warnings: List[str]) -> Optional[Dict[str, Any]]:
    where = f"主题/{path.name}"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        warnings.append(f"{where}：读不出来，已跳过（{type(e).__name__}）")
        return None
    try:
        fm, body = parse_frontmatter(text)
        if fm is None:
            warnings.append(f"{where}：没有 frontmatter，已跳过")
            return None
        parsed = parse_topic_block(generated_block(body))
    except MalformedNote as e:
        warnings.append(f"{where}：{e}，已跳过")
        return None
    except Exception as e:  # never let one odd card stop the page
        warnings.append(f"{where}：解析出错，已跳过（{type(e).__name__}: {e}）")
        return None
    domains = as_list(fm.get("领域"))
    return {
        "name": as_text(fm.get("主题")) or path.stem,
        "domain": domains[0] if domains else "",
        "books": [link_target(b) for b in as_list(fm.get("书目"))],
        "hours": round(as_number(fm.get("时长"), "时长", where, warnings), 1),
        **parsed,
    }


# -------------------------------------------------------------------- vault


def _read_json(path: Path, warnings: List[str], label: str) -> Optional[Any]:
    if not path.exists():
        warnings.append(f"{label} 不存在")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        warnings.append(f"{label} 读不出来（{type(e).__name__}）")
        return None


def read_vault(root: Path) -> Dict[str, Any]:
    """Parse the vault under `root` (the 微信读书 folder).

    Returns {"config", "stats", "books", "topics", "domains", "warnings"}.
    Books are sorted by reading hours (desc), topics by domain order then
    hours, domains by total book hours (desc) with 未归类 last.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"找不到目录：{root}")
    warnings: List[str] = []

    where = vault_paths(root)
    try:
        config = dict(atlas_lib.load_config(str(root)))
    except Exception as e:  # unreadable config: fall back to the defaults
        warnings.append(f".atlas/config.json 读不出来，按默认配置渲染（{type(e).__name__}）")
        config = json.loads(json.dumps(atlas_lib.DEFAULT_CONFIG))
    config["exclude"] = [str(x) for x in as_list(config.get("exclude")) if str(x)]

    stats = _read_json(where["stats_json"], warnings, ".atlas/stats.json")
    if stats is not None and not isinstance(stats, dict):
        warnings.append(".atlas/stats.json 不是对象，已忽略")
        stats = None

    books: List[Dict[str, Any]] = []
    for p in sorted(where["books_dir"].glob("*.md")) if where["books_dir"].is_dir() else []:
        b = read_book(p, warnings)
        if b:
            books.append(b)

    topic_files = sorted(where["topics_dir"].glob("*.md")) if where["topics_dir"].is_dir() else []
    topics: List[Dict[str, Any]] = []
    seen = set()
    for p in topic_files:
        t = read_topic(p, warnings)
        if not t:
            continue
        if t["name"] in seen:
            warnings.append(f"主题/{p.name}：主题名「{t['name']}」重复，已跳过")
            continue
        seen.add(t["name"])
        topics.append(t)

    by_file = {b["file"]: b for b in books}
    by_title = {b["title"]: b for b in books}

    def find_book(name: str) -> Optional[Dict[str, Any]]:
        return by_file.get(name) or by_title.get(name)

    # A topic's books: its 书目, keeping only books on the shelf.
    for t in topics:
        if not t["domain"]:
            t["domain"] = UNSORTED
        found, missing = [], []
        for name in t["books"]:
            b = find_book(name)
            if b and b["file"] not in found:
                found.append(b["file"])
            elif not b:
                missing.append(name)
        if missing:
            warnings.append(f"主题「{t['name']}」的书目里有 {len(missing)} 本不在 书/ 里：{'、'.join(missing[:3])}")
        t["books"] = found
        if not t["hours"]:
            t["hours"] = round(sum(by_file[f]["hours"] for f in found), 1)

    # A book's topics: its own 主题 field plus every card that lists it.
    topic_by_name = {t["name"]: t for t in topics}
    for b in books:
        names = [n for n in b["topics"] if n in topic_by_name]
        for t in topics:
            if b["file"] in t["books"] and t["name"] not in names:
                names.append(t["name"])
        b["topics"] = names
        if not b["domains"]:
            b["domains"] = list(dict.fromkeys(topic_by_name[n]["domain"] for n in names))
        if not b["domains"]:
            b["domains"] = [UNSORTED]

    # Domain order: most reading hours first, 未归类 always last.
    totals: Dict[str, List[float]] = {}
    for b in books:
        for d in b["domains"]:
            totals.setdefault(d, [0.0, 0])
            totals[d][0] += b["hours"]
            totals[d][1] += 1
    for t in topics:
        totals.setdefault(t["domain"], [0.0, 0])
    order = sorted(totals, key=lambda d: (d == UNSORTED, -totals[d][0], -totals[d][1], d))
    rank = {d: i for i, d in enumerate(order)}
    domains = [
        {
            "name": d,
            "books": totals[d][1],
            "hours": round(totals[d][0], 1),
            "topics": sum(1 for t in topics if t["domain"] == d),
        }
        for d in order
    ]

    books.sort(key=lambda b: (-b["hours"], -(b["marks"] + b["thoughtCount"]), b["file"]))
    topics.sort(key=lambda t: (rank[t["domain"]], -len(t["books"]), -t["hours"], t["name"]))

    return {
        "config": config,
        "stats": stats,
        "books": books,
        "topics": topics,
        "domains": domains,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="把书脉库读成一份 JSON，便于排查")
    ap.add_argument("--root", required=True, help="微信读书 根目录")
    args = ap.parse_args()
    data = read_vault(Path(args.root))
    print(json.dumps(data, ensure_ascii=False, indent=1))
