"""Coordinateur déterministe : demande -> plan -> revue -> corrections -> livraison contrôlée.

Ce module est du code, pas un agent. Il appelle des rôles (fonctions fournies : modèles réels ou faux de test),
lit leurs sorties selon des formats stricts, applique des règles écrites et n'écrit que par deux voies :
`deliver.save_plan` (le plan) et la trace de mission (`.zakios/missions/<mission_id>.json`, sans remplacement).

Règles :
- la demande et les critères sont immuables et transmis tels quels à chaque appel ;
- v1 + `max_corrections` corrections au plus (3 plans et 3 revues avec 2) ;
- chaque revue est liée à l'empreinte du plan examiné ; seule une revue ACCEPTE du **dernier** plan autorise la livraison ;
- les relances techniques (sortie hors format, erreur d'exécution) sont bornées à part ;
- verdict CLARIFICATION (critères contradictoires ou décision nécessaire de la personne) : arrêt immédiat, questions
  rapportées, aucune correction tentée, rien n'est enregistré ;
- ACCEPTE exige que chaque critère de la mission soit « couvert » : un critère abandonné ou non couvert l'interdit
  (contrôlé par le code sur la couverture rendue par le relecteur, pas laissé à son jugement) ;
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
GRAVITIES = ("bloquant", "majeur", "mineur", "clarification")
VERDICTS = ("ACCEPTE", "A_CORRIGER", "CLARIFICATION_REQUISE")
BUSINESS_OUTCOMES = ("accepte", "clarification_requise", "plafond_atteint")  # issues métier attendues
TECHNICAL_OUTCOMES = ("erreur_technique",)
COVERAGE_OK = "couvert"
COVERAGE_VALUES = ("couvert", "non_couvert", "abandonne")
_VERDICT = re.compile(r"^Verdict\s*:\s*(ACCEPTE|A_CORRIGER|CLARIFICATION_REQUISE)\s*$")
_FINDING = re.compile(r"^- \[(bloquant|majeur|mineur|clarification)\]\s+(.+)$")
_BINDING = re.compile(r"^Plan examin[ée]\s*:\s*([0-9a-f]{16})\s*$")
_CRITERION_ID = re.compile(r"^[A-Za-z]+[0-9]+$")
_COVERAGE = re.compile(r"^Couverture\s+(\S+)\s*:\s*(couvert|non_couvert|abandonn[ée])\s*$")


class MissionError(deliver.DeliveryError):
    pass


class TechnicalError(Exception):
    """Sortie hors format ou exécution en erreur : relance bornée."""


def _sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def criterion_id(criterion):
    """Identifiant d'un critère de mission : son premier mot (ex. « C1 remise correcte… » -> « C1 »)."""
    parts = criterion.split()
    if not parts:
        raise MissionError("critère de mission vide")
    return parts[0]


def plan_fingerprint(plan):
    """Empreinte courte (16 hex) du plan examiné ; le relecteur doit la recopier (« Plan examiné : … »)."""
    return _sha(plan)[:16]


def validate_criteria(criteria):
    """Identifiants stables : premier mot de chaque critère, de la forme lettres+chiffres (C1, K2…), uniques.
    Renvoie {identifiant: formulation complète}, conservée telle quelle dans la trace."""
    ids = {}
    for c in criteria:
        cid = criterion_id(c)
        if not _CRITERION_ID.match(cid):
            raise MissionError("identifiant de critère invalide : %r (attendu : lettres puis chiffres, ex. C1)" % cid)
        if cid in ids:
            raise MissionError("identifiant de critère en double : %s" % cid)
        ids[cid] = c
    if not ids:
        raise MissionError("aucun critère de mission")
    return ids


