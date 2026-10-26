"""Vérification des sources figées et construction des enregistrements de composants."""
import hashlib
import json
import os
import re
import subprocess

from .classify import classify
from .parse import first_prose_line, norm, parse_frontmatter, summarize

_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SCRIPT_HEADER = re.compile(r'(?:"""|\'\'\'|/\*\*?|#!?[^\n]*\n\s*#|//)\s*(.{20,240}?)(?:\n\s*\n|\*/|"""|\'\'\'|\n)', re.S)


class SourceError(Exception):
    """Une source obligatoire est absente, modifiée ou ne correspond pas au manifeste."""


def _git(path, *args):
    result = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def resolve_dir(sources_root, repo):
    for candidate in (repo, repo.lower()):
        path = os.path.join(sources_root, *candidate.split("/"))
        if os.path.isdir(path):
            return path
    return None


def verify_source(src, sources_root, allow_dirty=False):
    """Vérifie qu'une source locale correspond exactement au manifeste. Renvoie son chemin."""
    repo = src["repo"]
    expected = src.get("commit", "")
    if not _FULL_COMMIT.match(expected):
        raise SourceError("%s : le manifeste doit donner un commit complet (40 caractères)" % repo)
    path = src.get("path") or resolve_dir(sources_root, repo)
    if not path or not os.path.isdir(path):
        raise SourceError("%s : source absente (cherchée sous %s)" % (repo, sources_root))
    code, out, _ = _git(path, "rev-parse", "HEAD")
    if code != 0:
        raise SourceError("%s : %s n'est pas un dépôt git" % (repo, path))
    head = out.strip()
    if head != expected:
        raise SourceError("%s : commit local %s différent du manifeste %s" % (repo, head[:12], expected[:12]))
    if not allow_dirty:
        _, status, _ = _git(path, "status", "--porcelain")
        if status.strip():
            raise SourceError("%s : modifications locales détectées" % repo)
    return path


def is_dirty(path):
    _, status, _ = _git(path, "status", "--porcelain")
    return bool(status.strip())


def tracked_files(path, subdir=""):
    """Fichiers suivis par git, triés (ordre déterministe)."""
    args = ["ls-files", "-z"]
    if subdir:
        args += ["--", subdir]
    code, out, err = _git(path, *args)
    if code != 0:
        raise SourceError("git ls-files a échoué : %s" % err.strip())
    return sorted(f for f in out.split("\0") if f)


def _first_description(node):
    if isinstance(node, dict):
        value = node.get("description")
        if isinstance(value, str) and value.strip():
            return value
        for child in node.values():
            found = _first_description(child)
            if found:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _first_description(child)
            if found:
                return found
    return ""


def _script_summary(text):
    match = _SCRIPT_HEADER.search(text[:3000])
    return summarize(match.group(1)) if match else ""


