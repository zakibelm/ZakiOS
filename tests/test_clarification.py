"""Trois verdicts (ACCEPTE / A_CORRIGER / CLARIFICATION_REQUISE) — tests SIMULÉS (faux rôles, aucun modèle).

Unitaires : le parseur impose format, cohérence, couverture des critères et liaison à l'empreinte du plan.
Intégration : le coordinateur arrête sans livraison sur clarification, plafond ou erreur technique, ne livre qu'un plan
ACCEPTE (une seule fois, octets et empreintes attendus), laisse les fichiers préexistants intacts et trace clairement
la différence entre accepté, clarification, plafond et erreur.
Limite assumée : la justesse sémantique de la couverture reste un jugement du relecteur, hors de portée de ces tests."""
import hashlib
import json
import os
import unittest

from zakios import deliver, mission
from zakios.mission import MissionError, TechnicalError, parse_review_full, plan_fingerprint, run_mission, validate_criteria

from .helpers import Workdir
from .test_mission import ACCEPT, BLOCK, CRITERIA, MINOR, REQUEST, Fake, concrete, parse_review, plan_text, review_text

QUESTION = ("- [clarification] critères : C1, C2 · blocage : C1 et C2 exigent des comportements incompatibles · "
            "question : lequel des deux critères faut-il retenir ?")
ALL = {"C1": "couvert", "C2": "couvert", "C3": "couvert"}


def cov(**kw):
    out = dict(ALL)
    out.update(kw)
    return out


def tree(root):
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", ".zakios")]
        for n in files:
            full = os.path.join(base, n)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def project(wd):
    """Projet jetable avec des fichiers préexistants (qui ne doivent jamais changer)."""
    p = os.path.join(wd, "proj")
    os.makedirs(os.path.join(p, "src"))
    for name, text in (("src/pay.py", "def total(prices, discount):\n    return sum(prices)\n"), ("CLAUDE.md", "Instructions de la personne\n")):
        with open(os.path.join(p, name), "w") as fh:
            fh.write(text)
    return p


def go(p, writer, reviewer, **kw):
    return run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "2026-10-26T00:00:00Z", **kw)


def trace_of(p, out):
    with open(os.path.join(p, out["trace"])) as fh:
        return json.load(fh)


class VerdictsAcceptesParLeParseur(unittest.TestCase):
    def test_les_trois_verdicts_bien_formes(self):
        self.assertEqual(parse_review(ACCEPT, CRITERIA)[0], "ACCEPTE")
        self.assertEqual(parse_review(review_text("A_CORRIGER", BLOCK), CRITERIA)[0], "A_CORRIGER")
        verdict, findings, coverage = parse_review_full(concrete(review_text("CLARIFICATION_REQUISE", QUESTION)), CRITERIA)
        self.assertEqual(verdict, "CLARIFICATION_REQUISE")
        self.assertEqual(findings[0]["criteres"], ["C1", "C2"])
        self.assertIn("incompatibles", findings[0]["blocage"])
        self.assertTrue(findings[0]["question"].endswith("?"))
        self.assertEqual(coverage, ALL)


