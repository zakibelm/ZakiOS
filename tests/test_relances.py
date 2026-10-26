"""Relances techniques tracées — reproduction exacte du passage information_manquante n°3 (campagne C2), SIMULÉE.

Cas réel : le relecteur a d'abord nommé ses critères avec de mauvais identifiants ; l'avis a été refusé ; une relance
valide a donné CLARIFICATION_REQUISE ; arrêt sans livraison. Exigence : la tentative refusée reste visible dans
`erreurs_techniques` (rôle, tour, tentative, catégorie, cause, empreinte de la sortie, lien vers le journal),
les relances sont bornées, aucun appel ne suit une clarification valide, aucune livraison."""
import hashlib
import json
import os
import unittest

from zakios import mission
from zakios.mission import check_trace, run_mission

from .helpers import Workdir
from .test_clarification import project, tree
from .test_mission import Fake, plan_text, review_text

REQUEST = "Planifie le déploiement de la correction sur le serveur de production désigné par l'équipe infrastructure."
CRITERIA = ["M1 le plan cible le serveur de production désigné, avec son nom d'hôte exact", "M2 le plan prévoit un retour arrière vérifiable"]
ASK = ("- [clarification] critères : M1 · blocage : le nom d'hôte exact n'est ni dans la mission ni dans le projet · "
       "question : quel est le nom d'hôte exact du serveur de production ?")
GOOD = review_text("CLARIFICATION_REQUISE", ASK, couverture={"M1": "non_couvert", "M2": "couvert"})
WRONG_IDS = review_text("CLARIFICATION_REQUISE", ASK, couverture={"C1": "non_couvert", "C2": "couvert"})  # identifiants invalides
ACCEPT_OK = review_text("ACCEPTE", couverture={"M1": "couvert", "M2": "couvert"})
BLOCK_M2 = ("- [bloquant] critère « M2 » · Problème : retour arrière absent → Action : l'ajouter → "
            "Résultat : vérifiable · preuve : absence de retour arrière")
CORRIGER = review_text("A_CORRIGER", BLOCK_M2, couverture={"M1": "couvert", "M2": "non_couvert"})


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Journal:
    """Faux lien vers le journal : numérote les appels réels dans l'ordre."""
    def __init__(self):
        self.n = 0

    def tick(self, fake):
        return fake

    def __call__(self):
        return "log-%d.jsonl" % self.n


class Counted(Fake):
    def __init__(self, answers, journal):
        super().__init__(answers)
        self.journal = journal

    def __call__(self, *args):
        self.journal.n += 1
        return super().__call__(*args)


def go(p, writer, reviewer, journal=None, **kw):
    return run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "2026-10-26T00:00:00Z", journal=journal, **kw)


def trace_of(p, out):
    with open(os.path.join(p, out["trace"])) as fh:
        return json.load(fh)


class PassageInformationManquante3(unittest.TestCase):
    def test_identifiants_invalides_refus_relance_valide_clarification_arret_sans_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            j = Journal()
            writer = Counted([plan_text()], j)
            reviewer = Counted([WRONG_IDS, GOOD], j)
            out = go(p, writer, reviewer, journal=j)
            self.assertEqual((out["issue"], out["categorie"]), ("clarification_requise", "metier"))
            self.assertIsNone(out["livraison"])
            self.assertEqual(out["appels"], {"plan-writer": 1, "plan-reviewer": 2})
            self.assertEqual((len(writer.calls), len(reviewer.calls)), (1, 2))
            self.assertEqual(tree(p), before)  # rien d'écrit dans le projet
            self.assertFalse(os.path.exists(os.path.join(p, "docs")))
            tr = trace_of(p, out)
            self.assertNotIn("livraison", tr)
            self.assertEqual(len(tr["erreurs_techniques"]), 1)  # l'erreur récupérée reste visible
            e = tr["erreurs_techniques"][0]
            plan = reviewer.calls[0][2]
            self.assertEqual((e["role"], e["tour"], e["tentative"], e["categorie"], e["recuperee"]),
                             ("plan-reviewer", 1, 1, "format", True))
            self.assertIn("couverture", e["cause"])
            self.assertEqual(e["sortie_sha256"], sha(WRONG_IDS.replace("@PLAN@", mission.plan_fingerprint(plan))))
            self.assertEqual(e["journal"], "log-2.jsonl")  # écrivain = appel 1, relecteur refusé = appel 2
            self.assertEqual([(a["role"], a["resultat"]) for a in tr["appels_detail"]],
                             [("plan-writer", "valide"), ("plan-reviewer", "refuse_format"), ("plan-reviewer", "valide")])
            self.assertEqual(tr["tours"][0]["revue"]["relances_relecteur"], 1)
            self.assertEqual(tr["clarification"]["criteres"], ["M1"])
            self.assertEqual(check_trace(tr), [])

    def test_aucun_appel_apres_une_clarification_valide(self):
        with Workdir() as wd:
            p = project(wd)
            # réponses supplémentaires prévues : si le coordinateur les consommait, le test le verrait
            writer = Fake([plan_text(), plan_text("v2")])
            reviewer = Fake([GOOD, ACCEPT_OK])
            out = go(p, writer, reviewer)
            self.assertEqual(out["issue"], "clarification_requise")
            self.assertEqual((len(writer.calls), len(reviewer.calls)), (1, 1))
            self.assertEqual(len(writer.answers) + len(reviewer.answers), 2)  # réponses non consommées
            self.assertEqual(trace_of(p, out)["appels_detail"][-1]["resultat"], "valide")

    def test_clarification_apres_correction_et_relance(self):
        with Workdir() as wd:
            p = project(wd)
            writer = Fake([plan_text(), plan_text("v2")])
            reviewer = Fake([CORRIGER, "hors format", GOOD])
            out = go(p, writer, reviewer)
            self.assertEqual(out["issue"], "clarification_requise")
            self.assertEqual(out["appels"], {"plan-writer": 2, "plan-reviewer": 3})
            tr = trace_of(p, out)
            self.assertEqual([(e["tour"], e["tentative"], e["recuperee"]) for e in tr["erreurs_techniques"]], [(2, 1, True)])
            self.assertEqual(check_trace(tr), [])


