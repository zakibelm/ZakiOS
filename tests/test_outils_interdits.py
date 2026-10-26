"""Outils interdits : demandé / refusé par la plateforme / exécution confirmée / indéterminé — SIMULÉ (journaux fabriqués).

Le refus n'est jamais déduit du seul texte « No such tool » : il est recoupé avec l'appel concerné et la liste des
outils effectifs. Une tentative refusée est signalée (écart comportemental) sans bloquer ; une exécution confirmée ou un
résultat indéterminé arrête la mission sans livraison."""
import json
import os
import unittest

from zakios import mission, outils
from zakios.mission import check_trace, run_mission

from .helpers import Workdir
from .test_clarification import project, tree
from .test_mission import ACCEPT, CRITERIA, REQUEST, Fake, plan_text

EFFECTIVE = ["Read", "Glob", "Grep"]


def use(i, name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]}}


def res(i, text, is_error):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i, "content": text, "is_error": is_error}]}}


REFUS = "<tool_use_error>Error: No such tool available: Bash. Bash is not among the tools available here.</tool_use_error>"


class Analyse(unittest.TestCase):
    def one(self, events, effective=EFFECTIVE):
        return outils.analyse(events, effective)["interdits"]

    def test_outil_autorise_n_est_pas_un_ecart(self):
        a = outils.analyse([use("1", "Read", file_path="x"), res("1", "contenu", False)], EFFECTIVE)
        self.assertEqual((a["demandes"], a["interdits"]), ({"Read": 1}, []))

    def test_tentative_refusee_par_la_plateforme(self):
        ev = self.one([use("1", "Bash", command="git log"), res("1", REFUS, True)])
        self.assertEqual([(e["outil"], e["statut"]) for e in ev], [("Bash", "demande_refusee")])

    def test_execution_confirmee(self):
        ev = self.one([use("1", "Bash", command="ls"), res("1", "a\nb", False)])
        self.assertEqual(ev[0]["statut"], "execution_confirmee")

    def test_resultat_indetermine_sans_resultat_lie(self):
        self.assertEqual(self.one([use("1", "Bash", command="ls")])[0]["statut"], "indetermine")
        self.assertEqual(self.one([use("1", "Bash", command="ls"), res("autre", REFUS, True)])[0]["statut"], "indetermine")

    def test_le_texte_seul_ne_suffit_pas(self):
        # message de refus mais l'outil figure dans la liste effective : contradiction -> indéterminé
        self.assertEqual(self.one([use("1", "Bash"), res("1", REFUS, True)], EFFECTIVE + ["Bash"])[0]["statut"], "indetermine")
        # erreur d'un autre outil citée dans le message : indéterminé
        self.assertEqual(self.one([use("1", "Bash"), res("1", REFUS.replace("Bash", "Edit"), True)])[0]["statut"], "indetermine")
        # erreur sans indicateur d'erreur du résultat : exécution confirmée (pas un refus)
        self.assertEqual(self.one([use("1", "Bash"), res("1", REFUS, False)])[0]["statut"], "execution_confirmee")
        # erreur quelconque (la commande a pu s'exécuter) : indéterminé
        self.assertEqual(self.one([use("1", "Bash"), res("1", "exit code 1", True)])[0]["statut"], "indetermine")

    def test_analyse_de_journal_brut(self):
        log = "\n".join(json.dumps(e) for e in [{"type": "system", "subtype": "init", "tools": EFFECTIVE},
                                                  use("1", "Bash"), res("1", REFUS, True)])
        self.assertEqual(outils.analyse_log(log)["interdits"][0]["statut"], "demande_refusee")


def role_with(answers, audits):
    """Rôle simulé + audit d'outils fourni appel par appel."""
    fake = Fake(answers)
    queue = list(audits)

    def call(*args):
        return fake(*args)
    call.audit = lambda: queue.pop(0) if queue else {"demandes": {}, "interdits": []}
    call.fake = fake
    return call


def audit_of(*statuts):
    return {"demandes": {"Bash": len(statuts)},
            "interdits": [{"outil": "Bash", "id": "t%d" % i, "statut": s, "preuve": "p", "effectifs": EFFECTIVE} for i, s in enumerate(statuts)]}


NONE = {"demandes": {"Read": 1}, "interdits": []}


