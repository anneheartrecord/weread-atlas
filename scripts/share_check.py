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
only checked for contact and ID-like numbers.

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
    "工资", "薪水", "薪资", "年薪", "月薪", "年终奖", "奖金", "到手", "公积金", "个税",
    "存款", "储蓄", "积蓄", "存了", "攒了", "余额", "净资产", "身家",
    "负债", "房贷", "车贷", "贷款", "信用卡", "欠款",
    "持仓", "仓位", "加仓", "减仓", "清仓", "建仓", "割肉", "浮亏", "浮盈", "期权", "股票账户",
]

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
]

# Health.
HEALTH_WORDS = [
    "医院", "医生", "生病", "病了", "疾病", "抑郁", "焦虑症", "失眠", "吃药", "服药", "手术",
    "确诊", "体检", "住院", "心理咨询", "复查",
]

# A first-person sentence that also contains a number ("我去年存了…", "我 28 岁…").
FIRST_PERSON_NUMBER = r"我[^。！？!?]{0,30}\d|\d[^。！？!?]{0,30}我"

THOUGHT_CHECKS = [
    ("金额", MONEY_PATTERNS, True),
    ("收入与持仓", FINANCE_WORDS, False),
    ("联系方式或证件号", CONTACT_PATTERNS, True),
    ("家人与伴侣", FAMILY_WORDS, False),
    ("工作单位与同事", WORK_WORDS, False),
    ("健康", HEALTH_WORDS, False),
    ("带数字的个人经历", [FIRST_PERSON_NUMBER], True),
]
HIGHLIGHT_CHECKS = [("联系方式或证件号", CONTACT_PATTERNS, True)]

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


def run(paths, exclude_numbers=None, log=print):
    books = lib.load_books(paths)
    cfg = lib.load_config(paths.root)
    found, counts = find(books, cfg.get("exclude") or [])
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
    args = ap.parse_args(argv)
    return run(lib.Paths(args.root), exclude_numbers=args.exclude)


if __name__ == "__main__":
    sys.exit(main())