class RelancesBornees(unittest.TestCase):
    def test_epuisement_conserve_toutes_les_erreurs_et_ne_livre_rien(self):
        for retries in (0, 1, 2):
            with self.subTest(retries=retries), Workdir() as wd:
                p = project(wd)
                before = tree(p)
                j = Journal()
                reviewer = Counted([WRONG_IDS] * (retries + 3), j)
                out = go(p, Counted([plan_text()], j), reviewer, journal=j, max_technical_retries=retries)
                self.assertEqual((out["issue"], out["categorie"]), ("erreur_technique", "technique"))
                self.assertIsNone(out["livraison"])
                self.assertEqual(len(reviewer.calls), retries + 1)  # plafond des relances respecté
                self.assertEqual(tree(p), before)
                tr = trace_of(p, out)
                errs = tr["erreurs_techniques"]
                self.assertEqual([e["tentative"] for e in errs], list(range(1, retries + 2)))
                self.assertTrue(all(not e["recuperee"] and e["role"] == "plan-reviewer" for e in errs))
                self.assertEqual(len({e["journal"] for e in errs}), retries + 1)  # un lien de journal par tentative
                self.assertNotIn("livraison", tr)
                self.assertEqual(tr["arret"]["categorie"], "technique")
                self.assertEqual(check_trace(tr), [])

    def test_toutes_les_erreurs_recuperees_de_plusieurs_tours_sont_conservees_puis_livraison(self):
        with Workdir() as wd:
            p = project(wd)
            writer = Fake(["pas de bloc", plan_text(), plan_text("v2")])
            reviewer = Fake([CORRIGER, WRONG_IDS, ACCEPT_OK])
            out = go(p, writer, reviewer)
            self.assertEqual(out["issue"], "accepte")
            self.assertEqual(out["livraison"]["statut"], "enregistre")
            tr = trace_of(p, out)
            self.assertEqual([(e["role"], e["tour"], e["categorie"]) for e in tr["erreurs_techniques"]],
                             [("plan-writer", 1, "format"), ("plan-reviewer", 2, "format")])
            self.assertTrue(all(e["recuperee"] for e in tr["erreurs_techniques"]))
            self.assertEqual(check_trace(tr), [])

    def test_erreur_d_execution_est_tracee_sans_empreinte_de_sortie(self):
        with Workdir() as wd:
            p = project(wd)
            out = go(p, Fake([RuntimeError("boum"), plan_text()]), Fake([ACCEPT_OK]))
            self.assertEqual(out["issue"], "accepte")
            e = trace_of(p, out)["erreurs_techniques"][0]
            self.assertEqual((e["categorie"], e["sortie_sha256"], e["recuperee"]), ("execution", None, True))
            self.assertIn("boum", e["cause"])


class VerificateurDeTrace(unittest.TestCase):
    def good(self):
        with Workdir() as wd:
            p = project(wd)
            out = go(p, Fake([plan_text()]), Fake([WRONG_IDS, GOOD]))
            return trace_of(p, out)

    def test_detecte_une_erreur_recuperee_non_tracee(self):
        tr = self.good()
        tr["erreurs_techniques"] = []
        self.assertTrue(any("refus" in d or "relances" in d for d in check_trace(tr)))

    def test_detecte_un_appel_apres_la_clarification(self):
        tr = self.good()
        tr["appels_detail"].append({"n": 4, "role": "plan-writer", "tour": 2, "tentative": 1, "resultat": "valide"})
        tr["appels"]["plan-writer"] += 1  # trace par ailleurs cohérente : seul l'appel en trop doit être relevé
        self.assertTrue(any("clarification" in d for d in check_trace(tr)))

    def test_detecte_une_relance_hors_borne_et_une_livraison_apres_arret(self):
        tr = self.good()
        tr["erreurs_techniques"][0]["tentative"] = 9
        tr["livraison"] = {"chemin": "x"}
        d = " ".join(check_trace(tr))
        self.assertIn("bornées", d)
        self.assertIn("livraison présente", d)


if __name__ == "__main__":
    unittest.main()
