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

from . import deliver, outils
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


class ConfinementError(Exception):
    """Un outil interdit a été exécuté (ou on ne peut pas exclure qu'il l'ait été) : arrêt immédiat, jamais relancé."""


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


def _audit_tools(trace, role, turn, attempt, journal, tool_audit):
    """Inscrit les outils interdits demandés par l'appel qui vient d'avoir lieu (même si l'appel a échoué).
    Renvoie (audit, évènements bloquants) ; chaque outil interdit demandé reste visible comme écart comportemental."""
    if tool_audit is None:
        return None, []
    audit = tool_audit() or {"demandes": {}, "interdits": []}
    ref = journal() if journal else None
    for ev in audit["interdits"]:
        trace["ecarts_comportementaux"].append({"role": role, "tour": turn, "tentative": attempt, "outil": ev["outil"],
                                                "id": ev["id"], "statut": ev["statut"], "preuve": ev["preuve"], "journal": ref})
    return audit, [ev for ev in audit["interdits"] if ev["statut"] in outils.BLOCKING]


def _attempt(call, parse, retries, trace, role, turn, journal=None, tool_audit=None):
    """Appelle `call` puis `parse` ; relance au plus `retries` fois sur erreur technique.

    Chaque appel est inscrit dans le registre ordonné `trace["appels_detail"]` (avec les outils demandés) et chaque
    tentative refusée dans `trace["erreurs_techniques"]` (rôle, tour, numéro de tentative, catégorie, cause, empreinte
    de la sortie, lien vers le journal), **même si une relance réussit ensuite** (`recuperee`).
    Un outil interdit dont l'exécution est confirmée ou indéterminée arrête tout (ConfinementError, jamais relancé)."""
    errors = []
    for n in range(retries + 1):
        raw, category, cause = None, None, None
        try:
            raw = call()
        except (TechnicalError, deliver.DeliveryError) as exc:
            category, cause = "execution", str(exc)
        except Exception as exc:  # erreur d'exécution du rôle
            category, cause = "execution", "exécution en erreur (%s)" % exc
        audit, blocking = _audit_tools(trace, role, turn, n + 1, journal, tool_audit)
        entry = {"n": len(trace["appels_detail"]) + 1, "role": role, "tour": turn, "tentative": n + 1}
        if audit is not None:
            entry["outils"] = {"demandes": audit["demandes"],
                               "interdits": [{"outil": e["outil"], "id": e["id"], "statut": e["statut"]} for e in audit["interdits"]]}
        if blocking:
            entry["resultat"] = "bloque_outil_interdit"
            trace["appels_detail"].append(entry)
            raise ConfinementError("%s tour %d : outil interdit %s (%s)" % (
                role, turn, ", ".join(e["outil"] for e in blocking), ", ".join(e["statut"] for e in blocking)))
        parsed = None
        if category is None:
            try:
                parsed = parse(raw)
            except (TechnicalError, deliver.DeliveryError) as exc:
                category, cause = "format", str(exc)
        if category is None:
            entry["resultat"] = "valide"
            trace["appels_detail"].append(entry)
            for e in errors:
                e["recuperee"] = True
            return raw, parsed, errors
        err = {"role": role, "tour": turn, "tentative": n + 1, "categorie": category, "cause": cause,
               "sortie_sha256": _sha(raw) if isinstance(raw, str) else None,
               "journal": journal() if journal else None, "recuperee": False}
        errors.append(err)
        trace["erreurs_techniques"].append(err)
        entry["resultat"] = "refuse_" + category
        trace["appels_detail"].append(entry)
    raise TechnicalError("; ".join("%s tour %d tentative %d : %s" % (e["role"], e["tour"], e["tentative"], e["cause"])
                                   for e in errors))