def parse_clarification(body, known_ids=None):
    """Constat de clarification : `critères : K1, K2 · blocage : … · question : … ?` (les trois champs sont obligatoires)."""
    fields = {}
    for part in body.split("·"):
        m = re.match(r"^\s*(crit[èe]res?|blocage|question)\s*:\s*(.+?)\s*$", part, re.I | re.S)
        if m:
            key = m.group(1).lower().replace("è", "e")
            key = "criteres" if key.startswith("critere") else key
            if key in fields:
                raise TechnicalError("champ de clarification en double : %s" % key)
            fields[key] = m.group(2)
    for key in ("criteres", "blocage", "question"):
        if not fields.get(key):
            raise TechnicalError("clarification incomplète : champ « %s » manquant" % key)
    ids = [x.strip() for x in re.split(r"[,;]", fields["criteres"]) if x.strip()]
    if not ids:
        raise TechnicalError("clarification sans critère concerné")
    if known_ids is not None:
        unknown = [i for i in ids if i not in known_ids]
        if unknown:
            raise TechnicalError("clarification sur un critère inconnu : %s" % ", ".join(unknown))
    if "?" not in fields["question"]:
        raise TechnicalError("la clarification doit formuler une question précise (point d'interrogation attendu)")
    return {"criteres": ids, "blocage": fields["blocage"], "question": fields["question"]}


