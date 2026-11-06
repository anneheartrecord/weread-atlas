import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import locate  # noqa: E402


class LocateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.old = os.path.join(base, "旧库")
        self.new = os.path.join(base, "Deep", "iCloud", "新库")
        os.makedirs(self.old)
        os.makedirs(os.path.join(self.new, "阅读", "微信读书", ".atlas"))
        with open(os.path.join(self.new, "阅读", "微信读书", ".atlas", "config.json"), "w") as f:
            f.write("{}")
        self.reg = os.path.join(base, "obsidian.json")
        with open(self.reg, "w") as f:
            json.dump({"vaults": {
                "a": {"path": self.old, "ts": 1},
                "b": {"path": self.new, "ts": 5},
                "c": {"path": os.path.join(base, "已删除"), "ts": 9},
            }}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_registry_lists_existing_vaults_newest_first(self):
        vaults = locate.vaults_from_registry([self.reg])
        self.assertEqual([v[1] for v in vaults], [self.new, self.old])

    def test_finds_root_two_levels_deep(self):
        self.assertEqual(locate.roots_in(self.new), [os.path.join(self.new, "阅读", "微信读书")])
        self.assertEqual(locate.roots_in(self.old), [])

    def test_root_from_an_older_run_without_config_is_found(self):
        older = os.path.join(self.old, "微信读书", ".atlas")
        os.makedirs(older)
        with open(os.path.join(older, "books.json"), "w") as f:
            f.write("[]")
        self.assertEqual(locate.roots_in(self.old), [os.path.join(self.old, "微信读书")])

    def test_missing_registry_is_empty(self):
        self.assertEqual(locate.vaults_from_registry([os.path.join(self.tmp.name, "nope.json")]), [])


if __name__ == "__main__":
    unittest.main()
