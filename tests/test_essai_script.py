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