def parse_review_full(text, criteria=None, plan_sha=None):
    """(verdict, constats, couverture) d'après la réponse du relecteur de plan.

    Contrôles DÉTERMINISTES de format et de cohérence (le code les impose, le relecteur ne peut pas les contourner) :
    - ACCEPTE exige : aucun constat bloquant, majeur ou de clarification, et **chaque critère de la mission « couvert »** ;
    - A_CORRIGER exige au moins un constat bloquant ou majeur et aucune clarification ;
    - CLARIFICATION_REQUISE exige au moins un constat `[clarification]` complet (critères concernés, blocage, question) ;
    - si `criteria` est fourni, la couverture nomme chaque critère une fois, sans en inventer ;
    - si `plan_sha` est fourni, la revue doit recopier l'empreinte du plan examiné (« Plan examiné : … »), sinon refus.
    Ce qui n'est PAS garanti par le code : que la couverture déclarée soit sémantiquement juste. C'est un jugement du
    relecteur (modèle), mesuré par les essais, pas une garantie technique."""
    lines = text.split("\n")
    begins = [i for i, l in enumerate(lines) if l.strip() == REVIEW_BEGIN]
    ends = [i for i, l in enumerate(lines) if l.strip() == REVIEW_END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise TechnicalError("revue absente ou ambiguë : un seul bloc %s … %s attendu" % (REVIEW_BEGIN, REVIEW_END))
    known_ids = None if criteria is None else [criterion_id(c) for c in criteria]
    verdict, findings, coverage, bound = None, [], {}, []
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
        m = _BINDING.match(line)
        if m:
            bound.append(m.group(1))
            continue
        m = _COVERAGE.match(line)
        if m:
            cid, value = m.group(1), m.group(2).replace("é", "e")
            if cid in coverage:
                raise TechnicalError("couverture en double pour le critère %s" % cid)
            coverage[cid] = value
            continue
        m = _FINDING.match(line)
        if not m:
            raise TechnicalError("ligne hors format dans la revue : %r" % line[:80])
        body = m.group(2)
        if m.group(1) == "clarification":
            finding = {"gravite": "clarification", "texte": body}
            finding.update(parse_clarification(body, known_ids))
            findings.append(finding)
            continue
        low = body.lower()
        for word in ("problème", "action", "résultat", "preuve :"):
            if word not in low:
                raise TechnicalError("constat incomplet (« %s » manquant) : %r" % (word, line[:80]))
        findings.append({"gravite": m.group(1), "texte": body})
    if verdict is None:
        raise TechnicalError("verdict absent de la revue")
    if plan_sha is not None:
        if len(bound) != 1 or bound[0] != plan_sha[:16]:
            raise TechnicalError("revue liée à une autre empreinte : attendu %s, reçu %s" % (plan_sha[:16], bound or "aucune"))
    if criteria is not None:
        if sorted(coverage) != sorted(known_ids):
            raise TechnicalError("couverture incohérente : critères attendus %s, reçus %s" % (known_ids, sorted(coverage)))
    blocking = [f for f in findings if f["gravite"] in ("bloquant", "majeur")]
    clarif = [f for f in findings if f["gravite"] == "clarification"]
    not_covered = sorted(c for c, v in coverage.items() if v != COVERAGE_OK)
    if verdict == "ACCEPTE":
        if blocking:
            raise TechnicalError("revue incohérente : ACCEPTE malgré un constat %s" % blocking[0]["gravite"])
        if clarif:
            raise TechnicalError("revue incohérente : ACCEPTE malgré une clarification requise")
        if not_covered:
            raise TechnicalError("revue incohérente : ACCEPTE malgré un critère abandonné ou non couvert (%s)" % ", ".join(not_covered))
    elif verdict == "A_CORRIGER":
        if clarif:
            raise TechnicalError("revue incohérente : A_CORRIGER avec une clarification requise (verdict CLARIFICATION_REQUISE attendu)")
        if not blocking:
            raise TechnicalError("revue incohérente : A_CORRIGER sans constat bloquant ni majeur")
    else:  # CLARIFICATION_REQUISE
        if not clarif:
            raise TechnicalError("revue incohérente : CLARIFICATION_REQUISE sans constat de clarification")
    return verdict, findings, coverage


def parse_review(text, criteria=None, plan_sha=None):
    """(verdict, constats) — voir `parse_review_full`."""
    verdict, findings, _ = parse_review_full(text, criteria, plan_sha)
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


def assert_review_binding(entry):
    """Garde défensive : la revue d'un tour porte bien l'empreinte du plan de ce tour (sinon MissionError)."""
    revue = entry.get("revue")
    if not revue or revue.get("plan_examine_sha256") != entry.get("plan_sha256"):
        raise MissionError("revue liée à une autre empreinte que celle du plan du tour %s" % entry.get("tour"))


def run_mission(project, request, criteria, writer, reviewer, components=None, mission_id=None,
                max_corrections=2, max_technical_retries=1, now=None):
    """Exécute la mission. `writer(request, criteria, previous_plan, findings) -> texte` et
    `reviewer(request, criteria, plan) -> texte` sont fournis par l'appelant. Renvoie un compte rendu (dict).

    Issues métier attendues : `accepte`, `clarification_requise`, `plafond_atteint` (catégorie « metier »).
    `erreur_technique` (catégorie « technique ») est un dysfonctionnement, pas un résultat de mission."""
    criteria = list(criteria)
    ids = validate_criteria(criteria)
    mission_id = mission_id or derive_mission_id(request, criteria)
    stamp = (now or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))()
    trace = {"v": 2, "mission_id": mission_id, "ecrit_le": stamp,
             "demande_sha256": _sha(request), "criteres": criteria, "criteres_ids": ids,
             "criteres_sha256": _sha(json.dumps(criteria, ensure_ascii=False)),
             "composants": dict(components or {}), "tours": [], "erreurs_techniques": [],
             "max_corrections": max_corrections, "relances_techniques_max": max_technical_retries}
    calls = {"plan-writer": 0, "plan-reviewer": 0}

    def counted_writer(*args):
        calls["plan-writer"] += 1
        return writer(*args)

    def counted_reviewer(*args):
        calls["plan-reviewer"] += 1
        return reviewer(*args)

    plan = path = None
    findings = []
    outcome = None
    accepted_sha = None
    cause, concerned = None, []
    for turn in range(max_corrections + 1):
        try:
            _, (plan, path), errs = _attempt(
                lambda: counted_writer(request, criteria, plan, findings), deliver.extract_plan,
                max_technical_retries, trace["erreurs_techniques"], "planificateur tour %d" % (turn + 1))
        except TechnicalError:
            outcome, cause = "erreur_technique", "sortie du planificateur invalide ou exécution en erreur (relances épuisées)"
            break
        plan_sha = _sha(plan)
        entry = {"tour": turn + 1, "plan_sha256": plan_sha, "chemin_propose": path, "relances_planificateur": len(errs)}
        trace["tours"].append(entry)
        try:
            _, (verdict, found, coverage), errs = _attempt(
                lambda: counted_reviewer(request, criteria, plan),
                lambda raw: parse_review_full(raw, criteria, plan_sha),
                max_technical_retries, trace["erreurs_techniques"], "relecteur tour %d" % (turn + 1))
        except TechnicalError:
            outcome, cause = "erreur_technique", "revue invalide, incohérente ou liée à une autre empreinte (relances épuisées)"
            break
        entry["revue"] = {"plan_examine_sha256": plan_sha, "verdict": verdict, "constats": len(found),
                          "gravites": [f["gravite"] for f in found], "revue_sha256": _sha(json.dumps(found, ensure_ascii=False)),
                          "couverture": coverage, "relances_relecteur": len(errs)}
        entry["constats"] = found
        assert_review_binding(entry)
        if verdict == "CLARIFICATION_REQUISE":
            # une décision de la personne est nécessaire : la boucle s'arrête, aucune correction n'est tentée, rien n'est livré
            clarifs = [f for f in found if f["gravite"] == "clarification"]
            concerned = sorted({c for f in clarifs for c in f["criteres"]})
            trace["clarification"] = {"tour": turn + 1, "plan_sha256": plan_sha, "criteres": concerned,
                                      "questions": [f["question"] for f in clarifs], "blocages": [f["blocage"] for f in clarifs]}
            outcome, cause = "clarification_requise", "; ".join(f["blocage"] for f in clarifs)
            break
        if verdict == "ACCEPTE":
            accepted_sha = plan_sha
            outcome = "accepte"
            break
        findings = [f["texte"] for f in found]
        outcome = "plafond_atteint"  # remplacé si un tour suivant est accepté
        concerned = sorted(c for c, v in coverage.items() if v != COVERAGE_OK)
        cause = "%d plans refusés (A_CORRIGER) ; dernier verdict : %s" % (len(trace["tours"]), "; ".join(findings)[:300])
    category = "technique" if outcome in TECHNICAL_OUTCOMES else "metier"
    result = {"mission_id": mission_id, "issue": outcome, "categorie": category, "tours": len(trace["tours"]),
              "livraison": None, "questions": list(trace.get("clarification", {}).get("questions", [])),
              "appels": dict(calls)}
    if outcome == "accepte":
        assert accepted_sha == _sha(plan)  # la revue acceptée porte sur le dernier plan
        assert all(v == COVERAGE_OK for v in trace["tours"][-1]["revue"]["couverture"].values())  # aucun critère abandonné
        info = deliver.preview(path, plan, mission_id)
        saved = deliver.save_plan(project, path, plan, info["delivery_sha256"], mission=mission_id)
        saved2 = deliver.save_plan(project, path, plan, info["delivery_sha256"], mission=mission_id)
        stable = {"chemin": path, "delivery_sha256": saved["delivery_sha256"],
                  "content_sha256": saved["content_sha256"], "trace": saved["trace"]}
        trace["livraison"] = stable  # sans statut : celui-ci dépend du passage, pas de la mission
        result["livraison"] = dict(stable, statut=saved["status"], second=saved2["status"])
    else:
        # trace de l'arrêt : cause, critères concernés, empreintes des plans, appels déjà effectués (aucune livraison)
        trace["arret"] = {"issue": outcome, "categorie": category, "cause": cause, "criteres_concernes": concerned,
                          "plans_sha256": [t["plan_sha256"] for t in trace["tours"]], "appels": dict(calls)}
    trace["issue"] = outcome
    trace["categorie"] = category
    result["trace"] = write_trace(project, mission_id, trace)
    result["tours_detail"] = trace["tours"]
    return result
