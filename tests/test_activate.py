"""Pilote d'activation. Tout est fictif : composants, validations et licences restent dans les données de test."""
import json
import os
import unittest
from unittest import mock

from zakios import activate
from zakios import scan as scan_mod
from zakios.activate import ActivationError, apply, plan, rollback
from zakios.build import build

from .helpers import Workdir, agent, git, make_repo

REPO = "pilot/catalogue"
P = "components/"


def cid(rel):
    return "%s:%s%s" % (REPO, P, rel)


SIMPLE = cid("agents/simple-agent.md")
CONFLICT = cid("agents/conflict-agent.md")
WINDOWS = cid("agents/windows-agent.md")
NEEDS = cid("agents/needs-agent.md")
UNVALIDATED = cid("agents/unvalidated-agent.md")
SKILL = cid("skills/demo/SKILL.md")
OUTSIDE = cid("skills/outside/SKILL.md")
HOOK = cid("hooks/harmless/harmless.json")

VALIDATED = [SIMPLE, CONFLICT, WINDOWS, NEEDS, SKILL, OUTSIDE, HOOK]


def read(path, mode="rb"):
    with open(path, mode) as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def tree(root):
    """Tous les fichiers sous root (chemin relatif -> contenu), pour comparer des états."""
    out = {}
    for base, _, files in os.walk(root):
        for name in files:
            full = os.path.join(base, name)
            out[os.path.relpath(full, root)] = read(full)
    return out


class Pilot:
    def __init__(self, wd, licenses=True, validated=None, max_explored=None):
        self.wd = wd
        self.root = os.path.join(wd, "sources")
        files = {
            P + "agents/simple-agent.md": agent("simple-agent", "writes small focused helper scripts for the user"),
            P + "agents/conflict-agent.md": agent("conflict-agent", "rewrites configuration files in bulk"),
            P + "agents/windows-agent.md": agent("windows-agent", "manages registry keys on windows machines"),
            P + "agents/needs-agent.md": agent("needs-agent", "extends another agent with extra tooling"),
            P + "agents/unvalidated-agent.md": agent("unvalidated-agent", "never reviewed by a human yet"),
            P + "skills/demo/SKILL.md": "---\nname: demo\ndescription: Demonstrates a skill with a script and a resource.\n---\nCorps\n",
            P + "skills/demo/scripts/run.py": "import helper\nprint(helper.VALUE)\n",
            P + "skills/demo/scripts/helper.py": "VALUE = 1\n",
            P + "skills/demo/resources/data.txt": "ressource\n",
            P + "skills/outside/SKILL.md": "---\nname: outside\ndescription: Depends on a module outside its folder.\n---\nCorps\n",
            P + "skills/outside/scripts/use.py": "import extlib\n",
            P + "skills/extlib.py": "VALUE = 1\n",
            P + "hooks/harmless/harmless.json": json.dumps({"description": "prints a harmless reminder message"}),
            P + "hooks/harmless/harmless.py": "# Affiche un rappel inoffensif pour le pilote\nprint('rappel')\n",
        }
        self.commit = make_repo(self.root, REPO, files)
        path = os.path.join(self.root, REPO)
        for rel in (P + "skills/demo/scripts/run.py", P + "hooks/harmless/harmless.py"):
            os.chmod(os.path.join(path, rel), 0o755)
        git(path, "commit", "-qa", "--amend", "--no-edit")
        self.commit = git(path, "rev-parse", "HEAD")
        make_repo(self.root, "pilot/socle", {"agents/other.md": agent("other", "an unrelated reference agent")})
        socle_commit = git(os.path.join(self.root, "pilot/socle"), "rev-parse", "HEAD")
        self.manifest = os.path.join(wd, "sources.json")
        with open(self.manifest, "w") as handle:
            json.dump({"sources": [
                {"repo": REPO, "role": "catalogue", "commit": self.commit, "subdir": "components"},
                {"repo": "pilot/socle", "role": "socle", "commit": socle_commit}]}, handle)
        self.out = os.path.join(wd, "catalog")
        self.decisions = os.path.join(wd, "validated.json")
        self.licenses = os.path.join(wd, "licenses.json")
        self.annotations = os.path.join(wd, "annotations.json")
        self.project = os.path.join(wd, "project")
        os.makedirs(self.project)

        ctx = mock.patch.object(scan_mod, "MAX_EXPLORED_FILES", max_explored) if max_explored else mock.MagicMock()
        with ctx:
            build(self.manifest, self.root, self.out)
            registry = json.loads(read(os.path.join(self.out, "registry.json")))
            fingerprints = {c["component_id"]: c["provenance"]["fingerprint_sha256"] for c in registry["components"]}
            with open(self.decisions, "w") as handle:
                json.dump({c: {"validated": "conserver", "validated_by": "test", "validated_on": "2026-10-26",
                               "justification": "composant fictif", "fingerprint_sha256": fingerprints[c]}
                           for c in (VALIDATED if validated is None else validated)}, handle)
            if licenses:
                with open(self.licenses, "w") as handle:
                    json.dump({REPO: {"spdx": "MIT", "verified_by": "test", "verified_on": "2026-10-26",
                                      "commit": self.commit, "attribution": "Pilot Authors"}}, handle)
            with open(self.annotations, "w") as handle:
                json.dump({WINDOWS: {"platform": "windows"}, CONFLICT: {"conflicts_with": [SIMPLE]},
                           NEEDS: {"depends_on": [UNVALIDATED]}}, handle)
            build(self.manifest, self.root, self.out, decisions_path=self.decisions,
                  licenses_path=self.licenses, annotations_path=self.annotations)

    def plan(self, selection):
        return plan(self.project, self.out, self.root, selection)

    def apply(self, selection, **kw):
        return apply(self.project, self.out, self.root, selection, **kw)


