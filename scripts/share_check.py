#!/usr/bin/env python3
"""Before sharing the 书房 page: list thoughts and highlights that look personal.

Looks at everything the page can show (every thought and highlight in
books.json that the config `exclude` list does not already hide) and prints the
ones that match the patterns below, numbered, with the book title.

  python3 share_check.py --root <root>                 list
  python3 share_check.py --root <root> --exclude 3,7   hide items 3 and 7 from the page

--exclude appends the exact texts to `exclude` in .atlas/config.json; the
notes in the vault are not changed. Numbers refer to the listing produced from
the same data and config, so run the listing first.

Thoughts are your own words, so all checks apply to them. Highlights are the
book's text: finance books talk about money on every page, so highlights are
only checked for contact and ID-like numbers and the strong political words.
Topic cards (the conclusions, viewpoints and relation reasons in topics.json)
are listed separately: they cannot be hidden with --exclude, only edited.

The word lists are plain constants: extend them for your own situation (for
example add your employer, city or a partner's name to the matching list).
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_lib as lib  # noqa: E402
from digest import all_thoughts  # noqa: E402

# Money: currency signs or a number followed by a unit (5万, 300元, 20k, 1.5w).
MONEY_PATTERNS = [
    r"[¥￥$＄]\s*\d",
    r"\d[\d,.]*\s*(万|千|百万|千万|亿|元|块钱|块|美元|美金|港币|刀)",
    r"\d[\d,.]*\s*[kKwW](?![A-Za-z])",
]

# Salary, savings, debt and holdings.
FINANCE_WORDS = [
    "工资", "薪水", "薪资", "年薪", "月薪", "时薪", "日薪", "年终奖", "奖金", "到手", "公积金", "个税",
    "存款", "储蓄", "积蓄", "存了", "攒了", "余额", "净资产", "身家",
    "负债", "房贷", "车贷", "贷款", "信用卡", "欠款", "债务", "借款", "花呗",
    "持仓", "仓位", "加仓", "减仓", "清仓", "建仓", "割肉", "浮亏", "浮盈", "期权", "股票账户",
    "买入", "卖出", "抄底", "职级", "年包", "年入", "月入", "收入",
]

# Age and body numbers: "今年刚好21", "25-26岁", "胖了 8.7KG", "瘦身 50 斤", "超重了五十斤", "BMI 刚好在30边缘".
AGE_BODY_PATTERNS = [
    r"\d{2}\s*(岁|周岁)",
    r"今年\s*(刚好|才|已经)?\s*\d{2}",
    r"\d+(\.\d+)?\s*(kg|KG|Kg|公斤|斤)(?![A-Za-z])",
    r"[一二三四五六七八九十两几百]+\s*(公斤|斤)",
    r"BMI|体重|体脂|超重",
]

# Books that look like the user's own uploads rather than published books:
# imported (bookId CB_…) with a tool or blank author, or a file-like title with a date or locale tag.
UPLOAD_AUTHORS = ["python-docx", "docx", "microsoft", "administrator", "wps", "word", "unknown", "未知"]
UPLOAD_TITLE_PATTERNS = [r"20\d{2}[-_.]?\d{2}[-_.]?\d{2}", r"\.(zh|en)-[A-Za-z]{2}", r"_\d{6,}"]

# Phone numbers, e-mail addresses, ID cards and other long digit strings.
CONTACT_PATTERNS = [
    r"(?<!\d)1[3-9]\d{9}(?!\d)",
    r"[\w.+-]+@[\w-]+\.[\w.]+",
    r"(?<!\d)\d{17}[\dXx](?![\dXx])",
    r"(?<!\d)\d{8,}(?!\d)",
]

# Family and partner.
FAMILY_WORDS = [
    "老婆", "老公", "妻子", "丈夫", "女朋友", "男朋友", "女友", "男友", "我对象", "前任", "恋爱",
    "爸爸", "妈妈", "我爸", "我妈", "父亲", "母亲", "父母", "爸妈", "家里", "家人",
    "孩子", "儿子", "女儿", "岳父", "岳母", "公公", "婆婆", "亲戚", "结婚", "离婚", "婚礼", "彩礼",
]

# Employer and colleagues.
WORK_WORDS = [
    "公司", "老板", "领导", "上司", "同事", "组长", "部门", "团队里", "离职", "跳槽", "辞职",
    "面试", "绩效", "晋升", "升职", "加班", "裁员", "入职", "试用期", "offer", "HR",
    "裸辞", "gap", "Gap", "退休", "求职", "找工作", "转岗", "工时", "大厂", "副业",
]

# Health.
HEALTH_WORDS = [
    "医院", "医生", "生病", "病了", "疾病", "抑郁", "焦虑症", "失眠", "吃药", "服药", "手术",
    "确诊", "体检", "住院", "心理咨询", "复查",
]

# Politically sensitive words. Mainland readers, platforms and employers react to these.
# The strong list is checked everywhere; the broader list only in the owner's own thoughts,
# because books mention governments and elections on every other page.
POLITICAL_STRONG = [
    "共产党", "党中央", "政治局", "习近平", "毛泽东", "毛主席", "文革", "文化大革命", "六四", "天安门",
    "台独", "维稳", "翻墙", "言论自由", "宪政", "独裁", "极权", "专制",
]
POLITICAL_WORDS = POLITICAL_STRONG + ["党员", "政府", "政权", "民主", "集权", "审查", "选举", "台湾", "西藏", "新疆",
                                      "体制", "党委", "书记", "一把手", "政绩", "城投"]

# A first-person sentence that also contains a number ("我去年存了…", "我 28 岁…").
FIRST_PERSON_NUMBER = r"我[^。！？!?]{0,30}\d|\d[^。！？!?]{0,30}我"

THOUGHT_CHECKS = [
    ("金额", MONEY_PATTERNS, True),
    ("收入与持仓", FINANCE_WORDS, False),
    ("联系方式或证件号", CONTACT_PATTERNS, True),
    ("家人与伴侣", FAMILY_WORDS, False),
    ("工作单位与同事", WORK_WORDS, False),
    ("健康", HEALTH_WORDS, False),
    ("年龄与身体数字", AGE_BODY_PATTERNS, True),
    ("带数字的个人经历", [FIRST_PERSON_NUMBER], True),
    ("政治敏感", POLITICAL_WORDS, False),
]
HIGHLIGHT_CHECKS = [("联系方式或证件号", CONTACT_PATTERNS, True), ("政治敏感", POLITICAL_STRONG, False)]
# Topic cards: conclusions, viewpoints and relation reasons the agent wrote. They state what books
# say, so money words, a quoted "我" and ages from a book ("30 岁以上") are normal there; what does
# not belong is the owner's own life with its numbers, or politics.
# The owner speaking about their own numbers, money or employer: "我月薪三万…", "我 28 岁…".
FIRST_PERSON_FACT = (r"(?<![自本忘唯无])我(?![们执])[^。！？!?]{0,30}"
                     r"(\d|[一二三四五六七八九十两百千]+\s*(万|千|岁|斤|公斤|块|元)|月薪|年薪|工资|存款|收入|公司|老板)")
TOPIC_CHECKS = [
    ("第一人称的个人情况", [FIRST_PERSON_FACT], True),
    ("政治敏感", POLITICAL_STRONG, False),
]

CLIP = 120


def flags(text, checks):
    hits = []
    for label, items, is_regex in checks:
        if is_regex:
            if any(re.search(p, text) for p in items):
                hits.append(label)
        elif any(w in text for w in items):
            hits.append(label)
    return hits


def own_uploads(books, hidden):
    """Books on the page that look like the user's own files; their titles and links would be public."""
    out = []
    for b in books:
        if b["fileName"] in hidden or not str(b.get("bookId", "")).startswith("CB_"):
            continue
        author = (b.get("author") or "").strip().lower()
        title = b.get("title") or ""
        reasons = []
        if not author or any(w in author for w in UPLOAD_AUTHORS):
            reasons.append("作者显示为 %s" % (b.get("author") or "空"))
        if any(re.search(p, title) for p in UPLOAD_TITLE_PATTERNS):
            reasons.append("书名像文件名")
        if reasons:
            out.append({"book": title or b["fileName"], "fileName": b["fileName"], "reasons": reasons})
    return out


