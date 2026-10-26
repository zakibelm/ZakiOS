#!/usr/bin/env python3
"""Audit INDÉPENDANT des artefacts d'un essai réel (ne se fie pas au code de sortie ni aux verdicts du script d'essai).

Pour chaque mission (dossier `copie-*` + journaux `log-*.jsonl` d'un dossier de travail) il recalcule :
  - l'empreinte de chaque plan à partir de la sortie réelle de l'agent dans le journal ;
  - la revue : on ré-analyse le texte réel du relecteur avec le parseur et l'empreinte attendue, puis on compare verdict
    et empreinte à la trace ;
  - le lien revue -> plan, l'identité plan accepté -> aperçu -> fichier enregistré -> trace de livraison ;
  - l'absence de livraison après clarification, plafond ou erreur ;
  - l'arbre du projet avant/après (dossier `base`) ;
  - les outils effectifs lus dans les événements d'initialisation et les outils réellement appelés.
Les plans v1 injectés (essai de coordination) sont comparés au fichier de test correspondant.
Usage : python3 scripts/audit_artefacts.py DOSSIER_DE_TRAVAIL [--out audit.json]
Code de sortie : 0 aucune divergence ; 1 au moins une divergence (toutes sont listées)."""
import argparse, glob, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from essai_lot1 import diff_tree, sha_tree  # noqa: E402
from zakios import deliver, mission, outils  # noqa: E402

FIXTURES = {"A": "m1_sans_c3.md", "B": "m2_non_verifiable.md", "temoin": "temoin.md", "M4": "m4_sans_verifier.md"}
READONLY = ["Glob", "Grep", "Read"]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_log(path):
    tools, model, used, result, errs = [], None, [], "", None
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            tools, model = e.get("tools", []), e.get("model")
        if e.get("type") == "assistant":
            used += [c["name"] for c in e["message"]["content"] if c.get("type") == "tool_use"]
        if e.get("type") == "result":
            result, errs = e.get("result", ""), e.get("is_error")
    return {"tools": tools, "model": model, "used": used, "result": result, "is_error": errs}


