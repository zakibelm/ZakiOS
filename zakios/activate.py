"""Activation contrôlée : aperçu, installation transactionnelle et retour arrière dans un projet.

Périmètre du pilote (Linux, Claude Code CLI) :
- on n'installe que des composants explicitement sélectionnés dont la décision humaine est valide,
  la licence vérifiée et l'empreinte complète ;
- rien n'est écrit pendant l'aperçu ;
- les fichiers du projet qui ne viennent pas de ZakiOS ne sont jamais écrasés, ni par l'installation,
  ni par un retour arrière ou une reprise après interruption ;
- aucune lecture, écriture ou suppression ne sort du projet : toutes les opérations passent par des
  descripteurs de dossier ouverts sans suivre les liens symboliques (Linux) ;
- les hooks sont copiés mais jamais activés (aucune modification de settings.json) ;
- une installation qui échoue en cours de route est annulée complètement.
"""
import errno
import hashlib
import json
import os
import stat
import subprocess
import time
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from . import policy
from .build import load_catalog
from .scan import resolve_dir

STATE_DIR = ".zakios"
LOCK_FILE = "lock.json"
PROFILE_FILE = "profile.json"
JOURNAL_DIR = "journal"
INSTALLABLE_TYPES = ("agent", "command", "skill", "hook", "socle")

# Le Socle est chargé par le projet : `.claude/CLAUDE.md` importe ses règles. Fichier propre à ZakiOS,
# distinct du CLAUDE.md de la racine : celui de l'utilisateur n'est jamais lu ni modifié.
SOCLE_IMPORT = b"@socle/REGLES.md\n"
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
    if kind == "socle":
        return {".claude/socle/REGLES.md": files[path], ".claude/CLAUDE.md": (SOCLE_IMPORT, False)}, []
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


# ---------------------------------------------------------------- accès sûr au projet

class UnsafePath(ActivationError):
    pass


def _parts(rel):
    parts = rel.split("/")
    if not rel or any(p in ("", ".", "..") for p in parts) or rel.startswith("/") or "\0" in rel:
        raise UnsafePath("chemin invalide ou sortant du projet : %r" % rel)
    return parts


