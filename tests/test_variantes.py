import unittest, pathlib, re
from zakios.parse import parse_frontmatter

ROOT = pathlib.Path(__file__).resolve().parent.parent
V = ROOT / "variantes"


def fm(path):
    meta = parse_frontmatter(path.read_text())
    return meta[0] if isinstance(meta, tuple) else meta


class Variantes(unittest.TestCase):
    files = list(V.rglob("*.md"))

    def test_trois_variantes(self):
        self.assertEqual(len(self.files), 3)

    def test_reviewer_lecture_seule(self):
        text = (V / "agents/code-reviewer.md").read_text()
        tools = re.search(r"^tools:(.*)$", text, re.M).group(1)
        for forbidden in ("Write", "Edit"):
            self.assertNotIn(forbidden, tools)

    def test_aucune_dependance_orpheline(self):
        for f in self.files:
            self.assertNotIn("superpowers:", f.read_text().split("-->", 1)[-1], f)
            self.assertNotIn("REQUIRED SUB-SKILL", f.read_text(), f)

    def test_renvoi_socle_et_marqueur(self):
        marker = "ZAKIOS-SOCLE v1 · PDCA"
        self.assertIn(marker, (ROOT / "socle/REGLES.md").read_text())
        for f in self.files:
            t = f.read_text()
            self.assertIn("socle/REGLES.md", t, f)
            self.assertIn(marker, t, f)

    def test_provenance_des_adaptations(self):
        for name in ("agents/code-reviewer.md", "skills/writing-plans/SKILL.md"):
            self.assertIn("Provenance", (V / name).read_text())

    def test_run_tests_sans_ecriture(self):
        t = (V / "commands/run-tests.md").read_text()
        self.assertNotRegex(re.search(r"allowed-tools:(.*)", t).group(1), r"Write|Edit")
