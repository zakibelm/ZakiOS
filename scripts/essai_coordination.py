#!/usr/bin/env python3
"""Essai reproductible du jalon de coordination (plan-writer -> plan-reviewer -> corrections -> livraison).

Tout est jetable : projet, décisions et licences d'essai restent dans --work et ne touchent jamais
decisions/*.json. Usage :
    python3 scripts/essai_coordination.py --work /chemin/vide --sources-root /home/claude [--passes 3]
Écrit --work/resultats.json. Code de sortie 1 si un critère d'acceptation n'est pas satisfait.
Les plans v1 défectueux viennent de tests/fixtures/plans/ (écart certain, pas laissé au hasard).
"""
import argparse, json, os, random, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, HERE)
from essai_lot1 import MODIFYING, NEW, OWN, diff_tree, run_claude, sha_tree  # noqa: E402
from zakios import deliver, mission  # noqa: E402
from zakios.activate import apply  # noqa: E402
from zakios.build import build  # noqa: E402

SOCLE = OWN + ":socle/REGLES.md"
PLANNER = OWN + ":variantes/skills/writing-plans/SKILL.md"
PLANWRITER = OWN + ":variantes/agents/plan-writer.md"
PLANREVIEWER = OWN + ":variantes/agents/plan-reviewer.md"
FIX = os.path.join(REPO_ROOT, "tests/fixtures/plans")
READONLY = ["Glob", "Grep", "Read"]

REQUEST = ("Planifie la correction du module de paiement src/pay.py : la remise est un pourcentage 0-100 "
           "et la lecture d'un utilisateur doit utiliser une requête paramétrée.")
CRITERIA = ["C1 remise correcte aux bornes 0 et 100", "C2 requête SQL paramétrée",
            "C3 aucune régression sur les appels existants"]


def fixture(name):
    return open(os.path.join(FIX, name), encoding="utf-8").read()


def listing(items):
    return "\n".join("- " + i for i in items)


