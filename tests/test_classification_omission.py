"""Classement d'un cas « omission corrigeable » : défaut absent (détection non exercée) vs défaut présent (détecté / manqué)."""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
spec = importlib.util.spec_from_file_location("garanties_reelles", os.path.join(ROOT, "scripts", "essai_garanties_reelles.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def plan(n):
    steps = "\n".join("%d. étape %d (src/pay.py)" % (i, i) for i in range(1, n + 1))
    return "# Plan\n## Planifier\n1. contexte\n## Exécuter\n%s\n## Vérifier\ncmd\n" % steps


class ClassementOmission(unittest.TestCase):
    def test_defaut_absent_detection_non_exercee(self):
        self.assertEqual(mod.classify_omission(plan(4), "ACCEPTE"), "defaut_absent_detection_non_exercee")

    def test_defaut_present_detecte(self):
        self.assertEqual(mod.classify_omission(plan(5), "A_CORRIGER"), "defaut_present_detecte")

    def test_defaut_present_manque(self):
        self.assertEqual(mod.classify_omission(plan(6), "ACCEPTE"), "defaut_present_manque")

    def test_l_etape_de_planifier_ne_compte_pas(self):
        self.assertEqual(mod.classify_omission(plan(2), "ACCEPTE"), "defaut_absent_detection_non_exercee")


if __name__ == "__main__":
    unittest.main()
