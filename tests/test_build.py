import hashlib
import json
import os
import unittest
from unittest import mock

from zakios import build as build_mod
from zakios import scan as scan_mod
from zakios import policy
from zakios.build import BuildError, ValidationError, build, validate_catalog

from .helpers import Workdir, change_source, git, make_world


FRONT = "Corps de l'agent cassé."


def agent_text(name, description):
    return "---\nname: %s\ndescription: %s\n---\n\nCorps.\n" % (name, description)


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def leftovers(out):
    parent, base = os.path.split(out)
    return [n for n in os.listdir(parent) if n.startswith(base + ".tmp-") or n == base + ".bak"]


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
            self.assertEqual(leftovers(out), [])

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
            self.assertEqual(leftovers(out), [])

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
            build(manifest, root, out)
            fingerprint = load_registry(out)[cid]["provenance"]["fingerprint_sha256"]
            with open(decisions, "w") as handle:
                json.dump({cid: {"validated": "conserver", "validated_by": "Zaki", "validated_on": "2026-10-26",
                                 "justification": "mission distincte", "fingerprint_sha256": fingerprint},
                           "acme/inconnu:x.md": {"validated": "archiver"}}, handle)
            report = build(manifest, root, out, decisions_path=decisions)
            decision = load_registry(out)[cid]["decision"]
            self.assertEqual((decision["validated"], decision["validated_by"]), ("conserver", "Zaki"))
            self.assertEqual(report["orphan_decisions"], ["acme/inconnu:x.md"])
            self.assertEqual(report["stale_decisions"], [])

    def test_validation_is_invalidated_when_content_changes(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            decisions = os.path.join(wd, "validated.json")
            cid = "acme/catalogue:components/agents/ops/devops-engineer.md"
            build(manifest, root, out)
            fingerprint = load_registry(out)[cid]["provenance"]["fingerprint_sha256"]
            with open(decisions, "w") as handle:
                json.dump({cid: {"validated": "conserver", "fingerprint_sha256": fingerprint}}, handle)
            change_source(root, manifest, "acme/catalogue",
                          {"components/agents/ops/devops-engineer.md": agent_text("devops-engineer", "nouvelle mission")})
            report = build(manifest, root, out, decisions_path=decisions)
            decision = load_registry(out)[cid]["decision"]
            self.assertIsNone(decision["validated"])
            self.assertEqual(decision["stale_validation"]["validated"], "conserver")
            self.assertEqual([d["component_id"] for d in report["stale_decisions"]], [cid])

    def test_validation_without_fingerprint_is_stale(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            decisions = os.path.join(wd, "validated.json")
            cid = "acme/catalogue:components/agents/ops/devops-engineer.md"
            with open(decisions, "w") as handle:
                json.dump({cid: {"validated": "conserver"}}, handle)
            report = build(manifest, root, os.path.join(wd, "catalog"), decisions_path=decisions)
            self.assertEqual(report["stale_decisions"][0]["reason"], "empreinte absente")

    def test_unknown_decision_value_is_refused(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            decisions = os.path.join(wd, "validated.json")
            with open(decisions, "w") as handle:
                json.dump({"acme/catalogue:x.md": {"validated": "adopter"}}, handle)
            with self.assertRaises(BuildError):
                build(manifest, root, os.path.join(wd, "catalog"), decisions_path=decisions)

    def test_composed_components_fingerprint_covers_all_behavior_files(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            hook_id = "acme/catalogue:components/hooks/git/guard.json"
            mod_id = "acme/catalogue:components/mods/security/jail/README.md"
            build(manifest, root, out)
            before = load_registry(out)
            self.assertIn("components/hooks/git/guard.py", before[hook_id]["provenance"]["fingerprint_files"])
            self.assertIn("components/mods/security/jail/hooks/block.ts", before[mod_id]["provenance"]["fingerprint_files"])
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.py": "# Autre comportement du script compagnon, README inchangé ici\n",
                "components/mods/security/jail/hooks/block.ts": "export const x = 2\n"})
            build(manifest, root, out)
            after = load_registry(out)
            for cid in (hook_id, mod_id):
                self.assertEqual(before[cid]["provenance"]["content_sha256"], after[cid]["provenance"]["content_sha256"])
                self.assertNotEqual(before[cid]["provenance"]["fingerprint_sha256"],
                                    after[cid]["provenance"]["fingerprint_sha256"])

    def test_invalid_metadata_is_quarantined(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            change_source(root, manifest, "acme/catalogue", {
                "components/agents/web/casse.md":
                    "---\nname: casse\ndescription: Use when: ceci casse\n---\n" + FRONT + "\n"})
            build(manifest, root, out)
            comp = load_registry(out)["acme/catalogue:components/agents/web/casse.md"]
            self.assertEqual(comp["evaluation"]["status"], policy.STATUS_INVALID)
            self.assertIsNone(comp["evaluation"]["best_match_id"])
            self.assertEqual(comp["evaluation"]["similar_in_catalog"], [])
            self.assertIn("revue requise", comp["decision"]["proposal"])

    def test_cross_layer_overlap_is_flagged(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            comp = load_registry(out)["acme/catalogue:components/agents/sec/security-auditor.md"]
            self.assertEqual(comp["evaluation"]["status"], policy.STATUS_CROSS_LAYER)
            self.assertEqual(comp["evaluation"]["cross_layer"][0]["component_id"],
                             "acme/socle:skills/security-scan/SKILL.md")

    def test_dirty_build_is_experimental(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            with open(os.path.join(root, "acme", "socle", "agents", "backend-developer.md"), "a") as handle:
                handle.write("modif locale\n")
            out = os.path.join(wd, "catalog")
            report = build(manifest, root, out, allow_dirty=True)
            self.assertEqual(report["build_mode"], "experimental_dirty")
            self.assertEqual(report["dirty_sources"], ["acme/socle"])
            self.assertEqual(validate_catalog(out)["build_mode"], "experimental_dirty")

    def test_clean_build_is_exact(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            self.assertEqual(build(manifest, root, os.path.join(wd, "catalog"), allow_dirty=True)["build_mode"], "exact")

    def test_concurrent_generation_is_refused(self):
        import fcntl
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            with open(out + ".lock", "a+") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BuildError) as ctx:
                    build(manifest, root, out)
            self.assertIn("déjà en cours", str(ctx.exception))
            build(manifest, root, out)  # le verrou est libéré

    def test_swap_never_leaves_the_catalog_missing(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            before = read(os.path.join(out, "registry.json"))
            real_rename = os.rename
            calls = []

            def flaky(src, dst):
                calls.append((src, dst))
                if dst == out and src.startswith(out + ".tmp-"):
                    raise OSError("panne simulée pendant le second renommage")
                return real_rename(src, dst)

            with mock.patch.object(build_mod, "_exchange", return_value=False), \
                    mock.patch.object(build_mod.os, "rename", side_effect=flaky):
                with self.assertRaises(OSError):
                    build(manifest, root, out)
            self.assertEqual(read(os.path.join(out, "registry.json")), before)
            self.assertEqual(leftovers(out), [])

    def test_atomic_exchange_replaces_the_catalog_in_one_step(self):
        with Workdir() as wd:
            a, b = os.path.join(wd, "a"), os.path.join(wd, "b")
            os.mkdir(a)
            os.mkdir(b)
            with open(os.path.join(a, "v"), "w") as handle:
                handle.write("ancien")
            with open(os.path.join(b, "v"), "w") as handle:
                handle.write("nouveau")
            if not build_mod._exchange(b, a):
                self.skipTest("échange atomique indisponible sur ce système")
            self.assertEqual(read(os.path.join(a, "v")), b"nouveau")
            self.assertEqual(read(os.path.join(b, "v")), b"ancien")

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

    def _tampered(self, edit_registry=None, edit_csv=None, edit_report=None, resync=True):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            for name, edit, is_json in (("registry.json", edit_registry, True), ("build_report.json", edit_report, True),
                                        ("crosswalk.csv", edit_csv, False)):
                if not edit:
                    continue
                path = os.path.join(out, name)
                if is_json:
                    data = json.loads(read(path))
                    edit(data)
                    with open(path, "w") as handle:
                        json.dump(data, handle)
                    if name == "registry.json" and resync:
                        rep_path = os.path.join(out, "build_report.json")
                        rep = json.loads(read(rep_path))
                        rep["registry_sha256"] = hashlib.sha256(read(path)).hexdigest()
                        with open(rep_path, "w") as handle:
                            json.dump(rep, handle)
                else:
                    text = read(path).decode("utf-8")
                    with open(path, "w", encoding="utf-8", newline="") as handle:
                        handle.write(edit(text))
            return validate_catalog(out)

    def test_csv_edit_with_same_row_count_is_detected(self):
        with self.assertRaises(ValidationError) as ctx:
            self._tampered(edit_csv=lambda t: t.replace("novelty_to_review", "equivalence_candidate", 1)
                           if "novelty_to_review" in t else t.replace("cross_layer_overlap", "equivalence_candidate", 1))
        self.assertIn("crosswalk.csv", str(ctx.exception))

    def test_dangling_reference_is_detected(self):
        def edit(data):
            for comp in data["components"]:
                if comp["evaluation"] and comp["evaluation"]["best_match_id"]:
                    comp["evaluation"]["best_match_id"] = "acme/socle:inexistant.md"
                    return
        with self.assertRaises(ValidationError):
            self._tampered(edit_registry=edit)

    def test_bad_hash_and_report_count_are_detected(self):
        def edit_registry(data):
            data["components"][0]["provenance"]["content_sha256"] = "xyz"
        with self.assertRaises(ValidationError):
            self._tampered(edit_registry=edit_registry)

        def edit_report(data):
            data["counts_by_type"]["agent"] += 1
        with self.assertRaises(ValidationError):
            self._tampered(edit_report=edit_report)

    def test_validated_decision_bound_to_another_content_is_detected(self):
        def edit(data):
            for comp in data["components"]:
                if comp["decision"]:
                    comp["decision"]["validated"] = "conserver"
                    comp["decision"]["validated_fingerprint_sha256"] = "0" * 64
                    return
        with self.assertRaises(ValidationError):
            self._tampered(edit_registry=edit)

    def test_report_from_another_generation_is_detected(self):
        def edit(data):
            data["components"][0]["name"] = "autre"
        with self.assertRaises(ValidationError) as ctx:
            self._tampered(edit_registry=edit, resync=False)
        self.assertIn("ne correspond pas", str(ctx.exception))

    def test_reader_keeps_a_consistent_generation_during_an_update(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            old_sha = json.loads(read(os.path.join(out, "build_report.json")))["registry_sha256"]
            dir_fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)  # lecteur qui a ouvert la génération courante
            try:
                change_source(root, manifest, "acme/catalogue",
                              {"components/agents/ops/devops-engineer.md": agent_text("devops-engineer", "autre mission")})
                build(manifest, root, out)  # publie une nouvelle génération pendant la lecture
                with os.fdopen(os.open("registry.json", os.O_RDONLY, dir_fd=dir_fd), "rb") as handle:
                    registry = handle.read()
                with os.fdopen(os.open("build_report.json", os.O_RDONLY, dir_fd=dir_fd), "rb") as handle:
                    report = json.loads(handle.read())
            finally:
                os.close(dir_fd)
            self.assertEqual(hashlib.sha256(registry).hexdigest(), report["registry_sha256"])
            self.assertEqual(report["registry_sha256"], old_sha)
            self.assertNotEqual(json.loads(read(os.path.join(out, "build_report.json")))["registry_sha256"], old_sha)

    def test_previous_generation_is_kept_once(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            build(manifest, root, out)
            build(manifest, root, out)
            self.assertTrue(os.path.isdir(out + ".prev"))
            self.assertEqual(leftovers(out), [])

    def test_missing_fcntl_refuses_to_build(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            with mock.patch.object(build_mod, "fcntl", None):
                with self.assertRaises(BuildError) as ctx:
                    build(manifest, root, os.path.join(wd, "catalog"))
            self.assertIn("plateforme non prise en charge", str(ctx.exception))

    def _fingerprints(self, wd, root, manifest):
        out = os.path.join(wd, "catalog")
        build(manifest, root, out)
        return {cid: c["provenance"]["fingerprint_sha256"] for cid, c in load_registry(out).items()}

    def test_fingerprint_follows_local_imports_of_hook_scripts(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.py": "from helpers.rules import check\nimport shared\nprint(check)\n",
                "components/hooks/git/helpers/rules.py": "def check():\n    return 1\n",
                "components/hooks/git/shared.py": "VALUE = 1\n"})
            hook = "acme/catalogue:components/hooks/git/guard.json"
            before = self._fingerprints(wd, root, manifest)
            files = load_registry(os.path.join(wd, "catalog"))[hook]["provenance"]["fingerprint_files"]
            self.assertIn("components/hooks/git/helpers/rules.py", files)
            self.assertIn("components/hooks/git/shared.py", files)
            change_source(root, manifest, "acme/catalogue", {"components/hooks/git/helpers/rules.py": "def check():\n    return 2\n"})
            after = self._fingerprints(wd, root, manifest)
            self.assertNotEqual(before[hook], after[hook])

    def test_fingerprint_follows_js_requires_and_transitive_imports(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.py": "import subprocess\n",
                "components/hooks/git/lint.js": "const a = require('./lib/a')\n",
                "components/hooks/git/lib/a.js": "const b = require('./b.js')\n",
                "components/hooks/git/lib/b.js": "module.exports = 1\n"})
            hook = "acme/catalogue:components/hooks/git/lint.js"
            before = self._fingerprints(wd, root, manifest)
            change_source(root, manifest, "acme/catalogue", {"components/hooks/git/lib/b.js": "module.exports = 2\n"})
            after = self._fingerprints(wd, root, manifest)
            self.assertNotEqual(before[hook], after[hook])

    def test_hook_config_referencing_a_script_in_another_folder(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.json": json.dumps({"hooks": {"PreToolUse": [{"command": "python3 scripts/check_push.py"}]}}),
                "components/hooks/git/scripts/check_push.py": "print(1)\n"})
            hook = "acme/catalogue:components/hooks/git/guard.json"
            before = self._fingerprints(wd, root, manifest)
            change_source(root, manifest, "acme/catalogue", {"components/hooks/git/scripts/check_push.py": "print(2)\n"})
            self.assertNotEqual(before[hook], self._fingerprints(wd, root, manifest)[hook])

    def test_skill_fingerprint_covers_its_scripts_and_resources(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            change_source(root, manifest, "acme/catalogue", {
                "components/skills/dev/scripts/run.py": "import util\n",
                "components/skills/dev/scripts/util.py": "X = 1\n"})
            skill = "acme/catalogue:components/skills/dev/SKILL.md"
            before = self._fingerprints(wd, root, manifest)
            change_source(root, manifest, "acme/catalogue", {"components/skills/dev/scripts/util.py": "X = 2\n"})
            self.assertNotEqual(before[skill], self._fingerprints(wd, root, manifest)[skill])

    def test_large_skill_still_follows_imports_outside_its_folder(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            files = {"components/skills/dev/data/f%03d.txt" % i: "x\n" for i in range(303)}
            files["components/skills/dev/scripts/run.py"] = "import extlib\n"
            files["components/skills/extlib.py"] = "VALUE = 1\n"
            change_source(root, manifest, "acme/catalogue", files)
            skill = "acme/catalogue:components/skills/dev/SKILL.md"
            before = self._fingerprints(wd, root, manifest)
            prov = load_registry(os.path.join(wd, "catalog"))[skill]["provenance"]
            self.assertIn("components/skills/extlib.py", prov["fingerprint_files"])
            self.assertTrue(prov["fingerprint_complete"])
            change_source(root, manifest, "acme/catalogue", {"components/skills/extlib.py": "VALUE = 2\n"})
            self.assertNotEqual(before[skill], self._fingerprints(wd, root, manifest)[skill])

    def test_import_cycles_do_not_loop(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.py": "import cycle_a\n",
                "components/hooks/git/cycle_a.py": "import cycle_b\n",
                "components/hooks/git/cycle_b.py": "import cycle_a\n"})
            self._fingerprints(wd, root, manifest)
            prov = load_registry(os.path.join(wd, "catalog"))["acme/catalogue:components/hooks/git/guard.json"]["provenance"]
            self.assertIn("components/hooks/git/cycle_b.py", prov["fingerprint_files"])
            self.assertTrue(prov["fingerprint_complete"])

    def test_incomplete_fingerprint_is_declared_and_blocks_validation(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            decisions = os.path.join(wd, "validated.json")
            hook = "acme/catalogue:components/hooks/git/guard.json"
            change_source(root, manifest, "acme/catalogue", {
                "components/hooks/git/guard.py": "import step1\n",
                "components/hooks/git/step1.py": "import step2\n",
                "components/hooks/git/step2.py": "import step3\n",
                "components/hooks/git/step3.py": "X = 1\n"})
            build(manifest, root, out)
            fingerprint = load_registry(out)[hook]["provenance"]["fingerprint_sha256"]
            with open(decisions, "w") as handle:
                json.dump({hook: {"validated": "conserver", "fingerprint_sha256": fingerprint}}, handle)
            with mock.patch.object(scan_mod, "MAX_EXPLORED_FILES", 3):
                report = build(manifest, root, out, decisions_path=decisions)
            comp = load_registry(out)[hook]
            self.assertFalse(comp["provenance"]["fingerprint_complete"])
            self.assertTrue(comp["provenance"]["fingerprint_unexplored"])
            self.assertIn(hook, report["incomplete_fingerprints"])
            self.assertIsNone(comp["decision"]["validated"])
            self.assertIn("incomplète", comp["decision"]["stale_validation"]["reason"])

    def test_verify_rejects_validation_on_incomplete_fingerprint(self):
        def edit(data):
            for comp in data["components"]:
                if comp["decision"]:
                    comp["provenance"]["fingerprint_complete"] = False
                    comp["provenance"]["fingerprint_unexplored"] = ["x.py"]
                    comp["decision"]["validated"] = "conserver"
                    comp["decision"]["validated_fingerprint_sha256"] = comp["provenance"]["fingerprint_sha256"]
                    return
        with self.assertRaises(ValidationError) as ctx:
            self._tampered(edit_registry=edit)
        self.assertIn("incomplète", str(ctx.exception))

    def test_invalid_socle_component_is_never_a_reference(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            out = os.path.join(wd, "catalog")
            devops_text = "automates kubernetes deployments terraform pipelines container registries and monitoring dashboards"
            change_source(root, manifest, "acme/socle", {
                "agents/devops-broken.md": "---\nname: devops-engineer\ndescription: Use when: casse\n---\n" + devops_text + "\n"})
            report = build(manifest, root, out)
            comps = load_registry(out)
            ev = comps["acme/catalogue:components/agents/ops/devops-engineer.md"]["evaluation"]
            self.assertNotEqual(ev["best_match_id"], "acme/socle:agents/devops-broken.md")
            self.assertEqual(ev["homonym_of"], [])
            self.assertNotEqual(ev["status"], policy.STATUS_EQUIVALENCE)
            self.assertTrue(any(i["path"] == "agents/devops-broken.md" for i in report["metadata_issues"]))

    def test_invalid_reference_is_rejected_by_verify(self):
        def edit(data):
            by_id = {c["component_id"]: c for c in data["components"]}
            by_id["acme/socle:agents/frontend-developer.md"]["metadata_issue"] = "yaml_invalide: simulé"
        with self.assertRaises(ValidationError):
            self._tampered(edit_registry=edit)

    def test_verified_license_requires_spdx_verifier_and_matching_commit(self):
        def edit(data):
            data["components"][0]["license"].update({"verified": True, "spdx": None})
        with self.assertRaises(ValidationError):
            self._tampered(edit_registry=edit)

    def test_license_and_annotation_files_are_applied_and_checked(self):
        with Workdir() as wd:
            root, manifest, commits = make_world(wd)
            out = os.path.join(wd, "catalog")
            lic, ann = os.path.join(wd, "lic.json"), os.path.join(wd, "ann.json")
            a, b = "acme/catalogue:components/agents/web/frontend-dev.md", "acme/catalogue:components/agents/ops/devops-engineer.md"
            with open(lic, "w") as handle:
                json.dump({"acme/catalogue": {"spdx": "MIT", "verified_by": "Zaki", "commit": commits["catalogue"]},
                           b: {"spdx": "Apache-2.0", "verified_by": "Zaki", "commit": commits["catalogue"]},
                           "acme/inconnu": {"spdx": "MIT", "verified_by": "Zaki", "commit": "a" * 40}}, handle)
            with open(ann, "w") as handle:
                json.dump({a: {"conflicts_with": [b], "platform": "linux"}, "acme/x.md": {"depends_on": []}}, handle)
            report = build(manifest, root, out, licenses_path=lic, annotations_path=ann)
            comps = load_registry(out)
            self.assertEqual(comps[a]["license"]["spdx"], "MIT")
            self.assertEqual(comps[b]["license"]["spdx"], "Apache-2.0")  # le composant l'emporte sur le dépôt
            self.assertEqual(comps[a]["relations"]["conflicts_with"], [b])
            self.assertEqual(comps[a]["compatibility"]["platform"], "linux")
            self.assertEqual(report["orphan_licenses"], ["acme/inconnu"])
            self.assertEqual(report["orphan_annotations"], ["acme/x.md"])

    def test_annotation_to_unknown_component_fails_verification(self):
        with Workdir() as wd:
            root, manifest, _ = make_world(wd)
            ann = os.path.join(wd, "ann.json")
            with open(ann, "w") as handle:
                json.dump({"acme/catalogue:components/agents/web/frontend-dev.md": {"depends_on": ["acme/nulle-part:x.md"]}}, handle)
            with self.assertRaises(ValidationError):
                build(manifest, root, os.path.join(wd, "catalog"), annotations_path=ann)

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
