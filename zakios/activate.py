"""Activation contrôlée : aperçu, installation transactionnelle et retour arrière dans un projet.

Périmètre du pilote (Linux, Claude Code CLI) :
- on n'installe que des composants explicitement sélectionnés dont la décision humaine est valide,
  la licence vérifiée et l'empreinte complète ;
- rien n'est écrit pendant l'aperçu ;
- les fichiers du projet qui ne viennent pas de ZakiOS ne sont jamais écrasés ;
- les hooks sont copiés mais jamais activés (aucune modification de settings.json) ;
- une installation qui échoue en cours de route est annulée complètement.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

from . import policy
from .build import BuildError, _Lock, load_catalog
from .scan import resolve_dir

STATE_DIR = ".zakios"
LOCK_FILE = "lock.json"
PROFILE_FILE = "profile.json"
JOURNAL_DIR = "journal"
INSTALLABLE_TYPES = ("agent", "command", "skill", "hook")
PLATFORMS_OK = (None, "linux", "any")


class ActivationError(Exception):
    def __init__(self, message, reasons=None):
        super().__init__(message)
        self.reasons = reasons or []


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- sources

def _git(path, *args):
    result = subprocess.run(["git", "-C", path, *args], capture_output=True)
    return result.returncode, result.stdout


def _read_package(rec, sources_root):
    """Contenu exact des fichiers du paquet au commit du catalogue. Renvoie (fichiers, raisons)."""
    prov = rec["provenance"]
    path = resolve_dir(sources_root, prov["source"])
    if not path:
        return None, ["source %s absente" % prov["source"]]
    files, digest = {}, hashlib.sha256()
    for rel in sorted(prov["fingerprint_files"]):
        code, data = _git(path, "cat-file", "blob", "%s:%s" % (prov["commit"], rel))
        if code != 0:
            return None, ["fichier %s introuvable au commit %s" % (rel, prov["commit"][:12])]
        code, tree = _git(path, "ls-tree", prov["commit"], "--", rel)
        mode = tree.split(b" ", 1)[0].decode() if code == 0 and tree else "100644"
        files[rel] = (data, mode == "100755")
        digest.update(("%s %s\n" % (rel, _sha(data))).encode("utf-8"))
    if digest.hexdigest() != prov["fingerprint_sha256"]:
        return None, ["le contenu des sources ne correspond pas à l'empreinte du catalogue"]
    return files, []


def _destinations(rec, files):
    """Chemins d'installation dans le projet : {chemin: (contenu, exécutable)}. Renvoie (dict, raisons)."""
    kind, path = rec["type"], rec["provenance"]["path"]
    folder = os.path.dirname(path)
    if kind == "agent":
        return {".claude/agents/" + os.path.basename(path): files[path]}, []
    if kind == "command":
        return {".claude/commands/" + os.path.basename(path): files[path]}, []
    if kind in ("skill", "hook"):
        outside = [f for f in files if not f.startswith(folder + "/")]
        if outside:
            return None, ["dépendance hors du paquet, non installable : %s" % ", ".join(sorted(outside)[:3])]
        if kind == "skill":
            root = ".claude/skills/%s/" % os.path.basename(folder)
        else:
            root = ".claude/hooks/zakios/%s/" % os.path.splitext(os.path.basename(path))[0]
        return {root + f[len(folder) + 1:]: files[f] for f in files}, []
    return None, ["type « %s » non installable dans le pilote" % kind]


# ---------------------------------------------------------------- état du projet

def _state_path(project, *parts):
    return os.path.join(project, STATE_DIR, *parts)


def _empty_lock():
    return {"version": 1, "components": {}, "history": []}


