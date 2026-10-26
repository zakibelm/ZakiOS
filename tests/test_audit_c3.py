"""L'audit indépendant lit des traces v2 avec relances (simulé : journaux fabriqués au format stream-json).

Il doit : relier chaque refus à son journal et à l'empreinte de la sortie, ne signaler aucune divergence sur le passage
« information_manquante n°3 » reproduit, et signaler une divergence si la trace omet l'erreur récupérée ou si le lien
de journal est faux."""
import json
import os
import shutil
import subprocess
import sys
import unittest

from zakios import mission, outils

from .helpers import Workdir
from .test_relances import ASK, CRITERIA, GOOD, REQUEST, WRONG_IDS
from .test_mission import plan_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "scripts", "audit_artefacts.py")


def write_log(path, text, extra=()):
    events = [{"type": "system", "subtype": "init", "tools": ["Read", "Glob", "Grep"], "model": "m"}, *extra,
              {"type": "result", "result": text, "is_error": False}]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(e) for e in events) + "\n")


def build_campaign(wd, forbidden=None):
    work = os.path.join(wd, "work")
    base = os.path.join(work, "base")
    os.makedirs(os.path.join(base, "src"))
    with open(os.path.join(base, "src/pay.py"), "w") as fh:
        fh.write("x\n")
    d = os.path.join(work, "copie-information_manquante-p3")
    shutil.copytree(base, d)
    answers = {"plan-writer": [plan_text()], "plan-reviewer": [WRONG_IDS, GOOD]}
    log = []
    audit = {"v": {"demandes": {}, "interdits": []}}

    def role(name):
        def call(*args):
            raw = answers[name].pop(0)
            if name == "plan-reviewer":
                raw = raw.replace("@PLAN@", mission.plan_fingerprint(args[2]))
            extra = forbidden if (forbidden and name == "plan-writer") else ()
            write_log(os.path.join(work, "log-information_manquante-p3-%d.jsonl" % len(log)), raw, extra)
            audit["v"] = outils.analyse(list(extra), ["Read", "Glob", "Grep"])
            log.append(raw)
            return raw
        return call

    out = mission.run_mission(d, REQUEST, CRITERIA, role("plan-writer"), role("plan-reviewer"), mission_id="m3",
                              journal=lambda: "log-information_manquante-p3-%d.jsonl" % (len(log) - 1),
                              tool_audit=lambda: audit["v"])
    return work, d, out


def audit(work):
    p = subprocess.run([sys.executable, "-B", AUDIT, work], capture_output=True, text=True)
    return p.returncode, p.stdout


class AuditDesRelances(unittest.TestCase):
    def test_passage_3_reproduit_sans_divergence(self):
        with Workdir() as wd:
            work, d, out = build_campaign(wd)
            self.assertEqual(out["issue"], "clarification_requise")
            code, text = audit(work)
            self.assertEqual(code, 0, text)
            self.assertIn('"erreurs_relancees_verifiees": 1', text)

    def test_detecte_une_erreur_recuperee_absente_de_la_trace(self):
        with Workdir() as wd:
            work, d, out = build_campaign(wd)
            tp = os.path.join(d, out["trace"])
            tr = json.load(open(tp))
            tr["erreurs_techniques"] = []
            json.dump(tr, open(tp, "w"))
            code, text = audit(work)
            self.assertEqual(code, 1)
            self.assertIn("refus", text)

    def test_detecte_un_lien_de_journal_ou_une_empreinte_faux(self):
        for field, value, needle in (("journal", "log-information_manquante-p3-0.jsonl", "lien de journal"),
                                     ("sortie_sha256", "0" * 64, "empreinte de la sortie")):
            with self.subTest(field), Workdir() as wd:
                work, d, out = build_campaign(wd)
                tp = os.path.join(d, out["trace"])
                tr = json.load(open(tp))
                tr["erreurs_techniques"][0][field] = value
                json.dump(tr, open(tp, "w"))
                code, text = audit(work)
                self.assertEqual(code, 1)
                self.assertIn(needle, text)


REFUS = "<tool_use_error>Error: No such tool available: Bash. Bash is not among the tools available here.</tool_use_error>"
CALL = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]}}


def result(text, is_error):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": text, "is_error": is_error}]}}


class AuditDesOutilsInterdits(unittest.TestCase):
    def test_tentative_refusee_listee_comme_ecart_sans_divergence(self):
        with Workdir() as wd:
            work, d, out = build_campaign(wd, forbidden=[CALL, result(REFUS, True)])
            code, text = audit(work)
            self.assertEqual(code, 0, text)
            self.assertIn("ÉCART COMPORTEMENTAL", text)
            self.assertIn('"tentatives_interdites": 1', text)

    def test_execution_interdite_est_une_divergence(self):
        with Workdir() as wd:
            work, d, out = build_campaign(wd, forbidden=[CALL, result("a\nb", False)])
            self.assertEqual(out["issue"], "erreur_technique")  # le coordinateur a bloqué
            code, text = audit(work)
            self.assertEqual(code, 1)
            self.assertIn("EXÉCUTION INTERDITE", text)

    def test_ecart_absent_de_la_trace_est_une_divergence(self):
        with Workdir() as wd:
            work, d, out = build_campaign(wd, forbidden=[CALL, result(REFUS, True)])
            tp = os.path.join(d, out["trace"])
            tr = json.load(open(tp))
            tr["ecarts_comportementaux"] = []
            json.dump(tr, open(tp, "w"))
            code, text = audit(work)
            self.assertEqual(code, 1)
            self.assertIn("écarts comportementaux tracés", text)


if __name__ == "__main__":
    unittest.main()
