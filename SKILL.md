---
name: weread-atlas
description: 书脉：把微信读书的划线和想法画成 Obsidian 里的知识地图。每本书一篇笔记，跨书归纳成主题卡片，再生成一个带舆图的本地书房网页。Use when the user wants their WeRead/微信读书 notes organised by topic in Obsidian, a knowledge map of what they have read, a 书房/reading-room page, or to refresh, re-theme or share one they already built. Triggers：「把微信读书笔记整理进 Obsidian」「按主题整理我的读书笔记」「画一张我的知识地图」「生成书房页」「更新书脉」「书房换个风格」「书房页要分享出去，先检查一下」. Needs the official weread-skills skill and WEREAD_API_KEY. Skip it for single-book lookups, store search, recommendations or reading-stat questions (call weread-skills directly), for exporting to Notion or other apps, and for turning a book into a post.
metadata:
  version: "0.1.0"
---

# 书脉 weread-atlas

把一个人在微信读书里留下的划线和想法，变成 Obsidian 里按主题组织的知识：

- `书/` 下每本书一篇笔记。
- `主题/` 下每个主题一张卡片，卡片上的每条观点都链回出处。
- `书房/index.html` 是一个本地网页，包含阅读统计、知识地图、主题卡片和书架。

核心承诺是**知识按主题存放，而不是按书存放**。同步笔记只是手段。

脚本只做确定性的工作：拉数据、写文件、渲染页面。需要判断的工作由你来做：归纳主题、写结论、提炼观点。所有脚本都在本 skill 的 `scripts/` 下，只依赖 Python 3.9+ 标准库，参数统一是 `--root <库>/微信读书`，用 `--help` 查看完整参数。

## 先定位根目录

根目录是用户 Obsidian 库里的 `微信读书/` 文件夹，下文记作 ROOT。

1. 根目录里存在 `.atlas/config.json`，说明以前跑过，这次是增量更新。查找方法：`find ~ -maxdepth 7 -path '*/.atlas/config.json' -not -path '*/node_modules/*' 2>/dev/null`，命中多个时问用户用哪个。

2. 找不到时问用户 Obsidian 库在哪，在库下建 `微信读书/` 作为 ROOT，这次是首次运行。

3. 检查 `WEREAD_API_KEY`。没有时请用户去 https://weread.qq.com/r/weread-skills 登录并复制 key，格式是 `wrk-` 开头，然后 `export WEREAD_API_KEY=...`。

4. 官方 weread-skills 没装时，fetch.py 会退出并给出安装指令，照着装完再继续。

## 首次运行

1. **拉数据**：`python3 scripts/fetch.py --root ROOT`。几百本书需要 10 到 20 分钟，这是正常的，接口只能逐个调用。完成标准是打印出书数、划线数和想法数，`.atlas/books.json` 和 `.atlas/stats.json` 都已生成。

2. **写书的笔记**：`python3 scripts/notes.py --root ROOT`。完成标准是 `书/` 下的篇数等于上一步的书数。

3. **出摘要**：`python3 scripts/digest.py --root ROOT --top 50`。默认只取笔记最多的 50 本，目的是让用户十几分钟内就看到一张像样的地图。用户明确说要全部时，加 `--top 0`。

4. **归纳主题**：先读 [`references/topics-guide.md`](references/topics-guide.md)，再逐个读完 `.atlas/digest/` 下的全部摘要文件，一个都不跳。然后按指南提出领域和主题的方案，整份列给用户确认一次。用户确认后写 `.atlas/topics.json`。完成标准是用户点头，并且摘要里的每一本书都出现在某个主题的 `books` 里，或者出现在 `assign` 里。

5. **写主题卡片**：`python3 scripts/topics.py --root ROOT`。校验报错时按提示改 `topics.json` 再跑，直到通过。

6. **渲染书房页**：`python3 scripts/render.py --root ROOT`，然后把 `ROOT/书房/index.html` 的完整路径给用户，告诉他双击打开即可。

7. **验收**：按下面的验收清单逐条检查，再向用户汇报。

## 增量更新

用户说更新、同步、又读了新书时走这一支：

1. 依次运行 `fetch.py`、`notes.py`。fetch 只会重拉笔记有变化的书。

2. `python3 scripts/digest.py --root ROOT --new`，读完列出的摘要。

