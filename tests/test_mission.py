"""Coordinateur de mission : toutes les branches, sans modèle (rôles remplacés par des faux)."""
import json
import os
import unittest

from zakios import deliver, mission
from zakios.mission import MissionError, TechnicalError, plan_fingerprint, run_mission
from zakios.mission import parse_review as _parse_review

from .helpers import Workdir

REQUEST = "Planifie la correction du module de paiement."
CRITERIA = ["C1 remise correcte aux bornes 0 et 100", "C2 requête SQL paramétrée", "C3 aucune régression sur les appels existants"]


def plan_text(title="v1", path="docs/plans/2026-10-26-paiement.md", extra=""):
    return ("Chemin proposé : %s\n%s\n# Plan : %s\n## Planifier\nC1 C2 C3\n%s\n%s\n" % (path, deliver.BEGIN, title, extra, deliver.END))


PLACEHOLDER = "@PLAN@"


def concrete(text, fingerprint="0" * 16):
    """Remplace l'espace réservé d'empreinte (utilisé pour analyser une revue hors coordinateur)."""
    return text.replace(PLACEHOLDER, fingerprint)


def parse_review(text, criteria=None, plan_sha=None):
    return _parse_review(concrete(text), criteria, plan_sha)


def review_text(verdict, *findings, couverture=None, bind=PLACEHOLDER):
    """Revue simulée. Par défaut, chaque critère de la mission est « couvert » et la revue recopie l'empreinte du plan
    réellement transmis (le faux rôle `Fake` remplace l'espace réservé)."""
    cov = couverture if couverture is not None else {mission.criterion_id(c): "couvert" for c in CRITERIA}
    lines = ["Plan examiné : %s" % bind] if bind else []
    lines += ["Couverture %s : %s" % (k, v) for k, v in cov.items()]
    body = "\n".join(lines + list(findings))
    return "%s\nVerdict : %s\n%s\n%s\n" % (mission.REVIEW_BEGIN, verdict, body, mission.REVIEW_END)


BLOCK = "- [bloquant] critère « C3 » · Problème : absent → Action : ajouter C3 → Résultat : couvert · preuve : absence du critère C3 attendu"
MINOR = "- [mineur] critère « C1 » · Problème : flou → Action : préciser → Résultat : mesurable · preuve : « C1 C2 C3 »"
ACCEPT = review_text("ACCEPTE", MINOR)
REJECT = review_text("A_CORRIGER", BLOCK)


class Fake:
    """Rôle simulé : renvoie les réponses prévues dans l'ordre et enregistre les appels."""
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, *args):
        self.calls.append(args)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, str) and len(args) == 3:  # relecteur : recopie l'empreinte du plan reçu
            answer = answer.replace(PLACEHOLDER, plan_fingerprint(args[2]))
        return answer


def project(wd):
    p = os.path.join(wd, "proj")
    os.makedirs(p)
    return p


def go(p, writer, reviewer, **kw):
    return run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "2026-10-26T00:00:00Z", **kw)


def exists(p, rel):
    return os.path.exists(os.path.join(p, rel))


class ParseReview(unittest.TestCase):
    def test_valid_accept_and_reject(self):
        self.assertEqual(parse_review(ACCEPT)[0], "ACCEPTE")
        verdict, findings = parse_review(REJECT)
        self.assertEqual((verdict, findings[0]["gravite"]), ("A_CORRIGER", "bloquant"))
        self.assertEqual(parse_review(review_text("ACCEPTE"))[1], [])  # accepté sans aucun constat

    def test_omission_uses_absence_as_proof(self):
        self.assertEqual(parse_review(REJECT)[1][0]["texte"].count("absence"), 1)

    def test_refuses_malformed_or_incoherent(self):
        bad = {
            "sans bloc": "Verdict : ACCEPTE",
            "deux blocs": ACCEPT + ACCEPT,
            "sans verdict": "%s\n%s\n%s\n" % (mission.REVIEW_BEGIN, MINOR, mission.REVIEW_END),
            "deux verdicts": "%s\nVerdict : ACCEPTE\nVerdict : ACCEPTE\n%s\n" % (mission.REVIEW_BEGIN, mission.REVIEW_END),
            "ligne libre": "%s\nVerdict : ACCEPTE\nTout va bien.\n%s\n" % (mission.REVIEW_BEGIN, mission.REVIEW_END),
            "constat incomplet": review_text("A_CORRIGER", "- [bloquant] critère C3 manquant"),
            "verdict inconnu": review_text("PEUT-ETRE"),
            "ACCEPTE malgré bloquant (M3)": review_text("ACCEPTE", BLOCK),
            "A_CORRIGER sans bloquant": review_text("A_CORRIGER", MINOR),
            "gravité inconnue": review_text("A_CORRIGER", BLOCK.replace("bloquant", "critique")),
        }
        for label, text in bad.items():
            with self.assertRaises(TechnicalError, msg=label):
                parse_review(text)


