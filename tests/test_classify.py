import unittest

from zakios.classify import COMPONENT_TYPES, classify


class ClassifyTests(unittest.TestCase):
    def test_plugin_manifest_is_a_plugin_never_a_hook(self):
        self.assertEqual(classify("plugins/guard/.claude-plugin/plugin.json"), "plugin")
        self.assertNotEqual(classify("plugins/guard/.claude-plugin/plugin.json"), "hook")

    def test_skill_and_embedded_agent(self):
        self.assertEqual(classify("skills/dev/tdd/SKILL.md"), "skill")
        self.assertEqual(classify("skills/dev/tdd/agents/grader.md"), "embedded_agent")
        self.assertEqual(classify("agents/web/frontend.md"), "agent")
        self.assertEqual(classify("categories/01-core/api.md"), "agent")

    def test_annexes_are_not_components(self):
        for rel in ("agents/README.md", "commands/CHANGELOG.md", "hooks/tests/guard.test.js",
                    "hooks/utils/helper.py", "node_modules/x/SKILL.md", "docs/guide.md",
                    "hooks/HOOK_PATTERNS.json", "agents/test_helper.py"):
            self.assertIsNone(classify(rel), rel)

    def test_commands_and_hooks(self):
        self.assertEqual(classify("commands/git/commit.md"), "command")
        self.assertEqual(classify(".claude/hooks/pre_tool_use.py"), "hook")
        self.assertEqual(classify("hooks/git/guard.json"), "hook")

    def test_a_mod_is_a_single_component(self):
        self.assertEqual(classify("mods/security/jail/README.md"), "mod")
        for rel in ("mods/README.md", "mods/security/jail/.claude-plugin/plugin.json",
                    "mods/security/jail/hooks/block.ts", "mods/security/jail/agents/helper.md",
                    "mods/security/jail/src/index.ts"):
            self.assertIsNone(classify(rel), rel)

    def test_framework_globs(self):
        self.assertEqual(classify("src/lib/orchestrator.py", ["src/lib/orchestrator.py"]), "framework_module")
        self.assertIsNone(classify("src/lib/orchestrator.py"))

    def test_all_types_are_known(self):
        sample = ["skills/a/SKILL.md", "agents/a.md", "skills/s/agents/a.md", "commands/a.md",
                  "hooks/a/b.json", "p/.claude-plugin/plugin.json", "mods/c/m/README.md"]
        self.assertTrue({classify(s) for s in sample} <= set(COMPONENT_TYPES))


if __name__ == "__main__":
    unittest.main()
