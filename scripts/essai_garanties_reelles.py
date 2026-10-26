#!/usr/bin/env python3
"""Bout en bout RÉEL (vrais appels `claude -p --agent plan-writer / plan-reviewer`), aucun plan injecté.

Cas (le premier plan est produit par le modèle) et issue attendue :
  historiques : inedit (accepte), non_resoluble (clarification_requise, était « plafond » avant la distinction),
                non_resoluble_2 (plafond_atteint : A_CORRIGER répété, critères de mission contraires à la structure PDCA),
                contradictoire_2 (clarification_requise), temoin_resoluble (accepte) — mesurés avant/après ;
  nouveaux    : omission_corrigeable (correction puis acceptation), contradiction_inedite (clarification_requise),
                information_manquante (clarification_requise ciblée sur M1).
Chaque passage utilise une copie neuve du projet jetable et des sessions `claude -p` neuves.

Usage : python3 scripts/essai_garanties_reelles.py --work /dossier/neuf --sources-root /home/claude
        [--only cas1,cas2] [--passes N]
Codes de sortie : 0 toutes les attentes satisfaites ; 1 au moins une attente ou un invariant non satisfait ;
                  2 au moins une erreur technique (issue `erreur_technique`) — distincte d'une issue métier.
Écrit --work/resultats.json. Ne modifie jamais decisions/*.json ; aucune installation réelle."""
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
CONTRADICTOIRE_2 = {
    "request": "Planifie la gestion d'une valeur absente (None) pour prices dans total(prices, discount) de src/pay.py.",
    "criteria": ["K1 total() ne lève jamais d'exception, même si prices vaut None",
                 "K2 total() lève TypeError si prices vaut None"],
}
TEMOIN_RESOLUBLE = {
    "request": "Planifie l'ajout d'une docstring à total(prices, discount) dans src/pay.py et d'un test minimal pour cette fonction.",
    "criteria": ["R1 la docstring décrit discount comme un pourcentage de 0 à 100",
                 "R2 un test couvre au moins discount=0 et discount=100"],
}
OMISSION_CORRIGEABLE = {  # contraintes de forme faciles à enfreindre au premier jet, corrigeables sans la personne
    "request": "Planifie la correction de total(prices, discount) dans src/pay.py (la remise est un pourcentage de 0 à 100).",
    "criteria": ["O1 le plan comporte au plus 4 étapes d'exécution numérotées",
                 "O2 chaque étape d'exécution cite le fichier qu'elle lit ou modifie",
                 "O3 chaque étape d'exécution tient sur une seule ligne",
                 "O4 la section « Vérifier » cite une commande exécutable qui contrôle la remise aux bornes 0 et 100"],
}
CONTRADICTION_INEDITE = {
    "request": "Planifie l'écriture des commandes dans un fichier journal.txt par une nouvelle fonction de src/export.py.",
    "criteria": ["T1 les lignes du fichier sont triées par date croissante",
                 "T2 les lignes du fichier sont triées par date décroissante",
                 "T3 le plan fixe l'emplacement du fichier de sortie"],
}
INFORMATION_MANQUANTE = {  # le nom de l'hôte n'existe ni dans la mission ni dans le projet
    "request": "Planifie le déploiement de la correction de total() de src/pay.py sur le serveur de production désigné par l'équipe infrastructure.",
    "criteria": ["M1 le plan cible le serveur de production désigné par l'équipe infrastructure, avec son nom d'hôte exact",
                 "M2 le plan prévoit un retour arrière vérifiable"],
}
# Cas redéfini après la campagne C1 : le témoin d'origine (TEMOIN_RESOLUBLE) était défectueux — le code de
# src/pay.py traite `discount` comme une fraction 0-1, donc « pourcentage 0-100 » + test à 100 n'étaient pas
# satisfaisables sans modifier le code. Le relecteur avait raison de demander une décision. Conservé pour mémoire.
TEMOIN_RESOLUBLE_2 = {
    "request": "Planifie l'ajout d'une docstring à total(prices, discount) dans src/pay.py, décrivant le comportement actuel du code tel qu'il est, sans le modifier, et d'un test minimal.",
    "criteria": ["R1 la docstring décrit discount comme une fraction entre 0 et 1, conformément au code actuel",
                 "R2 un test couvre au moins discount=0 (résultat = somme des prix) et discount=0.5 (moitié de la somme)",
                 "R3 le plan ne modifie pas le corps de total()"],
}
# NON_RESOLUBLE_2 (V1 interdit « Vérifier »/« Agir ») contredit le Socle PDCA : l'issue attendue « plafond »
# était mal conçue (le relecteur a légitimement demandé une clarification en C1). Retiré de la liste par défaut ;
# le plafond reste vérifié par les tests d'intégration, non réexercé en réel faute de scénario valide.
# (cas, issue attendue, exige_correction, critère de clarification attendu)
CASES = {
    "inedit": (INEDIT, "accepte", False, None),
    "non_resoluble": (NON_RESOLUBLE, "clarification_requise", False, None),
    "non_resoluble_2": (NON_RESOLUBLE_2, "plafond_atteint", False, None),
    "contradictoire_2": (CONTRADICTOIRE_2, "clarification_requise", False, None),
    "temoin_resoluble": (TEMOIN_RESOLUBLE, "accepte", False, None),  # défectueux (voir C1), hors défaut
    "temoin_resoluble_2": (TEMOIN_RESOLUBLE_2, "accepte", False, None),
    "omission_corrigeable": (OMISSION_CORRIGEABLE, "accepte", True, None),
    "contradiction_inedite": (CONTRADICTION_INEDITE, "clarification_requise", False, "T1"),
    "information_manquante": (INFORMATION_MANQUANTE, "clarification_requise", False, "M1"),
}
DEFAULT = "non_resoluble,temoin_resoluble_2,omission_corrigeable,contradiction_inedite,information_manquante"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Spy(Roles):
    """Rôles réels + empreinte de ce qui est réellement produit/transmis à chaque appel."""

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
    ap.add_argument("--only", default=DEFAULT, help="cas séparés par des virgules : " + ",".join(CASES))
    ap.add_argument("--passes", type=int, default=1)
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if os.path.exists(work) and os.listdir(work):
        sys.exit("--work doit être vide ou absent")
    os.makedirs(work, exist_ok=True)
    report = {"cas": {}, "echecs": [], "non_exerces": [], "erreurs_techniques": []}

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
    report["composants"] = components
    base = os.path.join(work, "base")
    os.makedirs(os.path.join(base, "src"))
    open(os.path.join(base, "src/pay.py"), "w").write(NEW)
    open(os.path.join(base, "CLAUDE.md"), "w").write("Instructions de la personne (ne pas toucher)\n")
    subprocess.run(["git", "init", "-q"], cwd=base)
    subprocess.run(["git", "add", "-A"], cwd=base)
    subprocess.run(["git", "-c", "user.name=e", "-c", "user.email=e@e", "commit", "-qm", "base"], cwd=base)
    apply(base, cat, a.sources_root, sel)

    for name in a.only.split(","):
        case, expect, needs_correction, clar_expected = CASES[name]
        for n in range(1, a.passes + 1):
            key = "%s/p%d" % (name, n)
            tag = key
            d = os.path.join(work, "copie-%s-p%d" % (name, n))
            shutil.copytree(base, d)
            before = sha_tree(d)
            mid = "garanties-%s-p%d" % (name, n)
            roles = Spy(d, a.model)
            out = mission.run_mission(d, case["request"], case["criteria"], roles.writer, roles.reviewer,
                                      components=components, mission_id=mid)
            for i, lg in enumerate(roles.log):
                open(os.path.join(work, "log-%s-p%d-%d.jsonl" % (name, n, i)), "w").write(lg)
            delta = diff_tree(before, sha_tree(d))
            trace = json.load(open(os.path.join(d, out["trace"])))
            tours = trace["tours"]
            res = {"cas": name, "passage": n, "attendu": expect, "issue": out["issue"], "categorie": out["categorie"],
                   "tours": out["tours"], "verdicts": [t.get("revue", {}).get("verdict") for t in tours],
                   "gravites": [t.get("revue", {}).get("gravites") for t in tours], "appels": roles.calls,
                   "appels_comptes": out["appels"], "changements": delta, "plans_sha256": [t["plan_sha256"] for t in tours],
                   "livraison": out["livraison"], "erreurs_techniques": trace["erreurs_techniques"]}
            report["cas"][key] = res
            if out["issue"] == "erreur_technique":
                report["erreurs_techniques"].append(key)
                continue  # distinct d'une issue métier : rapporté, code de sortie 2
            real = [c for c in roles.calls if not c.get("injecte")]
            check(len(real) >= 2 and not any(c.get("injecte") for c in roles.calls), tag + " : appels non réels")
            for c in real:
                check(sorted(c["outils"]) == READONLY, "%s : outils effectifs de %s = %s" % (tag, c["role"], c["outils"]))
                check(not set(c["utilises"]) & MODIFYING, "%s : outil modifiant utilisé par %s" % (tag, c["role"]))
            check(out["tours"] <= 3, tag + " : plafond dépassé")
            check(out["appels"]["plan-writer"] == len(roles.written) and out["appels"]["plan-reviewer"] == len(roles.reviewed),
                  tag + " : décompte d'appels incohérent")
            for t, rs in zip(tours, roles.reviewed):
                check("revue" in t and t["revue"]["plan_examine_sha256"] == t["plan_sha256"] == rs,
                      tag + " : revue non liée à l'empreinte du plan transmis")
            check(trace["composants"] == components, tag + " : empreintes des composants")
            check(trace["mission_id"] == mid == out["mission_id"], tag + " : identité")
            check(out["issue"] == expect, "%s : issue %s, attendu %s" % (tag, out["issue"], expect))
            if out["issue"] == "accepte":
                check(set(tours[-1]["revue"]["couverture"].values()) == {"couvert"}, tag + " : accepté avec un critère non couvert/abandonné")
                lv = out["livraison"]
                f = open(os.path.join(d, lv["chemin"]), "rb").read()
                check(sha(f.decode("utf-8")) == lv["content_sha256"], tag + " : fichier enregistré != content_sha256")
                check(sha(f.decode("utf-8")) == tours[-1]["plan_sha256"], tag + " : fichier enregistré != dernier plan")
                check(tours[-1]["revue"]["verdict"] == "ACCEPTE", tag + " : dernière revue non acceptée")
                check(lv["statut"] == "enregistre" and lv["second"] == "deja_enregistre", tag + " : statuts de livraison")
                check(delta["crees"] == [lv["chemin"]] and not delta["modifies"] and not delta["supprimes"], tag + " : changements %s" % delta)
                res["plan_enregistre_sha256"] = sha(f.decode("utf-8"))
                if needs_correction:
                    res["exerce"] = out["tours"] >= 2
                    if not res["exerce"]:
                        report["non_exerces"].append(key)  # le modèle a satisfait les critères du premier coup : rapporté, pas masqué
            else:
                check(out["livraison"] is None, tag + " : livraison malgré l'arrêt")
                check(not os.path.exists(os.path.join(d, "docs")), tag + " : un plan a été écrit")
                check(not os.path.exists(os.path.join(d, ".zakios/deliverables")), tag + " : trace de livraison présente")
                check(not delta["crees"] and not delta["modifies"] and not delta["supprimes"], tag + " : projet modifié %s" % delta)
                check("livraison" not in trace and "arret" in trace, tag + " : trace d'arrêt absente ou avec livraison")
            if out["issue"] == "clarification_requise":
                clar = trace["clarification"]
                check(res["verdicts"][-1] == "CLARIFICATION_REQUISE" and out["questions"], tag + " : clarification sans question")
                check(clar["plan_sha256"] == tours[-1]["plan_sha256"], tag + " : clarification non liée au plan examiné")
                check(out["appels"]["plan-writer"] == out["appels"]["plan-reviewer"] == len(tours), tag + " : appels après la clarification")
                if clar_expected:
                    check(clar_expected in clar["criteres"], "%s : clarification attendue sur %s, reçue sur %s" % (tag, clar_expected, clar["criteres"]))
                res["clarification"] = clar
            if out["issue"] == "plafond_atteint":
                check(out["tours"] == 3 and len(roles.reviewed) == 3 and all(v == "A_CORRIGER" for v in res["verdicts"]),
                      tag + " : plafond attendu avec 3 revues A_CORRIGER, reçu %s" % res["verdicts"])
    json.dump(report, open(os.path.join(work, "resultats.json"), "w"), indent=2, ensure_ascii=False)
    for k, r in report["cas"].items():
        print(k, "| attendu:", r["attendu"], "| issue:", r["issue"], "(%s)" % r["categorie"], "| tours:", r["tours"], "| verdicts:", r["verdicts"])
    if report["non_exerces"]:
        print("NON EXERCÉ (omission non commise au premier jet) :", report["non_exerces"])
    if report["erreurs_techniques"]:
        print("ERREUR TECHNIQUE (code 2) :", report["erreurs_techniques"])
    if report["echecs"]:
        print("ÉCHEC (attente non satisfaite) :", *report["echecs"], sep="\n - ")
    if report["erreurs_techniques"]:
        sys.exit(2)
    if report["echecs"]:
        sys.exit(1)
    print("TOUTES LES ATTENTES SATISFAITES")


if __name__ == "__main__":
    main()