class MissionTests(unittest.TestCase):
    def test_accepted_first_time_is_delivered_once(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([plan_text()]), Fake([ACCEPT])
            out = go(p, w, r, components={"plan-writer": "f7401c"})
            self.assertEqual((out["issue"], out["tours"]), ("accepte", 1))
            self.assertEqual(out["livraison"]["statut"], "enregistre")
            self.assertEqual(out["livraison"]["second"], "deja_enregistre")
            self.assertTrue(exists(p, "docs/plans/2026-10-26-paiement.md"))
            trace = json.load(open(os.path.join(p, out["trace"])))
            self.assertEqual(trace["composants"], {"plan-writer": "f7401c"})
            self.assertEqual(trace["tours"][0]["revue"]["plan_examine_sha256"], trace["tours"][0]["plan_sha256"])
            self.assertEqual(trace["livraison"]["delivery_sha256"], out["livraison"]["delivery_sha256"])

    def test_error_detected_corrected_and_review_is_redone(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("v1 sans C3"), plan_text("v2 avec C3")])
            r = Fake([REJECT, ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("accepte", 2))
            _, _, previous, findings = w.calls[1]
            self.assertIn("v1 sans C3", previous)               # le planificateur reçoit le plan précédent
            self.assertIn("C3", findings[0])                    # et les constats
            reviewed = [c[2] for c in r.calls]
            self.assertIn("v1 sans C3", reviewed[0])
            self.assertIn("v2 avec C3", reviewed[1])            # le plan corrigé est relu : l'ancienne acceptation ne vaut pas
            content = open(os.path.join(p, "docs/plans/2026-10-26-paiement.md")).read()
            self.assertIn("v2 avec C3", content)
            self.assertNotIn("v1 sans C3", content)
            t = json.load(open(os.path.join(p, out["trace"])))["tours"]
            self.assertNotEqual(t[0]["plan_sha256"], t[1]["plan_sha256"])
            self.assertEqual(t[1]["revue"]["plan_examine_sha256"], t[1]["plan_sha256"])
            self.assertEqual(t[0]["revue"]["verdict"], "A_CORRIGER")

    def test_ceiling_is_three_plans_and_three_reviews_and_nothing_is_saved(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("a"), plan_text("b"), plan_text("c"), plan_text("d")])
            r = Fake([REJECT, REJECT, REJECT, REJECT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("plafond_atteint", 3))
            self.assertEqual((len(w.calls), len(r.calls)), (3, 3))
            self.assertFalse(exists(p, "docs/plans"))
            self.assertIsNone(out["livraison"])
            self.assertTrue(exists(p, out["trace"]))             # l'échec est tracé

    def test_third_plan_accepted_is_the_one_delivered(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text("a"), plan_text("b"), plan_text("c")])
            r = Fake([REJECT, REJECT, ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("accepte", 3))
            self.assertIn("# Plan : c", open(os.path.join(p, "docs/plans/2026-10-26-paiement.md")).read())

    def test_request_and_criteria_are_identical_in_every_call(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([plan_text("a"), plan_text("b")]), Fake([REJECT, ACCEPT])
            go(p, w, r)
            for call in w.calls + r.calls:
                self.assertEqual(call[0], REQUEST)
                self.assertEqual(call[1], CRITERIA)

    def test_technical_retry_is_bounded_and_separate_from_corrections(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([plan_text()]), Fake(["n'importe quoi", ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], out["tours"]), ("accepte", 1))
            self.assertEqual(len(r.calls), 2)
            self.assertEqual(json.load(open(os.path.join(p, out["trace"])))["tours"][0]["revue"]["relances_relecteur"], 1)

    def test_technical_failure_after_retries_stops_without_saving(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([plan_text()]), Fake(["n'importe quoi", "encore n'importe quoi", ACCEPT])
            out = go(p, w, r)
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertEqual(len(r.calls), 2)                    # 1 appel + 1 relance, pas plus
            self.assertFalse(exists(p, "docs/plans"))
            self.assertTrue(json.load(open(os.path.join(p, out["trace"])))["erreurs_techniques"])

    def test_falsified_review_is_rejected(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([plan_text()]), Fake([review_text("ACCEPTE", BLOCK), review_text("ACCEPTE", BLOCK)])
            out = go(p, w, r)
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertFalse(exists(p, "docs/plans"))

    def test_bad_writer_output_and_writer_exception_are_bounded(self):
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake(["pas de bloc", plan_text()]), Fake([ACCEPT])
            self.assertEqual(go(p, w, r)["issue"], "accepte")
        with Workdir() as wd:
            p = project(wd)
            w, r = Fake([RuntimeError("boum"), RuntimeError("boum")]), Fake([ACCEPT])
            out = go(p, w, r)
            self.assertEqual((out["issue"], len(w.calls), len(r.calls)), ("erreur_technique", 2, 0))

    def test_plan_path_outside_perimeter_is_never_delivered(self):
        with Workdir() as wd:
            p = project(wd)
            w = Fake([plan_text(path="docs/plans/../../x.md"), plan_text(path="/etc/x.md")])
            out = go(p, w, Fake([ACCEPT]))
            self.assertEqual(out["issue"], "erreur_technique")
            self.assertFalse(exists(p, "docs"))

    def test_zero_corrections_allowed(self):
        with Workdir() as wd:
            p = project(wd)
            out = go(p, Fake([plan_text()]), Fake([REJECT]), max_corrections=0)
            self.assertEqual((out["issue"], out["tours"]), ("plafond_atteint", 1))

    def test_mission_trace_is_written_once_and_never_replaced(self):
        with Workdir() as wd:
            p = project(wd)
            out = go(p, Fake([plan_text()]), Fake([ACCEPT]), mission_id="mission-1")
            rel = out["trace"]
            before = open(os.path.join(p, rel)).read()
            again = go(p, Fake([plan_text()]), Fake([ACCEPT]), mission_id="mission-1")  # même mission, même contenu
            self.assertEqual(open(os.path.join(p, rel)).read(), before)
            self.assertEqual(again["livraison"]["statut"], "deja_enregistre")
            with self.assertRaises(deliver.DeliveryError):       # même chemin, autre plan : écrasement refusé
                go(p, Fake([plan_text("autre")]), Fake([ACCEPT]), mission_id="mission-1")
            with self.assertRaises(MissionError):                # même identifiant, autre contenu de trace
                mission.write_trace(p, "mission-1", {"v": 1, "autre": True})
            self.assertEqual(open(os.path.join(p, rel)).read(), before)

    def test_invalid_mission_id_and_symlinked_trace_dir_are_refused(self):
        with Workdir() as wd:
            p = project(wd)
            for bad in ("../x", "a/b", "", ".x"):
                with self.assertRaises(MissionError, msg=bad):
                    mission.write_trace(p, bad, {})
            outside = os.path.join(wd, "dehors")
            os.makedirs(outside)
            os.makedirs(os.path.join(p, ".zakios"))
            os.symlink(outside, os.path.join(p, ".zakios/missions"))
            with self.assertRaises(MissionError):
                mission.write_trace(p, "m1", {"a": 1})
            self.assertEqual(os.listdir(outside), [])

    def test_derived_mission_id_is_stable_and_depends_on_the_request(self):
        a = mission.derive_mission_id(REQUEST, CRITERIA)
        self.assertEqual(a, mission.derive_mission_id(REQUEST, CRITERIA))
        self.assertNotEqual(a, mission.derive_mission_id(REQUEST + "!", CRITERIA))
        self.assertNotEqual(a, mission.derive_mission_id(REQUEST, CRITERIA[:2]))


if __name__ == "__main__":
    unittest.main()
