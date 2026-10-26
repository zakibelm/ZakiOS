"""Génère zakios/pilote/campagnes.json depuis les preuves des campagnes (codes de sortie, résultats, audits indépendants).
Les chiffres viennent des fichiers de preuves ; seuls les titres et notes de périmètre sont rédigés ici.
Chaque campagne reste SÉPARÉE : aucun taux de réussite agrégé n'est calculé, l'échec de C3 est conservé.
Usage : python3 scripts/generer_campagnes.py [--check]   (--check : échoue si le fichier committé diffère)"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREUVES = os.path.join(ROOT, "docs", "revues", "preuves-clarification")
SORTIE = os.path.join(ROOT, "zakios", "pilote", "campagnes.json")

# (id, titre, commit testé, périmètre, dossiers de scripts [(étiquette, sous-dossier)], audits, remarque)
CAMPAGNES = [
    ("avant", "Avant — référence sans verdict de clarification", "fe16781",
     "Cas contradictoire K1/K2 avec l'ancien relecteur (sans CLARIFICATION_REQUISE).",
     [("garanties", "avant", None)], [],
     "Le plan abandonnait un critère et a été accepté puis livré : c'est le défaut qui a motivé CLARIFICATION_REQUISE."),
    ("C1", "C1 — intermédiaire", "b78dd67",
     "Campagne antérieure à la spécification complète ; plusieurs défauts venaient des cas de test eux-mêmes.",
     [("coordination", "campagne-C1/coordination", None), ("garanties", "campagne-C1/garanties", None)], [],
     "Cas défectueux corrigés sous de nouveaux noms ; échecs conservés. Un échec d'exécution (erreur technique) compté en coordination."),
    ("C2", "C2 — campagne finale de clarification", "8c45301",
     "Plans de coordination injectés (A, B, M4, témoin) et plans de garanties produits par le modèle, 3 passages.",
     [("coordination", "campagne-C2/coordination", "audit-coordination.json"), ("garanties", "campagne-C2/garanties", "audit-garanties.json")], [],
     "Le cas « omission corrigeable » n'a pas été exercé (le modèle n'a pas commis l'omission) : la boucle de correction n'est pas démontrée sur ce cas inédit."),
    ("C3", "C3 — traçabilité des relances", "4c0157a",
     "Information manquante, contradiction inédite, témoin résoluble ; 3 passages chacun ; rôles inchangés depuis C2.",
     [("garanties", "campagne-C3/garanties", "audit-garanties.json")], [],
     "ÉCHEC CONSERVÉ : le rédacteur a tenté d'appeler Bash (refusé par la plateforme, sans effet). Les critères de C3 n'ont pas été modifiés rétroactivement."),
    ("C4", "C4 — confinement des outils", "0fb7e39",
     "Mêmes trois cas que C3 rejoués ×3 avec la consigne « seuls Read, Glob, Grep » et la classification des outils.",
     [("garanties", "campagne-C4/garanties", "audit-garanties.json")], [],
     "Preuve de comportement sur 9 passages et un seul modèle, pas une garantie qu'aucune tentative n'aura jamais lieu."),
]


def _json(*parts):
    with open(os.path.join(PREUVES, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def _exit(sous):
    d = os.path.join(PREUVES, sous)
    for f in sorted(os.listdir(d)):
        if f.endswith(".exit"):
            with open(os.path.join(d, f)) as fh:
                return int(fh.read().strip())
    raise SystemExit("code de sortie introuvable : " + sous)


def construire():
    out = {"avertissement": "Chaque campagne est présentée séparément. Aucun taux agrégé : les périmètres, modèles et critères diffèrent.",
           "campagnes": []}
    for cid, titre, commit, perimetre, scripts, _, remarque in CAMPAGNES:
        entrees, tout_ok = [], True
        for label, sous, audit_name in scripts:
            res = _json(sous, "resultats.json")
            code = _exit(sous)
            e = {"script": label, "code_sortie": code, "echecs": res.get("echecs", []),
                 "non_exerces": res.get("non_exerces", []), "relances_recuperees": len(res.get("relances_recuperees", []))}
            if audit_name:
                a = _json(os.path.dirname(sous), audit_name)
                e["audit"] = {"missions": a["statistiques"]["missions"], "appels_reels": a["statistiques"]["appels_reels"],
                              "divergences": a["divergences"], "ecarts_comportementaux": a.get("ecarts_comportementaux", [])}
            tout_ok = tout_ok and code == 0 and not e["echecs"] and not e["non_exerces"] and not e.get("audit", {}).get("divergences")
            entrees.append(e)
        out["campagnes"].append({"id": cid, "titre": titre, "commit_teste": commit, "perimetre": perimetre,
                                 "criteres_satisfaits": tout_ok, "scripts": entrees, "remarque": remarque})
    return out


def main():
    data = json.dumps(construire(), ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        with open(SORTIE, encoding="utf-8") as fh:
            if fh.read() != data:
                sys.exit("campagnes.json n'est pas à jour : relancer scripts/generer_campagnes.py")
        return
    with open(SORTIE, "w", encoding="utf-8") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
