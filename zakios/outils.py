"""Analyse des appels d'outils d'un rôle à partir de son journal (événements `stream-json` de `claude -p`).

Distingue, pour chaque outil **demandé** hors de la liste autorisée (Read, Glob, Grep) :
  - `demande_refusee`     : la plateforme a refusé la demande (outil indisponible) ;
  - `execution_confirmee` : un résultat non erroné prouve que l'outil a été exécuté ;
  - `indetermine`         : on ne peut pas conclure (pas de résultat associé, résultat ambigu, contradiction).

Un refus n'est **pas** déduit du seul texte « No such tool » : on recoupe (1) le résultat lié à l'identifiant exact de
l'appel, (2) l'indicateur d'erreur du résultat, (3) le nom de l'outil cité dans le message, (4) l'absence de cet outil
dans la liste des outils effectifs annoncée à l'initialisation. Toute contradiction donne `indetermine`.
Fonction pure, sans entrée-sortie. Limite : elle juge ce que le journal montre ; elle ne prouve pas l'absence d'effet
hors journal (d'où le contrôle séparé de l'arbre du projet)."""
import json
import re

ALLOWED = ("Glob", "Grep", "Read")
STATUSES = ("demande_refusee", "execution_confirmee", "indetermine")
BLOCKING = ("execution_confirmee", "indetermine")


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def parse_events(log_text):
    out = []
    for line in log_text.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def analyse(events, effective_tools, allowed=ALLOWED):
    """Renvoie {"demandes": {outil: nombre}, "interdits": [évènement, ...]} pour un appel de rôle."""
    effective = set(effective_tools or [])
    calls, results = [], {}
    for e in events:
        msg = e.get("message") if isinstance(e, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if e.get("type") == "assistant" and c.get("type") == "tool_use":
                calls.append((c.get("id"), c.get("name")))
            if e.get("type") == "user" and c.get("type") == "tool_result":
                results.setdefault(c.get("tool_use_id"), []).append(c)
    demandes, interdits = {}, []
    for cid, name in calls:
        demandes[name] = demandes.get(name, 0) + 1
        if name in allowed:
            continue
        res = results.get(cid, [])
        ev = {"outil": name, "id": cid, "effectifs": sorted(effective)}
        if len(res) != 1:
            ev.update(statut="indetermine", preuve="%d résultat(s) associé(s) à l'appel" % len(res))
        else:
            r = res[0]
            msg = _text(r.get("content"))
            names_it = re.search(r"No such tool available:\s*%s\b" % re.escape(str(name)), msg) is not None
            if r.get("is_error") is True and names_it and name not in effective:
                ev.update(statut="demande_refusee",
                          preuve="résultat d'erreur lié à l'appel, message citant l'outil, outil absent de la liste effective")
            elif r.get("is_error") is not True:
                ev.update(statut="execution_confirmee", preuve="résultat non erroné lié à l'appel : %s" % msg[:120])
            else:
                ev.update(statut="indetermine",
                          preuve="résultat erroné ambigu (message citant l'outil : %s ; outil dans la liste effective : %s) : %s"
                                 % (names_it, name in effective, msg[:120]))
        interdits.append(ev)
    return {"demandes": demandes, "interdits": interdits}


def analyse_log(log_text, effective_tools=None):
    """Analyse un journal brut ; la liste des outils effectifs est lue dans l'évènement d'initialisation si absente."""
    events = parse_events(log_text)
    if effective_tools is None:
        effective_tools = next((e.get("tools", []) for e in events if e.get("type") == "system" and e.get("subtype") == "init"), [])
    return analyse(events, effective_tools)