3. 把新书归进已有主题，必要时补充或改写观点，然后改 `topics.json`。需要新建主题或新建领域时，先问用户。

4. 依次运行 `topics.py`、`render.py`，再按验收清单检查。

## 只换风格或重新渲染

运行 `python3 scripts/render.py --root ROOT --theme 舆图|羊皮纸|星空`。要让风格长期生效，就改 `.atlas/config.json` 里的 `theme`。

- 舆图：默认风格，古地图，领域是岛屿，主题是城池。
- 羊皮纸：素雅的星图。
- 星空：深色夜空，主题是星星，最适合截图分享。

## 分享前检查

书房页默认会显示用户的想法原话。文件只在本地时没有风险，风险出现在用户要把页面部署到网上、发给别人或截图公开的时候。用户提到这些意图时：

1. 运行 `python3 scripts/share_check.py --root ROOT`。它会列出看起来涉及隐私的想法和划线，比如金额、收入、家人、公司、健康。

2. 把列表原样给用户看，由用户选出要隐藏的编号。

3. 运行 `python3 scripts/share_check.py --root ROOT --exclude 3,7,12`，然后重新渲染。被隐藏的内容只是不上页面，库里的笔记不变。

## 验收清单

向用户汇报前逐条确认：

- `书/` 的篇数等于 books.json 的书数。

- `topics.py` 打印的主题数和领域数，与用户确认的方案一致。

- 随便打开两张主题卡片：一句话结论是一个可以被反驳的判断，核心观点都标了出处。

- 抽查一篇书的笔记：frontmatter 里有领域和主题，正文顶部的主题行能点到对应卡片。

- `render.py` 打印的书数和主题数与上面一致，没有警告；有警告时逐条说明原因。

汇报时告诉用户四件事：书房页的路径、领域和主题的清单、每本书的时长只是下限，以及在 Obsidian 里打开关系图谱就能看到书和主题连成的网。

## 坑

- **接口不能并发。** 并发调用会返回 HTTP 499，脚本已经串行加重试。不要为了提速自己并行调用。

- **升级提示。** 脚本以退出码 3 结束并打印 `upgrade_info` 时，先按提示升级官方 weread-skills，再从头重跑这一步。

- **只覆盖有笔记的书。** 书单来自 `/user/notebooks`，读完了但一条划线都没有的书不会出现。用户问起时如实说明。

- **时长是下限。** 单本书的时长是把每个月读得最多的前 10 本加起来得到的，没进过月度前 10 的书会显示 0。几百本书里有一半显示 0 是正常的。

- **改内容要改对地方。** 标记 `<!-- weread-atlas:begin -->` 和 `<!-- weread-atlas:end -->` 之间的内容每次运行都会被重写。用户想长期保留的补充，写在标记外面；想改主题卡片的结论或观点，改 `topics.json` 再跑 `topics.py`。

- **书的文件名就是链接。** 主题卡片、总览和书房页都靠文件名找到书，用户手动改了文件名，下次 `notes.py` 会按原名重新生成一篇，链接也会断。用户想改名时，提醒他这一点。

- **topics.json 里写文件名。** 书名以 `书/` 下的文件名为准，不带 `.md`。同名书的文件名带作者，例如 `金钱心理学（摩根·豪泽尔）`。写完先跑 `topics.py --check` 只做校验。

- **导入的书没有分类。** bookId 以 `CB_` 开头的书是用户自己导入的，接口不给分类，用 `assign` 给它们指定领域。

- **观点来自书。** 核心观点写的是书里的判断。用户自己的话只出现在我的想法一节，那一节由脚本从原话里挑选。

## 默认值

| 项 | 默认 | 改法 |
|---|---|---|
| 根目录名 | `微信读书` | config 的 `rootName` |
| 页面标题 | `书房` | config 的 `title` |
| 风格 | 舆图 | config 的 `theme` 或 `--theme` |
| 首次归纳的书数 | 50 | config 的 `topN` 或 `--top` |
| 页面上每本书的划线 | 最多 10 条 | 固定 |
| 主题卡片上的想法和划线 | 最多 3 条和 10 条 | 固定 |

文件格式的完整约定在 [`references/vault-format.md`](references/vault-format.md)，改脚本或手工修文件时再读。报错排查见 [`references/troubleshooting.md`](references/troubleshooting.md)。
