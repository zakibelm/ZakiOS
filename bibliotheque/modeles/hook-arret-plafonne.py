#!/usr/bin/env python3
"""Modèle ZakiOS (brouillon, contenu original) : hook Stop qui oblige l'agent à continuer tant qu'un contrôle échoue,
avec un PLAFOND d'essais pour qu'il ne boucle jamais sans fin.

Risque visé : un hook d'arrêt qui répond toujours « continue » épuise les tokens (voir docs/PRATIQUES.md, section 3).
Réglages par variables d'environnement :
  ZAKIOS_STOP_CHECK   commande de contrôle (ex. « python3 -m unittest discover -s tests -t . »). Absente : le hook laisse arrêter.
  ZAKIOS_STOP_MAX     nombre maximal de refus d'arrêt (défaut 3).
  ZAKIOS_STOP_TIMEOUT délai du contrôle en secondes (défaut 120).
Contrat : code 0 = l'agent peut s'arrêter ; code 2 = il ne s'arrête pas, le message (stderr) lui est renvoyé.
Un hook n'est jamais validé par un score : audit par comportement obligatoire (docs/GRILLE-AUDIT-HOOKS.md, contrôle 2).
"""
import json
import os
import re
import subprocess
import sys


def main():
    commande = os.environ.get("ZAKIOS_STOP_CHECK", "").strip()
    if not commande:
        return 0
    maximum = int(os.environ.get("ZAKIOS_STOP_MAX", "3"))
    delai = int(os.environ.get("ZAKIOS_STOP_TIMEOUT", "120"))
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    session = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id", "sans-session")))[:64]
    dossier = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()), ".claude", "state")
    compteur = os.path.join(dossier, "stop-%s.count" % session)

    try:
        r = subprocess.run(commande, shell=True, capture_output=True, text=True, timeout=delai)
        ok, sortie = r.returncode == 0, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        ok, sortie = False, "le contrôle a dépassé %d s" % delai

    if ok:
        if os.path.exists(compteur):
            os.remove(compteur)
        return 0

    essais = 0
    if os.path.exists(compteur):
        try:
            essais = int(open(compteur).read().strip() or 0)
        except ValueError:
            essais = 0
    essais += 1
    if essais > maximum:  # plafond atteint : on libère l'agent et on le dit
        os.remove(compteur) if os.path.exists(compteur) else None
        sys.stderr.write("Plafond de %d essais atteint : arrêt autorisé. Le contrôle échoue encore ; à signaler à la personne.\n" % maximum)
        return 0
    os.makedirs(dossier, exist_ok=True)
    with open(compteur, "w") as fh:
        fh.write(str(essais))
    fin = "\n".join(sortie.strip().splitlines()[-20:])
    sys.stderr.write("Contrôle en échec (essai %d/%d). Action : corriger puis relancer le contrôle.\n%s\n" % (essais, maximum, fin))
    return 2


if __name__ == "__main__":
    sys.exit(main())
