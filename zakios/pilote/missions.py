"""Gestion des missions du pilote : espaces jetables, limites, exécution du coordinateur, état public, confirmation.

Aucune règle de coordination ici : `mission.run_mission` décide (verdicts, plafond, relances, confinement, livraison
différée) ; ce module prépare l'espace, borne la durée et les appels, enregistre les sorties et expose l'état."""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
import time

from .. import deliver, mission, outils
from ..activate import apply
from ..build import build
from .roles import ClaudeRoles, SimulatedRoles

OWN = "zakibelm/ZakiOS"
SOCLE = OWN + ":socle/REGLES.md"
PLANNER = OWN + ":variantes/skills/writing-plans/SKILL.md"
PLANWRITER = OWN + ":variantes/agents/plan-writer.md"
PLANREVIEWER = OWN + ":variantes/agents/plan-reviewer.md"
SAMPLE_PAY = ("def total(prices, discount):\n    # discount est un pourcentage 0-100\n    return sum(prices) * (1 - discount)\n\n"
              "def read_user(db, name):\n    return db.execute(\"SELECT * FROM users WHERE name = '\" + name + \"'\")\n")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Invalid(Exception):
    pass


class Busy(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def prepare_base(cfg):
    """Projet d'exemple jetable + installation des rôles par le moteur (décisions/licences d'essai LOCALES au pilote :
    decisions/*.json et licences réelles ne sont jamais lus ni modifiés). Renvoie (dossier du projet de base, empreintes)."""
    data = os.path.abspath(cfg.data_dir)
    base = os.path.join(data, "base")
    meta = os.path.join(data, "base.json")
    if os.path.exists(meta) and os.path.isdir(base):
        return base, _load(meta)["composants"]
    work = os.path.join(data, "_prep")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    with open(os.path.join(REPO_ROOT, "sources.json"), encoding="utf-8") as fh:
        commit = next(s["commit"] for s in json.load(fh)["sources"] if s["repo"] == OWN)
    manifest = os.path.join(work, "sources.json")
    json.dump({"sources": [{"repo": OWN, "role": "propre", "commit": commit}]}, open(manifest, "w"))
    cat = os.path.join(work, "catalog")
    build(manifest, cfg.sources_root, cat)
    reg = _load(os.path.join(cat, "registry.json"))
    fp = {c["component_id"]: c["provenance"]["fingerprint_sha256"] for c in reg["components"]}
    sel = [SOCLE, PLANNER, PLANWRITER, PLANREVIEWER]
    dec, lic, ann = (os.path.join(work, n) for n in ("validated.json", "licenses.json", "annotations.json"))
    json.dump({c: {"validated": "conserver", "validated_by": "PILOTE (non réel)", "validated_on": "pilote",
                   "justification": "pilote jetable", "fingerprint_sha256": fp[c]} for c in sel}, open(dec, "w"))
    json.dump({OWN: {"spdx": "NOASSERTION", "verified_by": "PILOTE (non réel)", "verified_on": "pilote",
                     "commit": commit, "attribution": "pilote"}}, open(lic, "w"))
    json.dump({PLANWRITER: {"depends_on": [PLANNER]}}, open(ann, "w"))
    build(manifest, cfg.sources_root, cat, decisions_path=dec, licenses_path=lic, annotations_path=ann)
    proj = os.path.join(work, "base")
    os.makedirs(os.path.join(proj, "src"))
    open(os.path.join(proj, "src/pay.py"), "w").write(SAMPLE_PAY)
    open(os.path.join(proj, "CLAUDE.md"), "w").write("Projet d'exemple jetable du pilote ZakiOS.\n")
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "-c", "user.name=pilote", "-c", "user.email=p@p", "commit", "-qm", "base"], cwd=proj, check=True)
    apply(proj, cat, cfg.sources_root, sel)
    comps = {c: fp[c][:16] for c in sel}
    shutil.rmtree(base, ignore_errors=True)
    shutil.move(proj, base)
    _write_json(meta, {"composants": comps, "commit": commit})
    shutil.rmtree(work, ignore_errors=True)
    return base, comps


