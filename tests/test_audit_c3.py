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

from zakios import mission

from .helpers import Workdir
from .test_relances import ASK, CRITERIA, GOOD, REQUEST, WRONG_IDS
from .test_mission import plan_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "scripts", "audit_artefacts.py")


def write_log(path, text):
    events = [{"type": "system", "subtype": "init", "tools": ["Read", "Glob", "Grep"], "model": "m"},
              {"type": "result", "result": text, "is_error": False}]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(e) for e in events) + "\n")


def build_campaign(wd):
    work = os.path.join(wd, "work")
    base = os.path.join(work, "base")
    os.makedirs(os.path.join(base, "src"))
    with open(os.path.join(base, "src/pay.py"), "w") as fh:
        fh.write("x\n")
    d = os.path.join(work, "copie-information_manquante-p3")
    shutil.copytree(base, d)
    answers = {"plan-writer": [plan_text()], "plan-reviewer": [WRONG_IDS, GOOD]}
    log = []

    def role(name):
        def call(*args):
            raw = answers[name].pop(0)
            if name == "plan-reviewer":
                raw = raw.replace("@PLAN@", mission.plan_fingerprint(args[2]))
            write_log(os.path.join(work, "log-information_manquante-p3-%d.jsonl" % len(log)), raw)
            log.append(raw)
            return raw
        return call

    out = mission.run_mission(d, REQUEST, CRITERIA, role("plan-writer"), role("plan-reviewer"), mission_id="m3",
                              journal=lambda: "log-information_manquante-p3-%d.jsonl" % (len(log) - 1))
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


if __name__ == "__main__":
    unittest.main()
