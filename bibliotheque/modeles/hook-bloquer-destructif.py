#!/usr/bin/env python3
"""Modèle ZakiOS (brouillon, contenu original) : hook PreToolUse qui refuse les commandes Bash destructrices.

Idée tirée d'un exemple de la littérature Claude Code (voir bibliotheque/exemples.json) ; code réécrit ici.
Contrat : l'agent envoie un JSON sur l'entrée standard. Code 0 = laisser passer ; code 2 = bloquer, le message sur
stderr retourne à l'agent (Problème -> Action). Échec fermé : une entrée illisible bloque au lieu de laisser passer.
Un hook n'est jamais validé par un score : audit par comportement obligatoire (docs/GRILLE-AUDIT-HOOKS.md).

Installation (exemple, .claude/settings.json) :
  {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
     "command": "python3 \\"$CLAUDE_PROJECT_DIR/.claude/hooks/bloquer-destructif.py\\""}]}]}}
"""
import json
import re
import sys

REGLES = [
    (r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR])\b[^|;&]*(\s/(\s|$)|\s~|\s\*|\s\.\s*$|\s\$HOME)",
     "suppression récursive forcée sur la racine, le dossier personnel ou tout le répertoire",
     "supprimer des chemins précis et demander la confirmation de la personne"),
    (r"\bgit\s+reset\s+--hard\b", "perte des modifications non enregistrées",
     "utiliser `git stash` ou demander la confirmation de la personne"),
    (r"\bgit\s+push\b[^|;&]*(--force\b|--force-with-lease\b|\s-f\b)", "réécriture de l'historique distant",
     "pousser sans force, ou demander la confirmation de la personne"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*[fF]", "suppression de fichiers non suivis", "lister d'abord avec `git clean -n`"),
    (r"\b(drop|truncate)\s+(table|database)\b", "destruction de données SQL", "sauvegarder puis demander la confirmation"),
    (r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(ba|z)?sh\b", "exécution de code distant non relu",
     "télécharger, relire, puis exécuter"),
    (r"\bdd\s+if=|\bmkfs(\.|\s)|>\s*/dev/sd", "écriture directe sur un disque", "ne jamais le faire depuis un agent"),
    (r"\bchmod\s+-R\s+777\b", "permissions ouvertes à tous", "donner la permission minimale nécessaire"),
]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("Bloqué : entrée du hook illisible. Action : corriger la configuration du hook.\n")
        return 2
    if data.get("tool_name") != "Bash":
        return 0
    commande = str((data.get("tool_input") or {}).get("command", ""))
    for motif, probleme, action in REGLES:
        if re.search(motif, commande, re.IGNORECASE):
            sys.stderr.write("Bloqué : %s. Action : %s.\n" % (probleme, action))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