def check_trace(trace):
    """Cohérence interne d'une trace v2 (déterministe) : renvoie la liste des divergences (vide si cohérente).

    Contrôle : registre des appels ordonné et numéroté ; par rôle, appels = valides + refusés = trace["appels"] ;
    chaque refus a son entrée dans `erreurs_techniques` (et réciproquement), avec tentative <= relances + 1 ;
    relances par tour cohérentes ; après une clarification, aucun appel : le dernier appel est la revue valide du
    tour de la clarification ; aucune livraison après clarification, plafond ou erreur."""
    out = []
    ledger = trace.get("appels_detail", [])
    errors = trace.get("erreurs_techniques", [])
    maxr = trace.get("relances_techniques_max", 1)
    if [e.get("n") for e in ledger] != list(range(1, len(ledger) + 1)):
        out.append("registre des appels non ordonné")
    for role in ("plan-writer", "plan-reviewer"):
        mine = [e for e in ledger if e["role"] == role]
        refused = [e for e in mine if e["resultat"].startswith("refuse_")]
        if len(mine) != trace.get("appels", {}).get(role):
            out.append("%s : %d appels au registre, %s annoncés" % (role, len(mine), trace.get("appels", {}).get(role)))
        if len(refused) != len([e for e in errors if e["role"] == role]):
            out.append("%s : %d refus au registre, %d erreurs tracées" % (role, len(refused), len([e for e in errors if e["role"] == role])))
    for e in errors:
        if not (1 <= e["tentative"] <= maxr + 1):
            out.append("tentative %s hors des relances bornées (%d)" % (e["tentative"], maxr))
        if e["categorie"] not in ("format", "execution"):
            out.append("catégorie d'erreur inconnue : %s" % e["categorie"])
        if e["categorie"] == "format" and not e.get("sortie_sha256"):
            out.append("refus de format sans empreinte de sortie (tour %s)" % e["tour"])
    for t in trace.get("tours", []):
        for role, key in (("plan-writer", "relances_planificateur"), ("plan-reviewer", "relances_relecteur")):
            holder = t if key == "relances_planificateur" else t.get("revue")
            if holder is None:
                continue
            n = len([e for e in errors if e["role"] == role and e["tour"] == t["tour"] and e["recuperee"]])
            if holder.get(key) != n:
                out.append("tour %s : %s=%s, erreurs récupérées tracées=%d" % (t["tour"], key, holder.get(key), n))
    if trace.get("issue") == "clarification_requise":
        last = ledger[-1] if ledger else None
        if not last or last["role"] != "plan-reviewer" or last["resultat"] != "valide" or last["tour"] != trace["clarification"]["tour"]:
            out.append("un appel suit ou précède mal la clarification (dernier appel : %s)" % last)
    ecarts = trace.get("ecarts_comportementaux", [])
    listed = [e for x in ledger for e in x.get("outils", {}).get("interdits", [])]
    if len(listed) != len(ecarts):
        out.append("%d outils interdits au registre, %d écarts tracés" % (len(listed), len(ecarts)))
    for e in ecarts:
        if e["statut"] not in outils.STATUSES:
            out.append("statut d'écart inconnu : %s" % e["statut"])
    blocking = [e for e in ecarts if e["statut"] in outils.BLOCKING]
    if blocking:
        if trace.get("issue") != "erreur_technique" or trace.get("arret", {}).get("sous_categorie") != "confinement":
            out.append("exécution interdite ou indéterminée sans arrêt « confinement »")
        if not ledger or ledger[-1]["resultat"] != "bloque_outil_interdit":
            out.append("appel après un outil interdit exécuté ou indéterminé")
    elif any(x["resultat"] == "bloque_outil_interdit" for x in ledger):
        out.append("appel bloqué sans écart bloquant tracé")
    if trace.get("issue") != "accepte" and "livraison" in trace:
        out.append("livraison présente après %s" % trace.get("issue"))
    if trace.get("issue") == "erreur_technique" and not errors and trace.get("arret", {}).get("sous_categorie") != "confinement":
        out.append("erreur technique sans erreur tracée")
    return out


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
                max_corrections=2, max_technical_retries=1, now=None, journal=None, tool_audit=None, livraison="immediate"):
    """Exécute la mission. `writer(request, criteria, previous_plan, findings) -> texte` et
    `reviewer(request, criteria, plan) -> texte` sont fournis par l'appelant. Renvoie un compte rendu (dict).

    Issues métier attendues : `accepte`, `clarification_requise`, `plafond_atteint` (catégorie « metier »).
    `erreur_technique` (catégorie « technique ») est un dysfonctionnement, pas un résultat de mission.
    `journal()` (facultatif) renvoie la référence du journal du dernier appel réel, pour la trace des erreurs.
    `tool_audit()` (facultatif) renvoie l'analyse des outils demandés par le dernier appel (voir `outils.analyse`) :
    une demande refusée par la plateforme est signalée (écart comportemental) sans bloquer ; une exécution confirmée
    ou indéterminée d'un outil interdit arrête immédiatement la mission (erreur technique « confinement »), sans livraison.
    `livraison="immediate"` (défaut, comportement des campagnes C1–C4) enregistre le plan accepté ; `"differee"` ne fait
    que calculer l'aperçu exact : l'enregistrement exige ensuite `confirmer_livraison` (confirmation explicite)."""
    if livraison not in ("immediate", "differee"):
        raise MissionError("mode de livraison inconnu : %r" % livraison)
    criteria = list(criteria)
    ids = validate_criteria(criteria)
    mission_id = mission_id or derive_mission_id(request, criteria)
    stamp = (now or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))()
    trace = {"v": 2, "mission_id": mission_id, "ecrit_le": stamp,
             "demande_sha256": _sha(request), "criteres": criteria, "criteres_ids": ids,
             "criteres_sha256": _sha(json.dumps(criteria, ensure_ascii=False)),
             "composants": dict(components or {}), "tours": [], "erreurs_techniques": [], "appels_detail": [], "ecarts_comportementaux": [],
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
    cause, concerned, sub = None, [], None
    for turn in range(max_corrections + 1):
        try:
            _, (plan, path), errs = _attempt(
                lambda: counted_writer(request, criteria, plan, findings), deliver.extract_plan,
                max_technical_retries, trace, "plan-writer", turn + 1, journal, tool_audit)
        except ConfinementError as exc:
            outcome, cause, sub = "erreur_technique", "confinement : %s" % exc, "confinement"
            break
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
                max_technical_retries, trace, "plan-reviewer", turn + 1, journal, tool_audit)
        except ConfinementError as exc:
            outcome, cause, sub = "erreur_technique", "confinement : %s" % exc, "confinement"
            break
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
              "appels": dict(calls), "ecarts": list(trace["ecarts_comportementaux"])}
    if outcome == "accepte":
        assert accepted_sha == _sha(plan)  # la revue acceptée porte sur le dernier plan
        assert all(v == COVERAGE_OK for v in trace["tours"][-1]["revue"]["couverture"].values())  # aucun critère abandonné
        info = deliver.preview(path, plan, mission_id)
        if livraison == "differee":
            # aperçu exact seulement : rien n'est écrit dans le projet avant `confirmer_livraison`
            trace["livraison_differee"] = True
            trace["apercu"] = {"chemin": path, "delivery_sha256": info["delivery_sha256"], "content_sha256": info["content_sha256"]}
            result["apercu"] = dict(trace["apercu"], plan=plan)
        else:
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
        if sub:
            trace["arret"]["sous_categorie"] = sub
    trace["issue"] = outcome
    trace["categorie"] = category
    trace["appels"] = dict(calls)
    result["trace"] = write_trace(project, mission_id, trace)
    result["tours_detail"] = trace["tours"]
    return result