class Root:
    """Le projet, ouvert une fois comme descripteur de dossier.

    Toutes les opérations descendent composant par composant avec O_NOFOLLOW : un lien symbolique
    rencontré, même substitué après une vérification préalable, fait échouer l'opération au lieu de
    sortir du projet. Le chemin du projet lui-même est celui que l'utilisateur a choisi.
    """

    def __init__(self, path):
        self.path = os.path.realpath(path)
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        except OSError as exc:
            raise ActivationError("projet illisible (%s) : %s" % (path, exc))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _open_dir(self, dir_parts, create=False):
        """Descripteur du dossier désigné, ou FileNotFoundError s'il n'existe pas (et create est faux)."""
        fd = os.dup(self.fd)
        try:
            for part in dir_parts:
                try:
                    nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(part, 0o755, dir_fd=fd)
                    nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise UnsafePath("%s n'est pas un vrai dossier du projet (lien symbolique ou fichier)"
                                         % "/".join(dir_parts[:dir_parts.index(part) + 1]))
                    raise
                os.close(fd)
                fd = nfd
            return fd
        except BaseException:
            os.close(fd)
            raise

    def missing_dirs(self, rel):
        """Dossiers parents de `rel` qui n'existent pas encore (du plus haut au plus bas)."""
        parts = _parts(rel)[:-1]
        fd = os.dup(self.fd)
        missing = []
        try:
            for index, part in enumerate(parts):
                try:
                    nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    return ["/".join(parts[:i + 1]) for i in range(index, len(parts))]
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise UnsafePath("%s n'est pas un vrai dossier du projet" % "/".join(parts[:index + 1]))
                    raise
                os.close(fd)
                fd = nfd
        finally:
            os.close(fd)
        return missing

    def read(self, rel):
        """Contenu du fichier, ou None s'il n'existe pas. UnsafePath si un lien symbolique est rencontré."""
        parts = _parts(rel)
        try:
            parent = self._open_dir(parts[:-1])
        except FileNotFoundError:
            return None
        try:
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            except FileNotFoundError:
                return None
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENXIO):
                    raise UnsafePath("%s est un lien symbolique : refusé" % rel)
                raise
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise UnsafePath("%s n'est pas un fichier ordinaire" % rel)
                return handle.read()
        finally:
            os.close(parent)

    def is_executable(self, rel):
        parts = _parts(rel)
        try:
            parent = self._open_dir(parts[:-1])
        except FileNotFoundError:
            return False
        try:
            try:
                return bool(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False).st_mode & 0o100)
            except FileNotFoundError:
                return False
        finally:
            os.close(parent)

    def lexists(self, rel):
        """Vrai si quoi que ce soit (fichier, dossier, lien) occupe l'emplacement."""
        parts = _parts(rel)
        try:
            parent = self._open_dir(parts[:-1])
        except FileNotFoundError:
            return False
        try:
            os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
        finally:
            os.close(parent)

    def write_atomic(self, rel, data, executable=False, replace=True):
        """Écrit via un fichier temporaire. Avec replace=False, n'écrase jamais un fichier déjà présent."""
        parts = _parts(rel)
        parent = self._open_dir(parts[:-1], create=True)
        tmp = ".zakios-tmp-%s" % uuid.uuid4().hex[:10]
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fchmod(handle.fileno(), 0o755 if executable else 0o644)
                    os.fsync(handle.fileno())
            except BaseException:
                os.unlink(tmp, dir_fd=parent)
                raise
            if replace:
                os.rename(tmp, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            else:
                try:  # link échoue si la cible existe : création atomique sans écrasement
                    os.link(tmp, parts[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                finally:
                    os.unlink(tmp, dir_fd=parent)
        finally:
            os.close(parent)

    def remove(self, rel):
        parts = _parts(rel)
        try:
            parent = self._open_dir(parts[:-1])
        except FileNotFoundError:
            return
        try:
            try:
                os.unlink(parts[-1], dir_fd=parent)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent)

    def rmdir_if_empty(self, rel):
        parts = _parts(rel)
        try:
            parent = self._open_dir(parts[:-1])
        except FileNotFoundError:
            return
        try:
            try:
                os.rmdir(parts[-1], dir_fd=parent)
            except (FileNotFoundError, OSError) as exc:
                if not isinstance(exc, FileNotFoundError) and exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR):
                    raise
        finally:
            os.close(parent)

    def listdir(self, rel):
        try:
            fd = self._open_dir(_parts(rel))
        except FileNotFoundError:
            return []
        try:
            return sorted(os.listdir(fd))
        finally:
            os.close(fd)

    def lock(self):
        """Verrou exclusif du projet (le dossier d'état est créé ici, jamais avant)."""
        if fcntl is None:
            raise ActivationError("plateforme non prise en charge : le verrou du projet exige Linux ou macOS (fcntl)")
        state = self._open_dir([STATE_DIR], create=True)
        try:
            fd = os.open("project.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644, dir_fd=state)
        finally:
            os.close(state)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise ActivationError("une autre installation est déjà en cours dans ce projet")
        return fd


def _state(*parts):
    return "/".join((STATE_DIR,) + parts)


def _empty_lock():
    return {"version": 1, "components": {}, "history": []}


def _read_lock(root):
    data = root.read(_state(LOCK_FILE))
    return _empty_lock() if data is None else json.loads(data.decode("utf-8"))


def load_profile(project, profile_path=None):
    try:
        if profile_path:
            with open(profile_path, "rb") as handle:
                raw = handle.read()
        else:
            with Root(project) as root:
                raw = root.read(_state(PROFILE_FILE))
            if raw is None:
                raise ActivationError("profil absent : %s" % os.path.join(project, _state(PROFILE_FILE)))
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ActivationError("profil illisible : %s" % exc)
    selection = data.get("components") if isinstance(data, dict) else None
    if not isinstance(selection, list) or not all(isinstance(x, str) for x in selection):
        raise ActivationError("le profil doit contenir une liste « components » d'identifiants")
    return sorted(set(selection))


# ---------------------------------------------------------------- aperçu

def plan(project, catalog, sources_root, selection):
    """Calcule exactement ce que ferait l'installation, sans rien écrire (ni dossier d'état, ni verrou)."""
    with Root(project) as root:
        return _plan(root, catalog, sources_root, selection)


def _journal_statuses(root):
    """{transaction: statut} d'après les journaux, sans rien écrire."""
    out = {}
    for tx in root.listdir(_state(JOURNAL_DIR)):
        raw = root.read(_state(JOURNAL_DIR, tx, "meta.json"))
        if raw:
            out[tx] = json.loads(raw.decode("utf-8")).get("status")
    return out


def _journal_notes(root):
    """Journaux à connaître : installation interrompue à reprendre, conflits à revoir à la main."""
    notes = []
    for tx, status in _journal_statuses(root).items():
        if status == "started":
            notes.append("Installation interrompue détectée (%s) : apply la reprendra et l'annulera avant toute autre action." % tx)
        elif status == "conflict":
            notes.append("Journal %s en conflit : sauvegardes conservées dans %s, à revoir à la main."
                         % (tx, _state(JOURNAL_DIR, tx)))
    return notes


def _plan(root, catalog, sources_root, selection):
    project = root.path
    try:
        registry, registry_sha = load_catalog(catalog)
    except Exception as exc:  # catalogue illisible ou invalide
        raise ActivationError("catalogue invalide, activation refusée : %s" % exc)
    if registry.get("build_mode") != "exact":
        raise ActivationError("catalogue expérimental (sources modifiées localement) : activation refusée")
    by_id = {c["component_id"]: c for c in registry["components"]}
    try:
        lock = _read_lock(root)
    except UnsafePath as exc:
        raise ActivationError("dossier d'état hors du projet ou illisible, activation refusée : %s" % exc)
    except ValueError as exc:
        raise ActivationError("verrou d'installation illisible : %s" % exc)
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

    def read_disk(rel, cid):
        try:
            return root.read(rel), True
        except UnsafePath as exc:
            blocked.setdefault(cid, []).append("%s : chemin non sûr (%s)" % (rel, exc))
            return None, False

    def occupied(rel):
        try:
            return root.lexists(rel)
        except UnsafePath:
            return True

    for rel in sorted(desired):
        data, executable = desired[rel]
        cid = owners[rel]
        new_sha = _sha(data)
        disk, safe = read_disk(rel, cid)
        if not safe:
            continue
        entry = {"path": rel, "component_id": cid, "sha256": new_sha, "executable": executable}
        if rel in locked:
            if disk is None:
                actions.append(dict(entry, action="create"))
            elif _sha(disk) != locked[rel][1]:
                blocked.setdefault(cid, []).append("%s modifié localement depuis l'installation" % rel)
            elif _sha(disk) == new_sha:
                actions.append(dict(entry, action="unchanged"))
            else:
                actions.append(dict(entry, action="update"))
        elif disk is not None or occupied(rel):
            blocked.setdefault(cid, []).append("%s existe déjà dans le projet (fichier non géré par ZakiOS)" % rel)
        else:
            actions.append(dict(entry, action="create"))
    for rel in sorted(locked):
        if rel in desired:
            continue
        cid, sha = locked[rel]
        disk, safe = read_disk(rel, cid)
        if not safe:
            continue
        entry = {"path": rel, "component_id": cid, "sha256": sha, "executable": False}
        if disk is None:
            actions.append(dict(entry, action="forget"))
        elif _sha(disk) != sha:
            blocked.setdefault(cid, []).append("%s modifié localement : retrait refusé" % rel)
        else:
            actions.append(dict(entry, action="remove"))
    for cid, reasons in sorted(blocked.items()):
        refused.append({"component_id": cid, "reasons": reasons})
        actions = [a for a in actions if a["component_id"] != cid]

    refused.sort(key=lambda r: r["component_id"])
    notes = _journal_notes(root)
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

def _save_meta(root, tx, meta):
    root.write_atomic(_state(JOURNAL_DIR, tx, "meta.json"), _dump(meta).encode("utf-8"))


def _undo_conflicts(root, ops):
    """Raisons pour lesquelles annuler ces opérations ferait perdre un fichier de l'utilisateur.

    Valable pour un retour arrière explicite comme pour la reprise après interruption : l'état du
    disque est comparé à ce que ZakiOS a écrit (après) ou à ce qui existait avant l'opération.
    """
    reasons = []
    for op in ops:
        rel = op["path"]
        try:
            disk = root.read(rel)
            occupied = disk is not None or root.lexists(rel)
        except UnsafePath as exc:
            reasons.append("%s : chemin non sûr (%s) : restauration refusée" % (rel, exc))
            continue
        sha = _sha(disk) if disk is not None else None
        if op["kind"] == "created":
            if occupied and sha != op["after_sha256"]:
                reasons.append("%s modifié depuis l'installation : retour arrière refusé" % rel)
        elif op["kind"] == "updated":
            if occupied and sha not in (op["after_sha256"], op["before_sha256"]):
                reasons.append("%s modifié depuis l'installation : retour arrière refusé" % rel)
        elif op["kind"] == "removed":
            if occupied and sha != op["before_sha256"]:
                reasons.append("%s recréé depuis le retrait : restauration refusée" % rel)
    return reasons


def _undo(root, tx):
    """Annule une transaction à partir de son journal, ou signale un conflit en gardant les sauvegardes."""
    raw = root.read(_state(JOURNAL_DIR, tx, "meta.json"))
    if raw is None:
        raise ActivationError("journal %s introuvable" % tx)
    meta = json.loads(raw.decode("utf-8"))
    reasons = _undo_conflicts(root, meta["ops"])
    if reasons:
        meta["status"] = "conflict"
        meta["conflicts"] = reasons
        _save_meta(root, tx, meta)
        raise ActivationError("retour arrière impossible sans perdre des modifications ; sauvegardes conservées dans %s"
                              % _state(JOURNAL_DIR, tx), reasons)
    for op in reversed(meta["ops"]):
        rel = op["path"]
        if op["kind"] == "created":
            root.remove(rel)
        else:
            backup = root.read(_state(JOURNAL_DIR, tx, "backup", rel))
            if backup is None:
                raise ActivationError("sauvegarde manquante pour %s" % rel)
            try:
                root.write_atomic(rel, backup, op.get("executable_before", False), replace=(op["kind"] == "updated"))
            except FileExistsError:
                meta["status"] = "conflict"
                meta["conflicts"] = ["%s recréé pendant la restauration : restauration refusée" % rel]
                _save_meta(root, tx, meta)
                raise ActivationError("retour arrière interrompu, sauvegardes conservées dans %s" % _state(JOURNAL_DIR, tx),
                                      meta["conflicts"])
    for rel in reversed(meta.get("created_dirs", [])):
        root.rmdir_if_empty(rel)
    root.write_atomic(_state(LOCK_FILE), _dump(meta["lock_before"]).encode("utf-8"))
    meta["status"] = "rolled_back"
    _save_meta(root, tx, meta)


def _recover_interrupted(root):
    """Une installation interrompue (processus tué) laisse un journal « started » : on l'annule si c'est sans risque."""
    recovered = []
    for tx, status in _journal_statuses(root).items():
        if status == "started":
            try:
                _undo(root, tx)
            except ActivationError as conflict:
                raise ActivationError("installation bloquée : la reprise de l'installation interrompue %s est impossible. %s"
                                      % (tx, conflict), conflict.reasons) from conflict
            recovered.append(tx)
    return recovered


def apply(project, catalog, sources_root, selection, expected_plan=None, fault=None):
    """Installe la sélection, tout ou rien.

    `expected_plan` : empreinte lue dans l'aperçu ; si le plan a changé depuis, on refuse.
    `fault` : fonction appelée après chaque action (tests d'échec simulé).
    Une première validation sans écriture précède le dossier d'état et le verrou : un refus évident
    ne laisse rien dans le projet. Si un journal « started » (installation interrompue) existe, la
    reprise sécurisée passe en premier : verrou, annulation contrôlée, puis validation normale. Renvoie {"transaction", "applied", "unchanged"} ;
    transaction vaut None quand rien n'a changé.
    """
    with Root(project) as root:
        try:
            interrupted = "started" in _journal_statuses(root).values()
        except UnsafePath as exc:
            raise ActivationError("dossier d'état hors du projet, activation refusée : %s" % exc)
        if not interrupted:
            # Sans installation interrompue : validation préalable sans écriture.
            # Avec une installation interrompue, les fichiers déjà écrits paraîtraient « non gérés » :
            # on reprend d'abord sous verrou, puis on valide.
            _check(_plan(root, catalog, sources_root, selection), expected_plan)
        lock_fd = root.lock()
        try:
            return _apply_locked(root, catalog, sources_root, selection, expected_plan, fault)
        finally:
            os.close(lock_fd)


def _check(pl, expected_plan):
    if pl["refused"]:
        raise ActivationError("installation refusée, rien n'a été écrit", [
            "%s : %s" % (r["component_id"], "; ".join(r["reasons"])) for r in pl["refused"]])
    if expected_plan and expected_plan != pl["plan_sha256"]:
        raise ActivationError("le plan a changé depuis l'aperçu, rien n'a été écrit")


def _apply_locked(root, catalog, sources_root, selection, expected_plan, fault):
    recovered = _recover_interrupted(root)
    pl = _plan(root, catalog, sources_root, selection)  # sous verrou : le plan qui fait foi
    _check(pl, expected_plan)
    todo = [a for a in pl["actions"] if a["action"] != "unchanged"]
    unchanged = len(pl["actions"]) - len(todo)
    if not todo:
        return {"transaction": None, "applied": 0, "unchanged": unchanged, "recovered": recovered}

    lock_before = _read_lock(root)
    tx = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:6])
    meta = {"status": "started", "lock_before": lock_before, "ops": [], "created_dirs": [], "plan_sha256": pl["plan_sha256"]}
    _save_meta(root, tx, meta)
    try:
        for index, act in enumerate(todo):
            rel = act["path"]
            if act["action"] in ("create", "update"):
                data, executable = pl["_contents"][rel]
                op = {"kind": "created" if act["action"] == "create" else "updated", "path": rel,
                      "after_sha256": _sha(data)}
                if act["action"] == "update":
                    old = root.read(rel)
                    root.write_atomic(_state(JOURNAL_DIR, tx, "backup", rel), old)
                    op["before_sha256"] = _sha(old)
                    op["executable_before"] = root.is_executable(rel)
                new_dirs = root.missing_dirs(rel)
                meta["created_dirs"].extend(new_dirs)
                meta["ops"].append(op)
                _save_meta(root, tx, meta)  # le journal précède l'écriture
                try:
                    root.write_atomic(rel, data, executable, replace=(act["action"] == "update"))
                except FileExistsError:
                    # un fichier est apparu depuis le plan : il n'est pas à nous, on ne l'écrase pas
                    meta["ops"].pop()
                    del meta["created_dirs"][len(meta["created_dirs"]) - len(new_dirs):]
                    _save_meta(root, tx, meta)
                    raise ActivationError("%s est apparu depuis l'aperçu : installation annulée" % rel)
            elif act["action"] == "remove":
                old = root.read(rel)
                root.write_atomic(_state(JOURNAL_DIR, tx, "backup", rel), old)
                meta["ops"].append({"kind": "removed", "path": rel, "before_sha256": _sha(old),
                                    "executable_before": root.is_executable(rel)})
                _save_meta(root, tx, meta)
                root.remove(rel)
            # "forget" : le fichier a déjà disparu, seul le verrou change
            if fault:
                fault(index)
        lock_after = {"version": 1, "components": pl["installed"], "history": lock_before.get("history", []) + [tx]}
        root.write_atomic(_state(LOCK_FILE), _dump(lock_after).encode("utf-8"))
        meta["status"] = "committed"
        _save_meta(root, tx, meta)
    except BaseException as exc:
        try:
            _undo(root, tx)
        except ActivationError as conflict:
            raise ActivationError("échec pendant l'installation (%s) et retour arrière bloqué : %s"
                                  % (exc, conflict), conflict.reasons) from exc
        raise ActivationError("échec pendant l'installation, retour arrière effectué : %s" % exc) from exc
    return {"transaction": tx, "applied": len(todo), "unchanged": unchanged, "recovered": recovered}


def rollback(project):
    """Annule la dernière installation, sauf si cela ferait perdre des modifications de l'utilisateur."""
    with Root(project) as root:
        try:
            has_lock = root.read(_state(LOCK_FILE)) is not None
        except UnsafePath as exc:
            raise ActivationError("dossier d'état hors du projet, retour arrière refusé : %s" % exc)
        if not has_lock:
            raise ActivationError("aucune installation à annuler")
        lock_fd = root.lock()
        try:
            _recover_interrupted(root)
            lock = _read_lock(root)
            if not lock["history"]:
                raise ActivationError("aucune installation à annuler")
            tx = lock["history"][-1]
            _undo(root, tx)
            return {"transaction": tx}
        finally:
            os.close(lock_fd)
