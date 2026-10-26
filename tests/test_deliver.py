"""Enregistrement contrôlé des plans : création, idempotence, refus, concurrence, interruption."""
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import unittest

from zakios import deliver
from zakios.deliver import DeliveryError, preview, save_plan

from .helpers import Workdir

PATH = "docs/plans/2026-10-26-essai.md"
PLAN = "# Plan\n\nÉtapes PDCA.\n\n$(rm -rf /) `touch pwned`\n"


def rd(path):
    with open(path) as h:
        return h.read()


def wr(path, text):
    with open(path, "w") as h:
        h.write(text)


def dsha(path, text, mission=""):
    return deliver.preview(path, text, mission)["delivery_sha256"]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def tree(root):
    out = {}
    for base, _, files in os.walk(root):
        for n in files:
            p = os.path.join(base, n)
            with open(p, "rb") as h:
                out[os.path.relpath(p, root)] = h.read()
    return out


def project(wd):
    p = os.path.join(wd, "proj")
    os.makedirs(p)
    return p


def _worker(args):
    proj, content, queue = args
    try:
        r = save_plan(proj, PATH, content, dsha(PATH, content))
        queue.put(("ok", r["status"]))
    except DeliveryError as exc:
        queue.put(("refus", str(exc)))


class DeliverTests(unittest.TestCase):
    def test_preview_writes_nothing_and_normal_creation(self):
        with Workdir() as wd:
            p = project(wd)
            info = preview(PATH, PLAN)
            self.assertEqual(info["content_sha256"], sha(PLAN))
            self.assertEqual(tree(p), {})
            r = save_plan(p, PATH, PLAN, preview(PATH, PLAN, "m1")["delivery_sha256"], mission="m1")
            self.assertEqual(r["status"], "enregistre")
            self.assertEqual(rd(os.path.join(p, PATH)), PLAN)  # contenu jamais exécuté
            self.assertFalse(os.path.exists(os.path.join(p, "pwned")))
            self.assertIn('"mission": "m1"', rd(os.path.join(p, r["trace"])))

    def test_identical_content_is_already_saved_without_writing(self):
        with Workdir() as wd:
            p = project(wd)
            save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            before = tree(p)
            r = save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            self.assertEqual(r["status"], "deja_enregistre")
            self.assertEqual(tree(p), before)

    def test_different_content_at_same_path_is_refused(self):
        with Workdir() as wd:
            p = project(wd)
            save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            other = PLAN + "autre"
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, other, dsha(PATH, other))
            self.assertEqual(rd(os.path.join(p, PATH)), PLAN)

    def test_user_file_is_never_overwritten(self):
        with Workdir() as wd:
            p = project(wd)
            os.makedirs(os.path.join(p, "docs/plans"))
            wr(os.path.join(p, PATH), "mon plan à moi\n")
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            self.assertEqual(rd(os.path.join(p, PATH)), "mon plan à moi\n")

    def test_presented_plan_must_match(self):
        with Workdir() as wd:
            p = project(wd)
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, PLAN, dsha(PATH, "autre chose"))
            self.assertEqual(tree(p), {})

    def test_paths_outside_perimeter_are_refused(self):
        with Workdir() as wd:
            p = project(wd)
            for bad in ("/etc/x.md", "docs/plans/../../x.md", "../x.md", "docs/x.md", "docs/plans/x.txt",
                        "docs/plans/.md", "docs/plans/a b.md", "docs/plans", "docs/plans/", "docs/plans//x.md",
                        "docs/plans/./x.md", "src/docs/plans/x.md", "docs/plans/x.md\0", "docs\\plans\\x.md", ""):
                with self.assertRaises(DeliveryError, msg=bad):
                    save_plan(p, bad, PLAN, dsha(bad, PLAN))
            self.assertEqual(tree(p), {})

    def test_empty_or_binary_plan_is_refused(self):
        with Workdir() as wd:
            p = project(wd)
            for bad in ("", "  \n", b"\xff\xfe", b"a\0b"):
                data = bad if isinstance(bad, bytes) else bad.encode()
                with self.assertRaises(DeliveryError):
                    save_plan(p, PATH, data, dsha(PATH, data.decode("utf-8", "replace")) if False else hashlib.sha256(data).hexdigest())

    def test_symlinked_directory_is_refused(self):
        with Workdir() as wd:
            p = project(wd)
            outside = os.path.join(wd, "dehors")
            os.makedirs(outside)
            os.makedirs(os.path.join(p, "docs"))
            os.symlink(outside, os.path.join(p, "docs/plans"))
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            self.assertEqual(os.listdir(outside), [])

    def test_symlinked_docs_and_final_symlink_are_refused(self):
        with Workdir() as wd:
            p = project(wd)
            outside = os.path.join(wd, "dehors")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(p, "docs"))
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            os.unlink(os.path.join(p, "docs"))
            os.makedirs(os.path.join(p, "docs/plans"))
            target = os.path.join(wd, "cible.md")
            wr(target, "intact\n")
            os.symlink(target, os.path.join(p, PATH))
            with self.assertRaises(DeliveryError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN))
            self.assertEqual(rd(target), "intact\n")
            self.assertEqual(os.listdir(outside), [])

    def test_concurrent_creations_with_different_content_one_wins(self):
        with Workdir() as wd:
            p = project(wd)
            ctx = multiprocessing.get_context("fork")
            queue = ctx.Queue()
            a, b = PLAN + "A", PLAN + "B"
            procs = [ctx.Process(target=_worker, args=((p, c, queue),)) for c in (a, b) for _ in range(3)]
            for pr in procs:
                pr.start()
            for pr in procs:
                pr.join(30)
            results = [queue.get(timeout=5) for _ in procs]
            final = rd(os.path.join(p, PATH))
            self.assertIn(final, (a, b))
            self.assertEqual(sum(1 for r in results if r == ("ok", "enregistre")), 1)
            for kind, value in results:
                if kind == "refus":
                    self.assertIn("écrasement refusé", value)
            leftovers = [n for n in os.listdir(os.path.join(p, "docs/plans")) if n != os.path.basename(PATH)]
            self.assertEqual(leftovers, [])

    def test_interruption_before_write_leaves_nothing(self):
        with Workdir() as wd:
            p = project(wd)

            def boom(point):
                if point == "avant_ecriture":
                    raise RuntimeError("interruption simulée")
            with self.assertRaises(RuntimeError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN), fault=boom)
            self.assertFalse(os.path.exists(os.path.join(p, PATH)))
            self.assertEqual(save_plan(p, PATH, PLAN, dsha(PATH, PLAN))["status"], "enregistre")

    def test_interruption_after_write_is_completed_by_rerun(self):
        with Workdir() as wd:
            p = project(wd)

            def boom(point):
                if point == "apres_ecriture":
                    raise RuntimeError("interruption simulée")
            with self.assertRaises(RuntimeError):
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "m"), fault=boom, mission="m")
            self.assertEqual(rd(os.path.join(p, PATH)), PLAN)  # fichier complet, jamais partiel
            self.assertFalse(os.path.exists(os.path.join(p, ".zakios/deliverables", dsha(PATH, PLAN, "m") + ".json")))
            r = save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "m"), mission="m")
            self.assertEqual(r["status"], "deja_enregistre")
            self.assertTrue(os.path.exists(os.path.join(p, r["trace"])))  # la trace manquante est écrite
            self.assertEqual([n for n in os.listdir(os.path.join(p, "docs/plans")) if n.startswith(".")], [])

    def test_cli_requires_the_presented_sha(self):
        with Workdir() as wd:
            p = project(wd)
            f = os.path.join(wd, "plan.md")
            wr(f, PLAN)
            base = [sys.executable, "-m", "zakios", "save-plan", "--project", p, "--path", PATH, "--content-file", f]
            env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(os.path.abspath(deliver.__file__))))
            pv = subprocess.run(base + ["--preview"], capture_output=True, text=True, env=env)
            self.assertEqual(pv.returncode, 0)
            self.assertIn(dsha(PATH, PLAN), pv.stdout)
            self.assertEqual(tree(p), {})
            no_sha = subprocess.run(base, capture_output=True, text=True, env=env)
            self.assertEqual(no_sha.returncode, 1)
            ok = subprocess.run(base + ["--sha", dsha(PATH, PLAN)], capture_output=True, text=True, env=env)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertTrue(os.path.exists(os.path.join(p, PATH)))

    # ---- identité de la livraison
    def test_same_content_different_paths_have_distinct_traces(self):
        with Workdir() as wd:
            p = project(wd)
            a, b = "docs/plans/a.md", "docs/plans/b.md"
            ra = save_plan(p, a, PLAN, dsha(a, PLAN, "A"), mission="A")
            rb = save_plan(p, b, PLAN, dsha(b, PLAN, "B"), mission="B")
            self.assertNotEqual(ra["trace"], rb["trace"])
            self.assertEqual(ra["content_sha256"], rb["content_sha256"])
            ta = json.loads(rd(os.path.join(p, ra["trace"])))
            tb = json.loads(rd(os.path.join(p, rb["trace"])))
            self.assertEqual((ta["path"], ta["mission"]), (a, "A"))
            self.assertEqual((tb["path"], tb["mission"]), (b, "B"))

    def test_same_content_and_path_different_missions_are_explicit(self):
        with Workdir() as wd:
            p = project(wd)
            r1 = save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "M1"), mission="M1")
            r2 = save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "M2"), mission="M2")
            self.assertEqual((r1["status"], r2["status"]), ("enregistre", "deja_enregistre"))
            self.assertNotEqual(r1["trace"], r2["trace"])
            self.assertEqual(json.loads(rd(os.path.join(p, r1["trace"])))["mission"], "M1")
            self.assertEqual(json.loads(rd(os.path.join(p, r2["trace"])))["mission"], "M2")

    def test_destination_changed_after_preview_is_refused(self):
        with Workdir() as wd:
            p = project(wd)
            shown = dsha("docs/plans/a.md", PLAN)
            with self.assertRaises(DeliveryError):
                save_plan(p, "docs/plans/b.md", PLAN, shown)
            with self.assertRaises(DeliveryError):
                save_plan(p, "docs/plans/a.md", PLAN, shown, mission="autre mission")
            self.assertEqual(tree(p), {})

    def test_inconsistent_existing_trace_is_an_explicit_error(self):
        with Workdir() as wd:
            p = project(wd)
            r = save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "m"), mission="m")
            trace = os.path.join(p, r["trace"])
            data = json.loads(rd(trace))
            data["path"] = "docs/plans/ailleurs.md"
            wr(trace, json.dumps(data))
            with self.assertRaises(DeliveryError) as ctx:
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "m"), mission="m")
            self.assertIn("incohérente", str(ctx.exception))
            wr(trace, "pas du json")
            with self.assertRaises(DeliveryError) as ctx:
                save_plan(p, PATH, PLAN, dsha(PATH, PLAN, "m"), mission="m")
            self.assertIn("illisible", str(ctx.exception))

    def test_trace_is_never_overwritten(self):
        with Workdir() as wd:
            p = project(wd)
            r = save_plan(p, PATH, PLAN, dsha(PATH, PLAN), mission="")
            before = rd(os.path.join(p, r["trace"]))
            save_plan(p, PATH, PLAN, dsha(PATH, PLAN), mission="")
            self.assertEqual(rd(os.path.join(p, r["trace"])), before)  # saved_at d'origine conservé

    # ---- format du livrable
    def test_extract_plan_exact_bytes_and_path(self):
        body = "# Titre\n\n  texte avec espaces  \n\n\nfin\n"
        text = "ZAKIOS-SOCLE v1 · PDCA\nChemin proposé : `docs/plans/x.md`\n%s\n%s%s\n\nCANARI\n" % (deliver.BEGIN, body, deliver.END)
        plan, path = deliver.extract_plan(text)
        self.assertEqual(path, "docs/plans/x.md")
        self.assertEqual(plan, body)
        self.assertEqual(deliver.preview(path, plan)["content_sha256"], sha(body))

    def test_extract_plan_refuses_absent_or_ambiguous(self):
        good = "Chemin proposé : docs/plans/x.md\n%s\n# T\ncorps\n%s\n" % (deliver.BEGIN, deliver.END)
        deliver.extract_plan(good)
        cases = {
            "pas de bloc": "Chemin proposé : docs/plans/x.md\n# T\ncorps\n",
            "deux blocs": good + good,
            "fin avant début": "Chemin proposé : docs/plans/x.md\n%s\n# T\n%s\n" % (deliver.END, deliver.BEGIN),
            "sans chemin": "%s\n# T\n%s\n" % (deliver.BEGIN, deliver.END),
            "deux chemins": "Chemin proposé : docs/plans/x.md\nChemin proposé : docs/plans/y.md\n%s\n# T\n%s\n" % (deliver.BEGIN, deliver.END),
            "chemin hors périmètre": "Chemin proposé : docs/plans/../x.md\n%s\n# T\n%s\n" % (deliver.BEGIN, deliver.END),
            "sans titre niveau 1": "Chemin proposé : docs/plans/x.md\n%s\n## 1. Planifier\n%s\n" % (deliver.BEGIN, deliver.END),
            "bloc vide": "Chemin proposé : docs/plans/x.md\n%s\n%s\n" % (deliver.BEGIN, deliver.END),
        }
        for label, text in cases.items():
            with self.assertRaises(DeliveryError, msg=label):
                deliver.extract_plan(text)


if __name__ == "__main__":
    unittest.main()