class Manager:
    def __init__(self, cfg, base=None, components=None, roles_factory=None):
        self.cfg = cfg
        self.data = os.path.abspath(cfg.data_dir)
        os.makedirs(os.path.join(self.data, "missions"), exist_ok=True)
        if base is None:
            base, components = prepare_base(cfg)
        self.base, self.components = base, components or {}
        self.roles_factory = roles_factory or self._default_roles
        self.lock = threading.Lock()
        self.running = 0
        self.starts = []          # horodatages des créations (limite horaire)
        self.confirm_locks = {}
        self._mark_interrupted()

    # --- fabrique de rôles -------------------------------------------------------------------------------
    def _default_roles(self, project, request, criteria):
        if self.cfg.simulation:
            return SimulatedRoles(request, criteria)
        return ClaudeRoles(project, self.cfg.model, self.cfg.claude_bin, self.cfg.call_timeout)

    @property
    def mode(self):
        return "simulation" if self.cfg.simulation else "reel"

    def _dir(self, mid):
        if not (isinstance(mid, str) and mid.startswith("p-") and mid[2:].isalnum() and len(mid) <= 20):
            raise NotFound(mid)
        d = os.path.join(self.data, "missions", mid)
        if not os.path.isdir(d):
            raise NotFound(mid)
        return d

    def _mark_interrupted(self):
        root = os.path.join(self.data, "missions")
        for mid in os.listdir(root):
            p = os.path.join(root, mid, "etat.json")
            if os.path.exists(p):
                st = _load(p)
                if st.get("statut") in ("en_cours",):
                    st["statut"] = "interrompue"
                    st["evenements"].append({"t": _now(), "texte": "mission interrompue par un redémarrage du serveur"})
                    _write_json(p, st)

    # --- création ----------------------------------------------------------------------------------------
    def validate(self, request, criteria):
        c = self.cfg
        if not isinstance(request, str) or not request.strip():
            raise Invalid("la demande est vide")
        if len(request) > c.max_request_chars:
            raise Invalid("demande trop longue (max %d caractères)" % c.max_request_chars)
        if not isinstance(criteria, list) or not criteria:
            raise Invalid("au moins un critère obligatoire est requis")
        if len(criteria) > c.max_criteria:
            raise Invalid("trop de critères (max %d)" % c.max_criteria)
        for x in criteria:
            if not isinstance(x, str) or not x.strip() or len(x) > c.max_criterion_chars:
                raise Invalid("critère vide ou trop long (max %d caractères)" % c.max_criterion_chars)
        criteria = [x.strip() for x in criteria]
        try:
            mission.validate_criteria(criteria)  # règles d'identifiants : celles du coordinateur
        except mission.MissionError as exc:
            raise Invalid(str(exc))
        return request.strip(), criteria

    def create(self, request, criteria):
        request, criteria = self.validate(request, criteria)
        now = time.time()
        with self.lock:
            self.starts = [t for t in self.starts if now - t < 3600]
            if self.running >= self.cfg.max_concurrent:
                raise Busy("pilote occupé : %d mission(s) en cours (limite %d)" % (self.running, self.cfg.max_concurrent))
            if len(self.starts) >= self.cfg.max_missions_per_hour:
                raise Busy("limite horaire atteinte (%d missions par heure)" % self.cfg.max_missions_per_hour)
            self.running += 1
            self.starts.append(now)
        mid = "p-" + secrets.token_hex(5)
        d = os.path.join(self.data, "missions", mid)
        os.makedirs(os.path.join(d, "journaux"))
        os.makedirs(os.path.join(d, "sorties"))
        shutil.copytree(self.base, os.path.join(d, "projet"))
        st = {"id": mid, "statut": "en_cours", "mode": self.mode, "cree_le": _now(), "demande": request, "criteres": criteria,
              "evenements": [{"t": _now(), "texte": "mission créée dans un espace jetable"}]}
        _write_json(os.path.join(d, "etat.json"), st)
        threading.Thread(target=self._run, args=(mid,), daemon=True, name="mission-" + mid).start()
        return mid

    # --- exécution ---------------------------------------------------------------------------------------
    def _event(self, mid, text, **extra):
        d = os.path.join(self.data, "missions", mid)
        with self.lock:
            p = os.path.join(d, "etat.json")
            st = _load(p)
            st["evenements"].append(dict({"t": _now(), "texte": text}, **extra))
            _write_json(p, st)

    def _run(self, mid):
        d = os.path.join(self.data, "missions", mid)
        project = os.path.join(d, "projet")
        st = _load(os.path.join(d, "etat.json"))
        request, criteria = st["demande"], st["criteres"]
        deadline = time.time() + self.cfg.mission_timeout
        count = {"n": 0}
        try:
            roles = self.roles_factory(project, request, criteria)

            def wrap(role, fn):
                def call(*args):
                    if time.time() > deadline:
                        raise RuntimeError("durée maximale de mission dépassée (%d s)" % self.cfg.mission_timeout)
                    if count["n"] >= self.cfg.max_calls:
                        raise RuntimeError("plafond d'appels de rôles atteint (%d)" % self.cfg.max_calls)
                    count["n"] += 1
                    n = count["n"]
                    self._event(mid, "appel %d : %s démarré" % (n, role))
                    try:
                        out = fn(*args)
                    except Exception as exc:
                        self._save_call(d, roles, n, None)
                        self._event(mid, "appel %d : %s en erreur (%s)" % (n, role, str(exc)[:160]))
                        raise
                    self._save_call(d, roles, n, out)
                    self._event(mid, "appel %d : %s terminé" % (n, role))
                    return out
                return call
            result = mission.run_mission(project, request, criteria, wrap("plan-writer", roles.writer),
                                         wrap("plan-reviewer", roles.reviewer), components=self.components, mission_id=mid,
                                         journal=roles.last_journal, tool_audit=roles.tool_audit, livraison="differee")
            self._event(mid, "mission terminée : %s" % result["issue"])
            self._finish(mid, "termine")
        except Exception as exc:  # défaut du pilote lui-même (pas une issue de mission)
            self._event(mid, "défaut du pilote : %s" % str(exc)[:300])
            self._finish(mid, "defaut_pilote", erreur=str(exc)[:300])
        finally:
            with self.lock:
                self.running -= 1

    def _save_call(self, d, roles, n, out):
        """Journal brut de l'appel n (si le rôle en a produit un) et sortie brute (si l'appel a abouti)."""
        if len(roles.log) >= n:
            with open(os.path.join(d, "journaux", "%s%d.jsonl" % (roles.prefix, n - 1)), "w", encoding="utf-8") as fh:
                fh.write(roles.log[n - 1])
        if out is not None:
            with open(os.path.join(d, "sorties", "%d.txt" % n), "w", encoding="utf-8") as fh:
                fh.write(out)

    def _finish(self, mid, statut, **extra):
        with self.lock:
            p = os.path.join(self.data, "missions", mid, "etat.json")
            st = _load(p)
            st["statut"] = statut
            st.update(extra)
            _write_json(p, st)

    # --- lecture -----------------------------------------------------------------------------------------
    def _trace(self, d, mid):
        p = os.path.join(d, "projet", ".zakios", "missions", mid + ".json")
        return _load(p) if os.path.exists(p) else None

    def _output(self, d, n):
        p = os.path.join(d, "sorties", "%d.txt" % n)
        return _read(p) if os.path.exists(p) else None

    def _valid_call(self, tr, role, tour):
        for x in tr["appels_detail"]:
            if x["role"] == role and x["tour"] == tour and x["resultat"] == "valide":
                return x["n"]
        return None

    def get(self, mid):
        d = self._dir(mid)
        st = _load(os.path.join(d, "etat.json"))
        tr = self._trace(d, mid)
        pub = {"id": mid, "statut": st["statut"], "mode": st["mode"], "cree_le": st["cree_le"], "demande": st["demande"],
               "criteres": st["criteres"], "evenements": st["evenements"], "limites": self.limites()}
        if "erreur" in st:
            pub["defaut_pilote"] = st["erreur"]
        if tr is None:
            pub.update(etat_final=None, livraison_possible=False)
            return pub
        issue = tr["issue"]
        pub["issue"], pub["categorie"] = issue, tr["categorie"]
        pub["tours"] = []
        for t in tr["tours"]:
            rv = t.get("revue") or {}
            pub["tours"].append({"tour": t["tour"], "plan_sha256": t["plan_sha256"], "verdict": rv.get("verdict"),
                                 "gravites": rv.get("gravites", []), "couverture": rv.get("couverture", {}),
                                 "constats": [{"gravite": f["gravite"], "texte": f["texte"]} for f in t.get("constats", [])],
                                 "relances": {"plan-writer": t.get("relances_planificateur", 0), "plan-reviewer": rv.get("relances_relecteur", 0)}})
        pub["erreurs_techniques"] = tr["erreurs_techniques"]
        pub["ecarts_comportementaux"] = tr["ecarts_comportementaux"]
        pub["appels"] = tr["appels"]
        pub["incoherences_de_trace"] = mission.check_trace(tr)
        arret = tr.get("arret")
        if issue == "accepte":
            pub["etat_final"] = "accepte"
            ap = tr["apercu"]
            pub["apercu"] = {"chemin": ap["chemin"], "delivery_sha256": ap["delivery_sha256"], "content_sha256": ap["content_sha256"],
                             "plan": self._plan_text(d, tr, tr["tours"][-1]["tour"])}
            pub["livraison"] = st.get("livraison")
            pub["livraison_possible"] = st.get("livraison") is None
        else:
            pub["livraison_possible"] = False
            pub["arret"] = arret
            if issue == "clarification_requise":
                pub["etat_final"] = "clarification_requise"
                pub["clarification"] = tr["clarification"]
            elif issue == "plafond_atteint":
                pub["etat_final"] = "plafond_atteint"
            else:
                pub["etat_final"] = "erreur_technique"
        return pub

    def lister(self, limit=30):
        """Résumés des missions (les plus récentes d'abord) : uniquement des informations déjà publiques par mission."""
        root = os.path.join(self.data, "missions")
        rows = []
        for mid in os.listdir(root):
            p = os.path.join(root, mid, "etat.json")
            if not os.path.exists(p):
                continue
            st = _load(p)
            tr = self._trace(os.path.join(root, mid), mid)
            rows.append({"id": mid, "statut": st["statut"], "mode": st["mode"], "cree_le": st["cree_le"],
                         "demande": st["demande"][:140], "etat_final": (tr or {}).get("issue"),
                         "livre": bool(st.get("livraison"))})
        rows.sort(key=lambda r: r["cree_le"], reverse=True)
        return rows[:limit]

    def limites(self):
        c = self.cfg
        return {"missions_simultanees": c.max_concurrent, "duree_max_mission_s": c.mission_timeout, "appels_max": c.max_calls,
                "missions_par_heure": c.max_missions_per_hour}

    def _plan_text(self, d, tr, tour):
        n = self._valid_call(tr, "plan-writer", tour)
        raw = self._output(d, n) if n else None
        if raw is None:
            return None
        text, _ = deliver.extract_plan(raw)
        return text

    def plan(self, mid, tour):
        d = self._dir(mid)
        tr = self._trace(d, mid)
        if tr is None or not any(t["tour"] == tour for t in tr["tours"]):
            raise NotFound("plan")
        return self._plan_text(d, tr, tour)

    def review(self, mid, tour):
        d = self._dir(mid)
        tr = self._trace(d, mid)
        n = self._valid_call(tr, "plan-reviewer", tour) if tr else None
        raw = self._output(d, n) if n else None
        if raw is None:
            raise NotFound("revue")
        return raw

    def trace(self, mid):
        d = self._dir(mid)
        tr = self._trace(d, mid)
        if tr is None:
            raise NotFound("trace")
        return tr

    def audit(self, mid):
        """Recoupe la trace et les journaux bruts de la mission (cohérence, outils effectifs, outils interdits)."""
        d = self._dir(mid)
        tr = self._trace(d, mid)
        if tr is None:
            raise NotFound("trace")
        jd = os.path.join(d, "journaux")
        files = sorted(os.listdir(jd), key=lambda x: int(x.split("-")[-1].split(".")[0]))
        recomputed, eff = [], []
        for f in files:
            a = outils.analyse_log(_read(os.path.join(jd, f)))
            eff.append(f)
            recomputed += [(f, e["outil"], e["statut"]) for e in a["interdits"]]
        traced = sorted((os.path.basename(x["journal"] or ""), x["outil"], x["statut"]) for x in tr["ecarts_comportementaux"])
        out = {"incoherences_de_trace": mission.check_trace(tr), "journaux": len(files), "appels_au_registre": len(tr["appels_detail"]),
               "ecarts_recalcules_depuis_les_journaux": sorted(recomputed), "ecarts_traces": traced}
        out["concordance"] = (not out["incoherences_de_trace"] and sorted(recomputed) == traced
                              and len(files) == len(tr["appels_detail"]))
        return out

    # --- confirmation -------------------------------------------------------------------------------------
    def confirm(self, mid, delivery_sha256):
        d = self._dir(mid)
        with self.lock:
            lk = self.confirm_locks.setdefault(mid, threading.Lock())
        with lk:  # double clic : sérialisé ; le coordinateur garantit l'idempotence et l'absence d'écrasement
            st = _load(os.path.join(d, "etat.json"))
            tr = self._trace(d, mid)
            if st["statut"] != "termine" or tr is None or tr["issue"] != "accepte":
                raise Conflict("aucune livraison n'est possible pour cette mission")
            plan = self._plan_text(d, tr, tr["tours"][-1]["tour"])
            try:
                res = mission.confirmer_livraison(os.path.join(d, "projet"), mid, plan, delivery_sha256)
            except (mission.MissionError, deliver.DeliveryError) as exc:
                raise Conflict(str(exc))
            with self.lock:
                st = _load(os.path.join(d, "etat.json"))
                first = st.get("livraison") is None
                if first:
                    st["livraison"] = {k: res[k] for k in ("statut", "chemin", "delivery_sha256", "content_sha256")}
                    st["evenements"].append({"t": _now(), "texte": "livraison confirmée et enregistrée : %s (%s)" % (res["chemin"], res["statut"])})
                _write_json(os.path.join(d, "etat.json"), st)
            return dict(st["livraison"], derniere_confirmation=res["statut"])

    def delivered_file(self, mid):
        d = self._dir(mid)
        st = _load(os.path.join(d, "etat.json"))
        lv = st.get("livraison")
        if not lv:
            raise NotFound("livrable")
        return os.path.basename(lv["chemin"]), _read(os.path.join(d, "projet", lv["chemin"]), "rb")