def _read_lock(project):
    path = _state_path(project, LOCK_FILE)
    if not os.path.exists(path):
        return _empty_lock()
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_atomic(path, data, executable=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.zakios-tmp-%s" % (path, uuid.uuid4().hex[:8])
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.chmod(tmp, 0o755 if executable else 0o644)
    os.replace(tmp, path)


def _inside(project, rel):
    """Vrai si `rel` reste dans le projet, sans passer par un lien symbolique qui en sortirait."""
    root = os.path.realpath(project)
    target = os.path.join(project, rel)
    probe = os.path.dirname(target)
    while probe and not os.path.exists(probe):
        probe = os.path.dirname(probe)
    real = os.path.realpath(probe)
    if os.path.islink(target):
        return False
    return real == root or real.startswith(root + os.sep)


def _read_disk(project, rel):
    path = os.path.join(project, rel)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def load_profile(project, profile_path=None):
    path = profile_path or _state_path(project, PROFILE_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ActivationError("profil illisible (%s) : %s" % (path, exc))
    selection = data.get("components") if isinstance(data, dict) else None
    if not isinstance(selection, list) or not all(isinstance(x, str) for x in selection):
        raise ActivationError("le profil doit contenir une liste « components » d'identifiants")
    return sorted(set(selection))


# ---------------------------------------------------------------- aperçu

def plan(project, catalog, sources_root, selection):
    """Calcule exactement ce que ferait l'installation, sans rien écrire.

    Renvoie un dictionnaire : actions (create, update, unchanged, remove), refused (composants refusés
    avec leurs raisons), notes et plan_sha256 (empreinte du plan, pour lier l'aperçu à l'installation).
    """
    project = os.path.abspath(project)
    try:
        registry, registry_sha = load_catalog(catalog)
    except Exception as exc:  # catalogue illisible ou invalide
        raise ActivationError("catalogue invalide, activation refusée : %s" % exc)
    if registry.get("build_mode") != "exact":
        raise ActivationError("catalogue expérimental (sources modifiées localement) : activation refusée")
    by_id = {c["component_id"]: c for c in registry["components"]}
    lock = _read_lock(project)
    selection = sorted(set(selection))

    refused, desired, owners = [], {}, {}
    selected_ok = set(selection)

    def refuse(cid, *reasons):
        refused.append({"component_id": cid, "reasons": list(reasons)})
        selected_ok.discard(cid)

    # 1. contrôles par composant
    contents = {}
    for cid in selection:
        rec = by_id.get(cid)
        if rec is None:
            refuse(cid, "composant absent du catalogue")
            continue
        reasons = []
        prov, dec, lic, comp = rec["provenance"], rec.get("decision"), rec["license"], rec["compatibility"]
        if rec["type"] not in INSTALLABLE_TYPES:
            reasons.append("type « %s » non installable dans le pilote" % rec["type"])
        if not dec or dec.get("validated") not in policy.INSTALLABLE_DECISIONS:
            reasons.append("décision non validée par un humain (ou non installable)")
        elif dec.get("validated_fingerprint_sha256") != prov["fingerprint_sha256"]:
            reasons.append("validation liée à un autre contenu")
        if not prov.get("fingerprint_complete"):
            reasons.append("empreinte incomplète : dépendances non explorées")
        if rec.get("metadata_issue"):
            reasons.append("métadonnées invalides")
        if not lic.get("verified"):
            reasons.append("licence non vérifiée")
        if comp.get("platform") not in PLATFORMS_OK:
            reasons.append("incompatible avec Linux (plateforme déclarée : %s)" % comp.get("platform"))
        if not reasons:
            files, problems = _read_package(rec, sources_root)
            reasons += problems
            if files is not None:
                dests, problems = _destinations(rec, files)
                reasons += problems
                if dests is not None:
                    contents[cid] = dests
        if reasons:
            refuse(cid, *reasons)

    # 2. dépendances et conflits sur l'ensemble final (on répète : un refus peut en entraîner d'autres)
    changed = True
    while changed:
        changed = False
        for cid in sorted(selected_ok):
            rel = by_id[cid]["relations"]
            missing = [d for d in rel["depends_on"] if d not in selected_ok]
            clash = [x for x in rel["conflicts_with"] if x in selected_ok]
            reasons = []
            if missing:
                reasons.append("dépendance non sélectionnée ou refusée : %s" % ", ".join(missing))
            if clash:
                reasons.append("en conflit avec un composant sélectionné : %s" % ", ".join(clash))
            if reasons:
                refuse(cid, *reasons)
                changed = True

    # 3. destinations : pas de collision entre composants
    for cid in sorted(selected_ok):
        for dest in contents[cid]:
            if dest in owners and owners[dest] != cid:
                refuse(cid, "chemin %s déjà visé par %s" % (dest, owners[dest]))
                break
        else:
            for dest, value in contents[cid].items():
                owners[dest] = cid
                desired[dest] = value

    # 4. état du disque : jamais d'écrasement de fichiers qui ne viennent pas de ZakiOS
    locked = {}
    for cid, info in lock["components"].items():
        for rel, sha in info["files"].items():
            locked[rel] = (cid, sha)
    actions = []
    blocked = {}
    for rel in sorted(desired):
        data, executable = desired[rel]
        cid = owners[rel]
        new_sha = _sha(data)
        disk = _read_disk(project, rel)
        if not _inside(project, rel):
            blocked.setdefault(cid, []).append("%s sortirait du projet (lien symbolique)" % rel)
            continue
        if rel in locked:
            if disk is None:
                actions.append({"action": "create", "path": rel, "component_id": cid, "sha256": new_sha, "executable": executable})
            elif _sha(disk) != locked[rel][1]:
                blocked.setdefault(cid, []).append("%s modifié localement depuis l'installation" % rel)
            elif _sha(disk) == new_sha:
                actions.append({"action": "unchanged", "path": rel, "component_id": cid, "sha256": new_sha, "executable": executable})
            else:
                actions.append({"action": "update", "path": rel, "component_id": cid, "sha256": new_sha, "executable": executable})
        elif disk is not None or os.path.lexists(os.path.join(project, rel)):
            blocked.setdefault(cid, []).append("%s existe déjà dans le projet (fichier non géré par ZakiOS)" % rel)
        else:
            actions.append({"action": "create", "path": rel, "component_id": cid, "sha256": new_sha, "executable": executable})
    for rel in sorted(locked):
        if rel in desired:
            continue
        cid, sha = locked[rel]
        disk = _read_disk(project, rel)
        if disk is None:
            actions.append({"action": "forget", "path": rel, "component_id": cid, "sha256": sha, "executable": False})
        elif _sha(disk) != sha:
            blocked.setdefault(cid, []).append("%s modifié localement : retrait refusé" % rel)
        else:
            actions.append({"action": "remove", "path": rel, "component_id": cid, "sha256": sha, "executable": False})
    for cid, reasons in sorted(blocked.items()):
        refused.append({"component_id": cid, "reasons": reasons})
        actions = [a for a in actions if a["component_id"] != cid]

    refused.sort(key=lambda r: r["component_id"])
    notes = []
    if any(by_id[c]["type"] == "hook" for c in selected_ok if c in by_id):
        notes.append("Les hooks sont copiés sous .claude/hooks/zakios/ mais pas activés : settings.json n'est pas modifié.")
    body = {"registry_sha256": registry_sha, "actions": actions, "refused": refused, "selection": selection}
    result = dict(body)
    result["notes"] = notes
    result["project"] = project
    result["plan_sha256"] = _sha(_dump(body).encode("utf-8"))
    result["installed"] = {cid: {"commit": by_id[cid]["provenance"]["commit"],
                                 "fingerprint_sha256": by_id[cid]["provenance"]["fingerprint_sha256"],
                                 "license": {k: by_id[cid]["license"][k] for k in ("spdx", "attribution", "verified_by")},
                                 "files": {d: _sha(v[0]) for d, v in sorted(contents[cid].items())}}
                           for cid in sorted(selected_ok) if cid in contents and cid not in blocked}
    result["_contents"] = {rel: desired[rel] for rel in desired}
    return result


# ---------------------------------------------------------------- installation et retour arrière

def _journal_path(project, tx, *parts):
    return _state_path(project, JOURNAL_DIR, tx, *parts)


def _save_meta(project, tx, meta):
    _write_atomic(_journal_path(project, tx, "meta.json"), _dump(meta).encode("utf-8"))


def _undo(project, tx, check_user_edits):
    """Annule une transaction à partir de son journal. Renvoie les raisons de blocage éventuelles."""
    with open(_journal_path(project, tx, "meta.json"), encoding="utf-8") as handle:
        meta = json.load(handle)
    ops = meta["ops"]
    if check_user_edits:
        blocked = []
        for op in ops:
            if op["kind"] in ("created", "updated"):
                disk = _read_disk(project, op["path"])
                if disk is not None and _sha(disk) != op["after_sha256"]:
                    blocked.append("%s modifié depuis l'installation : retour arrière refusé" % op["path"])
        if blocked:
            raise ActivationError("retour arrière impossible sans perdre des modifications", blocked)
    for op in reversed(ops):
        target = os.path.join(project, op["path"])
        if op["kind"] == "created":
            if os.path.isfile(target):
                os.remove(target)
        elif op["kind"] in ("updated", "removed"):
            with open(_journal_path(project, tx, "backup", op["path"]), "rb") as handle:
                _write_atomic(target, handle.read(), op.get("executable_before", False))
    for rel in reversed(meta.get("created_dirs", [])):
        path = os.path.join(project, rel)
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
    _write_atomic(_state_path(project, LOCK_FILE), _dump(meta["lock_before"]).encode("utf-8"))
    meta["status"] = "rolled_back"
    _save_meta(project, tx, meta)


def _recover_interrupted(project):
    """Une installation interrompue (processus tué) laisse un journal « started » : on l'annule."""
    base = _state_path(project, JOURNAL_DIR)
    if not os.path.isdir(base):
        return []
    recovered = []
    for tx in sorted(os.listdir(base)):
        meta_path = _journal_path(project, tx, "meta.json")
        if not os.path.exists(meta_path):
            continue
        with open(meta_path, encoding="utf-8") as handle:
            status = json.load(handle).get("status")
        if status == "started":
            _undo(project, tx, check_user_edits=False)
            recovered.append(tx)
    return recovered


def apply(project, catalog, sources_root, selection, expected_plan=None, fault=None):
    """Installe la sélection, tout ou rien.

    `expected_plan` : empreinte lue dans l'aperçu ; si le plan a changé depuis, on refuse.
    `fault` : fonction appelée après chaque action (tests d'échec simulé).
    Renvoie {"transaction", "applied", "unchanged"} ; transaction vaut None quand rien n'a changé.
    """
    project = os.path.abspath(project)
    os.makedirs(_state_path(project), exist_ok=True)
    try:
        lock_ctx = _Lock(_state_path(project, "project"))
        lock_ctx.__enter__()
    except BuildError as exc:
        raise ActivationError("une autre installation est déjà en cours dans ce projet : %s" % exc)
    try:
        recovered = _recover_interrupted(project)
        pl = plan(project, catalog, sources_root, selection)
        if pl["refused"]:
            raise ActivationError("installation refusée, rien n'a été écrit", [
                "%s : %s" % (r["component_id"], "; ".join(r["reasons"])) for r in pl["refused"]])
        if expected_plan and expected_plan != pl["plan_sha256"]:
            raise ActivationError("le plan a changé depuis l'aperçu, rien n'a été écrit")
        todo = [a for a in pl["actions"] if a["action"] != "unchanged"]
        unchanged = len(pl["actions"]) - len(todo)
        if not todo:
            return {"transaction": None, "applied": 0, "unchanged": unchanged, "recovered": recovered}

        lock_before = _read_lock(project)
        tx = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:6])
        meta = {"status": "started", "lock_before": lock_before, "ops": [], "created_dirs": [], "plan_sha256": pl["plan_sha256"]}
        _save_meta(project, tx, meta)
        try:
            for index, act in enumerate(todo):
                rel, target = act["path"], os.path.join(project, act["path"])
                if act["action"] in ("create", "update"):
                    data, executable = pl["_contents"][rel]
                    op = {"kind": "created" if act["action"] == "create" else "updated", "path": rel,
                          "after_sha256": _sha(data)}
                    if act["action"] == "update":
                        old = _read_disk(project, rel)
                        _write_atomic(_journal_path(project, tx, "backup", rel), old)
                        op["executable_before"] = os.access(target, os.X_OK)
                    parent = os.path.dirname(rel)
                    missing = []
                    while parent and not os.path.isdir(os.path.join(project, parent)):
                        missing.append(parent)
                        parent = os.path.dirname(parent)
                    meta["created_dirs"].extend(reversed(missing))
                    meta["ops"].append(op)
                    _save_meta(project, tx, meta)  # le journal précède l'écriture
                    _write_atomic(target, data, executable)
                elif act["action"] == "remove":
                    old = _read_disk(project, rel)
                    _write_atomic(_journal_path(project, tx, "backup", rel), old)
                    meta["ops"].append({"kind": "removed", "path": rel, "executable_before": os.access(target, os.X_OK)})
                    _save_meta(project, tx, meta)
                    os.remove(target)
                # "forget" : le fichier a déjà disparu, seul le verrou change
                if fault:
                    fault(index)
            lock_after = {"version": 1, "components": pl["installed"],
                          "history": lock_before.get("history", []) + [tx]}
            _write_atomic(_state_path(project, LOCK_FILE), _dump(lock_after).encode("utf-8"))
            meta["status"] = "committed"
            _save_meta(project, tx, meta)
        except BaseException as exc:
            _undo(project, tx, check_user_edits=False)
            raise ActivationError("échec pendant l'installation, retour arrière effectué : %s" % exc) from exc
        return {"transaction": tx, "applied": len(todo), "unchanged": unchanged, "recovered": recovered}
    finally:
        lock_ctx.__exit__()


def rollback(project):
    """Annule la dernière installation, sauf si cela ferait perdre des modifications de l'utilisateur."""
    project = os.path.abspath(project)
    os.makedirs(_state_path(project), exist_ok=True)
    try:
        lock_ctx = _Lock(_state_path(project, "project"))
        lock_ctx.__enter__()
    except BuildError as exc:
        raise ActivationError("une autre installation est déjà en cours dans ce projet : %s" % exc)
    try:
        _recover_interrupted(project)
        lock = _read_lock(project)
        if not lock["history"]:
            raise ActivationError("aucune installation à annuler")
        tx = lock["history"][-1]
        _undo(project, tx, check_user_edits=True)
        return {"transaction": tx}
    finally:
        lock_ctx.__exit__()
