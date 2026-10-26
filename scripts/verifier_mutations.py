#!/usr/bin/env python3
"""Vérification par mutation des protections du coordinateur (tests SIMULÉS, aucun modèle).

Pour chaque mutation : copie temporaire du dépôt (les sources réelles ne sont jamais modifiées), retrait d'UNE protection
dans zakios/mission.py, exécution des tests de coordination (bytecode désactivé : pas de cache périmé). Les tests doivent
ÉCHOUER. Un contrôle de base (sans mutation) doit passer. Écrit le tableau en JSON si --out est fourni.
Code de sortie : 0 base verte et toutes les mutations détectées ; 1 sinon."""
import argparse, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = ["tests.test_mission", "tests.test_garanties_coordination", "tests.test_clarification"]
MUTATIONS = [
    ("acceptation_malgre_bloquant", "    if verdict == \"ACCEPTE\":\n        if blocking:", "    if verdict == \"ACCEPTE\":\n        if False:"),
    ("acceptation_malgre_clarification", "        if clarif:\n            raise TechnicalError(\"revue incohérente : ACCEPTE malgré une clarification requise\")", "        if False:\n            raise TechnicalError(\"x\")"),
    ("acceptation_malgre_critere_abandonne", "        if not_covered:\n            raise TechnicalError(\"revue incohérente : ACCEPTE", "        if False:\n            raise TechnicalError(\"revue incohérente : ACCEPTE"),
    ("livraison_apres_clarification", "    if outcome == \"accepte\":\n        assert accepted_sha", "    if outcome in (\"accepte\", \"clarification_requise\"):\n        accepted_sha = _sha(plan)\n        assert accepted_sha"),
    ("boucle_continue_apres_clarification", "            outcome, cause = \"clarification_requise\", \"; \".join(f[\"blocage\"] for f in clarifs)\n            break", "            outcome, cause = \"clarification_requise\", \"; \".join(f[\"blocage\"] for f in clarifs)"),
    ("plafond_de_corrections", "    for turn in range(max_corrections + 1):", "    for turn in range(max_corrections + 2):"),
    ("liaison_a_l_empreinte", "    if plan_sha is not None:\n        if len(bound)", "    if False:\n        if len(bound)"),
    ("couverture_des_criteres", "    if criteria is not None:\n        if sorted(coverage)", "    if False:\n        if sorted(coverage)"),
    ("clarification_sans_question", "    if \"?\" not in fields[\"question\"]:", "    if False:"),
    ("a_corriger_sans_constat_majeur", "        if not blocking:\n            raise TechnicalError(\"revue incohérente : A_CORRIGER", "        if False:\n            raise TechnicalError(\"revue incohérente : A_CORRIGER"),
]


def run_tests(tree):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-B", "-m", "unittest"] + TESTS, cwd=tree, env=env, capture_output=True, text=True)
    last = [l for l in p.stderr.strip().splitlines() if l][-1] if p.stderr.strip() else ""
    return p.returncode, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    rows, ok = [], True
    with tempfile.TemporaryDirectory() as tmp:
        tree = os.path.join(tmp, "repo")
        shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(".git", "docs", "catalog", "catalog.prev", "archive", "__pycache__"))
        target = os.path.join(tree, "zakios", "mission.py")
        original = open(target, encoding="utf-8").read()
        code, last = run_tests(tree)
        rows.append({"mutation": "(base, aucune)", "attendu": "tests verts", "code": code, "detail": last, "detectee": code == 0})
        ok &= code == 0
        for name, old, new in MUTATIONS:
            if original.count(old) != 1:
                rows.append({"mutation": name, "attendu": "tests rouges", "code": None, "detail": "motif introuvable (%d occurrences)" % original.count(old), "detectee": False})
                ok = False
                continue
            open(target, "w", encoding="utf-8").write(original.replace(old, new))
            code, last = run_tests(tree)
            rows.append({"mutation": name, "attendu": "tests rouges", "code": code, "detail": last, "detectee": code != 0})
            ok &= code != 0
        open(target, "w", encoding="utf-8").write(original)
        code, last = run_tests(tree)
        rows.append({"mutation": "(restauration, aucune)", "attendu": "tests verts", "code": code, "detail": last, "detectee": code == 0})
        ok &= code == 0
    for r in rows:
        print("%-42s %-14s code=%s  %s" % (r["mutation"], "OK" if r["detectee"] else "NON DÉTECTÉE", r["code"], r["detail"]))
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1, ensure_ascii=False)
    print("TOUTES LES PROTECTIONS SONT DÉTECTÉES" if ok else "ÉCHEC : au moins une mutation non détectée ou base rouge")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
