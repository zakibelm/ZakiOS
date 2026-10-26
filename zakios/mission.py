"""Coordinateur déterministe : demande -> plan -> revue -> corrections -> livraison contrôlée.

Ce module est du code, pas un agent. Il appelle des rôles (fonctions fournies : modèles réels ou faux de test),
lit leurs sorties selon des formats stricts, applique des règles écrites et n'écrit que par deux voies :
`deliver.save_plan` (le plan) et la trace de mission (`.zakios/missions/<mission_id>.json`, sans remplacement).

Règles :
- la demande et les critères sont immuables et transmis tels quels à chaque appel ;
- v1 + `max_corrections` corrections au plus (3 plans et 3 revues avec 2) ;
- chaque revue est liée à l'empreinte du plan examiné ; seule une revue ACCEPTE du **dernier** plan autorise la livraison ;
- les relances techniques (sortie hors format, erreur d'exécution) sont bornées à part ;
- au plafond ou après épuisement des relances : arrêt, rapport, rien n'est enregistré.
"""
import hashlib
import json
import re
import time

from . import deliver
from .activate import Root, UnsafePath

REVIEW_BEGIN = "=== DEBUT DE LA REVUE ZAKIOS ==="
REVIEW_END = "=== FIN DE LA REVUE ZAKIOS ==="
GRAVITIES = ("bloquant", "majeur", "mineur")
_VERDICT = re.compile(r"^Verdict\s*:\s*(ACCEPTE|A_CORRIGER)\s*$")
_FINDING = re.compile(r"^- \[(bloquant|majeur|mineur)\]\s+(.+)$")


class MissionError(deliver.DeliveryError):
    pass


class TechnicalError(Exception):
    """Sortie hors format ou exécution en erreur : relance bornée."""


