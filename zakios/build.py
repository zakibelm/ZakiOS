"""Génération du catalogue : sources vérifiées -> registre -> validation -> remplacement atomique."""
import csv
import hashlib
import io
import json
import os
import shutil
from collections import Counter, defaultdict

from . import __version__, policy
from .parse import is_yaml_marker
from .scan import SourceError, build_records, resolve_dir, verify_source
from .similarity import Index, vectorize

ROLES = ("catalogue", "socle", "existant")
REFERENCE_ROLES = ("socle", "existant")
PROBLEM_LIMIT = 20


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


def _swap(tmp_dir, out_dir):
    bak = out_dir + ".bak"
    if os.path.exists(bak):
        shutil.rmtree(bak)
    if os.path.exists(out_dir):
        os.rename(out_dir, bak)
    os.rename(tmp_dir, out_dir)
    shutil.rmtree(bak, ignore_errors=True)


def _evaluate(records, provisional):
    """Ajoute à chaque composant du catalogue son évaluation et sa proposition."""
    vectors = vectorize([r["_sim_text"] for r in records])
    ids = [r["component_id"] for r in records]
    by_family = defaultdict(lambda: {"ref": [], "cat": []})
    for i, rec in enumerate(records):
        fam = policy.family_of(rec["type"])
        role = rec["provenance"]["role"]
        if role in REFERENCE_ROLES:
            by_family[fam]["ref"].append(i)
        elif role == "catalogue":
            by_family[fam]["cat"].append(i)
    indexes = {fam: (Index(vectors, ids, g["ref"]), Index(vectors, ids, g["cat"])) for fam, g in by_family.items()}
    ref_names = defaultdict(lambda: defaultdict(list))
    for fam, g in by_family.items():
        for i in g["ref"]:
            ref_names[fam][_slug(records[i]["name"])].append(ids[i])

    for i, rec in enumerate(records):
        if rec["provenance"]["role"] != "catalogue":
            rec["evaluation"] = None
            rec["decision"] = None
            continue
        fam = policy.family_of(rec["type"])
        ref_idx, cat_idx = indexes[fam]
        best = ref_idx.top(vectors[i], 1)
        best_id, score = (ids[best[0][0]], best[0][1]) if best else (None, 0.0)
        neighbors = [{"component_id": ids[j], "score": s}
                     for j, s in cat_idx.top(vectors[i], 3, exclude=i)
                     if s >= policy.THRESHOLDS["neighbor"]]
        status = policy.status_for(rec["type"], score, rec["_has_text"])
        rec["evaluation"] = {
            "best_match_id": best_id,
            "score": score,
            "status": status,
            "homonym_of": sorted(ref_names[fam].get(_slug(rec["name"]), []))[:5],
            "similar_in_catalog": neighbors,
            "provisional_reason": policy.PROVISIONAL_REASON if provisional else None,
        }
        rec["decision"] = {
            "proposal": policy.PROPOSALS[status],
            "validated": None, "validated_by": None, "validated_on": None, "justification": "",
        }