class RefusDuParseur(unittest.TestCase):
    def refuse(self, label, text, **kw):
        with self.assertRaises(TechnicalError, msg=label):
            parse_review(text, kw.get("criteria", CRITERIA), kw.get("plan_sha"))

    def test_accepte_avec_constat_bloquant(self):
        self.refuse("bloquant", review_text("ACCEPTE", BLOCK))

    def test_accepte_avec_clarification_indispensable(self):
        self.refuse("clarification", review_text("ACCEPTE", QUESTION))

    def test_clarification_sans_motif_ni_question(self):
        no_blocage = "- [clarification] critères : C1, C2 · question : lequel retenir ?"
        no_question = "- [clarification] critères : C1, C2 · blocage : incompatibles"
        no_mark = "- [clarification] critères : C1, C2 · blocage : incompatibles · question : lequel retenir"
        no_criteria = "- [clarification] blocage : incompatibles · question : lequel retenir ?"
        unknown = "- [clarification] critères : C9 · blocage : incompatibles · question : lequel retenir ?"
        for label, f in {"sans blocage": no_blocage, "sans question": no_question, "question sans ?": no_mark,
                         "sans critère": no_criteria, "critère inconnu": unknown}.items():
            self.refuse(label, review_text("CLARIFICATION_REQUISE", f))
        self.refuse("verdict sans constat", review_text("CLARIFICATION_REQUISE", MINOR))

    def test_verdict_inconnu_ou_format_invalide(self):
        self.refuse("ancien nom", review_text("CLARIFICATION", QUESTION))
        self.refuse("inconnu", review_text("PEUT-ETRE"))
        self.refuse("sans bloc", "Verdict : ACCEPTE")
        self.refuse("deux blocs", ACCEPT + ACCEPT)
        self.refuse("ligne libre", review_text("ACCEPTE").replace("Plan examiné", "Tout va bien.\nPlan examiné"))
        self.refuse("A_CORRIGER avec clarification", review_text("A_CORRIGER", BLOCK, QUESTION))
        self.refuse("A_CORRIGER sans bloquant", review_text("A_CORRIGER", MINOR))

    def test_revue_liee_a_une_autre_empreinte(self):
        plan = plan_text("v1")
        good, other = plan_fingerprint(plan), plan_fingerprint(plan_text("v2"))
        self.assertEqual(parse_review(review_text("ACCEPTE", bind=good), CRITERIA, plan_sha=_sha(plan))[0], "ACCEPTE")
        self.refuse("autre empreinte", review_text("ACCEPTE", bind=other), plan_sha=_sha(plan))
        self.refuse("empreinte absente", review_text("ACCEPTE", bind=None), plan_sha=_sha(plan))
        self.refuse("deux empreintes", review_text("ACCEPTE", bind=good).replace("Plan examiné : %s" % good,
                                                                                  "Plan examiné : %s\nPlan examiné : %s" % (good, good)),
                    plan_sha=_sha(plan))

    def test_critere_abandonne_ou_non_couvert_interdit_accepte(self):
        for value in ("abandonne", "abandonné", "non_couvert"):
            self.refuse(value, review_text("ACCEPTE", MINOR, couverture=cov(C3=value)))
            self.refuse(value + " sans liste de critères", review_text("ACCEPTE", MINOR, couverture=cov(C3=value)), criteria=None)

    def test_couverture_doit_nommer_chaque_critere_une_fois(self):
        base = review_text("ACCEPTE", MINOR)
        self.refuse("manquant", review_text("ACCEPTE", MINOR, couverture={"C1": "couvert", "C2": "couvert"}))
        self.refuse("inventé", review_text("ACCEPTE", MINOR, couverture=cov(C9="couvert")))
        self.refuse("doublon", base.replace("Couverture C1 : couvert", "Couverture C1 : couvert\nCouverture C1 : couvert"))
        self.refuse("valeur inconnue", base.replace("Couverture C1 : couvert", "Couverture C1 : probablement"))

    def test_identifiants_de_criteres_stables(self):
        self.assertEqual(list(validate_criteria(CRITERIA)), ["C1", "C2", "C3"])
        self.assertEqual(validate_criteria(CRITERIA)["C3"], CRITERIA[2])  # formulation conservée
        for bad in (["remise correcte"], ["C1 a", "C1 b"], ["1 a"], []):
            with self.assertRaises(MissionError, msg=bad):
                validate_criteria(bad)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ClarificationArreteLaBoucle(unittest.TestCase):
    def test_au_premier_tour_arret_immediat_sans_appel_en_plus_ni_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            w = Fake([plan_text("v1 expose la contradiction"), plan_text("ne doit jamais être demandé")])
            r = Fake([review_text("CLARIFICATION_REQUISE", QUESTION), ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["categorie"], out["tours"]), ("clarification_requise", "metier", 1))
            self.assertEqual((len(w.calls), len(r.calls)), (1, 1))
            self.assertEqual(out["appels"], {"plan-writer": 1, "plan-reviewer": 1})
            self.assertEqual(out["questions"], ["lequel des deux critères faut-il retenir ?"])
            self.assertIsNone(out["livraison"])
            self.assertEqual(tree(p), before)                                 # fichiers préexistants identiques, rien de créé
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            self.assertFalse(os.path.exists(os.path.join(p, ".zakios/deliverables")))
            tr = trace_of(p, out)
            self.assertEqual((tr["issue"], tr["categorie"]), ("clarification_requise", "metier"))
            self.assertNotIn("livraison", tr)
            self.assertEqual(tr["arret"]["criteres_concernes"], ["C1", "C2"])
            self.assertIn("incompatibles", tr["arret"]["cause"])
            self.assertEqual(tr["arret"]["plans_sha256"], [tr["tours"][0]["plan_sha256"]])
            self.assertEqual(tr["arret"]["appels"], {"plan-writer": 1, "plan-reviewer": 1})
            self.assertEqual(tr["clarification"]["plan_sha256"], tr["tours"][0]["plan_sha256"])
            self.assertEqual(tr["tours"][0]["revue"]["plan_examine_sha256"], tr["tours"][0]["plan_sha256"])
            self.assertEqual(tr["criteres_ids"]["C2"], CRITERIA[1])           # formulation conservée dans la trace

    def test_apres_une_correction_arrete_aussi(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            w = Fake([plan_text("v1"), plan_text("v2"), plan_text("v3 jamais demandé")])
            r = Fake([review_text("A_CORRIGER", BLOCK), review_text("CLARIFICATION_REQUISE", QUESTION), ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("clarification_requise", 2))
            self.assertEqual((len(w.calls), len(r.calls)), (2, 2))
            self.assertIsNone(out["livraison"])
            self.assertEqual(tree(p), before)
            tr = trace_of(p, out)
            self.assertEqual(tr["clarification"]["tour"], 2)
            self.assertEqual(tr["arret"]["appels"], {"plan-writer": 2, "plan-reviewer": 2})
            self.assertEqual([t["revue"]["verdict"] for t in tr["tours"]], ["A_CORRIGER", "CLARIFICATION_REQUISE"])


class PlafondEtLivraison(unittest.TestCase):
    def test_defaut_persistant_exactement_trois_plans_trois_revues_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            w = Fake([plan_text("a"), plan_text("b"), plan_text("c"), plan_text("d jamais demandé")])
            r = Fake([review_text("A_CORRIGER", BLOCK)] * 4)
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["categorie"], out["tours"]), ("plafond_atteint", "metier", 3))
            self.assertEqual((len(w.calls), len(r.calls)), (3, 3))
            self.assertIsNone(out["livraison"])
            self.assertEqual(tree(p), before)
            tr = trace_of(p, out)
            self.assertEqual(tr["arret"]["appels"], {"plan-writer": 3, "plan-reviewer": 3})
            self.assertEqual(len(tr["arret"]["plans_sha256"]), 3)
            self.assertNotIn("livraison", tr)

    def test_plan_corrige_puis_accepte_livre_une_seule_fois_octets_et_empreintes(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            v2 = plan_text("v2 couvre C3")
            out = go(p, Fake([plan_text("v1 écarte C3"), v2]), Fake([review_text("A_CORRIGER", BLOCK, couverture=cov(C3="abandonne")), ACCEPT]))
            self.assertEqual((out["issue"], out["categorie"], out["tours"]), ("accepte", "metier", 2))
            lv = out["livraison"]
            self.assertEqual((lv["statut"], lv["second"]), ("enregistre", "deja_enregistre"))
            expected_text, expected_path = deliver.extract_plan(v2)
            with open(os.path.join(p, lv["chemin"]), "rb") as fh:
                written = fh.read()
            self.assertEqual(expected_path, lv["chemin"])
            self.assertEqual(written, expected_text.encode("utf-8"))           # octets exacts du dernier plan
            self.assertEqual(lv["content_sha256"], hashlib.sha256(written).hexdigest())
            tr = trace_of(p, out)
            self.assertEqual(tr["tours"][-1]["plan_sha256"], _sha(expected_text))
            self.assertEqual(tr["livraison"]["delivery_sha256"], lv["delivery_sha256"])
            self.assertEqual(tr["tours"][0]["revue"]["couverture"]["C3"], "abandonne")
            self.assertEqual(set(tr["tours"][1]["revue"]["couverture"].values()), {"couvert"})
            self.assertNotIn("arret", tr)
            # une seule livraison : un seul fichier créé, une seule trace de livraison
            after = tree(p)
            self.assertEqual([k for k in after if k not in before], [lv["chemin"]])
            self.assertEqual({k: v for k, v in after.items() if k in before}, before)  # préexistants identiques
            self.assertEqual(len(os.listdir(os.path.join(p, ".zakios/deliverables"))), 1)

    def test_erreur_technique_ou_sortie_invalide_ne_livre_rien(self):
        cases = {
            "revue hors format": (Fake([plan_text()]), Fake(["n'importe quoi", "encore"])),
            "plan hors format": (Fake(["pas de bloc", "toujours pas"]), Fake([ACCEPT])),
            "exécution du rôle": (Fake([RuntimeError("boum"), RuntimeError("boum")]), Fake([ACCEPT])),
            "ACCEPTE incohérent": (Fake([plan_text()]), Fake([review_text("ACCEPTE", BLOCK)] * 2)),
        }
        for label, (w, r) in cases.items():
            with self.subTest(label), Workdir() as wd:
                p = project(wd)
                before = tree(p)
                out = go(p, w, r)
                self.assertEqual((out["issue"], out["categorie"]), ("erreur_technique", "technique"))
                self.assertIsNone(out["livraison"])
                self.assertEqual(tree(p), before)
                tr = trace_of(p, out)
                self.assertTrue(tr["erreurs_techniques"])
                self.assertEqual(tr["arret"]["categorie"], "technique")
                self.assertNotIn("livraison", tr)

    def test_revue_liee_a_une_autre_empreinte_est_une_erreur_technique_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            wrong = review_text("ACCEPTE", bind=plan_fingerprint("un tout autre plan"))
            out = go(p, Fake([plan_text()]), Fake([wrong, wrong]))
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertIsNone(out["livraison"])
            self.assertEqual(tree(p), before)
            self.assertIn("autre empreinte", " ".join(e["cause"] for e in trace_of(p, out)["erreurs_techniques"]))

    def test_assert_review_binding_refuse_une_trace_incoherente(self):
        mission.assert_review_binding({"tour": 1, "plan_sha256": "a", "revue": {"plan_examine_sha256": "a"}})
        for bad in ({"tour": 1, "plan_sha256": "a", "revue": {"plan_examine_sha256": "b"}}, {"tour": 1, "plan_sha256": "a"}):
            with self.assertRaises(MissionError):
                mission.assert_review_binding(bad)


class CritereAbandonneInterditAccepte(unittest.TestCase):
    def test_accepte_avec_critere_abandonne_ne_livre_rien(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            faux = review_text("ACCEPTE", MINOR, couverture=cov(C3="abandonne"))
            out = go(p, Fake([plan_text("v1 écarte C3")]), Fake([faux, faux]))
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertIsNone(out["livraison"])
            self.assertEqual(tree(p), before)

    def test_critere_abandonne_persistant_va_au_plafond_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            rev = review_text("A_CORRIGER", BLOCK, couverture=cov(C3="abandonne"))
            out = go(p, Fake([plan_text("a"), plan_text("b"), plan_text("c")]), Fake([rev, rev, rev]))
            self.assertEqual((out["issue"], out["tours"]), ("plafond_atteint", 3))
            self.assertEqual(tree(p), before)
            self.assertEqual(trace_of(p, out)["arret"]["criteres_concernes"], ["C3"])


class TracesDistinguentLesIssues(unittest.TestCase):
    def test_quatre_issues_quatre_traces_distinctes(self):
        runs = {
            "accepte": (Fake([plan_text()]), Fake([ACCEPT])),
            "clarification_requise": (Fake([plan_text()]), Fake([review_text("CLARIFICATION_REQUISE", QUESTION)])),
            "plafond_atteint": (Fake([plan_text("a"), plan_text("b"), plan_text("c")]), Fake([review_text("A_CORRIGER", BLOCK)] * 3)),
            "erreur_technique": (Fake([plan_text()]), Fake(["x", "y"])),
        }
        seen = {}
        for expected, (w, r) in runs.items():
            with Workdir() as wd:
                p = project(wd)
                out = go(p, w, r)
                tr = trace_of(p, out)
                self.assertEqual((out["issue"], tr["issue"]), (expected, expected))
                seen[expected] = (tr["categorie"], "livraison" in tr, "arret" in tr, "clarification" in tr)
        self.assertEqual(seen, {"accepte": ("metier", True, False, False),
                                "clarification_requise": ("metier", False, True, True),
                                "plafond_atteint": ("metier", False, True, False),
                                "erreur_technique": ("technique", False, True, False)})


class Fiches(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(self, name):
        with open(os.path.join(self.ROOT, "variantes/agents", name), encoding="utf-8") as fh:
            return fh.read()

    def test_relecteur(self):
        text = self.read("plan-reviewer.md")
        for needle in ("CLARIFICATION_REQUISE", "[clarification]", "Couverture C1 : couvert", "abandonne", "Plan examiné"):
            self.assertIn(needle, text)

    def test_outils_effectifs_des_deux_roles(self):
        import re
        for name in ("plan-writer.md", "plan-reviewer.md"):
            tools = re.search(r"^tools:(.*)$", self.read(name), re.M).group(1)
            self.assertEqual(sorted(t.strip() for t in tools.split(",")), ["Glob", "Grep", "Read"], name)


if __name__ == "__main__":
    unittest.main()