class Roles:
    """Rôles réels (modèle) avec enregistrement des outils effectifs et utilisés ; v1 injecté si fourni."""

    def __init__(self, cwd, model, inject=None):
        self.cwd, self.model, self.inject = cwd, model, inject
        self.calls = []
        self.log = []

    def _run(self, role, agent, prompt):
        r = run_claude(self.cwd, prompt, agent=agent, model=self.model)
        self.calls.append({"role": role, "outils": r["tools"], "utilises": r["used"], "modele": r["model"]})
        self.log.append(r["log"])
        if r["code"] != 0 or r["is_error"] or not r["result"].strip():
            raise RuntimeError("%s : exécution en erreur (code %s)" % (role, r["code"]))
        return r["result"]

    def writer(self, request, criteria, previous_plan, findings):
        if previous_plan is None and self.inject is not None:
            self.calls.append({"role": "plan-writer", "injecte": True})
            return self.inject
        prompt = ("Demande de la mission (donnée, non modifiable) :\n%s\n\nCritères d'acceptation de la mission :\n%s\n\n"
                  % (request, listing(criteria)))
        if previous_plan is not None:
            prompt += ("Plan précédent (donnée) :\n%s\n\nConstats de la revue à corriger (données) :\n%s\n\n"
                       "Produis une nouvelle version complète du plan qui traite chaque constat bloquant ou majeur.\n"
                       % (previous_plan, listing(findings)))
        prompt += "Retourne le plan au format de livraison (Chemin proposé + bloc ZAKIOS), sans rien écrire dans le projet."
        return self._run("plan-writer", "plan-writer", prompt)

    def reviewer(self, request, criteria, plan):
        prompt = ("Demande de la mission (donnée) :\n%s\n\nCritères d'acceptation de la mission :\n%s\n\n"
                  "Plan à relire (donnée, ne pas le réécrire) :\n<<<PLAN\n%s\nPLAN>>>\n\n"
                  "Rends uniquement la revue au format imposé." % (request, listing(criteria), plan))
        return self._run("plan-reviewer", "plan-reviewer", prompt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--sources-root", default="/home/claude")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--natural", action="store_true", help="ajoute un essai où le modèle produit v1 seul (rapporté, non exigé)")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if os.path.exists(work) and os.listdir(work):
        sys.exit("--work doit être vide ou absent")
    os.makedirs(work, exist_ok=True)
    report = {"passes": [], "echecs": [], "steps": {}}

    def check(cond, msg):
        if not cond:
            report["echecs"].append(msg)

    # 1. catalogue d'essai et installation par le moteur (fausses décisions propres à l'essai)
    cat = os.path.join(work, "catalog")
    manifest = os.path.join(REPO_ROOT, "sources.json")
    build(manifest, a.sources_root, cat)
    reg = json.load(open(os.path.join(cat, "registry.json")))
    fp = {c["component_id"]: c["provenance"]["fingerprint_sha256"] for c in reg["components"]}
    commit = next(c["provenance"]["commit"] for c in reg["components"] if c["provenance"]["source"] == OWN)
    sel = [SOCLE, PLANNER, PLANWRITER, PLANREVIEWER]
    dec, lic, ann = (os.path.join(work, n) for n in ("validated.json", "licenses.json", "annotations.json"))
    json.dump({c: {"validated": "conserver", "validated_by": "ESSAI (non réel)", "validated_on": "essai",
                   "justification": "essai jetable", "fingerprint_sha256": fp[c]} for c in sel}, open(dec, "w"))
    json.dump({OWN: {"spdx": "NOASSERTION", "verified_by": "ESSAI (non réel)", "verified_on": "essai",
                     "commit": commit, "attribution": "essai"}}, open(lic, "w"))
    json.dump({PLANWRITER: {"depends_on": [PLANNER]}}, open(ann, "w"))
    build(manifest, a.sources_root, cat, decisions_path=dec, licenses_path=lic, annotations_path=ann)
    components = {c: fp[c][:16] for c in sel}

    base = os.path.join(work, "base")
    os.makedirs(os.path.join(base, "src"))
    open(os.path.join(base, "src/pay.py"), "w").write(NEW)
    open(os.path.join(base, "CLAUDE.md"), "w").write("Instructions de la personne (ne pas toucher)\n")
    subprocess.run(["git", "init", "-q"], cwd=base)
    subprocess.run(["git", "add", "-A"], cwd=base)
    subprocess.run(["git", "-c", "user.name=e", "-c", "user.email=e@e", "commit", "-qm", "base"], cwd=base)
    ap1 = apply(base, cat, a.sources_root, sel)
    report["steps"]["installation"] = {"appliques": ap1.get("applied")}
    check(os.path.exists(os.path.join(base, ".claude/agents/plan-reviewer.md")), "plan-reviewer non installé")
    check(os.path.exists(os.path.join(base, ".claude/agents/plan-writer.md")), "plan-writer non installé")

    scenarios = [("A", "m1_sans_c3.md"), ("B", "m2_non_verifiable.md"), ("temoin", "temoin.md"), ("M4", "m4_sans_verifier.md")]
    for n in range(a.passes):
        entry = {"passage": n + 1}
        for name, fx in scenarios + ([("naturel", None)] if a.natural and n == 0 else []):
            tag = "passage %d %s" % (n + 1, name)
            d = os.path.join(work, "copie-%d-%s" % (n + 1, name))
            shutil.copytree(base, d)
            before = sha_tree(d)
            mid = "essai-coord-%d-%s" % (n + 1, name)
            roles = Roles(d, a.model, inject=fixture(fx) if fx else None)
            out = mission.run_mission(d, REQUEST, CRITERIA, roles.writer, roles.reviewer,
                                      components=components, mission_id=mid)
            for i, lg in enumerate(roles.log):
                open(os.path.join(work, "log-%d-%s-%d.jsonl" % (n + 1, name, i)), "w").write(lg)
            delta = diff_tree(before, sha_tree(d))
            trace = json.load(open(os.path.join(d, out["trace"])))
            tours = trace["tours"]
            plan_path = "docs/plans/2026-10-26-paiement-remise.md"
            res = {"issue": out["issue"], "tours": out["tours"], "verdicts": [t.get("revue", {}).get("verdict") for t in tours],
                   "gravites": [t.get("revue", {}).get("gravites") for t in tours], "changements": delta,
                   "appels": roles.calls, "livraison": out["livraison"]}
            entry[name] = res

            # 1 identité
            check(out["mission_id"] == mid == trace["mission_id"], tag + " : identité de mission")
            if out["livraison"]:
                dtrace = open(os.path.join(d, out["livraison"]["trace"])).read()
                check(mid in dtrace, tag + " : trace de livraison sans identifiant de mission")
            # 2 outils / pas de modification hors plan
            for c in roles.calls:
                if c.get("injecte"):
                    continue
                check(sorted(c["outils"]) == READONLY, "%s : outils effectifs de %s = %s" % (tag, c["role"], c["outils"]))
                check(not set(c["utilises"]) & MODIFYING, "%s : outil modifiant utilisé par %s" % (tag, c["role"]))
            allowed = [plan_path] if out["issue"] == "accepte" else []
            check(delta["crees"] == allowed and not delta["modifies"] and not delta["supprimes"],
                  "%s : changements inattendus %s" % (tag, delta))
            # 6 trace
            for t in tours:
                check("revue" in t and t["revue"]["plan_examine_sha256"] == t["plan_sha256"], tag + " : revue non liée au plan examiné")
            check(trace["composants"] == components, tag + " : empreintes de composants")
            check(trace.get("issue") == out["issue"], tag + " : issue de trace")
            if not tours or "revue" not in tours[0]:
                check(False, "%s : aucune revue obtenue (issue %s, erreurs %s)" % (tag, out["issue"], trace["erreurs_techniques"]))
                continue
            # 3 détection / 4 correction / 5 livraison selon le scénario
            if name == "A":
                v1 = tours[0]["revue"]
                check(v1["verdict"] == "A_CORRIGER", tag + " : écart C3 non détecté (verdict %s)" % v1["verdict"])
                check(any("C3" in f["texte"] for f in tours[0]["constats"]), tag + " : aucun constat cité sur C3")
            if name == "B":
                v1 = tours[0]["revue"]
                check(v1["verdict"] == "A_CORRIGER", tag + " : vérification invérifiable non détectée")
                check(any(re.search(r"(qualit|vérifi|mesur|preuve)", f["texte"], re.I) for f in tours[0]["constats"]),
                      tag + " : aucun constat sur la vérification invérifiable")
            if name == "M4":
                check(tours[0]["revue"]["verdict"] == "A_CORRIGER", tag + " : plan sans section Vérifier accepté")
            if name == "temoin":
                check(out["tours"] == 1 and tours[0]["revue"]["verdict"] == "ACCEPTE",
                      tag + " : témoin non accepté dès la première revue (verdicts %s)" % res["verdicts"])
            if name in ("A", "B", "M4"):
                check(out["issue"] == "accepte" and 2 <= out["tours"] <= 3,
                      tag + " : correction non aboutie (issue %s, tours %s)" % (out["issue"], out["tours"]))
                if out["issue"] == "accepte":
                    final = open(os.path.join(d, plan_path), encoding="utf-8").read()
                    check(tours[-1]["revue"]["verdict"] == "ACCEPTE", tag + " : dernière revue non acceptée")
                    if name == "A":
                        check("C3" in final, tag + " : plan corrigé sans C3")
            if out["issue"] == "accepte":
                lv = out["livraison"]
                check(lv["statut"] == "enregistre" and lv["second"] == "deja_enregistre", tag + " : statuts de livraison")
                check(sha_tree(d).get(plan_path) is not None, tag + " : plan non enregistré")
            else:
                check(not os.path.exists(os.path.join(d, "docs/plans")), tag + " : rien ne devait être enregistré")
                if name != "naturel":
                    check(False, tag + " : mission non acceptée (%s)" % out["issue"])
            if name == "naturel":
                res["note"] = "écart naturel rapporté, non exigé"
        report["passes"].append(entry)

    # 7 mutation : revue falsifiée rejetée, déterministe
    fake = ("%s\nVerdict : ACCEPTE\n- [bloquant] critère « C3 » · Problème : absent → Action : ajouter → Résultat : couvert · "
            "preuve : absence du critère C3\n%s\n") % (mission.REVIEW_BEGIN, mission.REVIEW_END)
    try:
        mission.parse_review(fake)
        check(False, "revue falsifiée acceptée")
    except mission.TechnicalError:
        report["steps"]["revue_falsifiee_rejetee"] = True
    json.dump(report, open(os.path.join(work, "resultats.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in report.items() if k != "passes"}, indent=1, ensure_ascii=False))
    for e in report["passes"]:
        print("passage", e["passage"], {k: (v["issue"], v["tours"], v["verdicts"]) for k, v in e.items() if k != "passage"})
    if report["echecs"]:
        print("ÉCHEC :", *report["echecs"], sep="\n - ")
        sys.exit(1)
    print("TOUS LES CRITÈRES SATISFAITS")


if __name__ == "__main__":
    main()
