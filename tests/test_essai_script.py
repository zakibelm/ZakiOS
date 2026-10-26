import importlib.util, pathlib, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("essai_lot1", ROOT / "scripts" / "essai_lot1.py")
essai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(essai)


class DiffTree(unittest.TestCase):
    def test_creations_modifications_et_suppressions_sont_separees(self):
        before = {"a": "1", "b": "2", "c": "3"}
        after = {"a": "1", "b": "X", "d": "4"}
        self.assertEqual(essai.diff_tree(before, after),
                         {"crees": ["d"], "supprimes": ["c"], "modifies": ["b"]})

    def test_aucun_changement(self):
        self.assertFalse(any(essai.diff_tree({"a": "1"}, {"a": "1"}).values()))


GOOD_PLAN = """ZAKIOS-SOCLE v1 · PDCA

Chemin proposé : `docs/plans/2026-10-26-x.md`

# Plan
## 1. Planifier
Critères d'acceptation : C1.
## 2. Exécuter
Étapes.
## 3. Vérifier
Preuve attendue par critère.
## 4. Agir
En cas d'écart, corriger puis revérifier.
Fin du plan ZakiOS
CANARI
"""


class Grilles(unittest.TestCase):
    def test_plan_complet_et_incomplet(self):
        self.assertEqual(essai.grille_plan(GOOD_PLAN), [])
        self.assertIn("section Vérifier", essai.grille_plan(GOOD_PLAN.replace("Vérifier", "Contrôler")))
        self.assertTrue(essai.grille_plan("rien"))

    def test_extraction_du_plan(self):
        plan, path = essai.extract_plan(GOOD_PLAN)
        self.assertEqual(path, "docs/plans/2026-10-26-x.md")
        self.assertTrue(plan.startswith("# Plan") and plan.rstrip().endswith("Fin du plan ZakiOS"))
        self.assertEqual(essai.extract_plan("pas de plan"), (None, None))

    def test_grille_revue(self):
        ok = "src/pay.py:3 bloquant. Critères: non satisfait. preuve: extrait. Contrôles non exécutés. Corriger d'abord."
        self.assertEqual(essai.grille_revue(ok), [])
        self.assertIn("preuve", essai.grille_revue(ok.replace("preuve", "").replace("extrait", "")))
        self.assertIn("constat localisé (fichier:ligne)", essai.grille_revue("sans localisation"))

    def test_extraction_sans_titre_de_niveau_1(self):
        text = "ZAKIOS-SOCLE v1 · PDCA\n\n**Chemin proposé :** `docs/plans/a.md`\n\n## 1. Planifier\nx\nFin du plan ZakiOS\n"
        plan, path = essai.extract_plan(text)
        self.assertEqual(path, "docs/plans/a.md")
        self.assertTrue(plan.startswith("## 1. Planifier"))
