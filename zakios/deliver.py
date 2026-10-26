"""Enregistrement contrôlé d'un plan produit par un agent en lecture seule.

L'agent raisonne et retourne le plan ; ce module, déterministe, l'écrit. Il ne lit ni n'exécute
jamais le contenu du plan. Contrat :
- destination : un fichier .md sous docs/plans/, nom simple, chemin relatif sans « .. » ;
- liens symboliques refusés (couche Root : descente avec O_NOFOLLOW) ;
- jamais d'écrasement : contenu identique -> « deja_enregistre » sans écriture ; contenu différent -> refus ;
- création atomique sans remplacement (os.link), donc sûre en cas de créations concurrentes ;
- la livraison présentée est liée par son empreinte `delivery_sha256` (version du format, chemin cible, empreinte
  du contenu, mission) : changer le chemin ou la mission impose un nouvel aperçu ;
- une trace par livraison est écrite sous .zakios/deliverables/<delivery_sha256>.json ; si elle existe déjà,
  son contenu est vérifié et une incohérence est une erreur explicite ;
- `extract_plan` n'accepte qu'un livrable délimité et sans ambiguïté, et préserve exactement ses octets.
"""
import hashlib
import json
import os
import re
import time

from .activate import ActivationError, Root, UnsafePath

PLANS_DIR = "docs/plans"
FORMAT_VERSION = 1
BEGIN = "=== DEBUT DU PLAN ZAKIOS ==="
END = "=== FIN DU PLAN ZAKIOS ==="
_PATH_LINE = re.compile(r"^Chemin proposé\s*:\s*`?(docs/plans/[^`\s]+)`?\s*$", re.M)
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


def delivery_sha256(rel_path, content_sha256, mission=""):
    """Identité de la livraison : format, chemin cible, contenu, mission."""
    canonical = json.dumps({"v": FORMAT_VERSION, "path": rel_path, "content_sha256": content_sha256,
                            "mission": mission}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _sha(canonical.encode("utf-8"))


def extract_plan(text):
    """(plan, chemin proposé) d'après la réponse d'un agent. Refuse un livrable absent ou ambigu.

    Format imposé : une seule ligne « Chemin proposé : docs/plans/….md » hors du bloc, puis un seul bloc
    entre les lignes BEGIN et END dont la première ligne non vide est un titre « # ». Les octets du bloc
    (hors les lignes de délimitation) sont renvoyés tels quels."""
    lines = text.split("\n")
    begins = [i for i, l in enumerate(lines) if l.strip() == BEGIN]
    ends = [i for i, l in enumerate(lines) if l.strip() == END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise DeliveryError("livrable absent ou ambigu : un seul bloc %s … %s attendu" % (BEGIN, END))
    outside = "\n".join(lines[:begins[0]] + lines[ends[0] + 1:])
    paths = _PATH_LINE.findall(outside)
    if len(paths) != 1:
        raise DeliveryError("chemin proposé absent ou multiple (une seule ligne « Chemin proposé : docs/plans/….md » attendue)")
    body = "\n".join(lines[begins[0] + 1:ends[0]])
    first = next((l for l in body.split("\n") if l.strip()), "")
    if not re.match(r"^# \S", first):
        raise DeliveryError("le plan doit commencer par un titre de niveau 1 (« # … »)")
    check_path(paths[0])
    return body + "\n", paths[0]


def preview(rel_path, content, mission=""):
    """Ce qui serait enregistré, sans rien écrire (ni lire le projet)."""
    check_path(rel_path)
    data = _content(content)
    return {"path": rel_path, "mission": mission, "bytes": len(data), "content_sha256": _sha(data),
            "delivery_sha256": delivery_sha256(rel_path, _sha(data), mission)}


def _same_trace(found, wanted):
    keys = ("v", "path", "content_sha256", "mission", "delivery_sha256")
    return all(found.get(k) == wanted.get(k) for k in keys)


def save_plan(project, rel_path, content, expected_delivery_sha256, mission="", fault=None):
    """Enregistre le plan. `expected_delivery_sha256` est celui de l'aperçu présenté à la personne."""
    check_path(rel_path)
    data = _content(content)
    sha = _sha(data)
    delivery = delivery_sha256(rel_path, sha, mission)
    if expected_delivery_sha256 != delivery:
        raise DeliveryError("la livraison (contenu, chemin ou mission) n'est pas celle qui a été présentée : nouvel aperçu requis")
    trace_rel = ".zakios/deliverables/%s.json" % delivery
    trace = {"v": FORMAT_VERSION, "path": rel_path, "content_sha256": sha, "mission": mission,
             "delivery_sha256": delivery, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def hit(point):
        if fault:
            fault(point)

    try:
        with Root(project) as root:
            try:
                existing = root.read(rel_path)
                occupied = existing is not None or root.lexists(rel_path)
                old_trace = root.read(trace_rel)
            except UnsafePath as exc:
                raise DeliveryError("chemin non sûr, refusé : %s" % exc)
            if old_trace is not None:  # trace déjà là : elle doit décrire exactement cette livraison
                try:
                    found = json.loads(old_trace.decode("utf-8"))
                except ValueError:
                    raise DeliveryError("trace %s illisible : incohérence, rien n'est écrit" % trace_rel)
                if not isinstance(found, dict) or not _same_trace(found, trace):
                    raise DeliveryError("trace %s incohérente avec la livraison : rien n'est écrit" % trace_rel)
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
            if old_trace is None:
                try:
                    root.write_atomic(trace_rel, (json.dumps(trace, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode(),
                                      replace=False)
                except FileExistsError:  # trace écrite entre-temps par une livraison identique ? vérifier
                    found = json.loads((root.read(trace_rel) or b"{}").decode("utf-8"))
                    if not _same_trace(found, trace):
                        raise DeliveryError("trace %s incohérente avec la livraison" % trace_rel)
    except UnsafePath as exc:
        raise DeliveryError("chemin non sûr, refusé : %s" % exc)
    return {"status": status, "path": rel_path, "content_sha256": sha, "delivery_sha256": delivery, "trace": trace_rel}
