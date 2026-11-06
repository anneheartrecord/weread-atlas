"""Shared helpers for the 书脉 (weread-atlas) scripts.

Everything here follows references/vault-format.md: paths under the root folder,
config defaults, file names, the small YAML subset used in frontmatter, and the
marker block that scripts own inside each note.

Standard library only, Python 3.9+.
"""

import json
import os
import re
import sys

BEGIN = "<!-- weread-atlas:begin -->"
END = "<!-- weread-atlas:end -->"

DEFAULT_CONFIG = {
    "rootName": "微信读书",
    "title": "书房",
    "theme": "舆图",
    "topN": 50,
    "exclude": [],
    "hideBooks": [],
}
THEMES = ("舆图", "羊皮纸", "星空")

ORPHAN_SECTION = "没有对应划线的想法"
UNKNOWN_CHAPTER = "其他章节"


# ---------------------------------------------------------------- paths & config

class Paths(object):
    """All file locations, relative to the 微信读书 root folder."""

    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.atlas = os.path.join(self.root, ".atlas")
        self.config = os.path.join(self.atlas, "config.json")
        self.cache = os.path.join(self.atlas, "cache")
        self.readdata_cache = os.path.join(self.cache, "readdata")
        self.notebooks_cache = os.path.join(self.cache, "notebooks.json")
        self.books_json = os.path.join(self.atlas, "books.json")
        self.stats_json = os.path.join(self.atlas, "stats.json")
        self.topics_json = os.path.join(self.atlas, "topics.json")
        self.digest_dir = os.path.join(self.atlas, "digest")
        self.books_dir = os.path.join(self.root, "书")
        self.topics_dir = os.path.join(self.root, "主题")
        self.overview = os.path.join(self.root, "总览.md")
        self.shelf_dir = os.path.join(self.root, "书房")

    def book_cache(self, book_id):
        return os.path.join(self.cache, "%s.json" % book_id)

    def book_note(self, file_name):
        return os.path.join(self.books_dir, file_name + ".md")

    def topic_card(self, name):
        return os.path.join(self.topics_dir, name + ".md")


def load_config(root):
    """Config with defaults filled in. A missing file gives the defaults."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = Paths(root).config
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("%s must be a JSON object" % path)
        cfg.update(data)
    for key in ("exclude", "hideBooks"):
        if not isinstance(cfg.get(key), list):
            cfg[key] = []
    return cfg


def save_config(root, cfg):
    write_json(Paths(root).config, cfg)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def read_text(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write_text_if_changed(path, text):
    """Write only when the content differs. Returns True when the file changed."""
    if read_text(path) == text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def load_books(paths):
    books = read_json(paths.books_json)
    if books is None:
        die("找不到 %s，先运行 fetch.py" % paths.books_json)
    return books


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


_TAG_START = re.compile(r"<(?=[A-Za-z/!])")


def md_text(text):
    """One line of note text, with tag-like `<` escaped so Obsidian shows `<pid>` and `<br/>` as written."""
    return _TAG_START.sub(r"\\<", one_line(text))


def md_unescape(text):
    """Inverse of md_text's escaping, for readers of generated blocks."""
    return (text or "").replace("\\<", "<")


def one_line(text):
    """Keep text verbatim except that line breaks become spaces."""
    if text is None:
        return ""
    return re.sub(r"\r\n|\r|\n", " ", str(text)).strip()


def excluded(text, patterns):
    return any(p and p in text for p in patterns)


# ---------------------------------------------------------------- file names

FORBIDDEN_CHARS = '\\/:*?"<>|#^[]'
_CLOSERS = {"）": "（", ")": "(", "】": "【", "]": "["}
_OPENERS = set(_CLOSERS.values())
_NATIONALITY = re.compile(r"^\s*[\[【（(][^\]】）)]{1,6}[\]】）)]\s*")
_LEADING_BRACKETS = re.compile(r"^\s*(【[^【】]*】|\[[^\[\]]*\])\s*")
# subtitle separators; a colon between two digits (12:30) is not a separator
_SUBTITLE = re.compile(r"(?<!\d)[：:]|[：:](?!\d)|\||｜|——| - ")


