"""Socle commun et composants propres (rôle « propre »). Données fictives."""
import json
import os
import unittest

from zakios.activate import apply, plan, rollback
from zakios.build import build, read_generation

from .helpers import Workdir, agent, make_repo
from .test_activate import read, tree, write

REPO = "own/zakios"
SOCLE = REPO + ":socle/REGLES.md"
AGENT = REPO + ":variantes/agents/reviewer.md"


class SocleTests(unittest.TestCase):
    def world(self, wd):
        self.root = os.path.join(wd, "sources")
        commit = make_repo(self.root, REPO, {
            "socle/REGLES.md": "# Socle\nRègle commune.\n",
            "variantes/agents/reviewer.md": agent("reviewer", "reads a diff and reports findings"),
        })
        manifest = os.path.join(wd, "sources.json")
        json.dump({"sources": [{"repo": REPO, "role": "propre", "commit": commit}]}, open(manifest, "w"))
        self.out = os.path.join(wd, "catalog")
        build(manifest, self.root, self.out)
        reg = json.load(open(os.path.join(self.out, "registry.json")))
        fp = {c["component_id"]: c["provenance"]["fingerprint_sha256"] for c in reg["components"]}
        decisions, licenses = os.path.join(wd, "d.json"), os.path.join(wd, "l.json")
        json.dump({c: {"validated": "conserver", "validated_by": "test", "validated_on": "2026-10-26",
                       "justification": "fictif", "fingerprint_sha256": fp[c]} for c in (SOCLE, AGENT)},
                  open(decisions, "w"))
        json.dump({REPO: {"spdx": "MIT", "verified_by": "test", "verified_on": "2026-10-26",
                          "commit": commit, "attribution": "Own"}}, open(licenses, "w"))
        build(manifest, self.root, self.out, decisions_path=decisions, licenses_path=licenses)
        self.project = os.path.join(wd, "project")
        os.makedirs(self.project)
        return reg

    def test_propre_components_are_evaluated_and_socle_is_typed(self):
        with Workdir() as wd:
            reg = self.world(wd)
            by_id = {c["component_id"]: c for c in reg["components"]}
            self.assertEqual(by_id[SOCLE]["type"], "socle")
            self.assertEqual(by_id[SOCLE]["evaluation"]["status"], "behavior_audit_required")
            self.assertIsNotNone(by_id[AGENT]["evaluation"])

    def test_socle_installs_rules_and_import_then_rolls_back(self):
        with Workdir() as wd:
            self.world(wd)
            write(os.path.join(self.project, "CLAUDE.md"), "instructions de l utilisateur\n")
            before = tree(self.project)
            result = plan(self.project, self.out, self.root, [SOCLE, AGENT])
            self.assertEqual(result["refused"], [])
            self.assertEqual(tree(self.project), before)  # aperçu sans écriture
            apply(self.project, self.out, self.root, [SOCLE, AGENT], expected_plan=result["plan_sha256"])
            self.assertEqual(read(os.path.join(self.project, ".claude/CLAUDE.md")), b"@socle/REGLES.md\n")
            self.assertTrue(os.path.exists(os.path.join(self.project, ".claude/socle/REGLES.md")))
            self.assertEqual(read(os.path.join(self.project, "CLAUDE.md")), "instructions de l utilisateur\n".encode())
            rollback(self.project)
            after = {k: v for k, v in tree(self.project).items() if not k.startswith(".zakios")}
            self.assertEqual(after, before)  # le CLAUDE.md de l'utilisateur est intact

    def test_existing_dot_claude_claude_md_is_never_overwritten(self):
        with Workdir() as wd:
            self.world(wd)
            write(os.path.join(self.project, ".claude/CLAUDE.md"), "mes règles\n")
            result = plan(self.project, self.out, self.root, [SOCLE])
            self.assertTrue(result["refused"])
            self.assertIn("non géré", result["refused"][0]["reasons"][0])
            self.assertEqual(read(os.path.join(self.project, ".claude/CLAUDE.md")), "mes règles\n".encode())
            self.assertEqual(result["actions"], [])


if __name__ == "__main__":
    unittest.main()
