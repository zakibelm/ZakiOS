"""Garanties de la coordination — tests SIMULÉS (faux rôles, aucun appel de modèle).

1. unitaire : une revue « ACCEPTE » qui liste un défaut bloquant est rejetée ;
2. intégration : un défaut qui persiste après deux corrections arrête la mission après trois plans,
   sans aucune livraison, avec des empreintes cohérentes de bout en bout.
"""
import hashlib
import json
import os
import unittest

from zakios import mission
from zakios.mission import TechnicalError, run_mission

from .helpers import Workdir
from .test_mission import BLOCK, CRITERIA, REQUEST, Fake, parse_review, plan_text, review_text


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RevueContradictoire(unittest.TestCase):
    def test_accepte_avec_defaut_bloquant_est_rejete(self):
        faux = review_text("ACCEPTE", BLOCK)
        self.assertIn("Verdict : ACCEPTE", faux)
        self.assertIn("[bloquant]", faux)
        with self.assertRaises(TechnicalError) as ctx:
            parse_review(faux)
        self.assertIn("bloquant", str(ctx.exception).lower())

    def test_meme_cas_dans_le_coordinateur_ne_livre_rien(self):
        with Workdir() as wd:
            p = os.path.join(wd, "proj")
            os.makedirs(p)
            faux = review_text("ACCEPTE", BLOCK)
            out = run_mission(p, REQUEST, CRITERIA, Fake([plan_text()]), Fake([faux, faux]),
                              now=lambda: "2026-10-26T00:00:00Z")
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))


class DefautPersistant(unittest.TestCase):
    def test_arret_apres_trois_plans_sans_livraison_et_empreintes_coherentes(self):
        with Workdir() as wd:
            p = os.path.join(wd, "proj")
            os.makedirs(p)
            plans = [plan_text("v%d, C3 toujours absent" % i) for i in (1, 2, 3)]
            reviews = [review_text("A_CORRIGER", BLOCK) for _ in range(3)]
            writer, reviewer = Fake(plans + [plan_text("v4 ne doit jamais être demandé")]), Fake(reviews + [review_text("ACCEPTE")])
            out = run_mission(p, REQUEST, CRITERIA, writer, reviewer, max_corrections=2,
                              now=lambda: "2026-10-26T00:00:00Z")
            # arrêt propre : 3 plans, 3 revues, aucun quatrième appel
            self.assertEqual((out["issue"], out["tours"]), ("plafond_atteint", 3))
            self.assertEqual((len(writer.calls), len(reviewer.calls)), (3, 3))
            # aucune livraison : ni plan, ni trace de livraison, rien dans docs/
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            self.assertFalse(os.path.exists(os.path.join(p, ".zakios/deliverables")))
            # empreintes : chaque revue porte l'empreinte du plan RÉELLEMENT transmis au relecteur
            with open(os.path.join(p, out["trace"])) as fh:
                trace = json.load(fh)
            self.assertEqual(trace["issue"], "plafond_atteint")
            self.assertNotIn("livraison", trace)
            seen = [c[2] for c in reviewer.calls]
            self.assertEqual(len(trace["tours"]), 3)
            for tour, transmitted in zip(trace["tours"], seen):
                self.assertEqual(tour["plan_sha256"], sha(transmitted))
                self.assertEqual(tour["revue"]["plan_examine_sha256"], tour["plan_sha256"])
                self.assertEqual(tour["revue"]["verdict"], "A_CORRIGER")
            self.assertEqual(len({t["plan_sha256"] for t in trace["tours"]}), 3)
            # le plan précédent et les constats sont bien renvoyés au planificateur
            self.assertEqual(writer.calls[1][2], seen[0])
            self.assertEqual(writer.calls[2][2], seen[1])
            self.assertTrue(writer.calls[1][3])


if __name__ == "__main__":
    unittest.main()
