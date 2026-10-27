"""Importe la liste de veille GitHub (instantané de la feuille Google du 2026-10-27) vers zakios/pilote/veille.json.

La liste est DÉCLARATIVE : aucune valeur (licence, étoiles, maturité) n'est vérifiée ici, rien n'est installé, et les
statuts de la feuille (À tester / Évalué) sont reproduits tels quels. `--check` échoue si le JSON diffère de la source."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "veille", "feuille-2026-10-27.psv")
OUT = os.path.join(ROOT, "zakios", "pilote", "veille.json")
COLS = ["nom", "lien", "categorie", "type", "usage", "statut", "priorite", "licence", "etoiles", "maturite", "stack", "projets", "utilite"]
ENUMS = {"priorite": {"Haute", "Moyenne", "Basse"}, "statut": {"À tester", "Évalué"},
         "usage": {"Brique à intégrer", "À installer et utiliser", "Référence d'architecture", "Veille / annuaire"}}
LINK = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


PERMISSIVES = {"MIT", "Apache 2.0", "BSD-2-Clause"}


def criteres(d):
    """Critères de présélection, calculés ici (jamais dans le navigateur) uniquement à partir des valeurs DÉCLARÉES de la feuille."""
    lic = d["licence"] or "À vérifier"
    return {"licence_permissive": lic in PERMISSIVES,
            "licence_copyleft_ou_inconnue": lic not in PERMISSIVES,      # AGPL, MPL, « À vérifier » : à examiner avant tout usage
            "maintenu": d["maturite"] in ("Très actif", "Stable"),
            "utilisable": d["usage"] in ("Brique à intégrer", "À installer et utiliser"),
            "besoin_identifie": bool(d["projets"]) and d["projets"] != ["Aucun pour l'instant"]}


def construire():
    lines = open(SRC, encoding="utf-8").read().splitlines()
    assert lines[0].split("|")[0] == "Nom"
    items = []
    for n, line in enumerate(lines[1:], 2):
        cells = [c.strip() for c in line.split("|")]
        if len(cells) != len(COLS):
            raise SystemExit("ligne %d : %d colonnes au lieu de %d" % (n, len(cells), len(COLS)))
        d = dict(zip(COLS, cells))
        for k, allowed in ENUMS.items():
            if d[k] not in allowed:
                raise SystemExit("ligne %d : %s inattendu %r" % (n, k, d[k]))
        if d["lien"] and not LINK.fullmatch(d["lien"]):
            raise SystemExit("ligne %d : lien invalide %r" % (n, d["lien"]))
        etoiles = d["etoiles"].replace(" ", "")
        if etoiles and not etoiles.isdigit():
            raise SystemExit("ligne %d : étoiles invalides" % n)
        items.append({"nom": d["nom"], "lien": d["lien"] or None, "categorie": d["categorie"], "type": d["type"], "usage": d["usage"],
                      "statut": d["statut"], "priorite": d["priorite"], "licence": d["licence"] or None,
                      "etoiles_declarees": int(etoiles) if etoiles else None, "maturite": d["maturite"] or None,
                      "stack": [s.strip() for s in d["stack"].split(";") if s.strip()],
                      "projets": [s.strip() for s in d["projets"].split(";") if s.strip()],
                      "utilite": [s.strip() for s in d["utilite"].split(";") if s.strip()],
                      "licence_a_verifier": d["licence"] in ("", "À vérifier")})
    for i in items:
        i["criteres"] = criteres(i)
        i["preselection"] = all(i["criteres"][k] for k in ("licence_permissive", "maintenu", "utilisable", "besoin_identifie"))
    noms = [i["nom"].lower() for i in items]
    liens = [i["lien"] for i in items if i["lien"]]
    if len(set(noms)) != len(noms) or len(set(liens)) != len(liens):
        raise SystemExit("doublon détecté")
    return {"source": "Feuille Google « Veille GitHub - Repos et valeur ajoutée », instantané du 2026-10-27 (docs/veille/feuille-2026-10-27.psv)",
            "avertissement": "Liste de veille déclarative : licences, étoiles et maturité NON vérifiés ; rien n'est installé ni validé ; « À vérifier » ne vaut pas autorisation.",
            "regle_preselection": "licence permissive déclarée (MIT, Apache 2.0, BSD-2-Clause) ET maturité Très actif/Stable ET usage Brique à intégrer/À installer et utiliser ET projet concerné identifié",
            "total": len(items), "preselection": sum(1 for i in items if i["preselection"]), "depots": items}


if __name__ == "__main__":
    data = construire()
    txt = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        ok = os.path.exists(OUT) and open(OUT, encoding="utf-8").read() == txt
        print("veille.json à jour" if ok else "veille.json DIFFÈRE de la source")
        sys.exit(0 if ok else 1)
    open(OUT, "w", encoding="utf-8").write(txt)
    print("écrit %s : %d dépôts" % (OUT, data["total"]))
