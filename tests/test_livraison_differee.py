"""Livraison différée : aperçu exact d'abord, enregistrement seulement après confirmation explicite — SIMULÉ."""
import json
import os
import threading
import unittest

from zakios import deliver, mission
from zakios.mission import MissionError, confirmer_livraison, run_mission

from .helpers import Workdir
from .test_clarification import QUESTION, project, tree
from .test_mission import ACCEPT, CRITERIA, REQUEST, Fake, plan_text, review_text


def go(p, writer, reviewer, **kw):
    return run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "t", livraison="differee", mission_id="m1", **kw)


def accepted(p):
    plan = plan_text()
    out = go(p, Fake([plan]), Fake([ACCEPT]))
    return out, out["apercu"]["plan"]  # texte exact du plan examiné (hors enveloppe de livraison)


class Differee(unittest.TestCase):
    def test_accepte_ne_cree_rien_avant_confirmation_puis_enregistre_octets_exacts(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            out, plan = accepted(p)
            self.assertEqual(out["issue"], "accepte")
            self.assertIsNone(out["livraison"])
            self.assertEqual(out["apercu"]["plan"], plan)
            self.assertEqual(plan, deliver.extract_plan(plan_text())[0])
            self.assertEqual(tree(p), before)  # aucun fichier créé avant la confirmation
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            res = confirmer_livraison(p, "m1", plan, out["apercu"]["delivery_sha256"])
            self.assertEqual(res["statut"], "enregistre")
            with open(os.path.join(p, res["chemin"]), "rb") as fh:
                self.assertEqual(fh.read(), plan.encode("utf-8"))
            tr = json.load(open(os.path.join(p, out["trace"])))
            self.assertEqual(mission.check_trace(tr), [])

    def test_double_confirmation_idempotente_meme_en_concurrence(self):
        with Workdir() as wd:
            p = project(wd)
            out, plan = accepted(p)
            results, errors = [], []

            def click():
                try:
                    results.append(confirmer_livraison(p, "m1", plan, out["apercu"]["delivery_sha256"])["statut"])
                except Exception as exc:  # noqa
                    errors.append(exc)
            ts = [threading.Thread(target=click) for _ in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            self.assertEqual(errors, [])
            self.assertEqual(sorted(results).count("enregistre"), 1)
            self.assertEqual(set(results) - {"enregistre"}, {"deja_enregistre"})

    def test_refus_d_ecrasement(self):
        with Workdir() as wd:
            p = project(wd)
            out, plan = accepted(p)
            target = os.path.join(p, out["apercu"]["chemin"])
            os.makedirs(os.path.dirname(target))
            with open(target, "w") as fh:
                fh.write("contenu préexistant de la personne\n")
            with self.assertRaises(deliver.DeliveryError):
                confirmer_livraison(p, "m1", plan, out["apercu"]["delivery_sha256"])
            with open(target) as fh:
                self.assertEqual(fh.read(), "contenu préexistant de la personne\n")

    def test_refus_si_empreinte_ou_plan_differents(self):
        with Workdir() as wd:
            p = project(wd)
            out, plan = accepted(p)
            with self.assertRaises(MissionError):
                confirmer_livraison(p, "m1", plan, "0" * 64)
            with self.assertRaises(MissionError):
                confirmer_livraison(p, "m1", plan + "\nmodifié", out["apercu"]["delivery_sha256"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))

    def test_aucune_livraison_a_confirmer_apres_clarification_plafond_ou_erreur(self):
        cases = {
            "clarification": (Fake([plan_text()]), Fake([review_text("CLARIFICATION_REQUISE", QUESTION, couverture={"C1": "non_couvert", "C2": "non_couvert", "C3": "couvert"})])),
            "erreur": (Fake([plan_text()]), Fake(["hors format", "hors format"])),
        }
        for label, (w, r) in cases.items():
            with self.subTest(label), Workdir() as wd:
                p = project(wd)
                out = go(p, w, r)
                self.assertNotEqual(out["issue"], "accepte")
                self.assertNotIn("apercu", out)
                with self.assertRaises(MissionError):
                    confirmer_livraison(p, "m1", plan_text(), "0" * 64)
                self.assertFalse(os.path.exists(os.path.join(p, "docs")))

    def test_mode_inconnu_refuse_et_defaut_inchange(self):
        with Workdir() as wd:
            p = project(wd)
            with self.assertRaises(MissionError):
                run_mission(p, REQUEST, CRITERIA, Fake([]), Fake([]), livraison="autre")
            out = run_mission(p, REQUEST, CRITERIA, Fake([plan_text()]), Fake([ACCEPT]), now=lambda: "t")
            self.assertEqual(out["livraison"]["statut"], "enregistre")  # comportement par défaut des campagnes C1–C4


if __name__ == "__main__":
    unittest.main()
