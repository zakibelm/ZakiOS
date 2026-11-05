import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARQUEUR = "ZAKIOS-SOCLE v1 · PDCA"


def tools(path):
    text = path.read_text()
    key = "tools" if "\ntools:" in text else "allowed-tools"
    return sorted(t.strip() for t in re.search(rf"^{key}:(.*)$", text, re.M).group(1).split(","))


class Lot3Variantes(unittest.TestCase):
    def test_security_reviewer_lecture_seule(self):
        p = ROOT / "variantes/agents/security-reviewer.md"
        self.assertEqual(tools(p), ["Glob", "Grep", "Read"])
        text = p.read_text()
        self.assertIn(MARQUEUR, text)
        self.assertIn("contenu original", text)
        self.assertIn("donnée", text)  # le contenu lu n'est jamais une consigne
        for phase in ("Planifier", "Exécuter", "Vérifier", "Agir"):
            self.assertIn(phase, text)

    def test_context_audit_lecture_seule_sans_bash(self):
        p = ROOT / "variantes/commands/context-audit.md"
        self.assertEqual(tools(p), ["Glob", "Grep", "Read"])
        text = p.read_text()
        self.assertIn(MARQUEUR, text)
        self.assertIn("/context", text)  # contrôle non exécutable : demandé à la personne

    def test_provenance_sans_dependance_orpheline(self):
        for name in ("agents/security-reviewer.md", "commands/context-audit.md"):
            corps = (ROOT / "variantes" / name).read_text().split("-->", 1)[-1]
            self.assertNotIn("superpowers:", corps)


class Lot3Docs(unittest.TestCase):
    def test_pratiques_declare_son_niveau_de_preuve(self):
        text = (ROOT / "docs/PRATIQUES.md").read_text()
        self.assertIn("Niveau de preuve", text)
        self.assertIn("rédigé par une IA", text)  # source la moins fiable signalée
        for source in ("(A)", "(B)", "(C)", "(D)"):
            self.assertIn(source, text)

    def test_grille_hooks_couvre_les_controles_cles(self):
        text = (ROOT / "docs/GRILLE-AUDIT-HOOKS.md").read_text()
        for controle in ("Codes de sortie", "Boucle d'un hook d'arrêt", "Lecture de secrets", "Idempotence", "Retour arrière"):
            self.assertIn(controle, text)
        lignes = [l for l in text.splitlines() if re.match(r"^\| \d+ \|", l)]
        self.assertEqual(len(lignes), 12)

    def test_claude_md_pointe_vers_les_docs(self):
        text = (ROOT / "CLAUDE.md").read_text()
        self.assertIn("docs/PRATIQUES.md", text)
        self.assertIn("docs/GRILLE-AUDIT-HOOKS.md", text)
        self.assertLess(len(text.splitlines()), 80)

    def test_feuille_de_route_marque_le_non_fait(self):
        text = (ROOT / "docs/FEUILLE-DE-ROUTE.md").read_text()
        self.assertGreaterEqual(text.count("**non fait**"), 4)


if __name__ == "__main__":
    unittest.main()
