"""Aides de test : dépôts git minuscules construits à la volée."""
import json
import os
import subprocess
import tempfile

_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(path, *args):
    env = dict(os.environ, **_ENV)
    out = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, env=env, check=True)
    return out.stdout.strip()


def make_repo(sources_root, repo, files):
    """Crée <sources_root>/<owner>/<repo>, y committe `files` et renvoie le commit complet."""
    path = os.path.join(sources_root, *repo.split("/"))
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main")
    for rel, content in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "fixture")
    return git(path, "rev-parse", "HEAD")


def agent(name, description, body="Corps de l'agent."):
    return "---\nname: %s\ndescription: %s\n---\n\n%s\n" % (name, description, body)


FRONTEND = "builds accessible react components with typescript hooks state management and responsive layouts"
BACKEND = "designs rest endpoints database schemas authentication middleware and background job queues"
DEVOPS = "automates kubernetes deployments terraform pipelines container registries and monitoring dashboards"
DATA = "cleans datasets trains regression models evaluates metrics and produces notebook visualisations"
SECURITY = "audits dependencies scans secrets reviews permissions and writes threat models for services"


def make_world(workdir):
    """Un catalogue et un socle minuscules. Renvoie (sources_root, chemin du manifeste, commits)."""
    root = os.path.join(workdir, "sources")
    socle = make_repo(root, "acme/socle", {
        "agents/frontend-developer.md": agent("frontend-developer", FRONTEND),
        "agents/backend-developer.md": agent("backend-developer", BACKEND),
        "agents/data-scientist.md": agent("data-scientist", DATA),
        "agents/README.md": "# doc, pas un composant\n",
        "skills/security-scan/SKILL.md": "---\nname: security-scan\ndescription: %s\n---\nCorps\n" % SECURITY,
    })
    cat = make_repo(root, "acme/catalogue", {
        "components/agents/web/frontend-dev.md": agent("frontend-dev", FRONTEND + " and design systems"),
        "components/agents/ops/devops-engineer.md": agent("devops-engineer", DEVOPS),
        "components/agents/sec/security-auditor.md": agent("security-auditor", SECURITY),
        "components/hooks/git/guard.json": json.dumps({"description": "blocks pushes to main " + SECURITY}),
        "components/hooks/git/guard.py": "# Bloque les pushes directs vers main avant exécution du hook ici\nprint('x')\n",
        "components/mods/security/jail/README.md": "# jail\n\nRestreint les écritures de fichiers hors du projet pendant la session courante.\n",
        "components/mods/security/jail/.claude-plugin/plugin.json": json.dumps({"name": "jail", "description": "x"}),
        "components/mods/security/jail/hooks/block.ts": "export const x = 1\n",
        "components/skills/dev/SKILL.md": "---\nname: tdd\ndescription: >-\n  Guide pour écrire\n  des tests d'abord.\n---\nCorps\n",
    })
    manifest = {"sources": [
        {"repo": "acme/catalogue", "role": "catalogue", "commit": cat, "subdir": "components"},
        {"repo": "acme/socle", "role": "socle", "commit": socle},
        {"repo": "acme/zaki-os", "role": "existant", "required": False},
    ]}
    manifest_path = os.path.join(workdir, "sources.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle)
    return root, manifest_path, {"catalogue": cat, "socle": socle}


def change_source(root, manifest_path, repo, files):
    """Modifie et committe des fichiers d'une source, puis met le commit du manifeste à jour."""
    path = os.path.join(root, *repo.split("/"))
    for rel, content in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "change")
    commit = git(path, "rev-parse", "HEAD")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    for src in manifest["sources"]:
        if src["repo"] == repo:
            src["commit"] = commit
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle)
    return commit


class Workdir:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        return self._tmp.name

    def __exit__(self, *exc):
        self._tmp.cleanup()
