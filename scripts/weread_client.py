"""WeRead agent gateway client for 书脉.

- skill_version is read at runtime from the installed official weread skill's
  SKILL.md, so requests always report the version the user actually has.
- Calls are strictly sequential with a short pause between them; the gateway
  answers concurrent calls with HTTP 499.
- A response carrying upgrade_info stops everything (exit code 3).

Run directly to check the setup: python3 weread_client.py
"""

import argparse
import glob
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
PAUSE = 0.15           # seconds between calls
RETRIES = 5            # attempts per call
BACKOFF = 1.5          # seconds, grows linearly per attempt
TIMEOUT = 60

INSTALL_HINT = (
    "没有找到官方 weread skill，书脉需要它提供的版本号。\n"
    "请先安装：Download https://cdn.weread.qq.com/skills/weread-skills.zip and install the skill\n"
    "API Key 在这里获取：https://weread.qq.com/r/weread-skills\n"
    "也可以用 --skill-version x.y.z 手动指定版本。"
)

SKILL_ROOTS = [
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.agents/skills",
    "~/.agent-harness/skills",
]


class WereadError(Exception):
    pass


class UpgradeRequired(WereadError):
    """The gateway asked for a skill upgrade. Callers must stop and exit 3."""


class ApiError(WereadError):
    def __init__(self, api, errcode, msg):
        WereadError.__init__(self, "%s 返回错误 %s：%s" % (api, errcode, msg))
        self.api = api
        self.errcode = errcode


# ---------------------------------------------------------------- version discovery

def _frontmatter(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return text[3:end] if end > 0 else None


def _field(fm, name):
    """Value of `name:` in frontmatter; nested keys are matched at any indent."""
    m = re.search(r"^\s*%s:\s*['\"]?([^'\"\n]+?)['\"]?\s*$" % re.escape(name), fm, re.M)
    return m.group(1).strip() if m else None


def skill_version_from(path):
    fm = _frontmatter(path)
    if fm is None:
        return None
    # metadata: version: "x.y.z" first, then a top-level version:
    m = re.search(r"^metadata:\s*\n((?:[ \t]+.*\n?)*)", fm, re.M)
    if m:
        v = _field(m.group(1), "version")
        if v:
            return v
    m = re.search(r"^version:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", fm, re.M)
    return m.group(1).strip() if m else None


def candidate_skill_files():
    seen = []
    env = os.environ.get("WEREAD_SKILL_DIR")
    if env:
        seen.append(os.path.join(os.path.expanduser(env), "SKILL.md"))
    roots = [os.path.expanduser(r) for r in SKILL_ROOTS]
    for r in roots:
        seen.append(os.path.join(r, "weread-skills", "SKILL.md"))
    for r in roots:
        for p in sorted(glob.glob(os.path.join(r, "*weread*", "SKILL.md"))):
            fm = _frontmatter(p)
            if fm and _field(fm, "name") == "weread-skills" and p not in seen:
                seen.append(p)
    return seen


def discover_skill_version():
    for path in candidate_skill_files():
        if os.path.isfile(path):
            v = skill_version_from(path)
            if v:
                return v, path
    return None, None


# ---------------------------------------------------------------- client

class Client(object):
    def __init__(self, skill_version=None, api_key=None, pause=PAUSE, retries=RETRIES, verbose=True):
        self.api_key = api_key or os.environ.get("WEREAD_API_KEY")
        if not self.api_key:
            raise WereadError("没有设置 WEREAD_API_KEY。获取地址 https://weread.qq.com/r/weread-skills ，"
                              "然后 export WEREAD_API_KEY=<你的apikey>")
        if not skill_version:
            skill_version, _ = discover_skill_version()
        if not skill_version:
            raise WereadError(INSTALL_HINT)
        self.skill_version = skill_version
        self.pause = pause
        self.retries = retries
        self.verbose = verbose
        self.calls = 0
        self.retried = 0
        self.http499 = 0
        self._last = 0.0

    def _post(self, body):
        req = urllib.request.Request(
            GATEWAY, data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def call(self, api, **params):
        body = {"api_name": api}
        body.update(params)
        body["skill_version"] = self.skill_version
        last_err = None
        for attempt in range(self.retries):
            wait = self.pause - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                self.calls += 1
                data = self._post(body)
                self._last = time.time()
            except urllib.error.HTTPError as e:
                self._last = time.time()
                e.close()
                if e.code == 401 or e.code == 403:
                    raise WereadError("WEREAD_API_KEY 无效或已过期（HTTP %d）。重新获取：https://weread.qq.com/r/weread-skills" % e.code)
                if e.code == 499:
                    self.http499 += 1
                if e.code == 499 or e.code == 429 or e.code >= 500:
                    last_err = "HTTP %d" % e.code
                else:
                    raise WereadError("%s 请求失败：HTTP %d" % (api, e.code))
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ValueError) as e:
                self._last = time.time()
                last_err = repr(e)
            else:
                if isinstance(data, dict) and data.get("upgrade_info"):
                    info = data["upgrade_info"]
                    msg = info.get("message") if isinstance(info, dict) else str(info)
                    raise UpgradeRequired(msg or json.dumps(info, ensure_ascii=False))
                if isinstance(data, dict) and data.get("errcode") not in (None, 0):
                    raise ApiError(api, data.get("errcode"), data.get("errmsg") or data.get("msg") or "")
                return data
            self.retried += 1
            if attempt < self.retries - 1:
                time.sleep(BACKOFF * (attempt + 1))
        raise WereadError("%s 连续 %d 次失败，最后一次：%s" % (api, self.retries, last_err))


def make_client(args):
    """Build a Client from parsed CLI args; exits with a message on setup errors."""
    try:
        return Client(skill_version=getattr(args, "skill_version", None))
    except WereadError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="检查 weread skill 版本和 API Key 是否可用。")
    ap.add_argument("--skill-version", help="手动指定 skill_version，默认从官方 weread skill 读取")
    ap.add_argument("--ping", action="store_true", help="调一次 /user/notebooks 验证 Key")
    args = ap.parse_args(argv)
    v, path = discover_skill_version()
    if args.skill_version:
        v, path = args.skill_version, "--skill-version"
    if not v:
        print(INSTALL_HINT, file=sys.stderr)
        return 2
    print("skill_version %s（来自 %s）" % (v, path))
    if args.ping:
        try:
            c = Client(skill_version=v)
            r = c.call("/user/notebooks", count=1)
        except UpgradeRequired as e:
            print("需要升级官方 weread skill：%s" % e, file=sys.stderr)
            return 3
        except WereadError as e:
            print(str(e), file=sys.stderr)
            return 1
        print("连接正常，有笔记的书 %s 本" % r.get("totalBookCount"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