def sanitize_filename(name):
    out = "".join(ch for ch in name if ch not in FORBIDDEN_CHARS and ord(ch) >= 32)
    out = re.sub(r"\s+", " ", out).strip().strip(".").strip()
    return out[:120].strip()


def _strip_trailing_group(t):
    """Remove one bracketed group at the end, nested brackets included."""
    t = t.rstrip()
    if not t or t[-1] not in _CLOSERS:
        return t
    depth = 0
    for i in range(len(t) - 1, -1, -1):
        c = t[i]
        if c in _CLOSERS:
            depth += 1
        elif c in _OPENERS:
            depth -= 1
            if depth == 0:
                return t[:i].rstrip()
    return t


# Imported books often carry download-site tags, file extensions or numeric upload ids in their title.
_SOURCE_TAG = re.compile(r"lib|z-?lib|libgen|anna|archive|www\.|\.(com|org|net|sk|io|cn)\b|epub|mobi|azw|pdf", re.I)
_FILE_EXT = re.compile(r"\.(epub|mobi|azw3?|pdf|txt)$", re.I)
_UPLOAD_ID = re.compile(r"^\d{6,}[-_ ]+")


def display_title(title):
    """Title as shown to people: imported-file noise removed, everything else kept verbatim."""
    t = _UPLOAD_ID.sub("", _FILE_EXT.sub("", (title or "").strip()))
    while True:
        stripped = _strip_trailing_group(t)
        if stripped == t or not _SOURCE_TAG.search(t[len(stripped):]):
            break
        t = stripped
    return t.strip() or (title or "").strip()


def clean_title(title):
    """File-name stem for a book: drop subtitle and bracketed edition notes, then forbidden characters."""
    t = display_title(title)
    prev = None
    while prev != t:
        prev = t
        t = _strip_trailing_group(t)
    t = _LEADING_BRACKETS.sub("", t)
    t = _SUBTITLE.split(t)[0]
    name = sanitize_filename(t)
    if not name:
        name = sanitize_filename((title or "").strip().strip("（）()【】[] "))
    return name or "未命名"


def assign_filenames(books, previous):
    """Map bookId -> fileName.

    Names already assigned (previous, from the last books.json) never change.
    New books are named in order of their first note (noteSort, then bookId);
    the earlier one keeps the plain title, later ones get （作者）, then （作者，bookId）.
    Comparison ignores case because macOS and Windows file systems do.
    """
    ids = {str(b["bookId"]) for b in books}
    names = {k: v for k, v in previous.items() if k in ids}
    used = {v.casefold() for v in names.values()}
    pending = sorted((b for b in books if str(b["bookId"]) not in names),
                     key=lambda b: (b.get("noteSort") or 0, str(b["bookId"])))
    for b in pending:
        bid = str(b["bookId"])
        base = clean_title(b.get("title"))
        author = sanitize_filename(_NATIONALITY.sub("", b.get("author") or ""))
        options = [base]
        if author:
            options.append("%s（%s）" % (base, author))
            options.append("%s（%s，%s）" % (base, author, sanitize_filename(bid)))
        else:
            options.append("%s（%s）" % (base, sanitize_filename(bid)))
        name = next((o for o in options if o.casefold() not in used), None)
        n = 2
        while name is None:
            cand = "%s（%d）" % (options[-1], n)
            if cand.casefold() not in used:
                name = cand
            n += 1
        names[bid] = name
        used.add(name.casefold())
    return names


# ---------------------------------------------------------------- frontmatter

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_YAML_NUMBERISH = re.compile(r"^[-+]?(\.?\d[\d_.]*([eE][-+]?\d+)?|\.(inf|nan|Inf|NaN|INF|NAN)|0[xXoObB][0-9a-fA-F_]+)$")
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
_INDICATORS = "-?:,[]{}#&*!|>'\"%@`"
_KEY_LINE = re.compile(r"^([^\s#\-][^:]*?):(?:[ \t]+(.*))?$")


