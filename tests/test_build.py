import json
import os
import unittest
from unittest import mock

from zakios import build as build_mod
from zakios import policy
from zakios.build import BuildError, ValidationError, build, validate_catalog

from .helpers import Workdir, git, make_world


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def load_registry(out):
    return {c["component_id"]: c for c in json.loads(read(os.path.join(out, "registry.json")))["components"]}


class BuildTests(unittest.TestCase):
    def test_build_produces_a_valid_registry(self):
        with Workdir() as wd:
            root, manifest, commits = make_world(wd)
            out = os.path.join(wd, "catalog")
            report = build(manifest, root, out)
            self.assertEqual(validate_catalog(out)["components"], sum(report["counts_by_type"].values()))
            comps = load_registry(out)
            frontend = comps["acme/catalogue:components/agents/web/frontend-dev.md"]
            self.assertEqual(frontend["provenance"]["commit"], commits["catalogue"])
            self.assertEqual(len(frontend["provenance"]["content_sha256"]), 64)
            self.assertEqual(frontend["evaluation"]["status"], policy.STATUS_EQUIVALENCE)
            self.assertEqual(frontend["evaluation"]["best_match_id"], "acme/socle:agents/frontend-developer.md")
            self.assertFalse(frontend["license"]["verified"])
            self.assertIsNone(frontend["decision"]["validated"])

    def test_multiline_description_and_no_yaml_marker(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            skill = load_registry(out)["acme/catalogue:components/skills/dev/SKILL.md"]
            self.assertEqual(skill["function"]["summary"], "Guide pour écrire des tests d'abord.")

    def test_hooks_and_mods_are_never_adopted_automatically(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            comps = load_registry(out)
            hook = comps["acme/catalogue:components/hooks/git/guard.json"]
            mod = comps["acme/catalogue:components/mods/security/jail/README.md"]
            for comp in (hook, mod):
                self.assertEqual(comp["evaluation"]["status"], policy.STATUS_BEHAVIOR)
            # le script compagnon et les fichiers internes du mod ne sont pas des composants à part
            self.assertNotIn("acme/catalogue:components/hooks/git/guard.py", comps)
            self.assertFalse([c for c in comps if "jail/hooks" in c or "plugin.json" in c])

    def test_missing_existant_source_makes_everything_provisional(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            report = build(manifest, root, out)
            self.assertTrue(report["provisional"])
            self.assertTrue(any(s["status"] == "absente_facultative" for s in report["sources"]))
            for comp in load_registry(out).values():
                if comp["evaluation"]:
                    self.assertEqual(comp["evaluation"]["provisional_reason"], policy.PROVISIONAL_REASON)

    def test_reproducible_output(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            a, b = os.path.join(wd, "a"), os.path.join(wd, "b")
            build(manifest, root, a)
            build(manifest, root, b)
            for name in ("registry.json", "crosswalk.csv", "build_report.json"):
                self.assertEqual(read(os.path.join(a, name)), read(os.path.join(b, name)), name)

    def test_missing_required_source_stops_and_keeps_last_catalog(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            before = read(os.path.join(out, "registry.json"))
            data = json.loads(read(manifest))
            data["sources"].append({"repo": "acme/absent", "role": "socle", "commit": "a" * 40})
            with open(manifest, "w") as handle:
                json.dump(data, handle)
            with self.assertRaises(BuildError):
                build(manifest, root, out)
            self.assertEqual(read(os.path.join(out, "registry.json")), before)
            self.assertFalse(os.path.exists(out + ".tmp"))

    def test_commit_mismatch_is_refused(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            data = json.loads(read(manifest))
            data["sources"][1]["commit"] = "b" * 40
            with open(manifest, "w") as handle:
                json.dump(data, handle)
            with self.assertRaises(BuildError) as ctx:
                build(manifest, root, os.path.join(wd, "catalog"))
            self.assertIn("différent du manifeste", str(ctx.exception))

    def test_short_commit_is_refused(self):
        with Workdir() as wd:
            root, manifest, commits = make_world(wd)
            data = json.loads(read(manifest))
            data["sources"][1]["commit"] = commits["socle"][:12]
            with open(manifest, "w") as handle:
                json.dump(data, handle)
            with self.assertRaises(BuildError):
                build(manifest, root, os.path.join(wd, "catalog"))

    def test_local_modifications_are_detected(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            path = os.path.join(root, "acme", "socle", "agents", "backend-developer.md")
            with open(path, "a") as handle:
                handle.write("modif locale\n")
            out = os.path.join(wd, "catalog")
            with self.assertRaises(BuildError) as ctx:
                build(manifest, root, out)
            self.assertIn("modifications locales", str(ctx.exception))
            build(manifest, root, out, allow_dirty=True)

    def test_interrupted_generation_keeps_last_valid_catalog(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            before = read(os.path.join(out, "registry.json"))
            with mock.patch.object(build_mod, "validate_catalog", side_effect=ValidationError("simulé")):
                with self.assertRaises(ValidationError):
                    build(manifest, root, out)
            self.assertEqual(read(os.path.join(out, "registry.json")), before)
            self.assertFalse(os.path.exists(out + ".tmp"))

    def test_recovery_after_crash_during_swap(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            os.rename(out, out + ".bak")  # crash simulé : le catalogue courant a disparu
            build_mod._recover(out)
            self.assertTrue(os.path.exists(os.path.join(out, "registry.json")))

    def test_validated_decisions_survive_and_orphans_are_reported(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            decisions = os.path.join(wd, "validated.json")
            cid = "acme/catalogue:components/agents/ops/devops-engineer.md"
            with open(decisions, "w") as handle:
                json.dump({cid: {"validated": "conserver", "validated_by": "Zaki", "validated_on": "2026-10-26",
                                 "justification": "mission distincte"},
                           "acme/inconnu:x.md": {"validated": "archiver"}}, handle)
            report = build(manifest, root, out, decisions_path=decisions)
            decision = load_registry(out)[cid]["decision"]
            self.assertEqual((decision["validated"], decision["validated_by"]), ("conserver", "Zaki"))
            self.assertEqual(report["orphan_decisions"], ["acme/inconnu:x.md"])

    def test_validation_rejects_a_tampered_catalog(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            path = os.path.join(out, "registry.json")
            data = json.loads(read(path))
            for comp in data["components"]:
                if comp["type"] == "mod":
                    comp["evaluation"]["status"] = policy.STATUS_NOVELTY
            with open(path, "w") as handle:
                json.dump(data, handle)
            with self.assertRaises(ValidationError):
                validate_catalog(out)

    def test_invalid_frontmatter_is_reported_in_the_build_report(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            catalogue = os.path.join(root, "acme", "catalogue")
            bad = os.path.join(catalogue, "components", "agents", "web", "casse.md")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write("---\nname: casse\ndescription: Use when: ceci casse\n---\nCorps de l'agent cassé.\n")
            git(catalogue, "add", "-A")
            git(catalogue, "commit", "-q", "-m", "bad")
            data = json.loads(read(manifest))
            data["sources"][0]["commit"] = git(catalogue, "rev-parse", "HEAD")
            with open(manifest, "w") as handle:
                json.dump(data, handle)
            report = build(manifest, root, os.path.join(wd, "catalog"))
            self.assertEqual([i["path"] for i in report["metadata_issues"]], ["components/agents/web/casse.md"])


if __name__ == "__main__":
    unittest.main()