def make_record(src, repo_rel, rel, ctype, raw, issues, license_file, fingerprint=None):
    """Construit l'enregistrement d'un composant (observations seulement, sans décision)."""
    text = raw.decode("utf-8", errors="replace")
    stem = os.path.splitext(os.path.basename(rel))[0]
    name, summary, sim_text, tools, issue = "", "", "", "", None

    if ctype in ("skill", "agent", "embedded_agent", "command"):
        meta, body, issue = parse_frontmatter(text)
        fallback = os.path.basename(os.path.dirname(rel)) if ctype == "skill" else stem
        name = norm(meta.get("name")) or fallback
        raw_desc = meta.get("description")
        summary = summarize(raw_desc) if raw_desc else summarize(first_prose_line(body))
        tools = norm(meta.get("tools"))
        sim_text = norm(raw_desc) + " " + body[:2000]
    elif ctype == "plugin":
        try:
            manifest = json.loads(text)
            if not isinstance(manifest, dict):
                raise ValueError("manifeste non mapping")
        except ValueError as exc:
            manifest, issue = {}, "json_invalide: %s" % exc
        name = norm(manifest.get("name")) or os.path.basename(os.path.dirname(os.path.dirname(rel)))
        summary = summarize(manifest.get("description", ""))
        sim_text = norm(manifest.get("description")) + " " + norm(manifest.get("keywords"))
    elif ctype == "mod":
        name = os.path.basename(os.path.dirname(rel))
        summary = summarize(first_prose_line(text))
        sim_text = text[:2500]
    elif rel.endswith(".json"):  # configuration de hook
        name = stem
        try:
            summary = summarize(_first_description(json.loads(text)))
        except ValueError as exc:
            issue = "json_invalide: %s" % exc
        sim_text = stem.replace("-", " ") + " " + summary + " " + text[:1500]
    else:  # script de hook ou module de framework
        name = stem
        summary = _script_summary(text)
        sim_text = stem.replace("_", " ").replace("-", " ") + " " + text[:1500]

    if issue:
        issues.append({"source": src["repo"], "path": repo_rel, "issue": issue})
    return {
        "component_id": "%s:%s" % (src["repo"], repo_rel),
        "schema_version": None,
        "type": ctype,
        "name": name,
        "provenance": {
            "source": src["repo"], "role": src["role"], "path": repo_rel,
            "commit": src["commit"], "content_sha256": hashlib.sha256(raw).hexdigest(),
            "fingerprint_sha256": fingerprint[0] if fingerprint else hashlib.sha256(raw).hexdigest(),
            "fingerprint_files": fingerprint[1] if fingerprint else [repo_rel],
        },
        "license": {"verified": False, "repo_license_file": license_file, "spdx": None, "attribution": None},
        "function": {"summary": summary},
        "compatibility": {"platform": None, "min_version": None, "required_tools": tools or None},
        "relations": {"depends_on": [], "conflicts_with": [], "variant_of": [], "replaced_by": []},
        "metadata_issue": issue,
        "_sim_text": sim_text,
        "_has_text": bool(summary or norm(sim_text)),
    }


def _fingerprint(path, repo_files):
    """Empreinte d'un ensemble de fichiers : chemins et contenus, dans un ordre fixe."""
    digest = hashlib.sha256()
    for repo_rel in sorted(repo_files):
        with open(os.path.join(path, repo_rel), "rb") as handle:
            digest.update(("%s %s\n" % (repo_rel, hashlib.sha256(handle.read()).hexdigest())).encode("utf-8"))
    return digest.hexdigest(), sorted(repo_files)


def _behavior_files(repo_rel, ctype, all_files):
    """Fichiers qui déterminent le comportement d'un composant composé.

    mod : tout son dossier ; hook : sa configuration et les scripts qui portent le même nom.
    Les autres types sont leur propre fichier.
    """
    if ctype == "mod":
        prefix = os.path.dirname(repo_rel) + "/"
        return [f for f in all_files if f.startswith(prefix)]
    if ctype == "hook":
        folder, stem = os.path.dirname(repo_rel), os.path.splitext(os.path.basename(repo_rel))[0]
        return [f for f in all_files if os.path.dirname(f) == folder
                and os.path.splitext(os.path.basename(f))[0] == stem]
    return [repo_rel]


def build_records(src, path, issues):
    """Tous les composants d'une source, triés par chemin."""
    subdir = (src.get("subdir") or "").strip("/")
    files = tracked_files(path, subdir)
    license_file = next((f for f in files if os.path.basename(f).upper().startswith(("LICENSE", "LICENCE"))
                         and "/" not in f), None)
    if license_file is None and subdir:
        root_files = tracked_files(path)
        license_file = next((f for f in root_files if "/" not in f
                             and os.path.basename(f).upper().startswith(("LICENSE", "LICENCE"))), None)
    entries = []
    for repo_rel in files:
        rel = repo_rel[len(subdir) + 1:] if subdir else repo_rel
        ctype = classify(rel, src.get("framework_globs", []))
        if ctype:
            entries.append((repo_rel, rel, ctype))
    # Un hook décrit par un .json et son script compagnon forment un seul composant.
    json_hooks = {(os.path.dirname(rel), os.path.splitext(os.path.basename(rel))[0])
                  for _, rel, t in entries if t == "hook" and rel.endswith(".json")}
    records = []
    for repo_rel, rel, ctype in entries:
        key = (os.path.dirname(rel), os.path.splitext(os.path.basename(rel))[0])
        if ctype == "hook" and not rel.endswith(".json") and key in json_hooks:
            continue
        with open(os.path.join(path, repo_rel), "rb") as handle:
            raw = handle.read()
        fingerprint = _fingerprint(path, _behavior_files(repo_rel, ctype, files))
        records.append(make_record(src, repo_rel, rel, ctype, raw, issues, license_file, fingerprint))
    return records
