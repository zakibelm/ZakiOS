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


MAX_PACKAGE_FILES = 300
_PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import\s+([\w, ]+)|import\s+([\w., ]+))", re.M)
_JS_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\(\s*|import\s+)['"](\.{1,2}/[^'"]*|\.{1,2})['"]""")
_SH_SOURCE = re.compile(r"""^\s*(?:source|\.)\s+["']?([^\s"';|&]+)""", re.M)
_SCRIPT_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".json", ".yaml", ".yml", ".toml")
_PATH_IN_TEXT = re.compile(r"""[\w@./${}\-]+\.(?:py|js|mjs|cjs|ts|sh|bash)\b""")


def _fingerprint(path, repo_files):
    """Empreinte d'un ensemble de fichiers : chemins et contenus, dans un ordre fixe."""
    digest = hashlib.sha256()
    for repo_rel in sorted(repo_files):
        with open(os.path.join(path, repo_rel), "rb") as handle:
            digest.update(("%s %s\n" % (repo_rel, hashlib.sha256(handle.read()).hexdigest())).encode("utf-8"))
    return digest.hexdigest(), sorted(repo_files)


def _resolve_relative(base_dir, target, known):
    """Fichier suivi désigné par `target` (relatif à base_dir), avec les extensions usuelles."""
    joined = os.path.normpath(os.path.join(base_dir, target))
    candidates = [joined] + [joined + ext for ext in _SCRIPT_EXT]
    candidates += [os.path.join(joined, "index" + ext) for ext in (".js", ".ts", ".mjs")]
    candidates.append(os.path.join(joined, "__init__.py"))
    return next((c for c in candidates if c in known), None)


def _local_dependencies(path, repo_rel, known):
    """Fichiers locaux que `repo_rel` importe ou exécute (python, js/ts, shell), un niveau."""
    try:
        with open(os.path.join(path, repo_rel), "rb") as handle:
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    base = os.path.dirname(repo_rel)
    ext = os.path.splitext(repo_rel)[1]
    found = []
    if ext == ".py":
        modules = []
        for m in _PY_IMPORT.finditer(text):
            if m.group(1) is not None:  # from X import a, b : X, mais aussi X.a et X.b (sous-modules)
                source = m.group(1)
                modules.append(source)
                for name in m.group(2).split(","):
                    name = name.strip()
                    if name:
                        modules.append(source + name if source.endswith(".") else source + "." + name)
            else:
                modules.extend(n.strip().split(" as ")[0] for n in m.group(3).split(","))
        for mod in modules:
            if not mod:
                continue
            dots = len(mod) - len(mod.lstrip("."))
            rel = mod.lstrip(".").replace(".", "/")
            roots = [os.path.normpath(os.path.join(base, *([".."] * (dots - 1))))] if dots else []
            if not dots:  # import absolu : on cherche depuis le dossier du script puis ses parents
                cur = base
                while True:
                    roots.append(cur)
                    if not cur:
                        break
                    cur = os.path.dirname(cur)
            for root in roots:
                hit = _resolve_relative(root, rel, known) if rel else None
                if hit and hit.endswith(".py"):
                    found.append(hit)
                    break
    elif ext in (".js", ".mjs", ".cjs", ".ts"):
        for m in _JS_IMPORT.finditer(text):
            hit = _resolve_relative(base, m.group(1), known)
            if hit:
                found.append(hit)
    elif ext in (".sh", ".bash"):
        for m in _SH_SOURCE.finditer(text):
            hit = _resolve_relative(base, m.group(1), known)
            if hit:
                found.append(hit)
    return found


def _closure(path, seeds, known):
    """Seeds et toutes leurs dépendances locales, transitivement (borné)."""
    seen, queue = set(), sorted(seeds)
    while queue and len(seen) < MAX_PACKAGE_FILES:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(d for d in _local_dependencies(path, current, known) if d not in seen)
    return seen


def _referenced_scripts(path, config_rel, known, by_suffix):
    """Scripts cités dans une configuration de hook (commandes), résolus dans le dépôt."""
    try:
        with open(os.path.join(path, config_rel), "rb") as handle:
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    found = []
    for token in _PATH_IN_TEXT.findall(text):
        token = token.replace("${CLAUDE_PLUGIN_ROOT}/", "").replace("$CLAUDE_PROJECT_DIR/", "").lstrip("./")
        hit = _resolve_relative(os.path.dirname(config_rel), token, known) or (token if token in known else None)
        if hit is None:
            matches = by_suffix.get(os.path.basename(token), [])
            hit = matches[0] if len(matches) == 1 else None
        if hit:
            found.append(hit)
    return found


def _behavior_files(path, repo_rel, ctype, all_files, known, by_suffix):
    """Paquet complet qui détermine le comportement d'un composant.

    mod : tout son dossier ; skill : tout son dossier ; hook : configuration, scripts du même nom,
    scripts cités par la configuration ; plugin : manifeste, hooks, scripts et .mcp.json de sa racine.
    Pour chacun, on ajoute les dépendances locales importées par les scripts, transitivement.
    Agents et commandes sont leur propre fichier.
    """
    folder = os.path.dirname(repo_rel)
    if ctype == "mod":
        seeds = [f for f in all_files if f.startswith(folder + "/")]
    elif ctype == "skill":
        seeds = [f for f in all_files if f.startswith(folder + "/")] if folder else [repo_rel]
    elif ctype == "hook":
        stem = os.path.splitext(os.path.basename(repo_rel))[0]
        seeds = [f for f in all_files if os.path.dirname(f) == folder
                 and os.path.splitext(os.path.basename(f))[0] == stem]
        if repo_rel.endswith(".json"):
            seeds += _referenced_scripts(path, repo_rel, known, by_suffix)
    elif ctype == "plugin":
        root = os.path.dirname(folder)  # le manifeste vit dans <racine>/.claude-plugin/
        seeds = [repo_rel] + [f for f in all_files if f.startswith(root + "/" if root else "")
                              and (os.path.relpath(f, root).startswith(("hooks/", "scripts/"))
                                   or os.path.basename(f) in (".mcp.json", "hooks.json"))]
    elif ctype == "framework_module":
        seeds = [repo_rel]
    else:
        return [repo_rel]
    return sorted(_closure(path, set(seeds) | {repo_rel}, known) | set(seeds) | {repo_rel})


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
    known = set(tracked_files(path))
    by_suffix = {}
    for f in sorted(known):
        by_suffix.setdefault(os.path.basename(f), []).append(f)
    records = []
    for repo_rel, rel, ctype in entries:
        key = (os.path.dirname(rel), os.path.splitext(os.path.basename(rel))[0])
        if ctype == "hook" and not rel.endswith(".json") and key in json_hooks:
            continue
        with open(os.path.join(path, repo_rel), "rb") as handle:
            raw = handle.read()
        fingerprint = _fingerprint(path, _behavior_files(path, repo_rel, ctype, files, known, by_suffix))
        records.append(make_record(src, repo_rel, rel, ctype, raw, issues, license_file, fingerprint))
    return records
