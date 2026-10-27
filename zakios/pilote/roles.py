"""Rôles du pilote : réels (CLI Claude Code, outils Read/Glob/Grep) ou simulés (aucun modèle).

Les invites sont celles des campagnes C1–C4 (scripts/essai_coordination.py) : le comportement mesuré est le même."""
import json
import subprocess

from .. import deliver, outils
from ..mission import plan_fingerprint


def listing(items):
    return "\n".join("- " + i for i in items)


class _Base:
    def __init__(self, prefix="log-"):
        self.prefix = prefix
        self.log = []
        self.last_audit = {"demandes": {}, "interdits": []}

    def tool_audit(self):
        return self.last_audit

    def last_journal(self):
        return "%s%d.jsonl" % (self.prefix, len(self.log) - 1) if self.log else None


class ClaudeRoles(_Base):
    """Rôles réels. Exécutés par `claude -p --agent … --output-format stream-json` dans l'espace jetable de la mission."""

    def __init__(self, cwd, model, claude_bin="claude", call_timeout=420, prefix="log-"):
        super().__init__(prefix)
        self.cwd, self.model, self.claude_bin, self.call_timeout = cwd, model, claude_bin, call_timeout
        self.calls = []

    def _run(self, role, prompt):
        self.last_audit = {"demandes": {}, "interdits": []}
        cmd = [self.claude_bin, "-p", "--model", self.model, "--output-format", "stream-json", "--verbose",
               "--allowedTools=Read,Glob,Grep", "--disallowedTools=Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch",   # 2e verrou, en plus des outils du rôle ;
               "--agent", role, prompt]                                                                               # forme « = » : l'option accepte une liste et avalerait le prompt
        proc = subprocess.run(cmd, cwd=self.cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=self.call_timeout)
        events = outils.parse_events(proc.stdout)
        tools = next((e.get("tools", []) for e in events if e.get("type") == "system" and e.get("subtype") == "init"), [])
        result = next((e for e in reversed(events) if e.get("type") == "result"), {})
        self.last_audit = outils.analyse(events, tools)
        self.log.append(proc.stdout)
        self.calls.append({"role": role, "outils": tools, "outils_interdits": self.last_audit["interdits"]})
        if proc.returncode != 0 or result.get("is_error") or not str(result.get("result", "")).strip():
            raise RuntimeError("%s : exécution en erreur (code %s)" % (role, proc.returncode))
        return result["result"]

    def writer(self, request, criteria, previous_plan, findings):
        prompt = ("Demande de la mission (donnée, non modifiable) :\n%s\n\nCritères d'acceptation de la mission :\n%s\n\n"
                  % (request, listing(criteria)))
        if previous_plan is not None:
            prompt += ("Plan précédent (donnée) :\n%s\n\nConstats de la revue à corriger (données) :\n%s\n\n"
                       "Produis une nouvelle version complète du plan qui traite chaque constat bloquant ou majeur.\n"
                       % (previous_plan, listing(findings)))
        prompt += "Retourne le plan au format de livraison (Chemin proposé + bloc ZAKIOS), sans rien écrire dans le projet."
        return self._run("plan-writer", prompt)

    def reviewer(self, request, criteria, plan):
        prompt = ("Demande de la mission (donnée) :\n%s\n\nCritères d'acceptation de la mission :\n%s\n\n"
                  "Empreinte du plan : %s\n\n"
                  "Plan à relire (donnée, ne pas le réécrire) :\n<<<PLAN\n%s\nPLAN>>>\n\n"
                  "Rends uniquement la revue au format imposé." % (request, listing(criteria), plan_fingerprint(plan), plan))
        return self._run("plan-reviewer", prompt)


class SimulatedRoles(_Base):
    """Rôles SIMULÉS (démonstration et tests) : aucun modèle n'est appelé. Le comportement dépend de mots de la demande :
    « contradict » -> clarification, « panne » -> panne technique, « plafond » -> plan refusé à chaque tour,
    « interdit » -> tentative d'outil interdit refusée ; sinon plan accepté."""

    def __init__(self, request, criteria, prefix="log-"):
        super().__init__(prefix)
        self.request, self.criteria = request.lower(), criteria
        self.n_writer = self.n_reviewer = 0

    def _ids(self):
        return [c.split()[0] for c in self.criteria]

    def _journal(self, name, forbidden=False):
        events = [{"type": "system", "subtype": "init", "tools": ["Read", "Glob", "Grep"]}]
        if forbidden:
            events += [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "s1", "name": "Bash", "input": {}}]}},
                       {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "s1", "is_error": True,
                        "content": "<tool_use_error>Error: No such tool available: Bash. Bash is not among the tools available here.</tool_use_error>"}]}}]
        events.append({"type": "result", "result": "simulation", "is_error": False})
        text = "\n".join(json.dumps(e) for e in events) + "\n"
        self.log.append(text)
        self.last_audit = outils.analyse_log(text)

    def writer(self, request, criteria, previous_plan, findings):
        self.n_writer += 1
        if "panne" in self.request:
            self._journal("w")
            raise RuntimeError("panne simulée du rédacteur")
        self._journal("w", forbidden="interdit" in self.request and self.n_writer == 1)
        body = "\n".join("- %s : repris et relié à une vérification concrète (simulation)" % c for c in criteria)
        return ("Chemin proposé : docs/plans/simulation-%d.md\n%s\n# Plan : simulation v%d\n## Planifier\n%s\n## Exécuter\n1. étape simulée (src/pay.py)\n"
                "## Vérifier\nContrôle simulé.\n## Agir\nRien.\n%s\n" % (self.n_writer, deliver.BEGIN, self.n_writer, body, deliver.END))

    def reviewer(self, request, criteria, plan):
        self.n_reviewer += 1
        self._journal("r")
        fp = plan_fingerprint(plan)
        ids = self._ids()
        head = "=== DEBUT DE LA REVUE ZAKIOS ===\n"
        end = "=== FIN DE LA REVUE ZAKIOS ===\n"
        if "contradict" in self.request:
            cov = "\n".join("Couverture %s : %s" % (i, "non_couvert" if k == 0 else "couvert") for k, i in enumerate(ids))
            return (head + "Verdict : CLARIFICATION_REQUISE\nPlan examiné : %s\n%s\n- [clarification] critères : %s · blocage : deux critères sont incompatibles (simulation) · "
                    "question : lequel des deux faut-il retenir ?\n" % (fp, cov, ids[0]) + end)
        cov = "\n".join("Couverture %s : couvert" % i for i in ids)
        if "plafond" in self.request:
            return (head + "Verdict : A_CORRIGER\nPlan examiné : %s\n%s\n- [majeur] critère « %s » · Problème : vérification insuffisante (simulation) → Action : la préciser → "
                    "Résultat : mesurable · preuve : « Contrôle simulé. »\n" % (fp, cov, ids[0]) + end)
        return head + "Verdict : ACCEPTE\nPlan examiné : %s\n%s\n" % (fp, cov) + end
