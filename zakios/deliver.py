"""Enregistrement contrôlé d'un plan produit par un agent en lecture seule.

L'agent raisonne et retourne le plan ; ce module, déterministe, l'écrit. Il ne lit ni n'exécute
jamais le contenu du plan. Contrat :
- destination : un fichier .md sous docs/plans/, nom simple, chemin relatif sans « .. » ;
- liens symboliques refusés (couche Root : descente avec O_NOFOLLOW) ;
- jamais d'écrasement : contenu identique -> « deja_enregistre » sans écriture ; contenu différent -> refus ;
- création atomique sans remplacement (os.link), donc sûre en cas de créations concurrentes ;
- le plan présenté est lié par son empreinte : l'enregistrement exige celle de l'aperçu ;
- une trace (chemin, empreinte, mission) est écrite sous .zakios/deliverables/, de façon idempotente.
"""
import hashlib
import json
import os
import re
import time

from .activate import ActivationError, Root, UnsafePath

PLANS_DIR = "docs/plans"
MAX_BYTES = 1024 * 1024
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.md$")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class DeliveryError(ActivationError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def check_path(rel):
    """Chemin accepté : docs/plans/[sous-dossiers/]nom.md. Lève DeliveryError sinon."""
    if not isinstance(rel, str) or not rel or "\0" in rel or rel.startswith("/") or "\\" in rel:
        raise DeliveryError("chemin refusé (vide, absolu ou invalide) : %r" % (rel,))
    parts = rel.split("/")
    if parts[:2] != ["docs", "plans"] or len(parts) < 3:
        raise DeliveryError("chemin hors de %s/ : %s" % (PLANS_DIR, rel))
    if any(p in ("", ".", "..") for p in parts) or not all(_SEGMENT.match(p) for p in parts[2:-1]) \
            or not _NAME.match(parts[-1]):
        raise DeliveryError("nom de fichier refusé (Markdown simple attendu, sans « .. ») : %s" % rel)
    return parts


def _content(content):
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if not data.strip():
        raise DeliveryError("plan vide : rien à enregistrer")
    if len(data) > MAX_BYTES or b"\0" in data:
        raise DeliveryError("plan refusé (trop volumineux ou binaire)")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise DeliveryError("plan refusé (texte UTF-8 attendu)")
    return data


def preview(rel_path, content):
    """Ce qui serait enregistré, sans rien écrire (ni lire le projet)."""
    check_path(rel_path)
    data = _content(content)
    return {"path": rel_path, "sha256": _sha(data), "bytes": len(data)}


def save_plan(project, rel_path, content, expected_sha256, mission="", fault=None):
    """Enregistre le plan. `expected_sha256` est l'empreinte de l'aperçu présenté à la personne."""
    check_path(rel_path)
    data = _content(content)
    sha = _sha(data)
    if expected_sha256 != sha:
        raise DeliveryError("le plan à enregistrer n'est pas celui qui a été présenté (empreinte différente)")
    trace_rel = ".zakios/deliverables/%s.json" % sha
    trace = {"path": rel_path, "sha256": sha, "mission": mission, "presented_sha256": expected_sha256,
             "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def hit(point):
        if fault:
            fault(point)

    try:
        with Root(project) as root:
            try:
                existing = root.read(rel_path)
                occupied = existing is not None or root.lexists(rel_path)
            except UnsafePath as exc:
                raise DeliveryError("chemin non sûr, refusé : %s" % exc)
            status = None
            if occupied:
                if existing is not None and _sha(existing) == sha:
                    status = "deja_enregistre"
                else:
                    raise DeliveryError("%s existe déjà avec un autre contenu : écrasement refusé" % rel_path)
            else:
                hit("avant_ecriture")
                try:
                    root.write_atomic(rel_path, data, replace=False)
                    status = "enregistre"
                except FileExistsError:  # création concurrente : identique -> déjà enregistré, sinon refus
                    again = root.read(rel_path)
                    if again is not None and _sha(again) == sha:
                        status = "deja_enregistre"
                    else:
                        raise DeliveryError("%s a été créé entre-temps avec un autre contenu : écrasement refusé" % rel_path)
                hit("apres_ecriture")
            try:
                root.write_atomic(trace_rel, (json.dumps(trace, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode(),
                                  replace=False)
            except FileExistsError:
                pass  # trace déjà présente : idempotent
    except UnsafePath as exc:
        raise DeliveryError("chemin non sûr, refusé : %s" % exc)
    return {"status": status, "path": rel_path, "sha256": sha, "trace": trace_rel}
