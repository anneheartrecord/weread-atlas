---
name: weread-atlas
description: 书脉：把微信读书的划线和想法画成 Obsidian 里的知识地图。每本书一篇笔记，跨书归纳成主题卡片并写明主题之间为什么相连，再生成一个带知识环和书架的本地网页。Use when the user wants their WeRead/微信读书 notes organised by topic in Obsidian, a map of how the books they read connect, a reading-room page, or to refresh or share one they already built. Triggers：「把微信读书笔记整理进 Obsidian」「按主题整理我的读书笔记」「画一张我的知识地图」「看看我读的书之间有什么联系」「生成书房页」「更新书脉」「书房页要分享出去，先检查一下」. Needs the official weread-skills skill and WEREAD_API_KEY. Skip it for single-book lookups, store search, recommendations or reading-stat questions (call weread-skills directly), for exporting to Notion or other apps, and for turning a book into a post.
metadata:
  version: "0.1.0"
---

# 书脉 weread-atlas

把一个人在微信读书里留下的划线和想法，变成 Obsidian 里按主题组织的知识：

- `书/` 下每本书一篇笔记。
- `主题/` 下每个主题一张卡片，卡片上的每条观点都链回出处。
- `书房/index.html` 是一个本地网页：顶部是阅读总账，中间是知识环，领域是环上的弧，主题是弧上的点，主题之间的关系画成环内的连线，跨领域的脉络单独列在一旁；下面是阅读节奏和书架。页面跟随系统的浅色或深色设置。

核心承诺是**知识按主题存放，而不是按书存放**。同步笔记只是手段。

脚本只做确定性的工作：拉数据、写文件、渲染页面。需要判断的工作由你来做：归纳主题、写结论、提炼观点。所有脚本都在本 skill 的 `scripts/` 下，只依赖 Python 3.9+ 标准库，参数统一是 `--root <库>/微信读书`，用 `--help` 查看完整参数。

## 先定位根目录，再预检

根目录是用户 Obsidian 库里的 `微信读书/` 文件夹，下文记作 ROOT。

1. 运行 `python3 scripts/locate.py`。它读 Obsidian 自己的库注册表，列出所有库，并标出已经有书脉根目录的库，标记为 `书脉：<路径>`。

2. 有书脉根目录时，ROOT 就是它，这次走增量更新；有多个时问用户用哪个。没有时，问用户要用哪个库，在库下建 `微信读书/` 作为 ROOT，这次走首次运行。注册表找不到时，直接问用户库的路径。

3. 运行 `python3 scripts/weread_client.py --ping`，几秒钟内会验证官方 weread-skills 已安装、`WEREAD_API_KEY` 可用。有任何一项失败，都先解决再往下走：没装官方 skill 时，按它打印的安装指令装；没有 key 时，请用户到 https://weread.qq.com/r/weread-skills 登录并复制 `wrk-` 开头的 key，然后 `export WEREAD_API_KEY=...`。

## 首次运行

1. **拉数据**：`python3 scripts/fetch.py --root ROOT`。几百本书需要 10 到 20 分钟，这是正常的，接口只能逐个调用。完成标准是打印出书数、划线数和想法数，`.atlas/books.json` 和 `.atlas/stats.json` 都已生成。

2. **写书的笔记**：`python3 scripts/notes.py --root ROOT`。完成标准是 `书/` 下的篇数等于上一步的书数。

3. **出摘要**：`python3 scripts/digest.py --root ROOT --top 50`。先只取笔记最多的 50 本，让用户在半小时内看到一张像样的地图。用户要全部的书时，也先用这 50 本走完第 4、5 步，再按增量更新一节分批补进剩下的书，每批读完一轮 `--new` 的摘要，直到它报告没有新书。一次读几百本的摘要会撑满上下文，读到后面就开始漏。

4. **归纳主题**：先读 [`references/topics-guide.md`](references/topics-guide.md)，再逐个读完 `.atlas/digest/` 下的全部摘要文件，一个都不跳。然后按指南提出领域和主题的方案，连同主题之间的关系，整份列给用户确认一次。用户确认后写 `.atlas/topics.json`，每个主题带 2 到 5 条 `related`，`why` 说出连接两者的那个想法。完成标准是用户点头，摘要里的每一本书都出现在某个主题的 `books` 里或者 `assign` 里，并且每个主题都有 `related`。

5. **写主题卡片**：`python3 scripts/topics.py --root ROOT`。校验报错时按提示改 `topics.json` 再跑，直到通过。

6. **渲染书房页**：`python3 scripts/render.py --root ROOT`，然后把 `ROOT/书房/index.html` 的完整路径给用户，告诉他双击打开即可。

7. **验收**：按下面的验收清单逐条检查，再向用户汇报。

## 增量更新

用户说更新、同步、又读了新书时走这一支：

1. 依次运行 `fetch.py`、`notes.py`。fetch 只会重拉笔记有变化的书。

2. `python3 scripts/digest.py --root ROOT --new`，读完列出的摘要。