class Integration(unittest.TestCase):
    def run_it(self, w_audits, r_audits, **kw):
        # un seul `tool_audit` global : les audits sont servis dans l'ordre des appels (rédacteur, relecteur, ...)
        order = list(w_audits) + list(r_audits)
        queue = order
        with Workdir() as wd:
            p = project(wd)
            before = tree(p)
            writer, reviewer = Fake([plan_text()]), Fake([ACCEPT])
            out = run_mission(p, REQUEST, CRITERIA, writer, reviewer, now=lambda: "t", tool_audit=lambda: queue.pop(0), **kw)
            tr = json.load(open(os.path.join(p, out["trace"])))
            return out, tr, tree(p) == before, (len(writer.calls), len(reviewer.calls))

    def test_tentative_refusee_signalee_sans_bloquer_la_livraison(self):
        out, tr, unchanged, calls = self.run_it([audit_of("demande_refusee")], [NONE])
        self.assertEqual(out["issue"], "accepte")
        self.assertIsNotNone(out["livraison"])
        self.assertEqual([(e["outil"], e["statut"], e["role"]) for e in out["ecarts"]], [("Bash", "demande_refusee", "plan-writer")])
        self.assertEqual(tr["ecarts_comportementaux"], out["ecarts"])  # visible dans la trace
        self.assertEqual(check_trace(tr), [])

    def test_execution_interdite_bloque_la_livraison_et_arrete_tout(self):
        out, tr, unchanged, calls = self.run_it([audit_of("execution_confirmee")], [NONE])
        self.assertEqual((out["issue"], out["categorie"]), ("erreur_technique", "technique"))
        self.assertIsNone(out["livraison"])
        self.assertTrue(unchanged)
        self.assertEqual(calls, (1, 0))  # le relecteur n'est jamais appelé
        self.assertEqual(tr["arret"]["sous_categorie"], "confinement")
        self.assertNotIn("livraison", tr)
        self.assertEqual(tr["appels_detail"][-1]["resultat"], "bloque_outil_interdit")
        self.assertEqual(check_trace(tr), [])

    def test_resultat_indetermine_bloque_la_livraison(self):
        out, tr, unchanged, calls = self.run_it([NONE], [audit_of("indetermine")])
        self.assertEqual(out["issue"], "erreur_technique")
        self.assertIsNone(out["livraison"])
        self.assertTrue(unchanged)
        self.assertEqual(tr["arret"]["sous_categorie"], "confinement")
        self.assertEqual(tr["ecarts_comportementaux"][0]["statut"], "indetermine")
        self.assertEqual(check_trace(tr), [])

    def test_execution_interdite_n_est_jamais_relancee(self):
        out, tr, unchanged, calls = self.run_it([audit_of("execution_confirmee"), NONE, NONE], [NONE], max_technical_retries=2)
        self.assertEqual(calls[0], 1)
        self.assertEqual(out["issue"], "erreur_technique")

    def test_ecart_dans_un_appel_qui_echoue_au_format_reste_visible(self):
        queue = [audit_of("demande_refusee"), NONE, NONE]
        with Workdir() as wd:
            p = project(wd)
            out = run_mission(p, REQUEST, CRITERIA, Fake(["pas de bloc", plan_text()]), Fake([ACCEPT]),
                              now=lambda: "t", tool_audit=lambda: queue.pop(0))
            tr = json.load(open(os.path.join(p, out["trace"])))
        self.assertEqual(out["issue"], "accepte")
        self.assertEqual(len(tr["ecarts_comportementaux"]), 1)
        self.assertEqual(tr["ecarts_comportementaux"][0]["tentative"], 1)
        self.assertEqual(check_trace(tr), [])

    def test_verificateur_detecte_des_traces_falsifiees(self):
        out, tr, _, _ = self.run_it([audit_of("execution_confirmee")], [NONE])
        tr["arret"]["sous_categorie"] = "autre"
        self.assertTrue(any("confinement" in d for d in check_trace(tr)))
        out, tr, _, _ = self.run_it([audit_of("demande_refusee")], [NONE])
        tr["ecarts_comportementaux"] = []
        self.assertTrue(any("écarts tracés" in d for d in check_trace(tr)))


if __name__ == "__main__":
    unittest.main()
