"""Lecture des métadonnées (frontmatter YAML) avec un parseur sûr.

Aucune expression régulière ne sert à interpréter le YAML : les descriptions
multilignes (`|`, `>-`), les listes et les champs absents sont gérés par PyYAML.
Une erreur n'est jamais silencieuse : elle est renvoyée à l'appelant.
"""
import re

import yaml

_FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.S)
_EXAMPLE = re.compile(r"<example>", re.I)
_YAML_MARKER = re.compile(r"^\s*[|>][-+]?\s*$")


def parse_frontmatter(text):
    """Renvoie (métadonnées, corps, problème). Le problème vaut None si tout va bien."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text, None
    raw, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else "erreur YAML"
        return {}, body, "yaml_invalide: " + first
    if data is None:
        return {}, body, None
    if not isinstance(data, dict):
        return {}, body, "frontmatter_non_mapping"
    return data, body, None


def norm(value):
    """Texte normalisé : espaces réduits, listes jointes, absent -> chaîne vide."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(norm(v) for v in value)
    return re.sub(r"\s+", " ", str(value)).strip()


def summarize(description, limit=240):
    """Résumé court : on coupe avant les blocs d'exemples, puis on tronque."""
    text = _EXAMPLE.split(str(description or ""), maxsplit=1)[0]
    text = norm(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def first_prose_line(body, minimum=25):
    """Première ligne de prose du corps (hors titres de code, tableaux, listes)."""
    for line in str(body).splitlines():
        stripped = line.strip().lstrip("#").strip()
        if len(stripped) >= minimum and not stripped.startswith(("```", "|", "<", "-", "*", "!", "[")):
            return norm(stripped)
    return ""


def is_yaml_marker(text):
    """Vrai si le texte n'est qu'un marqueur de bloc YAML (`|`, `>`, `>-`...)."""
    return bool(_YAML_MARKER.match(str(text or "")))