def enumerate_missions(work):
    """[(clé, dossier de copie, journaux triés, nom de cas, injecté?)] pour les deux dispositions de dossiers."""
    out = []
    for d in sorted(glob.glob(os.path.join(work, "copie-*"))):
        tag = os.path.basename(d)[len("copie-"):]
        m = re.match(r"^(\d+)-(.+)$", tag)            # essai_coordination : copie-<passage>-<cas>
        if m:
            passage, name = m.group(1), m.group(2)
            logs = sorted(glob.glob(os.path.join(work, "log-%s-%s-*.jsonl" % (passage, name))), key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
            out.append(("%s/p%s" % (name, passage), d, logs, name, name in FIXTURES))
            continue
        m = re.match(r"^(.+)-p(\d+)$", tag)            # essai_garanties_reelles : copie-<cas>-p<N>
        if m:
            name, passage = m.group(1), m.group(2)
            logs = sorted(glob.glob(os.path.join(work, "log-%s-p%s-*.jsonl" % (name, passage))), key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
            out.append(("%s/p%s" % (name, passage), d, logs, name, False))
        else:                                          # ancienne disposition : copie-<cas> (un seul passage)
            logs = sorted(glob.glob(os.path.join(work, "log-%s-*.jsonl" % tag)), key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
            out.append((tag + "/p1", d, logs, tag, False))
    return out


def audit_one(key, d, logs, name, injected, base_tree, div, stats, parse_reviews=True, ecarts=None):
    ecarts = ecarts if ecarts is not None else []
    def bad(msg):
        div.append("%s : %s" % (key, msg))

    traces = glob.glob(os.path.join(d, ".zakios/missions/*.json"))
    if len(traces) != 1:
        return bad("%d traces de mission" % len(traces))
    tr = json.load(open(traces[0]))
    tours, criteria = tr["tours"], tr["criteres"]
    entries = [read_log(p) for p in logs]
    # outils effectifs et utilisés
    recomputed = []
    for p, e in zip(logs, entries):
        if sorted(e["tools"]) != READONLY:
            bad("outils effectifs %s dans %s" % (e["tools"], os.path.basename(p)))
        # outils demandés hors liste : recalcul indépendant depuis le journal brut (demande refusée / exécution / indéterminé)
        a = outils.analyse_log(open(p, encoding="utf-8").read(), e["tools"])
        for ev in a["interdits"]:
            recomputed.append((os.path.basename(p), ev["outil"], ev["statut"]))
            if ev["statut"] in outils.BLOCKING:
                stats["executions_interdites"] = stats.get("executions_interdites", 0) + 1
                bad("EXÉCUTION INTERDITE ou indéterminée : %s (%s) dans %s" % (ev["outil"], ev["statut"], os.path.basename(p)))
            else:
                stats["tentatives_interdites"] = stats.get("tentatives_interdites", 0) + 1
                ecarts.append("%s : %s demandé, refusé par la plateforme (%s)" % (key, ev["outil"], os.path.basename(p)))
    if "ecarts_comportementaux" in tr:
        traced = sorted((os.path.basename(x["journal"] or ""), x["outil"], x["statut"]) for x in tr["ecarts_comportementaux"])
        if traced != sorted(recomputed):
            bad("écarts comportementaux tracés %s != recalculés depuis les journaux %s" % (traced, sorted(recomputed)))
    stats["appels_reels"] += len(entries)
    # plans recalculés depuis les sorties réelles des rédacteurs (+ plan injecté)
    plans, reviews = [], []
    ledger = tr.get("appels_detail")
    if injected:
        text = open(os.path.join(ROOT, "tests/fixtures/plans", FIXTURES[name]), encoding="utf-8").read()
        plans.append(deliver.extract_plan(text))
    if ledger is not None:                              # trace v2 avec registre ordonné des appels (C3)
        for dv in mission.check_trace(tr):
            bad("trace incohérente : " + dv)
        real = ledger[1:] if injected else ledger       # le plan v1 injecté n'a pas de journal
        if len(real) != len(entries):
            bad("%d appels au registre (hors injecté), %d journaux : appel sans journal ou journal en trop" % (len(real), len(entries)))
        errs = list(tr["erreurs_techniques"])
        refused = [x for x in ledger if x["resultat"].startswith("refuse_")]
        if len(refused) != len(errs):
            bad("%d refus au registre, %d erreurs tracées" % (len(refused), len(errs)))
        plan_sha_by_tour = {t["tour"]: t["plan_sha256"] for t in tours}
        cur_plan_sha = plan_sha_by_tour.get(1) if injected else None
        k = 0
        for x, e, lp in zip(real, entries, logs):
            out_text = e["result"]
            if x["role"] == "plan-writer":
                if x["resultat"] == "valide":
                    plans.append(deliver.extract_plan(out_text))
                else:
                    try:
                        deliver.extract_plan(out_text)
                        bad("sortie refusée du rédacteur (tour %s) pourtant valide" % x["tour"])
                    except deliver.DeliveryError:
                        pass
            else:
                tour_sha = plan_sha_by_tour.get(x["tour"])
                if x["resultat"] == "valide":
                    reviews.append(out_text)
                elif tour_sha and parse_reviews:
                    try:
                        mission.parse_review_full(out_text, criteria, tour_sha)
                        bad("sortie refusée du relecteur (tour %s) pourtant valide" % x["tour"])
                    except mission.TechnicalError:
                        pass
            if x["resultat"].startswith("refuse_"):
                er = errs[k] if k < len(errs) else None
                k += 1
                if er is None:
                    continue
                if (er["role"], er["tour"], er["tentative"]) != (x["role"], x["tour"], x["tentative"]):
                    bad("erreur tracée %s != appel refusé %s" % ((er["role"], er["tour"], er["tentative"]), (x["role"], x["tour"], x["tentative"])))
                if er["sortie_sha256"] is not None and er["sortie_sha256"] != sha(out_text):
                    bad("empreinte de la sortie refusée (tour %s) != journal" % x["tour"])
                if er["journal"] is None or os.path.basename(er["journal"]) != os.path.basename(lp):
                    bad("lien de journal de l'erreur (%s) != journal de l'appel (%s)" % (er["journal"], os.path.basename(lp)))
                stats["erreurs_relancees_verifiees"] = stats.get("erreurs_relancees_verifiees", 0) + 1
    else:                                               # ancien format de trace (C1/C2) : lecture historique
        for e in entries:
            text = e["result"]
            if mission.REVIEW_BEGIN in text:
                reviews.append(text)
            else:
                try:
                    plans.append(deliver.extract_plan(text))
                except deliver.DeliveryError:
                    pass
    if len(plans) < len(tours):
        bad("%d plans recalculables pour %d tours" % (len(plans), len(tours)))
    for i, t in enumerate(tours):
        if i >= len(plans):
            break
        plan_text, plan_path = plans[i]
        if sha(plan_text) != t["plan_sha256"]:
            bad("tour %d : empreinte recalculée %s… != trace %s…" % (t["tour"], sha(plan_text)[:12], t["plan_sha256"][:12]))
        revue = t.get("revue")
        if not revue:
            bad("tour %d sans revue" % t["tour"])
            continue
        if revue["plan_examine_sha256"] != t["plan_sha256"]:
            bad("tour %d : revue non liée au plan du tour" % t["tour"])
        if parse_reviews and i < len(reviews):         # ré-analyse du texte réel du relecteur
            try:
                verdict, _, coverage = mission.parse_review_full(reviews[i], criteria, t["plan_sha256"])
                if verdict != revue["verdict"] or coverage != revue["couverture"]:
                    bad("tour %d : verdict/couverture recalculés (%s) != trace (%s)" % (t["tour"], verdict, revue["verdict"]))
            except mission.TechnicalError as exc:
                if not tr["erreurs_techniques"]:
                    bad("tour %d : revue réelle invalide sans erreur technique tracée (%s)" % (t["tour"], exc))
        stats["liens_revue_plan"] += 1
    # arbre du projet
    now = sha_tree(d)
    delta = diff_tree(base_tree, now)
    issue = tr["issue"]
    if issue == "accepte":
        lv = tr.get("livraison")
        if not lv:
            return bad("accepté sans livraison tracée")
        last = tours[-1]
        if last["revue"]["verdict"] != "ACCEPTE" or set(last["revue"].get("couverture", {}).values()) != {"couvert"}:
            bad("dernier tour non ACCEPTE ou couverture incomplète")
        f = os.path.join(d, lv["chemin"])
        data = open(f, "rb").read() if os.path.exists(f) else b""
        if hashlib.sha256(data).hexdigest() != lv["content_sha256"]:
            bad("fichier enregistré != content_sha256")
        if sha(data.decode("utf-8")) != last["plan_sha256"]:
            bad("fichier enregistré != dernier plan accepté")
        if i_plan := (plans[len(tours) - 1] if len(plans) >= len(tours) else None):
            info = deliver.preview(i_plan[1], i_plan[0], tr["mission_id"])
            if info["delivery_sha256"] != lv["delivery_sha256"]:
                bad("aperçu recalculé (delivery_sha256) != livraison tracée")
            if i_plan[1] != lv["chemin"]:
                bad("chemin proposé != chemin enregistré")
        dt = os.path.join(d, lv["trace"])
        if not os.path.exists(dt) or tr["mission_id"] not in open(dt, encoding="utf-8").read():
            bad("trace de livraison absente ou sans identifiant de mission")
        if delta["crees"] != [lv["chemin"]] or delta["modifies"] or delta["supprimes"]:
            bad("arbre du projet : %s" % delta)
        stats["livraisons_verifiees"] += 1
    else:
        if "livraison" in tr or "arret" not in tr:
            bad("trace d'arrêt incohérente après %s" % issue)
        if os.path.exists(os.path.join(d, "docs")) or os.path.exists(os.path.join(d, ".zakios/deliverables")):
            bad("livraison présente après %s" % issue)
        if delta["crees"] or delta["modifies"] or delta["supprimes"]:
            bad("arbre du projet modifié après %s : %s" % (issue, delta))
        if issue == "clarification_requise":
            cl = tr["clarification"]
            if cl["plan_sha256"] != tours[-1]["plan_sha256"] or not cl["questions"] or not cl["criteres"]:
                bad("clarification incomplète ou non liée au dernier plan")
            if tr["arret"]["appels"]["plan-writer"] != len(tours) + len([e for e in tr["erreurs_techniques"] if e["role"] == "plan-writer"]):
                bad("appel de rédacteur après la clarification")
            if ledger is not None and (ledger[-1]["role"] != "plan-reviewer" or ledger[-1]["resultat"] != "valide" or len(entries) != len(real)):
                bad("appel après la clarification (dernier appel du registre : %s)" % ledger[-1])
        if issue == "plafond_atteint" and len(tours) != tr["max_corrections"] + 1:
            bad("plafond : %d tours" % len(tours))
        stats["arrets_verifies"] += 1
    if len(tours) > tr["max_corrections"] + 1:
        bad("plafond dépassé")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--out")
    ap.add_argument("--sans-reanalyse-des-revues", action="store_true",
                    help="campagnes dont le format de revue est antérieur (ex. C1) : ne pas ré-analyser le texte des revues")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    base_tree = sha_tree(os.path.join(work, "base"))
    ecarts = []
    div, stats = [], {"missions": 0, "appels_reels": 0, "liens_revue_plan": 0, "livraisons_verifiees": 0, "arrets_verifies": 0}
    for key, d, logs, name, injected in enumerate_missions(work):
        stats["missions"] += 1
        audit_one(key, d, logs, name, injected, base_tree, div, stats, not a.sans_reanalyse_des_revues, ecarts)
    if stats["missions"] == 0:
        div.append("aucune mission trouvée dans %s (disposition de dossiers inconnue)" % work)
    report = {"dossier": work, "statistiques": stats, "divergences": div, "ecarts_comportementaux": ecarts}
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(stats, ensure_ascii=False))
    for x in div:
        print("DIVERGENCE :", x)
    for x in ecarts:
        print("ÉCART COMPORTEMENTAL (tentative interdite refusée par la plateforme) :", x)
    print("AUCUNE DIVERGENCE" if not div else "%d DIVERGENCE(S)" % len(div))
    sys.exit(1 if div else 0)


if __name__ == "__main__":
    main()
