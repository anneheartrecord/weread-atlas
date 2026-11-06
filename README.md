# 书脉 weread-atlas

[English](README_EN.md) · 中文

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white) ![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen) ![Agent Skill](https://img.shields.io/badge/Agent-Skill-purple)

把读过的书，画成一张自己的知识地图。

书脉是一个 agent skill。它从微信读书拿到你的划线和想法，在 Obsidian 里按主题重新组织：每本书一篇笔记，跨书归纳出的主题各成一张卡片，卡片上的每条观点都链回出处。最后生成一个本地书房网页，内容包括阅读统计、知识地图和书架。

知识不按书存放，按主题存放。同步笔记只是第一步。

## 它会生成什么

```
你的库/微信读书/
  总览.md          领域、主题和阅读统计的入口
  书/              每本有笔记的书一篇，章节、划线、想法逐字保留
  主题/            每个主题一张卡片：一句话结论、核心观点、我的想法、代表划线
  书房/index.html  本地书房页，双击即可打开
```

- 在 Obsidian 里打开关系图谱，书和主题会连成一张网。

- 主题由 agent 从你自己的笔记里归纳，不套固定分类。首次运行先处理笔记最多的 50 本，几百本书的账号大约半小时能看到地图：拉数据 10 分钟左右，归纳主题十几分钟。其余的书之后分批补齐。

- 重复运行只更新生成区块，你在笔记里写的其他内容保持原样。

- 书房页有三套风格：舆图、羊皮纸、星空。

## 安装

1. 安装微信读书官方 skill：对你的 agent 说 `Download https://cdn.weread.qq.com/skills/weread-skills.zip and install the skill`。

2. 到 https://weread.qq.com/r/weread-skills 登录，复制 `wrk-` 开头的 API Key，然后 `export WEREAD_API_KEY=wrk-...`。Key 只放在环境变量里。

3. 把本仓库放进你的 agent 的 skills 目录，例如：

   ```bash
   git clone https://github.com/anneheartrecord/weread-atlas ~/.claude/skills/weread-atlas
   ```

   Codex 用 `~/.codex/skills/`，其他支持 skill 的 agent 放进各自的 skills 目录。

只需要 Python 3.9 或更高版本，不依赖任何第三方库。

## 使用

对 agent 说：

> 把我微信读书的笔记按主题整理进 Obsidian，再生成一个书房页。

agent 会先找到你的 Obsidian 库，然后依次拉数据、写笔记、归纳主题，把领域和主题方案给你确认一次，最后渲染页面。之后说“更新书脉”就会增量同步，说“书房换成星空风格”就会换一套风格。

完整流程、默认值和注意事项写在 [SKILL.md](SKILL.md)，文件格式见 [references/vault-format.md](references/vault-format.md)。

## 隐私

数据只在你本机：脚本只调用微信读书官方接口，结果只写进你的 Obsidian 库。书房页默认会显示你的想法原话。打算部署到网上或发给别人之前，让 agent 做一次分享前检查：它会列出涉及金额、家人、公司、健康等内容的想法，由你决定隐藏哪些。隐藏的内容只是不上页面，库里的笔记不变。

## 已知限制

- 只包含有笔记的书。读过但没有划线的书不会出现。

- 单本书的阅读时长只能算下限：接口只给出每月读得最多的前 10 本。

- 首次拉取几百本书需要 10 到 20 分钟。接口不支持并发，之后的增量更新只需要几秒。

## 许可

[MIT](LICENSE)
