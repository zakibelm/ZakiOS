"""Classification des fichiers d'un dépôt source.

Types : skill, agent, embedded_agent, command, hook, plugin, mod, framework_module, socle.
Tout le reste (tests, documentation, ressources, configurations) est un fichier
annexe et n'est pas compté comme composant.

Un manifeste de plugin est un `plugin`, jamais un `hook` : un plugin est un
conteneur qui peut regrouper des skills, des agents et des hooks.
"""
import fnmatch

COMPONENT_TYPES = ("skill", "agent", "embedded_agent", "command", "hook", "plugin", "mod", "framework_module", "socle")

DOC_NAMES = {
    "readme.md", "changelog.md", "contributing.md", "license.md",
    "code_of_conduct.md", "security.md", "claude.md", "agents.md",
}
SCRIPT_EXTENSIONS = (".py", ".js", ".mjs", ".cjs", ".sh", ".ts")
IGNORED_DIRS = {"tests", "test", "__tests__", "node_modules", "__pycache__", ".git"}
HOOK_SUPPORT_DIRS = {"utils", "lib"}
AGENT_DIRS = {"agents", "subagents", "categories"}


def classify(rel, framework_globs=()):
    """Type du composant désigné par le chemin `rel` (relatif à la racine d'analyse), ou None."""
    parts = rel.split("/")
    low = [p.lower() for p in parts]
    name = low[-1]
    dirs = low[:-1]

    if any(d in IGNORED_DIRS for d in dirs):
        return None
    if name.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.py")) or name.startswith("test_"):
        return None
    for pattern in framework_globs:
        if fnmatch.fnmatch(rel, pattern):
            return "framework_module"

    if low == ["socle", "regles.md"]:
        return "socle"  # règles communes ZakiOS : un seul fichier, porté une seule fois

    if "mods" in dirs:
        # Un mod est un seul composant : son README le représente. Son plugin.json, ses hooks,
        # ses agents et ses autres fichiers lui appartiennent et ne sont pas comptés à part.
        i = dirs.index("mods")
        return "mod" if name == "readme.md" and len(parts) == i + 4 else None
    if name == "skill.md":
        return "skill"
    if name == "plugin.json" and ".claude-plugin" in dirs:
        return "plugin"
    if name in DOC_NAMES:
        return None

    if name.endswith(".md"):
        if "commands" in dirs:
            return "command"
        agent_idx = next((i for i, d in enumerate(dirs) if d in AGENT_DIRS), None)
        if agent_idx is not None:
            if "skills" in dirs and dirs.index("skills") < agent_idx:
                return "embedded_agent"
            return "agent"
        return None

    if name.endswith(SCRIPT_EXTENSIONS) and "hooks" in dirs and not any(d in HOOK_SUPPORT_DIRS for d in dirs):
        return "hook"
    if name.endswith(".json") and low[0] == "hooks" and len(parts) >= 3:
        return "hook"
    return None