class PilotTests(unittest.TestCase):
    def test_preview_writes_nothing_and_matches_what_is_installed(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            before = tree(wd)
            result = pilot.plan([SIMPLE, SKILL, HOOK])
            self.assertEqual(tree(wd), before)  # aperçu : aucune écriture
            self.assertEqual(result["refused"], [])
            previewed = sorted(a["path"] for a in result["actions"] if a["action"] == "create")
            self.assertEqual(previewed, [
                ".claude/agents/simple-agent.md",
                ".claude/hooks/zakios/harmless/harmless.json", ".claude/hooks/zakios/harmless/harmless.py",
                ".claude/skills/demo/SKILL.md", ".claude/skills/demo/resources/data.txt",
                ".claude/skills/demo/scripts/helper.py", ".claude/skills/demo/scripts/run.py"])
            out = pilot.apply([SIMPLE, SKILL, HOOK], expected_plan=result["plan_sha256"])
            self.assertEqual(out["applied"], 7)
            installed = sorted(p for p in tree(pilot.project) if p.startswith(".claude"))
            self.assertEqual(installed, previewed)

    def test_installed_content_is_exact_and_scripts_stay_executable(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SKILL, HOOK])
            self.assertEqual(read(os.path.join(pilot.project, ".claude/skills/demo/scripts/helper.py")), b"VALUE = 1\n")
            self.assertTrue(os.access(os.path.join(pilot.project, ".claude/skills/demo/scripts/run.py"), os.X_OK))
            self.assertFalse(os.access(os.path.join(pilot.project, ".claude/skills/demo/scripts/helper.py"), os.X_OK))
            self.assertTrue(os.access(os.path.join(pilot.project, ".claude/hooks/zakios/harmless/harmless.py"), os.X_OK))

    def test_hooks_are_never_activated(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            result = pilot.plan([HOOK])
            self.assertTrue(any("pas activés" in n for n in result["notes"]))
            pilot.apply([HOOK])
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/settings.json")))

    def test_unvalidated_component_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            result = pilot.plan([UNVALIDATED])
            self.assertIn("non validée", result["refused"][0]["reasons"][0])
            with self.assertRaises(ActivationError):
                pilot.apply([UNVALIDATED])
            self.assertEqual(tree(pilot.project), {})

    def test_unverified_license_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd, licenses=False)
            reasons = pilot.plan([SIMPLE])["refused"][0]["reasons"]
            self.assertIn("licence non vérifiée", reasons)
            with self.assertRaises(ActivationError):
                pilot.apply([SIMPLE])

    def test_license_bound_to_another_commit_is_not_applied(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            with open(pilot.licenses, "w") as handle:
                json.dump({REPO: {"spdx": "MIT", "verified_by": "test", "commit": "f" * 40}}, handle)
            report = build(pilot.manifest, pilot.root, pilot.out, decisions_path=pilot.decisions,
                           licenses_path=pilot.licenses, annotations_path=pilot.annotations)
            self.assertEqual(report["stale_licenses"], [REPO])
            self.assertIn("licence non vérifiée", pilot.plan([SIMPLE])["refused"][0]["reasons"])

    def test_incomplete_fingerprint_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd, max_explored=2)
            reasons = pilot.plan([SKILL])["refused"][0]["reasons"]
            self.assertTrue(any("empreinte incomplète" in r for r in reasons))

    def test_incompatible_components_are_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            by = {r["component_id"]: r["reasons"] for r in pilot.plan([WINDOWS, CONFLICT, SIMPLE, NEEDS])["refused"]}
            self.assertTrue(any("incompatible avec Linux" in r for r in by[WINDOWS]))
            self.assertTrue(any("en conflit" in r for r in by[CONFLICT]))
            self.assertTrue(any("dépendance" in r for r in by[NEEDS]))
            self.assertNotIn(SIMPLE, by)

    def test_package_with_dependency_outside_its_folder_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            reasons = pilot.plan([OUTSIDE])["refused"][0]["reasons"]
            self.assertTrue(any("hors du paquet" in r for r in reasons))

    def test_unknown_component_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            self.assertIn("absent du catalogue", pilot.plan(["pilot/catalogue:inconnu.md"])["refused"][0]["reasons"][0])

    def test_second_installation_changes_nothing(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE, SKILL])
            before = tree(pilot.project)
            stamps = {p: os.stat(os.path.join(pilot.project, p)).st_mtime_ns for p in before}
            journals = sorted(os.listdir(os.path.join(pilot.project, ".zakios/journal")))
            second = pilot.apply([SIMPLE, SKILL])
            self.assertEqual((second["transaction"], second["applied"]), (None, 0))
            self.assertEqual(tree(pilot.project), before)
            self.assertEqual({p: os.stat(os.path.join(pilot.project, p)).st_mtime_ns for p in before}, stamps)
            self.assertEqual(sorted(os.listdir(os.path.join(pilot.project, ".zakios/journal"))), journals)
            self.assertTrue(all(a["action"] == "unchanged" for a in pilot.plan([SIMPLE, SKILL])["actions"]))

    def test_existing_user_file_is_never_overwritten(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            mine = os.path.join(pilot.project, ".claude/agents/simple-agent.md")
            write(mine, "mon propre agent\n")
            write(os.path.join(pilot.project, "CLAUDE.md"), "règles du projet\n")
            reasons = pilot.plan([SIMPLE])["refused"][0]["reasons"]
            self.assertIn("non géré par ZakiOS", reasons[0])
            with self.assertRaises(ActivationError):
                pilot.apply([SIMPLE, SKILL])
            self.assertEqual(read(mine, "r"), "mon propre agent\n")
            self.assertEqual(read(os.path.join(pilot.project, "CLAUDE.md"), "r"), "règles du projet\n")
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/skills")))  # tout ou rien

    def test_symlink_escaping_the_project_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            outside = os.path.join(wd, "ailleurs")
            os.makedirs(outside)
            os.makedirs(os.path.join(pilot.project, ".claude"))
            os.symlink(outside, os.path.join(pilot.project, ".claude/agents"))
            reasons = pilot.plan([SIMPLE])["refused"][0]["reasons"]
            self.assertTrue(any("non sûr" in r or "existe déjà" in r for r in reasons))
            self.assertEqual(os.listdir(outside), [])

    def test_user_edit_of_an_installed_file_blocks_update_and_removal(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            path = os.path.join(pilot.project, ".claude/agents/simple-agent.md")
            with open(path, "a") as handle:
                handle.write("ma retouche\n")
            reasons = pilot.plan([])["refused"][0]["reasons"]  # retrait demandé
            self.assertIn("modifié localement", reasons[0])
            with self.assertRaises(ActivationError):
                pilot.apply([])
            self.assertIn("ma retouche", read(path, "r"))

    def test_removing_from_the_profile_removes_unmodified_files(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE, SKILL])
            pilot.apply([SKILL])
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/agents/simple-agent.md")))
            self.assertTrue(os.path.exists(os.path.join(pilot.project, ".claude/skills/demo/SKILL.md")))

    def test_simulated_failure_rolls_everything_back_without_touching_user_files(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            write(os.path.join(pilot.project, ".claude/agents/my-own.md"), "à moi\n")
            write(os.path.join(pilot.project, "notes.txt"), "notes\n")
            before = tree(pilot.project)

            def boom(index):
                if index == 3:
                    raise RuntimeError("panne simulée")

            with self.assertRaises(ActivationError) as ctx:
                pilot.apply([SIMPLE, SKILL, HOOK], fault=boom)
            self.assertIn("retour arrière effectué", str(ctx.exception))
            after = {p: c for p, c in tree(pilot.project).items() if not p.startswith(".zakios/journal")}
            after.pop(".zakios/project.lock", None)
            after.pop(".zakios/lock.json", None)
            expected = {p: c for p, c in before.items()}
            self.assertEqual(after, expected)
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/skills")))
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/hooks")))
            lock = json.loads(read(os.path.join(pilot.project, ".zakios/lock.json")))
            self.assertEqual(lock["components"], {})

    def test_failure_during_an_update_restores_previous_versions(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SKILL])
            skill_files = {p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}
            lock_before = read(os.path.join(pilot.project, ".zakios/lock.json"))
            # le catalogue change : nouvelle version du helper, validation refaite
            write(os.path.join(pilot.root, REPO, P + "skills/demo/scripts/helper.py"), "VALUE = 2\n")
            git(os.path.join(pilot.root, REPO), "commit", "-qam", "v2")
            new_commit = git(os.path.join(pilot.root, REPO), "rev-parse", "HEAD")
            manifest = json.loads(read(pilot.manifest))
            manifest["sources"][0]["commit"] = new_commit
            write(pilot.manifest, json.dumps(manifest))
            build(pilot.manifest, pilot.root, pilot.out)
            registry = json.loads(read(os.path.join(pilot.out, "registry.json")))
            fp = next(c["provenance"]["fingerprint_sha256"] for c in registry["components"] if c["component_id"] == SKILL)
            write(pilot.decisions, json.dumps({SKILL: {"validated": "conserver", "validated_by": "test", "fingerprint_sha256": fp}}))
            write(pilot.licenses, json.dumps({REPO: {"spdx": "MIT", "verified_by": "test", "commit": new_commit}}))
            build(pilot.manifest, pilot.root, pilot.out, decisions_path=pilot.decisions, licenses_path=pilot.licenses)
            self.assertEqual([a["action"] for a in pilot.plan([SKILL])["actions"]].count("update"), 1)

            def boom(index):
                raise RuntimeError("panne simulée")

            with self.assertRaises(ActivationError):
                pilot.apply([SKILL], fault=boom)
            self.assertEqual({p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}, skill_files)
            self.assertEqual(read(os.path.join(pilot.project, ".zakios/lock.json")), lock_before)

    def test_explicit_rollback_restores_the_previous_state(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            state_one = {p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}
            pilot.apply([SIMPLE, SKILL])
            out = rollback(pilot.project)
            self.assertTrue(out["transaction"])
            self.assertEqual({p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}, state_one)
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/skills")))
            rollback(pilot.project)
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/agents/simple-agent.md")))
            with self.assertRaises(ActivationError):
                rollback(pilot.project)

    def test_rollback_refuses_to_lose_user_edits(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            path = os.path.join(pilot.project, ".claude/agents/simple-agent.md")
            with open(path, "a") as handle:
                handle.write("travail de l'utilisateur\n")
            with self.assertRaises(ActivationError) as ctx:
                rollback(pilot.project)
            self.assertIn("modifié", ctx.exception.reasons[0])
            self.assertIn("travail de l'utilisateur", read(path, "r"))

    def test_interrupted_installation_is_undone_at_next_run(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            before = {p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}
            self._interrupt_install(pilot, [SIMPLE, SKILL])
            self.assertNotEqual({p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}, before)
            pilot.apply([SIMPLE])  # le prochain lancement reprend et annule
            self.assertEqual({p: c for p, c in tree(pilot.project).items() if p.startswith(".claude")}, before)

    def test_stale_preview_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            sha = pilot.plan([SIMPLE])["plan_sha256"]
            with self.assertRaises(ActivationError) as ctx:
                pilot.apply([SIMPLE, SKILL], expected_plan=sha)
            self.assertIn("plan a changé", str(ctx.exception))
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude")))

    def test_experimental_catalog_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            with open(os.path.join(pilot.root, REPO, "scratch.txt"), "w") as handle:
                handle.write("modif locale\n")
            build(pilot.manifest, pilot.root, pilot.out, allow_dirty=True, decisions_path=pilot.decisions,
                  licenses_path=pilot.licenses)
            with self.assertRaises(ActivationError) as ctx:
                pilot.plan([SIMPLE])
            self.assertIn("expérimental", str(ctx.exception))

    def test_tampered_catalog_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            path = os.path.join(pilot.out, "registry.json")
            data = json.loads(read(path))
            data["components"][0]["name"] = "falsifié"
            write(path, json.dumps(data))
            with self.assertRaises(ActivationError):
                pilot.plan([SIMPLE])

    def test_missing_source_is_refused(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            import shutil
            shutil.rmtree(os.path.join(pilot.root, REPO))
            self.assertIn("absente", pilot.plan([SIMPLE])["refused"][0]["reasons"][0])

    def test_content_comes_from_the_catalog_commit_not_the_working_tree(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            expected = read(os.path.join(pilot.root, REPO, P + "agents/simple-agent.md"))
            write(os.path.join(pilot.root, REPO, P + "agents/simple-agent.md"), "contenu modifié localement\n")
            pilot.apply([SIMPLE])
            self.assertEqual(read(os.path.join(pilot.project, ".claude/agents/simple-agent.md")), expected)

    def test_cli_plan_apply_rollback(self):
        import contextlib
        import io
        from zakios.__main__ import main
        with Workdir() as wd:
            pilot = Pilot(wd)
            profile = os.path.join(pilot.project, ".zakios", "profile.json")
            write(profile, json.dumps({"components": [SIMPLE, SKILL]}))
            common = ["--project", pilot.project, "--catalog", pilot.out, "--sources-root", pilot.root]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(main(["plan"] + common), 0)
            sha = buf.getvalue().strip().splitlines()[-1].split(" : ")[1]
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude")))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["apply", "--plan-sha", sha] + common), 0)
                self.assertTrue(os.path.exists(os.path.join(pilot.project, ".claude/agents/simple-agent.md")))
                self.assertEqual(main(["rollback", "--project", pilot.project]), 0)
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/agents/simple-agent.md")))
            write(profile, json.dumps({"components": [UNVALIDATED]}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan"] + common), 1)

    def test_real_style_catalog_without_human_validation_installs_nothing(self):
        with Workdir() as wd:
            pilot = Pilot(wd, validated=[])
            for component in (SIMPLE, SKILL, HOOK):
                self.assertTrue(pilot.plan([component])["refused"])

    # ---- audit d9ca9c0 : trois scénarios reproduits, puis récupération après interruption

    def test_rollback_never_overwrites_a_file_recreated_by_the_user(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            pilot.apply([])  # ZakiOS retire le fichier
            path = os.path.join(pilot.project, ".claude/agents/simple-agent.md")
            self.assertFalse(os.path.exists(path))
            write(path, "recréé par l'utilisateur\n")
            with self.assertRaises(ActivationError) as ctx:
                rollback(pilot.project)
            self.assertIn("recréé", ctx.exception.reasons[0])
            self.assertEqual(read(path, "r"), "recréé par l'utilisateur\n")
            journals = os.listdir(os.path.join(pilot.project, ".zakios/journal"))
            statuses = [json.loads(read(os.path.join(pilot.project, ".zakios/journal", j, "meta.json")))["status"] for j in journals]
            self.assertIn("conflict", statuses)  # sauvegardes conservées pour revue

    def test_parent_replaced_by_symlink_never_deletes_outside_files(self):
        import shutil
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE, SKILL])
            claude = os.path.join(pilot.project, ".claude")
            outside = os.path.join(wd, "ailleurs")
            # copies exactes des fichiers installés : même contenu, donc indiscernables par leur seul hash
            shutil.copytree(os.path.join(claude, "agents"), os.path.join(outside, "agents"))
            shutil.copytree(os.path.join(claude, "skills"), os.path.join(outside, "skills"))
            for name in ("agents", "skills"):
                shutil.rmtree(os.path.join(claude, name))
                os.symlink(os.path.join(outside, name), os.path.join(claude, name))
            before = tree(outside)
            with self.assertRaises(ActivationError):
                pilot.apply([])
            self.assertEqual(tree(outside), before)
            with self.assertRaises(ActivationError):
                rollback(pilot.project)
            self.assertEqual(tree(outside), before)

    def test_state_directory_outside_the_project_is_refused_and_nothing_is_written_there(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            outside = os.path.join(wd, "ailleurs")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(pilot.project, ".zakios"))
            with self.assertRaises(ActivationError):
                pilot.apply([UNVALIDATED])  # refusé
            with self.assertRaises(ActivationError):
                pilot.apply([SIMPLE])  # acceptable en soi, mais l'état est hors du projet
            with self.assertRaises(ActivationError):
                pilot.plan([SIMPLE])
            with self.assertRaises(ActivationError):
                rollback(pilot.project)
            self.assertEqual(os.listdir(outside), [])
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude")))

    def test_refused_apply_creates_no_state_directory_or_lock(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            with self.assertRaises(ActivationError):
                pilot.apply([UNVALIDATED])
            self.assertEqual(os.listdir(pilot.project), [])

    def test_destination_parent_symlink_blocks_creation(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            outside = os.path.join(wd, "ailleurs")
            os.makedirs(outside)
            os.makedirs(os.path.join(pilot.project, ".claude"))
            os.symlink(outside, os.path.join(pilot.project, ".claude/skills"))
            with self.assertRaises(ActivationError):
                pilot.apply([SKILL])
            self.assertEqual(os.listdir(outside), [])

    def _interrupt_install(self, pilot, selection):
        real = activate.Root.write_atomic

        def killed(self, rel, data, executable=False, **kw):
            real(self, rel, data, executable, **kw)
            if rel.endswith("scripts/helper.py"):
                raise KeyboardInterrupt  # interruption brutale après des écritures

        with mock.patch.object(activate.Root, "write_atomic", killed), \
                mock.patch.object(activate, "_undo", lambda *a, **k: None):
            with self.assertRaises(ActivationError):
                pilot.apply(selection)

    def test_recovery_after_interruption_keeps_user_edits_made_in_between(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            pilot.apply([SIMPLE])
            self._interrupt_install(pilot, [SIMPLE, SKILL])
            edited = os.path.join(pilot.project, ".claude/skills/demo/SKILL.md")
            self.assertTrue(os.path.exists(edited))
            with open(edited, "a") as handle:
                handle.write("modification de l'utilisateur après l'interruption\n")
            with self.assertRaises(ActivationError) as ctx:
                pilot.apply([SIMPLE])
            self.assertIn("modifié", ctx.exception.reasons[0])
            self.assertIn("après l'interruption", read(edited, "r"))
            base = os.path.join(pilot.project, ".zakios/journal")
            statuses = [json.loads(read(os.path.join(base, j, "meta.json")))["status"] for j in os.listdir(base)]
            self.assertIn("conflict", statuses)
            notes = pilot.plan([SIMPLE])["notes"]
            self.assertTrue(any("conflit" in n for n in notes))

    def test_file_created_by_the_user_after_the_preview_is_never_overwritten(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            mine = os.path.join(pilot.project, ".claude/agents/simple-agent.md")
            real_plan = activate._plan
            state = {"n": 0}

            def racing_plan(*args, **kwargs):
                result = real_plan(*args, **kwargs)
                state["n"] += 1
                if state["n"] == 2:  # le plan sous verrou vient d'être calculé : l'utilisateur écrit maintenant
                    write(mine, "écrit en même temps par l'utilisateur\n")
                return result

            with mock.patch.object(activate, "_plan", racing_plan):
                with self.assertRaises(ActivationError) as ctx:
                    pilot.apply([SIMPLE, SKILL])
            self.assertIn("apparu depuis l'aperçu", str(ctx.exception))
            self.assertEqual(read(mine, "r"), "écrit en même temps par l'utilisateur\n")
            self.assertFalse(os.path.exists(os.path.join(pilot.project, ".claude/skills")))

    def test_unsafe_names_in_a_destination_are_never_followed(self):
        with Workdir() as wd:
            pilot = Pilot(wd)
            root = activate.Root(pilot.project)
            try:
                for bad in ("../x", "a/../../x", "/abs", "a//b", "./x", ""):
                    with self.assertRaises(ActivationError):
                        root.read(bad)
            finally:
                root.close()


if __name__ == "__main__":
    unittest.main()