def _needs_quotes(s):
    if s == "" or s != s.strip():
        return True
    if any(c in s for c in ':#[],{}'):
        return True
    if s[0] in _INDICATORS:
        return True
    if s.lower() in _YAML_WORDS or _YAML_NUMBERISH.match(s):
        return True
    return False


def format_scalar(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v) if isinstance(v, float) else str(v)
    s = one_line(v) if ("\n" in str(v) or "\r" in str(v)) else str(v)
    if _needs_quotes(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def format_value(v):
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(format_scalar(x) for x in v) + "]"
    return format_scalar(v)


def _parse_double_quoted(s, i):
    """s[i] == '"'. Returns (string, index after closing quote)."""
    out = []
    i += 1
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(nxt, nxt))
            i += 2
            continue
        if c == '"':
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


def _parse_single_quoted(s, i):
    out = []
    i += 1
    while i < len(s):
        c = s[i]
        if c == "'":
            if i + 1 < len(s) and s[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


def parse_scalar(s):
    s = s.strip()
    if s == "" or s == "~" or s == "null":
        return None
    if s[0] == '"':
        return _parse_double_quoted(s, 0)[0]
    if s[0] == "'":
        return _parse_single_quoted(s, 0)[0]
    if _NUMBER.match(s):
        return float(s) if "." in s else int(s)
    if s in ("true", "false"):
        return s == "true"
    return s


def parse_value(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1]
        items, i, cur = [], 0, ""
        if not inner.strip():
            return []
        while i < len(inner):
            c = inner[i]
            if c in "\"'" and not cur.strip():
                parser = _parse_double_quoted if c == '"' else _parse_single_quoted
                val, i = parser(inner, i)
                cur = None
                items.append(val)
                # skip to the next comma
                while i < len(inner) and inner[i] != ",":
                    i += 1
                i += 1
                cur = ""
                continue
            if c == ",":
                items.append(parse_scalar(cur))
                cur = ""
            else:
                cur += c
            i += 1
        if cur.strip():
            items.append(parse_scalar(cur))
        return items
    return parse_scalar(s)


class Frontmatter(object):
    """Ordered frontmatter that keeps each entry's raw lines.

    Entries the scripts don't touch are written back byte for byte, so user
    keys, their order and their formatting survive.
    """

    def __init__(self, entries=None):
        self.entries = entries or []  # list of [key or None, [raw lines]]

    @classmethod
    def parse(cls, text):
        entries = []
        for line in text.split("\n"):
            m = _KEY_LINE.match(line)
            if m and not line.startswith((" ", "\t")):
                entries.append([m.group(1).strip(), [line]])
            elif entries:
                entries[-1][1].append(line)
            else:
                entries.append([None, [line]])
        return cls(entries)

    def keys(self):
        return [k for k, _ in self.entries if k is not None]

    def _find(self, key):
        for e in self.entries:
            if e[0] == key:
                return e
        return None

    def get(self, key, default=None):
        e = self._find(key)
        if e is None:
            return default
        m = _KEY_LINE.match(e[1][0])
        rest = (m.group(2) or "") if m else ""
        if rest.strip() == "":
            items = [ln.strip()[1:].strip() for ln in e[1][1:] if ln.strip().startswith("-")]
            if items:
                return [parse_scalar(x) for x in items]
            return None
        return parse_value(rest)

    def to_dict(self):
        return {k: self.get(k) for k in self.keys()}

    def set(self, key, value):
        e = self._find(key)
        line = ("%s: %s" % (key, format_value(value))).rstrip()
        if e is None:
            self.entries.append([key, [line]])
        elif self.get(key) != value or isinstance(self.get(key), bool) != isinstance(value, bool):
            e[1] = [line]

    def remove(self, key):
        self.entries = [e for e in self.entries if e[0] != key]

    def text(self):
        lines = []
        for _, raw in self.entries:
            lines.extend(raw)
        return "\n".join(lines)


def parse_frontmatter(text):
    """Split text into (Frontmatter or None, body). CRLF is read as LF."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n") and text.strip() != "---":
        return None, text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() in ("---", "..."):
            fm = Frontmatter.parse("\n".join(lines[1:i])) if i > 1 else Frontmatter()
            return fm, "\n".join(lines[i + 1:])
    return None, text


def dump_frontmatter(fields):
    fm = Frontmatter()
    for k, v in fields.items():
        fm.set(k, v)
    return "---\n" + fm.text() + "\n---\n"


def read_frontmatter(text):
    """Frontmatter as a plain dict ({} when there is none)."""
    if text is None:
        return {}
    fm, _ = parse_frontmatter(text.replace("\r\n", "\n"))
    return fm.to_dict() if fm else {}


# ---------------------------------------------------------------- marker block

def read_block(text):
    """Content between the markers, without the surrounding newlines, or None."""
    if text is None:
        return None
    text = text.replace("\r\n", "\n")
    b = text.find(BEGIN)
    if b < 0:
        return None
    e = text.find(END, b + len(BEGIN))
    if e < 0:
        return None
    return text[b + len(BEGIN):e].strip("\n")


def merge_note(existing, block_inner, set_fields=None, remove_fields=()):
    """Return the new file text.

    - Only the text between BEGIN and END is replaced; everything else stays.
    - Frontmatter: fields in set_fields are updated in place or appended,
      fields in remove_fields are dropped, every other entry is kept as is.
    - No markers yet: the block goes right after the frontmatter and the old
      body follows after one blank line.
    - CRLF files stay CRLF.
    """
    existing = existing or ""
    crlf = "\r\n" in existing
    text = existing.replace("\r\n", "\n")
    fm, body = parse_frontmatter(text)
    set_fields = set_fields or {}
    if fm is None and (set_fields or not text):
        fm = Frontmatter() if set_fields else None
    if fm is not None:
        for k, v in set_fields.items():
            fm.set(k, v)
        for k in remove_fields:
            fm.remove(k)

    inner = block_inner.replace("\r\n", "\n").strip("\n")
    block = BEGIN + "\n" + (inner + "\n" if inner else "") + END

    b = body.find(BEGIN)
    e = body.find(END, b + len(BEGIN)) if b >= 0 else -1
    if b >= 0 and e >= 0:
        body = body[:b] + block + body[e + len(END):]
    else:
        rest = body.lstrip("\n")
        body = block + "\n" + ("\n" + rest if rest.strip() else "")

    out = body
    if fm is not None and (fm.entries or text.startswith("---")):
        fm_text = fm.text()
        out = "---\n" + (fm_text + "\n" if fm_text else "") + "---\n" + body
    if crlf:
        out = out.replace("\n", "\r\n")
    return out


# ---------------------------------------------------------------- book note block

def topic_line(topic_names):
    if not topic_names:
        return ""
    return "> 主题：" + " · ".join("[[%s]]" % t for t in topic_names)


def render_book_block(book, topic_names):
    """Generated part of 书/<fileName>.md. Shared by notes.py and topics.py."""
    parts = []
    line = topic_line(topic_names)
    if line:
        parts.append(line)
    for ch in book.get("chapters", []):
        hls = ch.get("highlights", [])
        if not hls:
            continue
        lines = ["## " + (one_line(ch.get("title")) or UNKNOWN_CHAPTER), ""]
        for h in hls:
            lines.append("- " + md_text(h.get("text")))
            for t in thought_lines(h.get("thought")):
                lines.append("  - 💭 " + md_text(t))
        parts.append("\n".join(lines))
    orphans = [o for o in book.get("orphanThoughts", []) if one_line(o.get("text"))]
    if orphans:
        lines = ["## " + ORPHAN_SECTION, ""]
        for o in orphans:
            lines.append("- 💭 " + md_text(o.get("text")))
            if one_line(o.get("quote")):
                lines.append("  > " + md_text(o.get("quote")))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def thought_lines(thought):
    """books.json joins several thoughts on one highlight with '\\n'."""
    if not thought:
        return []
    return [t.strip() for t in str(thought).split("\n") if t.strip()]


def wikilink(name):
    return "[[%s]]" % name


def unwikilink(value):
    v = str(value).strip()
    if v.startswith("[[") and v.endswith("]]"):
        v = v[2:-2]
        return v.split("|")[0]
    return v
