#!/usr/bin/env python3
"""Bout en bout RÉEL (vrais appels `claude -p --agent plan-writer / plan-reviewer`), deux cas :
  - inédit : une demande qui n'a jamais servi aux essais précédents ; attendu : plan accepté et livré identique ;
  - non résoluble : des critères contradictoires et une interdiction d'escalade ; attendu : arrêt au plafond
    (3 plans, 3 revues), aucun plan livré.
Aucun plan n'est injecté : les deux rôles sont des appels réels. Installation d'essai uniquement dans --work.
Usage : python3 scripts/essai_garanties_reelles.py --work /dossier/neuf --sources-root /home/claude
Écrit --work/resultats.json ; code 1 si une attente ou un invariant échoue. Ne modifie jamais decisions/*.json."""
import argparse, hashlib, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, HERE)
from essai_coordination import (PLANREVIEWER, PLANNER, PLANWRITER, READONLY, SOCLE, Roles)  # noqa: E402
from essai_lot1 import MODIFYING, NEW, OWN, diff_tree, sha_tree  # noqa: E402
from zakios import mission  # noqa: E402
from zakios.activate import apply  # noqa: E402
from zakios.build import build  # noqa: E402

INEDIT = {
    "request": ("Planifie l'ajout d'une fonction export_csv(rows, path) dans un nouveau fichier src/export.py : "
                "elle écrit une liste de dictionnaires dans un fichier CSV."),
    "criteria": ["E1 la première ligne contient les en-têtes dans l'ordre des clés du premier enregistrement",
                 "E2 les virgules, guillemets et sauts de ligne dans les valeurs sont correctement échappés",
                 "E3 si le fichier de destination existe déjà, la fonction lève une erreur explicite et n'écrase rien"],
}
NON_RESOLUBLE = {
    "request": "Planifie la modification de total(prices, discount) dans src/pay.py pour un rabais de 50.",
    "criteria": ["U1 total(prices, 50) renvoie exactement sum(prices)",
                 "U2 total(prices, 50) renvoie exactement sum(prices) / 2",
                 "U3 le plan se déroule sans aucune question ni escalade vers la personne, quelle que soit la situation"],
}
NON_RESOLUBLE_2 = {
    "request": "Planifie la correction de total(prices, discount) dans src/pay.py (la remise est un pourcentage 0-100).",
    "criteria": ["V1 le plan ne contient que les sections « Planifier » et « Exécuter » ; toute section « Vérifier » ou « Agir » est interdite",
                 "V2 la correction de total() est décrite en une seule étape d'exécution"],
}
CONTRADICTOIRE_2 = {  # contradiction dont la résolution appartient à la personne (jamais utilisé avant)
    "request": "Planifie la gestion d'une valeur absente (None) pour prices dans total(prices, discount) de src/pay.py.",
    "criteria": ["K1 total() ne lève jamais d'exception, même si prices vaut None",
                 "K2 total() lève TypeError si prices vaut None"],
}
TEMOIN_RESOLUBLE = {  # cas résoluble, jamais utilisé avant
    "request": "Planifie l'ajout d'une docstring à total(prices, discount) dans src/pay.py et d'un test minimal pour cette fonction.",
    "criteria": ["R1 la docstring décrit discount comme un pourcentage de 0 à 100",
                 "R2 un test couvre au moins discount=0 et discount=100"],
}
# `attendu` pour contradictoire_2 : arrêt par clarification, sans livraison (verdict introduit après cette mesure « avant »).
CASES = {"inedit": (INEDIT, "accepte"), "non_resoluble": (NON_RESOLUBLE, "clarification_requise"),  # était « plafond_atteint » avant la distinction (jamais observé : accepté)
         
         "non_resoluble_2": (NON_RESOLUBLE_2, "plafond_atteint"),
         "contradictoire_2": (CONTRADICTOIRE_2, "clarification_requise"),
         "temoin_resoluble": (TEMOIN_RESOLUBLE, "accepte")}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Spy(Roles):
    """Roles réels + empreinte de ce qui est réellement transmis/produit à chaque appel."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.written, self.reviewed = [], []

    def writer(self, request, criteria, previous_plan, findings):
        out = super().writer(request, criteria, previous_plan, findings)
        self.written.append(sha(out))
        return out

    def reviewer(self, request, criteria, plan):
        self.reviewed.append(sha(plan))
        return super().reviewer(request, criteria, plan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--sources-root", default="/home/claude")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", default=",".join(["inedit", "non_resoluble"]), help="cas à exécuter, séparés par des virgules : " + ",".join(CASES))
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if os.path.exists(work) and os.listdir(work):
        sys.exit("--work doit être vide ou absent")
    os.makedirs(work, exist_ok=True)
    report = {"cas": {}, "echecs": []}

    def check(cond, msg):
        if not cond:
            report["echecs"].append(msg)

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
    apply(base, cat, a.sources_root, sel)

    for name, (case, expect) in [(n, CASES[n]) for n in a.only.split(",")]:
        d = os.path.join(work, "copie-" + name)
        shutil.copytree(base, d)
        before = sha_tree(d)
        mid = "garanties-reelles-" + name
        roles = Spy(d, a.model)
        out = mission.run_mission(d, case["request"], case["criteria"], roles.writer, roles.reviewer,
                                  components=components, mission_id=mid)
        for i, lg in enumerate(roles.log):
            open(os.path.join(work, "log-%s-%d.jsonl" % (name, i)), "w").write(lg)
        delta = diff_tree(before, sha_tree(d))
        trace = json.load(open(os.path.join(d, out["trace"])))
        tours = trace["tours"]
        res = {"attendu": expect, "issue": out["issue"], "tours": out["tours"], "verdicts": [t.get("revue", {}).get("verdict") for t in tours],
               "gravites": [t.get("revue", {}).get("gravites") for t in tours], "appels": roles.calls, "changements": delta,
               "plans_sha256": [t["plan_sha256"] for t in tours], "livraison": out["livraison"],
               "erreurs_techniques": trace["erreurs_techniques"]}
        report["cas"][name] = res
        tag = name
        # invariants communs
        real = [c for c in roles.calls if not c.get("injecte")]
        check(len(real) >= 2 and not any(c.get("injecte") for c in roles.calls), tag + " : appels non réels")
        for c in real:
            check(sorted(c["outils"]) == READONLY, "%s : outils effectifs de %s = %s" % (tag, c["role"], c["outils"]))
            check(not set(c["utilises"]) & MODIFYING, "%s : outil modifiant utilisé par %s" % (tag, c["role"]))
        check(out["tours"] <= 3, tag + " : plafond dépassé")
        for t, ws, rs in zip(tours, roles.written, roles.reviewed):
            check("revue" in t and t["revue"]["plan_examine_sha256"] == t["plan_sha256"] == rs,
                  tag + " : revue non liée à l'empreinte du plan transmis")
        # le plan transmis au relecteur est bien celui extrait de la sortie du rédacteur (hors texte de livraison autour)
        check(trace["composants"] == components, tag + " : empreintes des composants")
        check(trace["mission_id"] == mid == out["mission_id"], tag + " : identité")
        check(out["issue"] == expect, "%s : issue %s, attendu %s" % (tag, out["issue"], expect))
        if out["issue"] == "accepte":
            check(set(tours[-1]["revue"]["couverture"].values()) == {"couvert"}, tag + " : accepté avec un critère non couvert/abandonné")
            lv = out["livraison"]
            f = open(os.path.join(d, lv["chemin"]), "rb").read()
            check(sha(f.decode("utf-8")) == lv["content_sha256"], tag + " : fichier enregistré != content_sha256")
            check(tours[-1]["revue"]["verdict"] == "ACCEPTE", tag + " : dernière revue non acceptée")
            check(lv["statut"] == "enregistre" and lv["second"] == "deja_enregistre", tag + " : statuts de livraison")
            check(delta["crees"] == [lv["chemin"]] and not delta["modifies"] and not delta["supprimes"], tag + " : changements %s" % delta)
            res["plan_enregistre_sha256"] = sha(f.decode("utf-8"))
        else:
            check(out["livraison"] is None, tag + " : livraison malgré l'échec")
            check(not os.path.exists(os.path.join(d, "docs")), tag + " : un plan a été écrit")
            check(not os.path.exists(os.path.join(d, ".zakios/deliverables")), tag + " : trace de livraison présente")
            check(not delta["crees"] and not delta["modifies"] and not delta["supprimes"], tag + " : projet modifié %s" % delta)
            check("livraison" not in trace, tag + " : trace avec livraison")
        if out["issue"] == "clarification_requise":
            check(res["verdicts"][-1] == "CLARIFICATION" and out["questions"], tag + " : clarification sans question")
            check(trace["clarification"]["plan_sha256"] == tours[-1]["plan_sha256"], tag + " : clarification non liée au plan examiné")
            check(len(roles.written) == len(roles.reviewed) == len(tours), tag + " : appels après la clarification")
            res["questions"] = out["questions"]
        if name == "non_resoluble_2":
            check(out["tours"] == 3 and len(roles.reviewed) == 3, "non résoluble : 3 plans et 3 revues attendus")
            check(all(v == "A_CORRIGER" for v in res["verdicts"]), "non résoluble : verdicts %s" % res["verdicts"])
    json.dump(report, open(os.path.join(work, "resultats.json"), "w"), indent=2, ensure_ascii=False)
    for n, r in report["cas"].items():
        print(n, "| attendu:", r["attendu"], "| issue:", r["issue"], "| tours:", r["tours"], "| verdicts:", r["verdicts"])
    if report["echecs"]:
        print("ÉCHEC :", *report["echecs"], sep="\n - ")
        sys.exit(1)
    print("TOUS LES CRITÈRES SATISFAITS")


if __name__ == "__main__":
    main()
