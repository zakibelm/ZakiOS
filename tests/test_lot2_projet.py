import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
V = ROOT / "variantes" / "commands"
MARQUEUR = "ZAKIOS-SOCLE v1 · PDCA"


def allowed_tools(path):
    text = path.read_text()
    return [t.strip() for t in re.search(r"^allowed-tools:(.*)$", text, re.M).group(1).split(",")]


class Lot2Variantes(unittest.TestCase):
    def test_marqueur_et_provenance(self):
        for name in ("verify-ui.md", "commit.md"):
            text = (V / name).read_text()
            self.assertIn("Variante ZakiOS (brouillon), contenu original", text, name)
            self.assertIn(MARQUEUR, text, name)
            for phase in ("Planifier", "Exécuter", "Vérifier", "Agir"):
                self.assertIn(phase, text, f"{name} : phase {phase}")

    def test_commit_ne_peut_ni_pousser_ni_ecrire_des_fichiers(self):
        tools = allowed_tools(V / "commit.md")
        for t in tools:
            self.assertNotIn("push", t)
            self.assertNotIn("Write", t)
            self.assertNotIn("Edit", t)
            if t.startswith("Bash"):
                self.assertRegex(t, r"^Bash\(git (status|diff|log|add|commit):\*\)$")

    def test_commit_interdit_les_actions_destructrices(self):
        text = (V / "commit.md").read_text()
        for forbidden in ("git push", "--amend", "--no-verify"):
            self.assertIn(forbidden, text)

    def test_verify_ui_ne_modifie_pas_le_projet(self):
        tools = allowed_tools(V / "verify-ui.md")
        self.assertNotIn("Write", tools)
        self.assertNotIn("Edit", tools)
        self.assertIn("mcp__playwright__*", tools)
        self.assertIn("MCP Playwright indisponible", (V / "verify-ui.md").read_text())


class ProjetClaude(unittest.TestCase):
    def test_claude_md_porte_les_regles_non_negociables(self):
        text = (ROOT / "CLAUDE.md").read_text()
        for marker in ("python3 -m unittest", "python3 -m zakios verify", "licence", "audit par comportement", "ne l'édite pas à la main"):
            self.assertIn(marker, text)
        self.assertLess(len(text.splitlines()), 80)

    def test_garde_fous_de_permissions(self):
        cfg = json.loads((ROOT / ".claude" / "settings.json").read_text())
        deny = cfg["permissions"]["deny"]
        for protected in ("catalog/**", "sources/**", "archive/**", "decisions/validated.json", "decisions/licenses.json"):
            self.assertIn(f"Edit({protected})", deny)
            self.assertIn(f"Write({protected})", deny)
        # aucune permission d'écriture réseau ni de push accordée par défaut
        for rule in cfg["permissions"]["allow"]:
            self.assertNotIn("push", rule)
            self.assertNotIn("curl", rule)


if __name__ == "__main__":
    unittest.main()