def _sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def parse_review(text):
    """(verdict, constats) d'après la réponse du relecteur de plan. Refuse tout ce qui est hors format ou incohérent."""
    lines = text.split("\n")
    begins = [i for i, l in enumerate(lines) if l.strip() == REVIEW_BEGIN]
    ends = [i for i, l in enumerate(lines) if l.strip() == REVIEW_END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise TechnicalError("revue absente ou ambiguë : un seul bloc %s … %s attendu" % (REVIEW_BEGIN, REVIEW_END))
    verdict, findings = None, []
    for raw in lines[begins[0] + 1:ends[0]]:
        line = raw.strip()
        if not line:
            continue
        m = _VERDICT.match(line)
        if m:
            if verdict is not None:
                raise TechnicalError("deux verdicts dans la revue")
            verdict = m.group(1)
            continue
        m = _FINDING.match(line)
        if not m:
            raise TechnicalError("ligne hors format dans la revue : %r" % line[:80])
        body = m.group(2)
        low = body.lower()
        for word in ("problème", "action", "résultat", "preuve :"):
            if word not in low:
                raise TechnicalError("constat incomplet (« %s » manquant) : %r" % (word, line[:80]))
        findings.append({"gravite": m.group(1), "texte": body})
    if verdict is None:
        raise TechnicalError("verdict absent de la revue")
    blocking = [f for f in findings if f["gravite"] in ("bloquant", "majeur")]
    if verdict == "ACCEPTE" and blocking:
        raise TechnicalError("revue incohérente : ACCEPTE malgré un constat %s" % blocking[0]["gravite"])
    if verdict == "A_CORRIGER" and not blocking:
        raise TechnicalError("revue incohérente : A_CORRIGER sans constat bloquant ni majeur")
    return verdict, findings


def _attempt(call, parse, retries, log, label):
    """Appelle `call` puis `parse` ; relance au plus `retries` fois sur erreur technique."""
    errors = []
    for n in range(retries + 1):
        try:
            raw = call()
            return raw, parse(raw), errors
        except (TechnicalError, deliver.DeliveryError) as exc:
            errors.append("%s tentative %d : %s" % (label, n + 1, exc))
        except Exception as exc:  # erreur d'exécution du rôle
            errors.append("%s tentative %d : exécution en erreur (%s)" % (label, n + 1, exc))
    log.extend(errors)
    raise TechnicalError("; ".join(errors))


def derive_mission_id(request, criteria):
    return "m-" + _sha(json.dumps({"request": request, "criteria": list(criteria)}, ensure_ascii=False,
                                  sort_keys=True))[:16]


def write_trace(project, mission_id, trace):
    """Écrit la trace de mission une seule fois ; identique si elle existe (hors horodatage), sinon erreur."""
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$", mission_id):
        raise MissionError("identifiant de mission invalide : %r" % mission_id)
    rel = ".zakios/missions/%s.json" % mission_id
    body = dict(trace)
    payload = (json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    try:
        with Root(project) as root:
            try:
                root.write_atomic(rel, payload, replace=False)
            except FileExistsError:
                old = json.loads((root.read(rel) or b"{}").decode("utf-8"))
                stable = lambda d: {k: v for k, v in d.items() if k != "ecrit_le"}
                if stable(old) != stable(body):
                    raise MissionError("la trace %s existe déjà avec un autre contenu : rien n'est écrit" % rel)
    except UnsafePath as exc:
        raise MissionError("chemin de trace non sûr : %s" % exc)
    return rel


def run_mission(project, request, criteria, writer, reviewer, components=None, mission_id=None,
                max_corrections=2, max_technical_retries=1, now=None):
    """Exécute la mission. `writer(request, criteria, previous_plan, findings) -> texte` et
    `reviewer(request, criteria, plan) -> texte` sont fournis par l'appelant. Renvoie un compte rendu (dict)."""
    criteria = list(criteria)
    mission_id = mission_id or derive_mission_id(request, criteria)
    stamp = (now or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))()
    trace = {"v": 1, "mission_id": mission_id, "ecrit_le": stamp,
             "demande_sha256": _sha(request), "criteres": criteria, "criteres_sha256": _sha(json.dumps(criteria, ensure_ascii=False)),
             "composants": dict(components or {}), "tours": [], "erreurs_techniques": [],
             "max_corrections": max_corrections, "relances_techniques_max": max_technical_retries}
    plan = path = None
    findings = []
    outcome = None
    accepted_sha = None
    for turn in range(max_corrections + 1):
        try:
            _, (plan, path), errs = _attempt(
                lambda: writer(request, criteria, plan, findings), deliver.extract_plan,
                max_technical_retries, trace["erreurs_techniques"], "planificateur tour %d" % (turn + 1))
        except TechnicalError:
            outcome = "erreur_technique"
            break
        plan_sha = _sha(plan)
        entry = {"tour": turn + 1, "plan_sha256": plan_sha, "chemin_propose": path, "relances_planificateur": len(errs)}
        trace["tours"].append(entry)
        try:
            _, (verdict, found), errs = _attempt(
                lambda: reviewer(request, criteria, plan), parse_review,
                max_technical_retries, trace["erreurs_techniques"], "relecteur tour %d" % (turn + 1))
        except TechnicalError:
            outcome = "erreur_technique"
            break
        entry["revue"] = {"plan_examine_sha256": plan_sha, "verdict": verdict, "constats": len(found),
                          "gravites": [f["gravite"] for f in found], "revue_sha256": _sha(json.dumps(found, ensure_ascii=False)),
                          "relances_relecteur": len(errs)}
        entry["constats"] = found
        if verdict == "ACCEPTE":
            accepted_sha = plan_sha
            outcome = "accepte"
            break
        findings = [f["texte"] for f in found]
        outcome = "plafond_atteint"  # remplacé si un tour suivant est accepté
    result = {"mission_id": mission_id, "issue": outcome, "tours": len(trace["tours"]), "livraison": None}
    if outcome == "accepte":
        assert accepted_sha == _sha(plan)  # la revue acceptée porte sur le dernier plan
        info = deliver.preview(path, plan, mission_id)
        saved = deliver.save_plan(project, path, plan, info["delivery_sha256"], mission=mission_id)
        saved2 = deliver.save_plan(project, path, plan, info["delivery_sha256"], mission=mission_id)
        stable = {"chemin": path, "delivery_sha256": saved["delivery_sha256"],
                  "content_sha256": saved["content_sha256"], "trace": saved["trace"]}
        trace["livraison"] = stable  # sans statut : celui-ci dépend du passage, pas de la mission
        result["livraison"] = dict(stable, statut=saved["status"], second=saved2["status"])
    trace["issue"] = outcome
    result["trace"] = write_trace(project, mission_id, trace)
    result["tours_detail"] = trace["tours"]
    return result