def published_items(books, exclude):
    """(book, kind, text) for everything the page may show, in a stable order."""
    for b in books:
        for text, quote in all_thoughts(b):
            if not lib.excluded(text, exclude):
                yield b, "想法", text
        for ch in b.get("chapters", []):
            for h in ch.get("highlights", []):
                t = h.get("text") or ""
                if t and not lib.excluded(t, exclude):
                    yield b, "划线", t


def find(books, exclude):
    found, counts = [], {"想法": 0, "划线": 0}
    seen = set()
    for b, kind, text in published_items(books, exclude):
        counts[kind] += 1
        if (kind, text) in seen:
            continue
        hits = flags(text, THOUGHT_CHECKS if kind == "想法" else HIGHLIGHT_CHECKS)
        if hits:
            seen.add((kind, text))
            found.append({"book": b.get("title") or b["fileName"], "kind": kind, "text": text, "flags": hits})
    return found, counts


def topic_texts(data):
    """(topic, part, text) for every piece of agent-written text the page shows on topic cards."""
    if not isinstance(data, dict):
        return
    for t in data.get("topics") or []:
        if not isinstance(t, dict):
            continue
        name = t.get("name") or ""
        if t.get("oneLiner"):
            yield name, "一句话结论", str(t["oneLiner"])
        for v in t.get("viewpoints") or []:
            if isinstance(v, dict):
                text = "".join(str(v.get(k) or "") for k in ("claim", "text"))
                if text:
                    yield name, "观点", "%s：%s" % (v.get("claim") or "", v.get("text") or "")
        for r in t.get("related") or []:
            if isinstance(r, dict) and r.get("why"):
                yield name, "关系理由", "%s：%s" % (r.get("topic") or "", r["why"])


