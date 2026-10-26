"""Distinction « clarification requise » / « critère obligatoire abandonné » — tests SIMULÉS (faux rôles, aucun modèle).

Unitaires : parse_review_full impose les règles de cohérence (le relecteur ne peut pas les contourner).
Intégration : run_mission arrête la boucle sans livraison sur CLARIFICATION, et ne livre jamais un plan dont un critère
obligatoire est abandonné ou non couvert."""
import json
import os
import unittest

from zakios import mission
from zakios.mission import TechnicalError, parse_review, parse_review_full, run_mission

from .helpers import Workdir
from .test_mission import ACCEPT, BLOCK, CRITERIA, MINOR, REQUEST, Fake, plan_text, review_text

QUESTION = ("- [clarification] critère « C1/C2 » · Problème : C1 et C2 sont contradictoires → Action : lequel des deux "
            "faut-il retenir ? → Résultat : le plan peut être jugé après la décision · preuve : « C1 … C2 »")
ALL = {"C1": "couvert", "C2": "couvert", "C3": "couvert"}


def cov(**kw):
    out = dict(ALL)
    out.update(kw)
    return out


def project(wd):
    p = os.path.join(wd, "proj")
    os.makedirs(p)
    return p


def go(p, writer, reviewer, **kw):
    return run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "2026-10-26T00:00:00Z", **kw)


def trace_of(p, out):
    with open(os.path.join(p, out["trace"])) as fh:
        return json.load(fh)


class ParseClarification(unittest.TestCase):
    def test_clarification_valide(self):
        verdict, findings, coverage = parse_review_full(review_text("CLARIFICATION", QUESTION), CRITERIA)
        self.assertEqual(verdict, "CLARIFICATION")
        self.assertEqual([f["gravite"] for f in findings], ["clarification"])
        self.assertEqual(coverage, ALL)

    def test_incoherences_refusees(self):
        bad = {
            "CLARIFICATION sans question": review_text("CLARIFICATION", MINOR),
            "ACCEPTE avec une clarification": review_text("ACCEPTE", QUESTION),
            "A_CORRIGER avec une clarification": review_text("A_CORRIGER", BLOCK, QUESTION),
        }
        for label, text in bad.items():
            with self.assertRaises(TechnicalError, msg=label):
                parse_review(text, CRITERIA)


class ParseCouverture(unittest.TestCase):
    def test_critere_abandonne_interdit_accepte(self):
        for value in ("abandonne", "abandonné", "non_couvert"):
            text = review_text("ACCEPTE", MINOR, couverture=cov(C3=value))
            with self.assertRaises(TechnicalError, msg=value) as ctx:
                parse_review(text, CRITERIA)
            self.assertIn("C3", str(ctx.exception))
            # même sans la liste des critères de la mission, la règle s'applique à la couverture rendue
            with self.assertRaises(TechnicalError, msg=value):
                parse_review(text)

    def test_critere_abandonne_avec_a_corriger_est_permis(self):
        text = review_text("A_CORRIGER", BLOCK, couverture=cov(C3="abandonne"))
        self.assertEqual(parse_review_full(text, CRITERIA)[2]["C3"], "abandonne")

    def test_couverture_doit_nommer_chaque_critere_une_fois(self):
        incomplete = review_text("ACCEPTE", MINOR, couverture={"C1": "couvert", "C2": "couvert"})
        invented = review_text("ACCEPTE", MINOR, couverture=cov(C9="couvert"))
        duplicated = review_text("ACCEPTE", MINOR).replace("Couverture C1 : couvert", "Couverture C1 : couvert\nCouverture C1 : couvert")
        unknown = review_text("ACCEPTE", MINOR).replace("Couverture C1 : couvert", "Couverture C1 : probablement")
        for label, text in {"manquant": incomplete, "inventé": invented, "doublon": duplicated, "valeur inconnue": unknown}.items():
            with self.assertRaises(TechnicalError, msg=label):
                parse_review(text, CRITERIA)

    def test_acceptation_complete_reste_valide(self):
        self.assertEqual(parse_review(ACCEPT, CRITERIA)[0], "ACCEPTE")