def confirmer_livraison(project, mission_id, plan_text, expected_delivery_sha256):
    """Enregistrement contrôlé d'un plan ACCEPTE dont la livraison a été différée (confirmation explicite).

    Refuse : trace absente ou non acceptée, livraison non différée, empreinte de livraison différente de celle présentée,
    plan différent de celui examiné et accepté, revue non ACCEPTE ou critère non couvert. Idempotent (double
    confirmation -> « deja_enregistre ») ; jamais d'écrasement (délégué à `deliver.save_plan`)."""
    rel = ".zakios/missions/%s.json" % mission_id
    try:
        with Root(project) as root:
            raw = root.read(rel)
    except UnsafePath as exc:
        raise MissionError("chemin de trace non sûr : %s" % exc)
    if raw is None:
        raise MissionError("trace de mission introuvable : %s" % mission_id)
    trace = json.loads(raw.decode("utf-8"))
    if trace.get("issue") != "accepte" or not trace.get("livraison_differee") or "apercu" not in trace:
        raise MissionError("aucune livraison à confirmer pour cette mission (issue : %s)" % trace.get("issue"))
    last = trace["tours"][-1]
    revue = last.get("revue") or {}
    if revue.get("verdict") != "ACCEPTE" or any(v != COVERAGE_OK for v in revue.get("couverture", {}).values()):
        raise MissionError("la dernière revue n'est pas un ACCEPTE complet")
    if _sha(plan_text) != last["plan_sha256"] or revue.get("plan_examine_sha256") != last["plan_sha256"]:
        raise MissionError("le plan présenté n'est pas celui qui a été examiné et accepté")
    ap = trace["apercu"]
    if expected_delivery_sha256 != ap["delivery_sha256"]:
        raise MissionError("l'empreinte de livraison confirmée n'est pas celle de l'aperçu présenté")
    info = deliver.preview(ap["chemin"], plan_text, mission_id)
    if info["delivery_sha256"] != ap["delivery_sha256"]:
        raise MissionError("aperçu recalculé différent de l'aperçu tracé")
    saved = deliver.save_plan(project, ap["chemin"], plan_text, ap["delivery_sha256"], mission=mission_id)
    return {"statut": saved["status"], "chemin": ap["chemin"], "delivery_sha256": saved["delivery_sha256"],
            "content_sha256": saved["content_sha256"], "trace": saved["trace"]}