def find_topic_text(data):
    out = []
    for name, part, text in topic_texts(data):
        hits = flags(text, TOPIC_CHECKS)
        if hits:
            out.append({"topic": name, "part": part, "text": text, "flags": hits})
    return out


def run(paths, exclude_numbers=None, hide_numbers=None, log=print):
    cfg = lib.load_config(paths.root)
    hidden = set(cfg.get("hideBooks") or [])
    books = [b for b in lib.load_books(paths) if b["fileName"] not in hidden]
    found, counts = find(books, cfg.get("exclude") or [])
    uploads = own_uploads(books, hidden)
    if hide_numbers:
        bad = [n for n in hide_numbers if not 1 <= n <= len(uploads)]
        if bad:
            log("书的编号超出范围（1–%d）：%s。先不带参数运行，看清编号再选。" % (len(uploads), ", ".join(map(str, bad))))
            return 1
        for n in hide_numbers:
            cfg["hideBooks"].append(uploads[n - 1]["fileName"])
        lib.save_config(paths.root, cfg)
        log("已把 %d 本书加入 hideBooks，书房页重新渲染后整本不再显示。库里的笔记没有改动。" % len(hide_numbers))
        if not exclude_numbers:
            return 0
    if exclude_numbers:
        bad = [n for n in exclude_numbers if not 1 <= n <= len(found)]
        if bad:
            log("编号超出范围（1–%d）：%s。先不带 --exclude 运行，看清编号再选。" % (len(found), ", ".join(map(str, bad))))
            return 1
        added = 0
        for n in exclude_numbers:
            text = found[n - 1]["text"]
            if text not in cfg["exclude"]:
                cfg["exclude"].append(text)
                added += 1
        lib.save_config(paths.root, cfg)
        log("已把 %d 条加入 %s 的 exclude，书房页重新渲染后不再显示。库里的笔记没有改动。" % (added, paths.config))
        return 0
    log("检查了书房页可能显示的 %d 条想法和 %d 条划线，%d 条看起来涉及个人信息："
        % (counts["想法"], counts["划线"], len(found)))
    for i, f in enumerate(found, 1):
        text = f["text"] if len(f["text"]) <= CLIP else f["text"][:CLIP] + "…"
        log("[%d] 《%s》%s · %s：%s" % (i, f["book"], f["kind"], "、".join(f["flags"]), text))
    if found:
        log("要隐藏哪几条，运行：share_check.py --root <根目录> --exclude 编号,编号")
    if uploads:
        log("")
        log("另有 %d 本书看起来是自己上传的文件，书名会公开，阅读链接别人也打不开：" % len(uploads))
        for i, u in enumerate(uploads, 1):
            log("[书%d] 《%s》：%s" % (i, u["book"], "，".join(u["reasons"])))
        log("要整本隐藏，运行：share_check.py --root <根目录> --hide-books 编号,编号")
    topic_hits = find_topic_text(lib.read_json(paths.topics_json))
    if topic_hits:
        log("")
        log("主题卡片里的文字有 %d 处值得再看一眼，它们会整句出现在页面上：" % len(topic_hits))
        for h in topic_hits:
            text = h["text"] if len(h["text"]) <= CLIP else h["text"][:CLIP] + "…"
            log("[主题] 「%s」%s · %s：%s" % (h["topic"], h["part"], "、".join(h["flags"]), text))
        log("这些是 agent 写的文字，不能用 --exclude 隐藏；要改就改 .atlas/topics.json，再运行 topics.py 和 render.py。")
    log("")
    log("部署时只上传 书房/index.html 这一个文件。.atlas/ 里有全部笔记原文和账号缓存，书/ 是笔记本身，都不要公开。")
    return 0


def _numbers(value):
    try:
        return [int(x) for x in value.replace("，", ",").split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError("编号要写成 3,7,12 这样")


def main(argv=None):
    ap = argparse.ArgumentParser(description="分享书房页前，列出看起来涉及个人信息的想法和划线。")
    ap.add_argument("--root", required=True, help="Obsidian 库里的 微信读书 根目录")
    ap.add_argument("--exclude", type=_numbers, help="把这些编号的原文加入配置的 exclude，例如 3,7,12")
    ap.add_argument("--hide-books", type=_numbers, help="把列表里这些编号的书整本从书房页隐藏，例如 1,2")
    args = ap.parse_args(argv)
    return run(lib.Paths(args.root), exclude_numbers=args.exclude, hide_numbers=args.hide_books)


if __name__ == "__main__":
    sys.exit(main())
