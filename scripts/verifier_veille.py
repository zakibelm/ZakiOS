"""Vérifie en direct (API publique GitHub, lecture seule, sans jeton) les dépôts PRÉSÉLECTIONNÉS de zakios/pilote/veille.json
et écrit un rapport des écarts avec les valeurs déclarées dans la feuille. À lancer là où internet est ouvert (ex. le VPS).

    python3 scripts/verifier_veille.py [--sortie docs/veille/verification-AAAA-MM-JJ.json] [--tous]

Aucune modification de veille.json : le rapport est un constat séparé. Limite de l'API anonyme : 60 requêtes/heure."""
import argparse, datetime, json, os, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMISSIVES = {"MIT", "Apache-2.0", "BSD-2-Clause"}
SPDX = {"Apache 2.0": "Apache-2.0", "MIT": "MIT", "BSD-2-Clause": "BSD-2-Clause", "AGPL v3": "AGPL-3.0", "MPL 2.0": "MPL-2.0"}


def telecharger(repo):
    req = urllib.request.Request("https://api.github.com/repos/" + repo, headers={"Accept": "application/vnd.github+json", "User-Agent": "zakios-veille"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def constat(dep, j, aujourdhui, jours_max=90):
    """Compare un dépôt de la feuille (dict de veille.json) à la réponse de l'API (dict). Fonction pure, testée hors ligne."""
    lic = (j.get("license") or {}).get("spdx_id")
    declaree = SPDX.get(dep["licence"] or "", dep["licence"])
    push = j.get("pushed_at", "")[:10]
    age = (aujourdhui - datetime.date.fromisoformat(push)).days if push else None
    ecarts = []
    if j.get("archived"):
        ecarts.append("ARCHIVÉ")
    if j.get("disabled"):
        ecarts.append("DÉSACTIVÉ")
    if lic in (None, "NOASSERTION"):
        ecarts.append("licence non détectée par GitHub")
    elif declaree not in (None, "À vérifier") and lic != declaree:
        ecarts.append("licence déclarée %s ≠ GitHub %s" % (dep["licence"], lic))
    elif declaree in (None, "À vérifier"):
        ecarts.append("licence « À vérifier » : GitHub indique %s" % lic)
    if lic not in (None, "NOASSERTION") and lic not in PERMISSIVES:
        ecarts.append("licence NON permissive (%s) : sort de la présélection" % lic)
    if age is None or age > jours_max:
        ecarts.append("inactif : dernier push %s" % (push or "inconnu"))
    if j.get("full_name", "").lower() != "/".join(dep["lien"].split("/")[-2:]).lower():
        ecarts.append("renommé/déplacé : %s" % j.get("full_name"))
    ds = dep["etoiles_declarees"]
    if ds and j.get("stargazers_count") and not (0.5 <= j["stargazers_count"] / ds <= 2):
        ecarts.append("étoiles déclarées %s vs réelles %s" % (ds, j["stargazers_count"]))
    return {"nom": dep["nom"], "repo": j.get("full_name"), "licence_github": lic, "etoiles_github": j.get("stargazers_count"),
            "dernier_push": push, "archive": bool(j.get("archived")), "ecarts": ecarts, "conforme": not ecarts}


def main(argv=None, fetch=telecharger, today=None, pause=0.3):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--tous", action="store_true", help="vérifier les 124 (au-delà de 60 requêtes/h il faut un jeton GitHub)")
    a = ap.parse_args(argv)
    today = today or datetime.date.today()
    data = json.load(open(os.path.join(ROOT, "zakios", "pilote", "veille.json"), encoding="utf-8"))
    cibles = [d for d in data["depots"] if (a.tous or d["preselection"])]
    out, erreurs = [], []
    for d in cibles:
        if not d["lien"]:
            erreurs.append({"nom": d["nom"], "erreur": "pas de lien dans la feuille"})
            continue
        repo = "/".join(d["lien"].split("/")[-2:])
        try:
            out.append(constat(d, fetch(repo), today))
        except urllib.error.HTTPError as e:
            erreurs.append({"nom": d["nom"], "erreur": "HTTP %s" % e.code})
        except Exception as e:                      # réseau, JSON : consigné, jamais ignoré
            erreurs.append({"nom": d["nom"], "erreur": type(e).__name__})
        time.sleep(pause)
    rapport = {"date": today.isoformat(), "source": "API publique GitHub, anonyme", "verifies": len(out), "erreurs": erreurs,
               "conformes": sum(1 for x in out if x["conforme"]), "resultats": out}
    sortie = a.sortie or os.path.join(ROOT, "docs", "veille", "verification-%s.json" % today.isoformat())
    json.dump(rapport, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%d vérifiés, %d conformes, %d erreurs -> %s" % (len(out), rapport["conformes"], len(erreurs), sortie))
    for x in out:
        if x["ecarts"]:
            print("-", x["nom"], "|", "; ".join(x["ecarts"]))
    for e in erreurs:
        print("! ", e["nom"], e["erreur"])
    return 0 if not erreurs else 2


if __name__ == "__main__":
    sys.exit(main())