def _slug(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _apply_validated(records, decisions_path):
    """Fusionne les décisions validées par un humain. Elles ne sont jamais écrasées par une génération."""
    orphans = []
    if not decisions_path or not os.path.exists(decisions_path):
        return orphans
    with open(decisions_path, encoding="utf-8") as handle:
        validated = json.load(handle)
    by_id = {r["component_id"]: r for r in records}
    for cid, entry in sorted(validated.items()):
        rec = by_id.get(cid)
        if rec is None or rec.get("decision") is None:
            orphans.append(cid)
            continue
        for key in ("validated", "validated_by", "validated_on", "justification"):
            if key in entry:
                rec["decision"][key] = entry[key]
    return orphans


def _crosswalk_csv(records):
    buf = io.StringIO(newline="")
    cols = ["component_id", "source", "path", "type", "name", "summary", "best_match_id", "score",
            "status", "homonym_of", "proposal", "provisional_reason"]
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


def build(manifest_path, sources_root, out_dir, allow_dirty=False, decisions_path=None):
    """Génère le catalogue dans `out_dir`. En cas d'échec, le dernier catalogue valide reste intact."""
    manifest, manifest_sha = load_manifest(manifest_path)
    out_dir = os.path.abspath(out_dir)
    _recover(out_dir)

    records, issues, source_status = [], [], []
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
        found = build_records(src, path, issues)
        records.extend(found)
        source_status.append({"repo": src["repo"], "role": src["role"], "status": "verifiee",
                              "commit": src["commit"], "components": len(found)})

    records.sort(key=lambda r: r["component_id"])
    for rec in records:
        rec["schema_version"] = policy.SCHEMA_VERSION
    provisional = not any(r["provenance"]["role"] == "existant" for r in records)
    _evaluate(records, provisional)
    orphans = _apply_validated(records, decisions_path)

    by_source, by_type, status_counts = _counts(records)
    registry_components = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
    report = {
        "schema_version": policy.SCHEMA_VERSION, "zakios_version": __version__, "manifest_sha256": manifest_sha,
        "sources": sorted(source_status, key=lambda s: s["repo"]),
        "counts_by_source_and_type": by_source, "counts_by_type": by_type, "evaluation_by_type": status_counts,
        "empty_summaries": sum(1 for r in records if not r["function"]["summary"]),
        "metadata_issues": sorted(issues, key=lambda i: (i["source"], i["path"])),
        "orphan_decisions": orphans, "provisional": provisional,
        "provisional_reason": policy.PROVISIONAL_REASON if provisional else None,
    }
    registry = {"schema_version": policy.SCHEMA_VERSION, "manifest_sha256": manifest_sha,
                "components": registry_components}

    tmp_dir = out_dir + ".tmp"
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)
    try:
        for name, content in (("registry.json", _dump(registry)), ("crosswalk.csv", _crosswalk_csv(records)),
                              ("build_report.json", _dump(report))):
            with open(os.path.join(tmp_dir, name), "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
        validate_catalog(tmp_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    _swap(tmp_dir, out_dir)
    return report


def validate_catalog(directory):
    """Vérifie un catalogue généré. Lève ValidationError avec la liste des problèmes."""
    problems = []
    try:
        with open(os.path.join(directory, "registry.json"), encoding="utf-8") as handle:
            registry = json.load(handle)
        with open(os.path.join(directory, "build_report.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        with open(os.path.join(directory, "crosswalk.csv"), encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, ValueError) as exc:
        raise ValidationError("catalogue illisible : %s" % exc)

    comps = registry.get("components", [])
    if registry.get("schema_version") != policy.SCHEMA_VERSION:
        problems.append("version de schéma inattendue : %r" % registry.get("schema_version"))
    if not comps:
        problems.append("registre vide")
    ids = [c.get("component_id") for c in comps]
    if len(ids) != len(set(ids)):
        problems.append("identifiants de composants en double")
    for c in comps:
        cid = c.get("component_id")
        prov = c.get("provenance", {})
        if len(prov.get("commit", "")) != 40:
            problems.append("%s : commit incomplet" % cid)
        if not prov.get("content_sha256"):
            problems.append("%s : empreinte de contenu absente" % cid)
        if is_yaml_marker(c.get("function", {}).get("summary", "")):
            problems.append("%s : marqueur YAML utilisé comme description" % cid)
        ev = c.get("evaluation")
        if ev is None:
            continue
        if c["type"] in policy.BEHAVIOR_TYPES and ev["status"] != policy.STATUS_BEHAVIOR:
            problems.append("%s : un hook, plugin ou mod ne peut pas être décidé automatiquement" % cid)
        if ev["status"] not in policy.STATUSES:
            problems.append("%s : statut inconnu %r" % (cid, ev["status"]))
        if "adopter" in c["decision"]["proposal"].lower():
            problems.append("%s : proposition affirmative non prouvable" % cid)
    evaluated = [c for c in comps if c.get("evaluation") is not None]
    if len(rows) != len(evaluated):
        problems.append("crosswalk.csv : %d lignes pour %d composants évalués" % (len(rows), len(evaluated)))
    if sum(report.get("counts_by_type", {}).values()) != len(comps):
        problems.append("build_report.json : comptes incohérents avec le registre")
    if problems:
        raise ValidationError("; ".join(problems[:PROBLEM_LIMIT]) + (" ..." if len(problems) > PROBLEM_LIMIT else ""))
    return {"components": len(comps), "evaluated": len(evaluated)}