class ClarificationArreteLaBoucle(unittest.TestCase):
    def test_clarification_au_premier_tour_arrete_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("v1 expose la contradiction"), plan_text("ne doit jamais être demandé")])
            r = Fake([review_text("CLARIFICATION", QUESTION), review_text("ACCEPTE")])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("clarification_requise", 1))
            self.assertEqual((len(w.calls), len(r.calls)), (1, 1))            # aucune correction tentée
            self.assertEqual(len(out["questions"]), 1)
            self.assertIn("contradictoires", out["questions"][0])
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            self.assertFalse(os.path.exists(os.path.join(p, ".zakios/deliverables")))
            tr = trace_of(p, out)
            self.assertEqual(tr["issue"], "clarification_requise")
            self.assertNotIn("livraison", tr)
            self.assertEqual(tr["clarification"]["questions"], out["questions"])
            self.assertEqual(tr["clarification"]["plan_sha256"], tr["tours"][0]["plan_sha256"])
            self.assertEqual(tr["tours"][0]["revue"]["plan_examine_sha256"], tr["tours"][0]["plan_sha256"])
            self.assertEqual(tr["tours"][0]["revue"]["verdict"], "CLARIFICATION")

    def test_clarification_apres_une_correction_arrete_aussi(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("v1"), plan_text("v2"), plan_text("v3 jamais demandé")])
            r = Fake([review_text("A_CORRIGER", BLOCK), review_text("CLARIFICATION", QUESTION), review_text("ACCEPTE")])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("clarification_requise", 2))
            self.assertEqual((len(w.calls), len(r.calls)), (2, 2))
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            tr = trace_of(p, out)
            self.assertEqual(tr["clarification"]["tour"], 2)
            self.assertEqual([t["revue"]["verdict"] for t in tr["tours"]], ["A_CORRIGER", "CLARIFICATION"])

    def test_clarification_falsifiee_est_rejetee_et_ne_livre_rien(self):
        with Workdir() as wd:
            p = project(wd)
            faux = review_text("ACCEPTE", QUESTION)
            out = go(p, Fake([plan_text()]), Fake([faux, faux]))
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))


class CritereAbandonneInterditAccepte(unittest.TestCase):
    def test_accepte_avec_critere_abandonne_ne_livre_rien(self):
        with Workdir() as wd:
            p = project(wd)
            faux = review_text("ACCEPTE", MINOR, couverture=cov(C3="abandonne"))
            out = go(p, Fake([plan_text("v1 écarte C3")]), Fake([faux, faux]))
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            self.assertTrue(trace_of(p, out)["erreurs_techniques"])

    def test_critere_abandonne_corrige_puis_accepte_avec_couverture_complete(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("v1 écarte C3"), plan_text("v2 couvre C3")])
            r = Fake([review_text("A_CORRIGER", BLOCK, couverture=cov(C3="abandonne")), ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("accepte", 2))
            self.assertEqual(out["livraison"]["statut"], "enregistre")
            tr = trace_of(p, out)
            self.assertEqual(tr["tours"][0]["revue"]["couverture"]["C3"], "abandonne")
            self.assertEqual(set(tr["tours"][1]["revue"]["couverture"].values()), {"couvert"})
            with open(os.path.join(p, out["livraison"]["chemin"])) as fh:
                self.assertIn("v2 couvre C3", fh.read())

    def test_critere_abandonne_persistant_va_au_plafond_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            rev = review_text("A_CORRIGER", BLOCK, couverture=cov(C3="abandonne"))
            out = go(p, Fake([plan_text("a"), plan_text("b"), plan_text("c")]), Fake([rev, rev, rev]))
            self.assertEqual((out["issue"], out["tours"]), ("plafond_atteint", 3))
            self.assertIsNone(out["livraison"])
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))


class FicheRelecteur(unittest.TestCase):
    def test_fiche_decrit_clarification_et_couverture(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "variantes/agents/plan-reviewer.md"), encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("CLARIFICATION", "[clarification]", "Couverture C1 : couvert", "abandonne"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
