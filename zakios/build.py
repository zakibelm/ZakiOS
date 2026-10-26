"""Génération du catalogue : sources vérifiées -> registre -> validation -> remplacement atomique."""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict

try:  # verrou de fichier (Linux, macOS)
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from . import __version__, policy
from .classify import COMPONENT_TYPES
from .parse import is_yaml_marker
from .scan import SourceError, build_records, is_dirty, resolve_dir, verify_source
from .similarity import Index, vectorize

ROLES = ("catalogue", "socle", "existant", "propre")
REFERENCE_ROLES = ("socle", "existant")
# Rôles évalués et décidés par un humain : le catalogue externe et les composants propres de ZakiOS.
EVALUATED_ROLES = ("catalogue", "propre")
PROBLEM_LIMIT = 20
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
BUILD_EXACT = "exact"
BUILD_EXPERIMENTAL = "experimental_dirty"


class BuildError(Exception):
    pass


class ValidationError(Exception):
    pass


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load_manifest(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise BuildError("manifeste illisible : %s" % exc)
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise BuildError("le manifeste doit contenir une liste « sources »")
    seen = set()
    for src in sources:
        src.setdefault("required", True)
        needed = ("repo", "role") if not src["required"] else ("repo", "role", "commit")
        for key in needed:
            if not src.get(key):
                raise BuildError("source sans champ « %s » : %r" % (key, src))
        if src["role"] not in ROLES:
            raise BuildError("rôle inconnu « %s » pour %s" % (src["role"], src["repo"]))
        if src["repo"] in seen:
            raise BuildError("source en double : %s" % src["repo"])
        seen.add(src["repo"])
    return manifest, hashlib.sha256(raw).hexdigest()


def _recover(out_dir):
    """Si une génération précédente a été interrompue pendant le remplacement, on restaure."""
    bak = out_dir + ".bak"
    if not os.path.exists(out_dir) and os.path.isdir(bak):
        os.rename(bak, out_dir)


def _exchange(a, b):
    """Échange atomique de deux dossiers (Linux renameat2 RENAME_EXCHANGE). False si indisponible."""
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (ImportError, OSError, AttributeError):
        return False
    return renameat2(-100, os.fsencode(a), -100, os.fsencode(b), 2) == 0  # AT_FDCWD, RENAME_EXCHANGE


def _keep_previous(old_dir, out_dir):
    """Garde la génération précédente dans <out>.prev : un lecteur qui l'avait déjà ouverte peut finir sa lecture."""
    prev = out_dir + ".prev"
    if os.path.exists(prev):
        shutil.rmtree(prev, ignore_errors=True)
    os.rename(old_dir, prev)


def _swap(tmp_dir, out_dir):
    """Remplace out_dir par tmp_dir sans que out_dir disparaisse pour un lecteur.

    Chemin normal : échange atomique, l'ancien catalogue se retrouve dans tmp_dir et devient `.prev`.
    Repli (système sans échange atomique) : deux renommages ; si le second échoue, l'ancien catalogue
    est restauré immédiatement avant de relever l'erreur. Dans ce cas seulement, un court intervalle
    sans catalogue existe : la plateforme prise en charge est Linux.
    """
    if not os.path.exists(out_dir):
        os.rename(tmp_dir, out_dir)
        return
    if _exchange(tmp_dir, out_dir):
        _keep_previous(tmp_dir, out_dir)
        return
    bak = out_dir + ".bak"
    if os.path.exists(bak):
        shutil.rmtree(bak)
    os.rename(out_dir, bak)
    try:
        os.rename(tmp_dir, out_dir)
    except OSError:
        os.rename(bak, out_dir)
        raise
    _keep_previous(bak, out_dir)


class _Lock:
    """Un seul build à la fois par dossier de sortie."""

    def __init__(self, out_dir):
        self._path = out_dir + ".lock"
        self._handle = None

    def __enter__(self):
        if fcntl is None:
            raise BuildError("plateforme non prise en charge : le verrou de génération exige Linux ou macOS (fcntl)")
        self._handle = open(self._path, "a+")
        try:
            fcntl.flock(self._handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._handle.close()
            raise BuildError("une autre génération est déjà en cours pour %s" % os.path.basename(self._path[:-5]))
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._handle, fcntl.LOCK_UN)
        self._handle.close()


def _evaluate(records, provisional):
    """Ajoute à chaque composant du catalogue son évaluation et sa proposition."""
    vectors = vectorize([r["_sim_text"] for r in records])
    ids = [r["component_id"] for r in records]
    by_family = defaultdict(lambda: {"ref": [], "cat": []})
    for i, rec in enumerate(records):
        fam = policy.family_of(rec["type"])
        role = rec["provenance"]["role"]
        if rec["metadata_issue"]:  # quarantaine : ni référence, ni voisin, ni homonyme
            continue
        if role in REFERENCE_ROLES:
            by_family[fam]["ref"].append(i)
        elif role in EVALUATED_ROLES:
            by_family[fam]["cat"].append(i)
    indexes = {fam: (Index(vectors, ids, g["ref"]), Index(vectors, ids, g["cat"])) for fam, g in by_family.items()}
    ref_names = defaultdict(lambda: defaultdict(list))
    for fam, g in by_family.items():
        for i in g["ref"]:
            ref_names[fam][_slug(records[i]["name"])].append(ids[i])

    for i, rec in enumerate(records):
        if rec["provenance"]["role"] not in EVALUATED_ROLES:
            rec["evaluation"] = None
            rec["decision"] = None
            continue
        fam = policy.family_of(rec["type"])
        ref_idx, cat_idx = indexes[fam]
        invalid = bool(rec["metadata_issue"])
        cross_layer = []
        if invalid:
            # Quarantaine : un fichier mal lu n'est pas comparé sur le texte qui en reste.
            best_id, score, neighbors = None, 0.0, []
        else:
            best = ref_idx.top(vectors[i], 1)
            best_id, score = (ids[best[0][0]], best[0][1]) if best else (None, 0.0)
            neighbors = [{"component_id": ids[j], "score": s}
                         for j, s in cat_idx.top(vectors[i], 3, exclude=i)
                         if s >= policy.THRESHOLDS["neighbor"]]
            if fam in policy.CONTENT_FAMILIES:
                for other in policy.CONTENT_FAMILIES:
                    if other == fam or other not in indexes:
                        continue
                    hit = indexes[other][0].top(vectors[i], 1)
                    if hit and hit[0][1] >= policy.THRESHOLDS["partial_overlap"]:
                        cross_layer.append({"component_id": ids[hit[0][0]], "family": other, "score": hit[0][1]})
        status = policy.status_for(rec["type"], score, rec["_has_text"], invalid=invalid)
        if status == policy.STATUS_NOVELTY and cross_layer:
            status = policy.STATUS_CROSS_LAYER
        rec["evaluation"] = {
            "best_match_id": best_id,
            "score": score,
            "status": status,
            "homonym_of": [] if invalid else sorted(ref_names[fam].get(_slug(rec["name"]), []))[:5],
            "similar_in_catalog": neighbors,
            "cross_layer": cross_layer,
            "provisional_reason": policy.PROVISIONAL_REASON if provisional else None,
        }
        rec["decision"] = {
            "proposal": policy.PROPOSALS[status],
            "validated": None, "validated_by": None, "validated_on": None, "justification": "",
            "validated_fingerprint_sha256": None, "stale_validation": None,
        }


def _slug(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _apply_validated(records, decisions_path):
    """Fusionne les décisions validées par un humain, à condition que le contenu n'ait pas changé.

    Chaque validation porte l'empreinte du composant au moment de l'approbation
    (`fingerprint_sha256`). Si elle manque ou diffère, la validation est périmée : elle n'est pas
    appliquée et reste visible dans `stale_validation` pour une nouvelle revue.
    Renvoie (identifiants orphelins, validations périmées).
    """
    orphans, stale = [], []
    if not decisions_path or not os.path.exists(decisions_path):
        return orphans, stale
    with open(decisions_path, encoding="utf-8") as handle:
        validated = json.load(handle)
    by_id = {r["component_id"]: r for r in records}
    for cid, entry in sorted(validated.items()):
        value = entry.get("validated")
        if value is not None and value not in policy.ALLOWED_DECISIONS:
            raise BuildError("decisions : valeur « %s » non autorisée pour %s (autorisées : %s)"
                             % (value, cid, ", ".join(policy.ALLOWED_DECISIONS)))
        rec = by_id.get(cid)
        if rec is None or rec.get("decision") is None:
            orphans.append(cid)
            continue
        current = rec["provenance"]["fingerprint_sha256"]
        approved = entry.get("fingerprint_sha256")
        incomplete = not rec["provenance"]["fingerprint_complete"]
        if value is not None and (approved != current or incomplete):
            reason = ("empreinte incomplète : dépendances non explorées" if incomplete else
                      "empreinte absente" if not approved else "contenu modifié depuis la validation")
            rec["decision"]["stale_validation"] = {"validated": value, "reason": reason,
                                                   "approved_fingerprint_sha256": approved}
            stale.append({"component_id": cid, "reason": reason})
            continue
        for key in ("validated", "validated_by", "validated_on", "justification"):
            if key in entry:
                rec["decision"][key] = entry[key]
        rec["decision"]["validated_fingerprint_sha256"] = approved
    return orphans, stale


def _load_json_dict(path, label):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise BuildError("%s illisible : %s" % (label, exc))
    if not isinstance(data, dict):
        raise BuildError("%s doit être un objet JSON" % label)
    return data


def _apply_licenses(records, licenses_path):
    """Applique les licences vérifiées par un humain, par dépôt ou par composant.

    Une vérification est liée au commit lu (`commit`) : si le dépôt a avancé, elle est périmée et
    n'est pas appliquée. Une entrée par composant l'emporte sur l'entrée de son dépôt.
    """
    data = _load_json_dict(licenses_path, "licences")
    by_id = {r["component_id"]: r for r in records}
    by_repo = defaultdict(list)
    for rec in records:
        by_repo[rec["provenance"]["source"]].append(rec)
    orphans, stale = [], []
    ordered = sorted(data, key=lambda k: (k in by_id, k))  # dépôts d'abord, composants ensuite
    for key in ordered:
        entry = data[key]
        targets = [by_id[key]] if key in by_id else by_repo.get(key, [])
        if not targets:
            orphans.append(key)
            continue
        for field in ("spdx", "verified_by"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise BuildError("licences : champ « %s » requis pour %s" % (field, key))
        if entry.get("commit") != targets[0]["provenance"]["commit"]:
            stale.append(key)
            continue
        for rec in targets:
            rec["license"].update({"verified": True, "spdx": entry["spdx"], "attribution": entry.get("attribution"),
                                   "verified_by": entry["verified_by"], "verified_on": entry.get("verified_on"),
                                   "verified_commit": entry["commit"]})
    return orphans, stale


def _apply_annotations(records, annotations_path):
    """Relations (dépendances, conflits) et compatibilité déclarées par un humain."""
    data = _load_json_dict(annotations_path, "annotations")
    by_id = {r["component_id"]: r for r in records}
    orphans = []
    for cid in sorted(data):
        entry = data[cid]
        rec = by_id.get(cid)
        if rec is None:
            orphans.append(cid)
            continue
        for key in ("depends_on", "conflicts_with", "variant_of", "replaced_by"):
            if key in entry:
                if not isinstance(entry[key], list) or not all(isinstance(x, str) for x in entry[key]):
                    raise BuildError("annotations : « %s » doit être une liste d'identifiants (%s)" % (key, cid))
                rec["relations"][key] = sorted(set(entry[key]))
        for key in ("platform", "min_version"):
            if key in entry:
                rec["compatibility"][key] = entry[key]
    return orphans


def _crosswalk_csv(records):
    buf = io.StringIO(newline="")
    cols = ["component_id", "source", "path", "type", "name", "summary", "best_match_id", "score",
            "status", "homonym_of", "cross_layer", "proposal", "provisional_reason"]
    writer = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    writer.writeheader()
    for rec in records:
        ev = rec["evaluation"]
        if ev is None:
            continue
        writer.writerow({
            "component_id": rec["component_id"], "source": rec["provenance"]["source"],
            "path": rec["provenance"]["path"], "type": rec["type"], "name": rec["name"],
            "summary": rec["function"]["summary"], "best_match_id": ev["best_match_id"] or "",
            "score": ev["score"], "status": ev["status"], "homonym_of": ";".join(ev["homonym_of"]),
            "cross_layer": ";".join(m["component_id"] for m in ev["cross_layer"]),
            "proposal": rec["decision"]["proposal"], "provisional_reason": ev["provisional_reason"] or "",
        })
    return buf.getvalue()


def _counts(records):
    by_source = defaultdict(Counter)
    by_type = Counter()
    status = defaultdict(Counter)
    for rec in records:
        by_source[rec["provenance"]["source"]][rec["type"]] += 1
        by_type[rec["type"]] += 1
        if rec["evaluation"]:
            status[rec["type"]][rec["evaluation"]["status"]] += 1
    return ({k: dict(sorted(v.items())) for k, v in sorted(by_source.items())},
            dict(sorted(by_type.items())),
            {k: dict(sorted(v.items())) for k, v in sorted(status.items())})


def build(manifest_path, sources_root, out_dir, allow_dirty=False, decisions_path=None,
          licenses_path=None, annotations_path=None):
    """Génère le catalogue dans `out_dir`. En cas d'échec, le dernier catalogue valide reste intact.

    Avec `allow_dirty`, le résultat est marqué expérimental si une source a des modifications locales :
    ce n'est alors pas une reconstruction exacte du commit.
    """
    manifest, manifest_sha = load_manifest(manifest_path)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    with _Lock(out_dir):
        return _build_locked(manifest, manifest_sha, sources_root, out_dir, allow_dirty, decisions_path,
                             licenses_path, annotations_path)


def _build_locked(manifest, manifest_sha, sources_root, out_dir, allow_dirty, decisions_path,
                  licenses_path=None, annotations_path=None):
    _recover(out_dir)
    parent, base = os.path.dirname(out_dir), os.path.basename(out_dir)
    for leftover in os.listdir(parent):  # restes d'une génération interrompue (nous tenons le verrou)
        if leftover.startswith(base + ".tmp-"):
            shutil.rmtree(os.path.join(parent, leftover), ignore_errors=True)

    records, issues, source_status, dirty_sources = [], [], [], []
    for src in sorted(manifest["sources"], key=lambda s: s["repo"]):
        path = src.get("path") or resolve_dir(sources_root, src["repo"])
        if not path and not src["required"]:
            source_status.append({"repo": src["repo"], "role": src["role"], "status": "absente_facultative",
                                  "commit": src.get("commit"), "components": 0})
            continue
        try:
            path = verify_source(src, sources_root, allow_dirty)
        except SourceError as exc:
            raise BuildError(str(exc))
        dirty = allow_dirty and is_dirty(path)
        if dirty:
            dirty_sources.append(src["repo"])
        found = build_records(src, path, issues)
        records.extend(found)
        source_status.append({"repo": src["repo"], "role": src["role"],
                              "status": "modifiee_localement" if dirty else "verifiee",
                              "commit": src["commit"], "components": len(found)})

    records.sort(key=lambda r: r["component_id"])
    for rec in records:
        rec["schema_version"] = policy.SCHEMA_VERSION
    provisional = not any(r["provenance"]["role"] == "existant" for r in records)
    _evaluate(records, provisional)
    orphans, stale = _apply_validated(records, decisions_path)
    orphan_licenses, stale_licenses = _apply_licenses(records, licenses_path)
    orphan_annotations = _apply_annotations(records, annotations_path)
    build_mode = BUILD_EXPERIMENTAL if dirty_sources else BUILD_EXACT

    by_source, by_type, status_counts = _counts(records)
    registry_components = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
    report = {
        "schema_version": policy.SCHEMA_VERSION, "zakios_version": __version__, "manifest_sha256": manifest_sha,
        "build_mode": build_mode, "dirty_sources": sorted(dirty_sources),
        "sources": sorted(source_status, key=lambda s: s["repo"]),
        "counts_by_source_and_type": by_source, "counts_by_type": by_type, "evaluation_by_type": status_counts,
        "empty_summaries": sum(1 for r in records if not r["function"]["summary"]),
        "metadata_issues": sorted(issues, key=lambda i: (i["source"], i["path"])),
        "incomplete_fingerprints": sorted(r["component_id"] for r in records if not r["provenance"]["fingerprint_complete"]),
        "orphan_decisions": orphans, "stale_decisions": stale,
        "orphan_licenses": orphan_licenses, "stale_licenses": stale_licenses,
        "orphan_annotations": orphan_annotations, "provisional": provisional,
        "provisional_reason": policy.PROVISIONAL_REASON if provisional else None,
    }
    registry = {"schema_version": policy.SCHEMA_VERSION, "manifest_sha256": manifest_sha,
                "build_mode": build_mode, "components": registry_components}

    registry_text = _dump(registry)
    report["registry_sha256"] = hashlib.sha256(registry_text.encode("utf-8")).hexdigest()
    tmp_dir = tempfile.mkdtemp(prefix=os.path.basename(out_dir) + ".tmp-", dir=os.path.dirname(out_dir))
    try:
        for name, content in (("registry.json", registry_text), ("crosswalk.csv", _crosswalk_csv(registry_components)),
                              ("build_report.json", _dump(report))):
            with open(os.path.join(tmp_dir, name), "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
        validate_catalog(tmp_dir)
        os.chmod(tmp_dir, 0o755)  # mkdtemp crée en 0700
        _swap(tmp_dir, out_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return report


def _is_hex(pattern, value):
    return isinstance(value, str) and bool(pattern.match(value))


GENERATION_FILES = ("registry.json", "build_report.json", "crosswalk.csv")


def read_generation(directory):
    """Lit les trois fichiers d'une même génération, via un descripteur de dossier ouvert une seule fois.

    L'échange atomique ne change pas le dossier que ce descripteur désigne : même si une nouvelle
    génération est publiée pendant la lecture, on ne mélange pas ancien registre et nouveau rapport.
    Renvoie {nom: octets}.
    """
    last = None
    for _ in range(5):
        try:
            dir_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError as exc:
            raise ValidationError("catalogue illisible : %s" % exc)
        try:
            data = {}
            for name in GENERATION_FILES:
                fd = os.open(name, os.O_RDONLY, dir_fd=dir_fd)
                with os.fdopen(fd, "rb") as handle:
                    data[name] = handle.read()
            return data
        except OSError as exc:  # génération supprimée pendant la lecture : on recommence
            last = exc
        finally:
            os.close(dir_fd)
    raise ValidationError("catalogue illisible : %s" % last)


def validate_catalog(directory):
    """Vérifie un catalogue généré. Lève ValidationError avec la liste des problèmes."""
    return _validate_generation(read_generation(directory))[0]


def load_catalog(directory):
    """Lit et valide une génération en une seule lecture. Renvoie (registre, empreinte du registre)."""
    raw = read_generation(directory)
    _, registry = _validate_generation(raw)
    return registry, hashlib.sha256(raw["registry.json"]).hexdigest()


def _validate_generation(raw):
    problems = []
    try:
        registry = json.loads(raw["registry.json"].decode("utf-8"))
        report = json.loads(raw["build_report.json"].decode("utf-8"))
        csv_text = raw["crosswalk.csv"].decode("utf-8")
    except ValueError as exc:
        raise ValidationError("catalogue illisible : %s" % exc)
    if not isinstance(registry, dict) or not isinstance(report, dict):
        raise ValidationError("registre ou rapport mal formé")
    if report.get("registry_sha256") != hashlib.sha256(raw["registry.json"]).hexdigest():
        problems.append("le rapport ne correspond pas à ce registre (générations mélangées ou registre modifié)")

    comps = registry.get("components")
    if not isinstance(comps, list) or not comps:
        raise ValidationError("registre vide ou mal formé")
    if registry.get("schema_version") != policy.SCHEMA_VERSION:
        problems.append("version de schéma inattendue : %r" % registry.get("schema_version"))
    if report.get("schema_version") != registry.get("schema_version"):
        problems.append("rapport et registre n'ont pas la même version de schéma")
    if not _is_hex(_HEX64, registry.get("manifest_sha256")) or registry.get("manifest_sha256") != report.get("manifest_sha256"):
        problems.append("empreinte du manifeste absente ou différente entre registre et rapport")
    if registry.get("build_mode") not in (BUILD_EXACT, BUILD_EXPERIMENTAL) or registry.get("build_mode") != report.get("build_mode"):
        problems.append("mode de génération incohérent entre registre et rapport")
    if (registry.get("build_mode") == BUILD_EXACT) == bool(report.get("dirty_sources")):
        problems.append("mode de génération et sources modifiées incohérents")

    ids = [c.get("component_id") for c in comps if isinstance(c, dict)]
    if len(ids) != len(comps):
        raise ValidationError("composant mal formé dans le registre")
    id_set = set(ids)
    if len(ids) != len(id_set):
        problems.append("identifiants de composants en double")
    by_id = {c["component_id"]: c for c in comps}
    reference_roles = set(REFERENCE_ROLES)

    for c in comps:
        cid = c["component_id"]
        prov = c.get("provenance")
        if not isinstance(prov, dict):
            problems.append("%s : provenance absente" % cid)
            continue
        if c.get("type") not in COMPONENT_TYPES:
            problems.append("%s : type inconnu %r" % (cid, c.get("type")))
            continue
        if prov.get("role") not in ROLES:
            problems.append("%s : rôle inconnu %r" % (cid, prov.get("role")))
        if cid != "%s:%s" % (prov.get("source"), prov.get("path")):
            problems.append("%s : identifiant différent de source:chemin" % cid)
        if c.get("schema_version") != policy.SCHEMA_VERSION:
            problems.append("%s : version de schéma du composant inattendue" % cid)
        if not _is_hex(_HEX40, prov.get("commit")):
            problems.append("%s : commit incomplet ou non hexadécimal" % cid)
        for key in ("content_sha256", "fingerprint_sha256"):
            if not _is_hex(_HEX64, prov.get(key)):
                problems.append("%s : %s invalide" % (cid, key))
        if not isinstance(prov.get("fingerprint_complete"), bool) or not isinstance(prov.get("fingerprint_unexplored"), list):
            problems.append("%s : état de complétude de l'empreinte invalide" % cid)
        elif prov["fingerprint_complete"] == bool(prov["fingerprint_unexplored"]):
            problems.append("%s : complétude de l'empreinte incohérente avec les fichiers non explorés" % cid)
        files = prov.get("fingerprint_files")
        if not isinstance(files, list) or not files or prov.get("path") not in files:
            problems.append("%s : liste des fichiers de l'empreinte invalide" % cid)
        func = c.get("function")
        if not isinstance(func, dict) or not isinstance(func.get("summary"), str):
            problems.append("%s : résumé absent" % cid)
        elif is_yaml_marker(func["summary"]):
            problems.append("%s : marqueur YAML utilisé comme description" % cid)
        lic = c.get("license")
        if not isinstance(lic, dict) or not isinstance(lic.get("verified"), bool):
            problems.append("%s : bloc licence invalide" % cid)
        elif lic["verified"] and not (lic.get("spdx") and lic.get("verified_by")
                                      and lic.get("verified_commit") == prov.get("commit")):
            problems.append("%s : licence marquée vérifiée sans licence, vérificateur ou commit correspondant" % cid)
        rel = c.get("relations")
        if not isinstance(rel, dict) or any(not isinstance(rel.get(k), list) for k in
                                            ("depends_on", "conflicts_with", "variant_of", "replaced_by")):
            problems.append("%s : bloc relations invalide" % cid)
        else:
            for key in ("depends_on", "conflicts_with", "variant_of", "replaced_by"):
                for target in rel[key]:
                    if target not in id_set:
                        problems.append("%s : relation %s vers un composant inexistant" % (cid, key))

        ev, dec = c.get("evaluation"), c.get("decision")
        if prov.get("role") not in EVALUATED_ROLES:
            if ev is not None or dec is not None:
                problems.append("%s : évaluation sur un composant de référence" % cid)
            continue
        if not isinstance(ev, dict) or not isinstance(dec, dict):
            problems.append("%s : évaluation ou décision absente" % cid)
            continue
        status = ev.get("status")
        if status not in policy.STATUSES:
            problems.append("%s : statut inconnu %r" % (cid, status))
            continue
        if c["type"] in policy.BEHAVIOR_TYPES and status not in (policy.STATUS_BEHAVIOR, policy.STATUS_INVALID):
            problems.append("%s : un hook, plugin ou mod ne peut pas être décidé automatiquement" % cid)
        if c.get("metadata_issue") and status != policy.STATUS_INVALID:
            problems.append("%s : métadonnées invalides non mises en quarantaine" % cid)
        if status == policy.STATUS_INVALID and not c.get("metadata_issue"):
            problems.append("%s : statut « métadonnées invalides » sans problème enregistré" % cid)
        score = ev.get("score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 1.0001:
            problems.append("%s : score invalide" % cid)
        elif status in (policy.STATUS_EQUIVALENCE, policy.STATUS_PARTIAL, policy.STATUS_NOVELTY) \
                and policy.status_for(c["type"], score, True) != status:
            problems.append("%s : statut incohérent avec le score" % cid)
        elif status == policy.STATUS_CROSS_LAYER and (score >= policy.THRESHOLDS["partial_overlap"] or not ev.get("cross_layer")):
            problems.append("%s : chevauchement inter-couches incohérent" % cid)
        best = ev.get("best_match_id")
        if best is not None:
            target = by_id.get(best)
            if target is None or target["provenance"].get("role") not in reference_roles \
                    or policy.family_of(target["type"]) != policy.family_of(c["type"]) or target.get("metadata_issue"):
                problems.append("%s : meilleur équivalent invalide (%s)" % (cid, best))
        refs = [("homonym_of", t) for t in ev.get("homonym_of", [])]
        refs += [(k, item.get("component_id")) for k in ("similar_in_catalog", "cross_layer") for item in ev.get(k, [])]
        for key, target in refs:
            if target not in id_set:
                problems.append("%s : %s référence un composant inexistant" % (cid, key))
            elif by_id[target].get("metadata_issue"):
                problems.append("%s : %s référence un composant aux métadonnées invalides" % (cid, key))
        if "adopter" in dec.get("proposal", "").lower():
            problems.append("%s : proposition affirmative non prouvable" % cid)
        if dec.get("proposal") != policy.PROPOSALS[status]:
            problems.append("%s : proposition différente de la politique" % cid)
        value = dec.get("validated")
        if value is not None:
            if value not in policy.ALLOWED_DECISIONS:
                problems.append("%s : décision validée non autorisée %r" % (cid, value))
            if prov.get("fingerprint_complete") is not True:
                problems.append("%s : décision validée sur une empreinte incomplète" % cid)
            if dec.get("validated_fingerprint_sha256") != prov.get("fingerprint_sha256"):
                problems.append("%s : décision validée liée à un autre contenu" % cid)

    # Comptes recalculés à partir du registre, comparés au rapport.
    by_source, by_type, status_counts = _counts(comps)
    if report.get("counts_by_source_and_type") != by_source:
        problems.append("rapport : comptes par source et par type différents du registre")
    if report.get("counts_by_type") != by_type:
        problems.append("rapport : comptes par type différents du registre")
    if report.get("evaluation_by_type") != status_counts:
        problems.append("rapport : comptes par statut différents du registre")
    for src in report.get("sources", []):
        if src.get("components") != sum(by_source.get(src.get("repo"), {}).values()):
            problems.append("rapport : nombre de composants de %s différent du registre" % src.get("repo"))
    if report.get("empty_summaries") != sum(1 for c in comps if not c["function"]["summary"]):
        problems.append("rapport : nombre de résumés vides différent du registre")
    if report.get("incomplete_fingerprints") != sorted(c["component_id"] for c in comps
                                                      if c["provenance"].get("fingerprint_complete") is False):
        problems.append("rapport : empreintes incomplètes différentes du registre")
    if len(report.get("metadata_issues", [])) != sum(1 for c in comps if c.get("metadata_issue")):
        problems.append("rapport : problèmes de métadonnées différents du registre")

    # Le CSV est une vue du registre : on le régénère et on compare octet pour octet.
    try:
        if csv_text != _crosswalk_csv(comps):
            problems.append("crosswalk.csv différent du registre")
    except (KeyError, TypeError):
        problems.append("crosswalk.csv impossible à recalculer : registre mal formé")

    if problems:
        raise ValidationError("; ".join(problems[:PROBLEM_LIMIT]) + (" ..." if len(problems) > PROBLEM_LIMIT else ""))
    evaluated = sum(1 for c in comps if c.get("evaluation") is not None)
    return {"components": len(comps), "evaluated": evaluated, "build_mode": registry["build_mode"]}, registry