3. 把新书归进已有主题，必要时补充或改写观点，然后改 `topics.json`。需要新建主题或新建领域时，先问用户；新主题也要写 `related`。`--new` 一次列出的摘要超过 4 个文件时，读完前 4 个就先写 `topics.json` 并运行 `topics.py`，再重新运行 `--new` 处理剩下的。

4. 依次运行 `topics.py`、`render.py`，再按验收清单检查。

## 只重新渲染

运行 `python3 scripts/render.py --root ROOT`。书房页只有一种样式，浅色和深色跟随系统设置，没有风格可选；用户要换风格时如实说明。旧配置里的 `theme` 字段会被忽略。页面标题改 `.atlas/config.json` 的 `title`。

## 分享前检查

书房页默认会显示用户的想法原话。文件只在本地时没有风险，风险出现在用户要把页面部署到网上、发给别人或截图公开的时候。用户提到这些意图时：

1. 运行 `python3 scripts/share_check.py --root ROOT`。它列出两类东西：看起来涉及隐私的想法和划线，比如金额、收入、年龄、体重、家人、公司、健康；以及看起来是用户自己上传的文件，这类书的书名会公开，阅读链接别人也打不开。

2. 脚本靠关键词，会漏。再自己通读一遍页面上会出现的想法，把能认出这个人的内容补进来：年龄、公司内部的叫法、具体的离职或求职经历。然后把整份清单给用户看，由用户选。

3. 按用户的选择运行 `share_check.py --root ROOT --exclude 3,7,12` 隐藏单条，`--hide-books 1,2` 整本隐藏；脚本漏掉、你补出来的条目，把原文片段直接追加到 `.atlas/config.json` 的 `exclude`。然后重新渲染。隐藏写在配置里，以后每次渲染都生效；库里的笔记不变。

4. 提醒用户：部署时只上传 `书房/index.html` 这一个文件。`.atlas/` 里有全部笔记原文、账号缓存和被隐藏内容的原文，`书/` 是笔记本身，这两处都不要公开。

## 验收清单

向用户汇报前逐条确认：

- `书/` 的篇数等于 books.json 的书数。

- `topics.py` 打印的主题数和领域数，与用户确认的方案一致。

- 随便打开两张主题卡片：一句话结论是一个可以被反驳的判断，核心观点都标了出处，末尾的相关主题一节有 2 到 5 条，理由说的是想法而不是“两者相关”。

- `topics.py` 没有打印“没有 related”的提醒，也就是每个主题都有关系。

- 抽查一篇书的笔记：frontmatter 里有领域和主题，正文顶部的主题行能点到对应卡片。

- `render.py` 打印的书数和主题数与上面一致，没有警告；有警告时逐条说明原因。它打印的跨领域关系不是 0 条，打开页面时知识环旁边的脉络栏列着这些跨领域关系和理由；只有一个领域时，脉络栏改列同领域的关系。

汇报时告诉用户四件事：书房页的路径、领域和主题的清单、每本书的时长只是下限，以及在 Obsidian 里打开关系图谱就能看到书和主题连成的网。

## 坑

- **按脚本原样串行调用。** 接口一并发就返回 HTTP 499，脚本已经串行调用并带重试，直接运行脚本即可，几百本书的首次拉取要 10 到 20 分钟。

- **退出码 3 就先升级。** 脚本打印 `upgrade_info` 并以退出码 3 结束时，按提示升级官方 weread-skills，再重跑这一步。

- **改内容要改对地方。** 标记 `<!-- weread-atlas:begin -->` 和 `<!-- weread-atlas:end -->` 之间的内容每次运行都会被重写。用户想长期保留的补充写在标记外面；想改主题卡片的结论或观点，改 `topics.json` 再跑 `topics.py`。

- **topics.json 里写文件名。** 书名以 `书/` 下的文件名为准，不带 `.md`，摘要里的文件名那一行就是它。写完先跑 `topics.py --check` 只做校验。bookId 以 `CB_` 开头的是用户自己导入的书，没有分类，用 `assign` 给它们指定领域。

- **观点来自书。** 核心观点写的是书里的判断。用户自己的话只出现在我的想法一节，那一节由脚本从原话里挑选。

- **向用户说明口径。** 书单只含有笔记的书；单本时长只是下限，一半书显示 0 是正常的。用户问起其他现象时，先查排错文档。

## 默认值

| 项 | 默认 | 改法 |
|---|---|---|
| 根目录名 | `微信读书` | config 的 `rootName` |
| 页面标题 | `书脉` | config 的 `title` |
| 首次归纳的书数 | 50 | config 的 `topN` 或 `--top` |
| 页面上每本书的划线 | 最多 10 条 | 固定 |
| 主题卡片上的想法和划线 | 最多 3 条和 10 条 | 固定 |

文件格式的完整约定在 [`references/vault-format.md`](references/vault-format.md)，改脚本或手工修文件时再读。报错排查见 [`references/troubleshooting.md`](references/troubleshooting.md)。
