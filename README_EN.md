# weread-atlas (书脉)

English · [中文](README.md)

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white) ![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen) ![Agent Skill](https://img.shields.io/badge/Agent-Skill-purple)

Turn the books you have read into a map of what you know.

weread-atlas is an agent skill. It pulls your highlights and notes from WeRead (微信读书) and reorganises them in Obsidian by topic. You get one note per book, plus one card per topic drawn across books, and every viewpoint on a card links back to its sources. It then renders a local reading-room page with your reading stats, a knowledge map and your bookshelf.

Knowledge is filed by topic, not by book. Syncing the notes is only the first step.

## What it produces

```
your-vault/微信读书/
  总览.md          overview: domains, topics and reading stats
  书/              one note per book with notes; chapters, highlights and thoughts kept verbatim
  主题/            one card per topic: a one-line conclusion, viewpoints, your thoughts, key highlights
  书房/index.html  the reading-room page; open it with a double click
```

- Open Obsidian's graph view and books and topics form one network.

- Topics are drawn from your own notes, not from a fixed taxonomy. The first run covers the 50 books with the most notes, so an account with a few hundred books gets its map in about half an hour: roughly 10 minutes to fetch and 15 to work out topics. The remaining books can be added in batches.

- Re-runs only rewrite the generated block. Anything else you write in a note stays where it is.

- The page comes in three styles: 舆图 (old map), 羊皮纸 (parchment) and 星空 (night sky).

## Install

1. Install the official WeRead skill. Tell your agent: `Download https://cdn.weread.qq.com/skills/weread-skills.zip and install the skill`.

2. Sign in at https://weread.qq.com/r/weread-skills, copy your API key (it starts with `wrk-`), then run `export WEREAD_API_KEY=wrk-...`. Keep the key in the environment only.

3. Put this repository in your agent's skills folder, for example:

   ```bash
   git clone https://github.com/anneheartrecord/weread-atlas ~/.claude/skills/weread-atlas
   ```

   Codex uses `~/.codex/skills/`. For any other agent that supports skills, use its own skills folder.

It needs only Python 3.9 or later and no third-party packages.

## Use

Tell your agent:

> Organise my WeRead notes into Obsidian by topic and make me a reading-room page.

The agent finds your Obsidian vault, fetches your data, writes the book notes and works out topics. It shows you the proposed domains and topics once for confirmation, then renders the page. Later, "update my atlas" syncs only what changed, and "switch the reading room to the night-sky style" changes the style.

The full workflow, defaults and caveats are in [SKILL.md](SKILL.md). The file formats are in [references/vault-format.md](references/vault-format.md).

## Privacy

Your data stays on your machine. The scripts call only the official WeRead API and write only into your Obsidian vault. The page shows your thoughts verbatim by default. Before you deploy it or share it, ask the agent for a share check. It lists thoughts that mention money, family, employers, health and the like, and you choose which to hide. Hidden items are left off the page only; your notes are untouched.

## Known limits

- Only books with notes are included. Books you read without highlighting anything do not appear.

- Per-book reading time is a lower bound, because the API only reports each month's top 10 books.

- The first fetch of a few hundred books takes 10 to 20 minutes because the API does not allow parallel calls. Later updates take seconds.

## License

[MIT](LICENSE)
