import unittest

from zakios.parse import is_yaml_marker, norm, parse_frontmatter, summarize


class ParseTests(unittest.TestCase):
    def test_folded_description_is_not_a_marker(self):
        text = "---\nname: a\ndescription: >-\n  première ligne\n  seconde ligne\n---\ncorps"
        meta, body, issue = parse_frontmatter(text)
        self.assertIsNone(issue)
        self.assertEqual(norm(meta["description"]), "première ligne seconde ligne")
        self.assertFalse(is_yaml_marker(norm(meta["description"])))
        self.assertEqual(body, "corps")

    def test_literal_block_description(self):
        meta, _, issue = parse_frontmatter("---\ndescription: |\n  ligne un\n  ligne deux\n---\n")
        self.assertIsNone(issue)
        self.assertEqual(norm(meta["description"]), "ligne un ligne deux")

    def test_missing_fields_are_not_errors(self):
        meta, _, issue = parse_frontmatter("---\nname: seul\n---\ncorps")
        self.assertIsNone(issue)
        self.assertEqual(norm(meta.get("description")), "")

    def test_no_frontmatter(self):
        meta, body, issue = parse_frontmatter("# Titre\n\ntexte")
        self.assertEqual((meta, issue), ({}, None))
        self.assertTrue(body.startswith("# Titre"))

    def test_invalid_yaml_is_reported_not_silenced(self):
        meta, _, issue = parse_frontmatter("---\nname: a\ndescription: Use when: ceci casse le YAML\n---\n")
        self.assertEqual(meta, {})
        self.assertTrue(issue.startswith("yaml_invalide"))

    def test_unicode_and_lists(self):
        meta, _, issue = parse_frontmatter("---\nname: é\ntools: [Read, Write]\ndescription: خدمة عربية — français\n---\n")
        self.assertIsNone(issue)
        self.assertEqual(norm(meta["tools"]), "Read, Write")
        self.assertIn("عربية", norm(meta["description"]))

    def test_summarize_cuts_examples_and_truncates(self):
        self.assertEqual(summarize("Mission claire.<example>long exemple</example>"), "Mission claire.")
        self.assertLessEqual(len(summarize("x" * 500)), 240)

    def test_marker_detection(self):
        for marker in ("|", ">", ">-", "|+", " >- "):
            self.assertTrue(is_yaml_marker(marker))
        self.assertFalse(is_yaml_marker("vraie description"))


if __name__ == "__main__":
    unittest.main()
