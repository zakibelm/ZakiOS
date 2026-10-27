"""Pilote supervisé — parcours HTTP complet (API → coordinateur → rôles → trace → aperçu → enregistrement).

TOUT CE FICHIER EST SIMULÉ : les rôles sont SimulatedRoles (aucun modèle appelé). Le vrai parcours avec de vrais agents est
exercé séparément (scripts/essai_pilote_reel.py) ; ces tests prouvent la plomberie, la sécurité et les refus."""
import glob
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

from zakios.pilote.config import Config
from zakios.pilote.missions import Manager
from zakios.pilote.server import serve

TOKEN = "jeton-de-test-0123456789"
CRIT = ["C1 remise correcte", "C2 requête paramétrée"]
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Pilote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        base = os.path.join(cls.tmp, "base")
        os.makedirs(os.path.join(base, "src"))
        with open(os.path.join(base, "src/pay.py"), "w") as fh:
            fh.write("def total(p, d):\n    return sum(p)\n")
        with open(os.path.join(base, "CLAUDE.md"), "w") as fh:
            fh.write("Instructions de la personne\n")
        cls.decisions_avant = cls._hash_decisions()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def _hash_decisions():
        out = {}
        for p in sorted(glob.glob(os.path.join(REPO, "decisions", "*.json"))):
            with open(p, "rb") as fh:
                out[p] = sha(fh.read())
        return out

    def setUp(self):
        self.data = tempfile.mkdtemp(dir=self.tmp)
        self.cfg = Config(data_dir=self.data, sources_root=self.tmp, token=TOKEN, simulation=True, port=0)
        self.mgr = Manager(self.cfg, base=os.path.join(self.tmp, "base"), components={"x": "0" * 16})
        self.httpd, self.pilot = serve(self.cfg, self.mgr)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.cookie = None

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # --- aides HTTP ---------------------------------------------------------------------------------------
    def req(self, method, path, body=None, auth=True, headers=None, raw=False):
        h = {"X-Zakios-Pilote": "1"} if method == "POST" else {}
        if auth and self.cookie:
            h["Cookie"] = self.cookie
        h.update(headers or {})
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.request(method, path, data, h)
        r = c.getresponse()
        payload = r.read()
        hdrs = dict(r.getheaders())
        c.close()
        if raw:
            return r.status, payload, hdrs
        try:
            return r.status, json.loads(payload or b"null"), hdrs
        except ValueError:
            return r.status, payload, hdrs

    def login(self):
        st, _, h = self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False)
        self.assertEqual(st, 200)
        self.cookie = h["Set-Cookie"].split(";")[0]

    def start(self, demande="Planifie la correction", criteres=None):
        self.login() if not self.cookie else None
        st, d, _ = self.req("POST", "/api/missions", {"demande": demande, "criteres": criteres or CRIT})
        self.assertEqual(st, 202, d)
        return d["id"]

    def wait(self, mid, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            st, d, _ = self.req("GET", "/api/missions/" + mid)
            if d["statut"] != "en_cours":
                return d
            time.sleep(0.1)
        self.fail("mission non terminée")

    def project_files(self, mid):
        root = os.path.join(self.data, "missions", mid, "projet")
        out = {}
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if x != ".git"]
            for f in fn:
                p = os.path.join(dp, f)
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, root)] = sha(fh.read())
        return out

    # --- accès --------------------------------------------------------------------------------------------
    def test_acces_protege_et_csrf(self):
        self.assertEqual(self.req("GET", "/api/etat", auth=False)[0], 401)
        self.assertEqual(self.req("GET", "/api/missions/p-0123456789", auth=False)[0], 401)
        self.assertEqual(self.req("POST", "/api/missions", {"demande": "x", "criteres": CRIT}, auth=False)[0], 401)
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": "mauvais"}, auth=False)[0], 401)
        st, _, _ = self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False, headers={"X-Zakios-Pilote": "0"})
        self.assertEqual(st, 403)
        st, _, _ = self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False, headers={"Origin": "http://autre.example"})
        self.assertEqual(st, 403)
        st, _, h = self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False)
        self.assertEqual(st, 200)
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Strict", h["Set-Cookie"])
        self.cookie = h["Set-Cookie"].split(";")[0]
        self.assertEqual(self.req("GET", "/api/etat")[0], 200)
        # Bearer accepté, mauvais Bearer refusé
        self.cookie = None
        self.assertEqual(self.req("GET", "/api/etat", headers={"Authorization": "Bearer " + TOKEN})[0], 200)
        self.assertEqual(self.req("GET", "/api/etat", headers={"Authorization": "Bearer faux"})[0], 401)

    def test_limitation_des_essais_de_connexion(self):
        codes = [self.req("POST", "/api/connexion", {"jeton": "x%d" % i}, auth=False)[0] for i in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5:], [429, 429])
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False)[0], 429)  # même le bon jeton, le temps du blocage

    def test_en_tetes_de_securite_et_pages_statiques(self):
        st, body, h = self.req("GET", "/", auth=False, raw=True)
        self.assertEqual(st, 200)
        self.assertIn("script-src 'self'", h["Content-Security-Policy"])
        html = body.decode()
        self.assertNotRegex(html, r"<script(?![^>]*\ssrc=)")      # aucun script en ligne
        self.assertNotRegex(html, r"\son[a-z]+=")                  # aucun gestionnaire d'événement en ligne
        self.assertNotIn("style=", html)
        self.assertEqual(h["Cache-Control"], "no-store")
        for f in ("/app.js", "/style.css", "/gsap.min.js"):
            self.assertEqual(self.req("GET", f, auth=False, raw=True)[0], 200, f)
        js = self.req("GET", "/app.js", auth=False, raw=True)[1].decode()
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("localStorage", js)       # aucune livraison ni donnée stockée dans le navigateur

    def test_aucune_dependance_externe_dans_l_interface(self):
        import re
        for f in ("index.html", "app.js", "style.css"):
            with open(os.path.join(REPO, "zakios", "pilote", "static", f), encoding="utf-8") as fh:
                txt = fh.read()
            urls = set(re.findall(r"https?://[^\s\"')<>]+", txt))
            self.assertEqual(urls - {"https://github.com/zakibelm/ZakiOS"}, set(), f)
            self.assertNotIn("@import", txt)
            self.assertNotIn("googleapis", txt)

    def test_campagnes_separees_avec_echec_c3_et_sans_taux_agrege(self):
        self.assertEqual(self.req("GET", "/api/campagnes", auth=False)[0], 401)
        self.login()
        st, d, _ = self.req("GET", "/api/campagnes")
        self.assertEqual(st, 200)
        ids = [c["id"] for c in d["campagnes"]]
        self.assertEqual(ids, ["avant", "C1", "C2", "C3", "C4"])
        c3 = next(c for c in d["campagnes"] if c["id"] == "C3")
        self.assertFalse(c3["criteres_satisfaits"])
        self.assertTrue(any("outil modifiant" in e for s in c3["scripts"] for e in s["echecs"]))
        self.assertTrue(next(c for c in d["campagnes"] if c["id"] == "C4")["criteres_satisfaits"])
        cles = set()

        def collecter(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    cles.add(k.lower())
                    collecter(v)
            elif isinstance(x, list):
                for v in x:
                    collecter(v)
        collecter(d)
        for k in cles:                      # aucune clé d'agrégat entre campagnes (mots entiers)
            self.assertFalse(set(k.split("_")) & {"taux", "rate", "total", "global", "score", "moyenne"}, k)
        self.assertIn("Aucun taux agrégé", d["avertissement"])

    def test_campagnes_json_a_jour_avec_les_preuves(self):
        r = subprocess.run(["python3", "-B", os.path.join(REPO, "scripts", "generer_campagnes.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # --- correctifs issus de l'audit (red team du 2026-10-27) ---------------------------------------------------------
    def test_limite_d_essais_par_visiteur_derriere_un_proxy_de_confiance(self):
        for _ in range(5):
            self.assertEqual(self.req("POST", "/api/connexion", {"jeton": "x" * 20}, auth=False, headers={"X-Real-IP": "203.0.113.9"})[0], 401)
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": "x" * 20}, auth=False, headers={"X-Real-IP": "203.0.113.9"})[0], 429)
        # l'attaquant est bloqué, pas les autres visiteurs
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False, headers={"X-Real-IP": "198.51.100.7"})[0], 200)

    def test_x_real_ip_ignoree_si_le_pair_n_est_pas_un_proxy_de_confiance(self):
        self.cfg.trusted_proxies = ()          # le pair (127.0.0.1) n'est plus de confiance
        for i in range(5):                      # l'attaquant change d'adresse déclarée à chaque essai : sans effet
            self.assertEqual(self.req("POST", "/api/connexion", {"jeton": "x" * 20}, auth=False, headers={"X-Real-IP": "203.0.113.%d" % i})[0], 401)
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False, headers={"X-Real-IP": "198.51.100.7"})[0], 429)

    def test_x_real_ip_invalide_retombe_sur_l_adresse_du_pair(self):
        for _ in range(5):
            self.req("POST", "/api/connexion", {"jeton": "x" * 20}, auth=False, headers={"X-Real-IP": "pas-une-ip"})
        self.assertEqual(self.req("POST", "/api/connexion", {"jeton": TOKEN}, auth=False, headers={"X-Real-IP": "pas-une-ip"})[0], 429)

    def test_deconnexion_invalide_la_session(self):
        self.login()
        self.assertEqual(self.req("GET", "/api/etat")[0], 200)
        st, _, h = self.req("POST", "/api/deconnexion", {})
        self.assertEqual(st, 200)
        self.assertIn("Max-Age=0", h["Set-Cookie"])
        self.assertEqual(self.req("GET", "/api/etat")[0], 401)      # l'ancien cookie ne vaut plus rien côté serveur
        self.assertEqual(self.req("POST", "/api/deconnexion", {}, auth=False, headers={"X-Zakios-Pilote": "0"})[0], 403)

    def test_head_repond_comme_get_sans_corps(self):
        st, body, h = self.req("GET", "/", raw=True)
        sth, bodyh, hh = self.req("HEAD", "/", raw=True)
        self.assertEqual((st, sth), (200, 200))
        self.assertEqual(bodyh, b"")
        self.assertEqual(hh["Content-Length"], h["Content-Length"])
        self.assertEqual(self.req("HEAD", "/api/etat", raw=True)[0], 401)
        self.assertEqual(self.req("HEAD", "/api/sante", raw=True)[0], 200)

    def test_hsts_seulement_en_mode_https(self):
        self.assertNotIn("Strict-Transport-Security", self.req("GET", "/", raw=True)[2])
        self.cfg.secure_cookie = True
        self.assertIn("max-age=", self.req("GET", "/", raw=True)[2]["Strict-Transport-Security"])

    def test_appel_reel_restreint_aux_outils_de_lecture(self):
        """Le 2e verrou est bien transmis à `claude`, en forme « = » (l'option est variadique et avalerait le prompt)."""
        from zakios.pilote.roles import ClaudeRoles
        fake = os.path.join(self.tmp, "faux-claude")
        with open(fake, "w") as fh:
            fh.write("#!/usr/bin/env python3\nimport sys,json\nopen(%r,'w').write(json.dumps(sys.argv[1:]))\n"
                     "print(json.dumps({'type':'system','subtype':'init','tools':['Read','Glob','Grep']}))\n"
                     "print(json.dumps({'type':'result','is_error':False,'result':'ok'}))\n" % os.path.join(self.tmp, "argv.json"))
        os.chmod(fake, 0o755)
        roles = ClaudeRoles(self.tmp, "sonnet", claude_bin=fake)
        self.assertEqual(roles._run("plan-writer", "LE PROMPT"), "ok")
        with open(os.path.join(self.tmp, "argv.json")) as fh:
            argv = json.load(fh)
        self.assertIn("--allowedTools=Read,Glob,Grep", argv)
        interdits = next(a for a in argv if a.startswith("--disallowedTools=")).split("=", 1)[1].split(",")
        for t in ("Bash", "Write", "Edit", "WebFetch"):
            self.assertIn(t, interdits)
        self.assertEqual(argv[-1], "LE PROMPT")
        self.assertEqual(argv[argv.index("--agent") + 1], "plan-writer")

    def test_dockerfile_fixe_la_version_et_l_image_n_embarque_pas_de_secret(self):
        with open(os.path.join(REPO, "deploy", "Dockerfile"), encoding="utf-8") as fh:
            d = fh.read()
        self.assertRegex(d, r"claude-code@\$\{CLAUDE_CODE_VERSION\}")
        self.assertRegex(d, r"ARG CLAUDE_CODE_VERSION=\d+\.\d+\.\d+")
        self.assertIn("python3-yaml", d)
        with open(os.path.join(REPO, ".dockerignore")) as fh:
            ign = fh.read().split()
        for motif in (".git", "*.env", "**/pilote.env"):
            self.assertIn(motif, ign)

    def test_veille_outils_importee_sans_rien_valider(self):
        self.assertEqual(self.req("GET", "/api/veille", auth=False)[0], 401)
        self.login()
        st, d, _ = self.req("GET", "/api/veille")
        self.assertEqual(st, 200)
        self.assertEqual(d["total"], 124)
        self.assertEqual(len(d["depots"]), 124)
        self.assertIn("NON vérifiés", d["avertissement"])
        self.assertEqual({x["statut"] for x in d["depots"]}, {"À tester", "Évalué"})   # aucun statut inventé
        self.assertEqual(sum(1 for x in d["depots"] if x["priorite"] == "Haute"), 22)
        pre = [x for x in d["depots"] if x["preselection"]]
        self.assertEqual(d["preselection"], len(pre))
        for x in pre:    # la règle est vérifiée indépendamment, sur les données brutes
            self.assertIn(x["licence"], ("MIT", "Apache 2.0", "BSD-2-Clause"), x["nom"])
            self.assertIn(x["maturite"], ("Très actif", "Stable"), x["nom"])
            self.assertIn(x["usage"], ("Brique à intégrer", "À installer et utiliser"), x["nom"])
            self.assertNotEqual(x["projets"], ["Aucun pour l'instant"], x["nom"])
        self.assertFalse([x["nom"] for x in pre if "AGPL" in (x["licence"] or "") or x["licence_a_verifier"]])
        self.assertEqual([x["nom"] for x in d["depots"] if not x["lien"]], ["OpenDataLoader PDF (Hancom)", "daVinci-MagiHuman", "PyMuPDF4LLM"])
        self.assertTrue(all(x["licence_a_verifier"] for x in d["depots"] if x["licence"] in (None, "À vérifier")))

    def test_veille_json_a_jour_avec_la_source(self):
        r = subprocess.run(["python3", "-B", os.path.join(REPO, "scripts", "importer_veille.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bibliotheque_et_liste_des_missions(self):
        self.login()
        st, d, _ = self.req("GET", "/api/bibliotheque")
        self.assertEqual(st, 200)
        self.assertEqual(sorted(c["nom"] for c in d["composants"]), ["REGLES.md", "code-reviewer", "plan-reviewer", "plan-writer"])
        with open(os.path.join(REPO, "variantes", "agents", "plan-reviewer.md"), "rb") as fh:
            attendu = sha(fh.read())
        self.assertEqual(next(c for c in d["composants"] if c["nom"] == "plan-reviewer")["sha256"], attendu)
        self.assertEqual(self.req("GET", "/api/missions")[1], {"missions": []})
        mid = self.start()
        self.wait(mid)
        lst = self.req("GET", "/api/missions")[1]["missions"]
        self.assertEqual([(m["id"], m["etat_final"], m["livre"]) for m in lst], [(mid, "accepte", False)])

    def test_validation_des_entrees(self):
        self.login()
        for body in ({"demande": "", "criteres": CRIT}, {"demande": "x", "criteres": []}, {"demande": "x", "criteres": ["sans identifiant"]},
                     {"demande": "x" * 5000, "criteres": CRIT}, {"demande": "x", "criteres": ["C1 a"] * 20}, {"demande": 3, "criteres": CRIT},
                     {"demande": "x", "criteres": ["C1 a", "C1 doublon"]}):
            st, d, _ = self.req("POST", "/api/missions", body)
            self.assertEqual(st, 400, body)
        st, _, _ = self.req("POST", "/api/missions", b"pas du json")
        self.assertEqual(st, 400)
        st, _, _ = self.req("POST", "/api/missions", b"{" + b" " * 40000 + b"}")
        self.assertEqual(st, 400)
        self.assertEqual(os.listdir(os.path.join(self.data, "missions")), [])  # rien de créé

    # --- parcours -----------------------------------------------------------------------------------------
    def test_accepte_apercu_confirmation_et_octets_exacts(self):
        mid = self.start()
        m = self.wait(mid)
        self.assertEqual((m["statut"], m["etat_final"], m["mode"]), ("termine", "accepte", "simulation"))
        self.assertTrue(m["livraison_possible"])
        self.assertEqual(m["tours"][-1]["verdict"], "ACCEPTE")
        ap = m["apercu"]
        before = self.project_files(mid)
        self.assertFalse(any(k.startswith("docs") for k in before))  # rien n'est écrit avant la confirmation
        st, _, _ = self.req("GET", "/api/missions/%s/livrable" % mid)
        self.assertEqual(st, 404)
        st, d, _ = self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": "0" * 64})
        self.assertEqual(st, 409)  # empreinte différente de l'aperçu : refusée
        self.assertEqual(self.project_files(mid), before)
        st, d, _ = self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": ap["delivery_sha256"]})
        self.assertEqual((st, d["statut"]), (200, "enregistre"))
        st, data, _ = self.req("GET", "/api/missions/%s/livrable" % mid, raw=True)
        self.assertEqual(st, 200)
        self.assertEqual(data.decode(), ap["plan"])  # le fichier enregistré est exactement l'aperçu montré
        after = self.project_files(mid)
        nouveaux = set(after) - set(before)
        self.assertIn(ap["chemin"], nouveaux)
        self.assertTrue(all(k == ap["chemin"] or k.startswith(".zakios/") for k in nouveaux), nouveaux)
        for k in before:  # fichiers préexistants inchangés
            self.assertEqual(before[k], after[k], k)
        # preuves consultables et cohérentes
        st, tr, _ = self.req("GET", "/api/missions/%s/trace" % mid)
        self.assertEqual(st, 200)
        self.assertEqual(tr["issue"], "accepte")
        st, au, _ = self.req("GET", "/api/missions/%s/audit" % mid)
        self.assertEqual(st, 200)
        self.assertTrue(au["concordance"], au)
        self.assertEqual(au["incoherences_de_trace"], [])
        st, pl, _ = self.req("GET", "/api/missions/%s/plan/1" % mid)
        st2, rv, _ = self.req("GET", "/api/missions/%s/revue/1" % mid)
        self.assertEqual((st, st2), (200, 200))
        self.assertIn("Verdict : ACCEPTE", rv["texte"])

    def test_double_clic_confirmation_un_seul_enregistrement(self):
        mid = self.start()
        ap = self.wait(mid)["apercu"]
        res, errs = [], []

        def clic():
            try:
                res.append(self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": ap["delivery_sha256"]}))
            except Exception as exc:  # noqa
                errs.append(exc)
        ts = [threading.Thread(target=clic) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual({r[0] for r in res}, {200})
        self.assertEqual(sorted(r[1]["derniere_confirmation"] for r in res).count("enregistre"), 1)
        self.assertEqual({r[1]["statut"] for r in res}, {"enregistre"})
        self.assertEqual(len(glob.glob(os.path.join(self.data, "missions", mid, "projet", "docs", "**", "*.md"), recursive=True)), 1)

    def test_refus_d_ecrasement(self):
        mid = self.start()
        ap = self.wait(mid)["apercu"]
        target = os.path.join(self.data, "missions", mid, "projet", ap["chemin"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write("contenu préexistant de la personne\n")
        st, d, _ = self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": ap["delivery_sha256"]})
        self.assertEqual(st, 409)
        with open(target) as fh:
            self.assertEqual(fh.read(), "contenu préexistant de la personne\n")
        self.assertEqual(self.req("GET", "/api/missions/%s/livrable" % mid)[0], 404)

    def test_clarification_aucune_livraison(self):
        mid = self.start("Cas contradictoire : contradict")
        m = self.wait(mid)
        self.assertEqual(m["etat_final"], "clarification_requise")
        self.assertFalse(m["livraison_possible"])
        self.assertIsNone(m.get("apercu"))
        self.assertEqual(m["tours"][-1]["verdict"], "CLARIFICATION_REQUISE")
        self.assertTrue(m["clarification"]["questions"])
        self.assertEqual(self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": "0" * 64})[0], 409)
        self.assertFalse(any(k.startswith("docs") for k in self.project_files(mid)))

    def test_panne_erreur_technique_visible_aucune_livraison(self):
        mid = self.start("Provoque une panne")
        m = self.wait(mid)
        self.assertEqual(m["etat_final"], "erreur_technique")
        self.assertTrue(m["erreurs_techniques"])
        self.assertFalse(m["livraison_possible"])
        self.assertEqual(self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": "0" * 64})[0], 409)
        self.assertFalse(any(k.startswith("docs") for k in self.project_files(mid)))

    def test_plafond_atteint_aucune_livraison(self):
        mid = self.start("Cas de plafond")
        m = self.wait(mid)
        self.assertEqual(m["etat_final"], "plafond_atteint")
        self.assertEqual([t["verdict"] for t in m["tours"]], ["A_CORRIGER"] * 3)
        self.assertFalse(m["livraison_possible"])
        self.assertEqual(self.req("POST", "/api/missions/%s/confirmer" % mid, {"delivery_sha256": "0" * 64})[0], 409)
        self.assertFalse(any(k.startswith("docs") for k in self.project_files(mid)))

    def test_ecart_comportemental_signale(self):
        mid = self.start("Tentative d'outil interdit")
        m = self.wait(mid)
        self.assertTrue(m["ecarts_comportementaux"])
        e = m["ecarts_comportementaux"][0]
        self.assertEqual((e["outil"], e["statut"]), ("Bash", "demande_refusee"))
        self.assertEqual(m["etat_final"], "accepte")  # refusée par la plateforme : visible, non bloquante

    # --- limites -----------------------------------------------------------------------------------------
    def test_concurrence_limitee(self):
        gate = threading.Event()
        orig = self.mgr._default_roles

        def lent(project, request, criteria):
            r = orig(project, request, criteria)
            w = r.writer

            def slow(*a):
                gate.wait(20)
                return w(*a)
            r.writer = slow
            return r
        self.mgr.roles_factory = lent
        self.login()
        a = self.start()
        st, d, _ = self.req("POST", "/api/missions", {"demande": "autre", "criteres": CRIT})
        self.assertEqual(st, 429)
        gate.set()
        self.wait(a)
        st, d, _ = self.req("POST", "/api/missions", {"demande": "autre", "criteres": CRIT})
        self.assertEqual(st, 202)
        self.wait(d["id"])

    def test_limite_horaire(self):
        self.cfg.max_missions_per_hour = 2
        self.login()
        for _ in range(2):
            self.wait(self.start())
        self.assertEqual(self.req("POST", "/api/missions", {"demande": "x", "criteres": CRIT})[0], 429)

    def test_plafond_d_appels_du_pilote(self):
        self.cfg.max_calls = 1
        mid = self.start()
        m = self.wait(mid)
        self.assertNotEqual(m["etat_final"], "accepte")
        self.assertFalse(m["livraison_possible"])

    def test_duree_maximale(self):
        self.cfg.mission_timeout = -1
        m = self.wait(self.start())
        self.assertNotEqual(m["etat_final"], "accepte")
        self.assertFalse(m["livraison_possible"])

    # --- isolation et secrets ---------------------------------------------------------------------------------------
    def test_missions_isolees_et_identifiants_non_devinables(self):
        a = self.start()
        self.wait(a)
        b = self.start()
        self.wait(b)
        self.assertNotEqual(a, b)
        self.assertNotEqual(os.path.realpath(os.path.join(self.data, "missions", a, "projet")), os.path.realpath(os.path.join(self.data, "missions", b, "projet")))
        for bad in ("/api/missions/..%2f..%2fetc", "/api/missions/p-zzzzzzzzzz", "/api/missions/p-0123456789/plan/9", "/api/missions/p-0123456789/revue/1"):
            self.assertIn(self.req("GET", bad)[0], (404,))

    def test_aucun_secret_dans_les_reponses_ni_les_fichiers(self):
        mid = self.start()
        self.wait(mid)
        blobs = []
        for p in ("", "/trace", "/audit", "/plan/1", "/revue/1"):
            blobs.append(json.dumps(self.req("GET", "/api/missions/" + mid + p)[1]))
        blobs.append(json.dumps(self.req("GET", "/api/etat")[1]))
        blobs.append(json.dumps(self.req("GET", "/api/sante", auth=False)[1]))
        for root, _, files in os.walk(os.path.join(self.data, "missions")):
            for f in files:
                try:
                    blobs.append(open(os.path.join(root, f), encoding="utf-8").read())
                except UnicodeDecodeError:
                    pass
        for b in blobs:
            self.assertNotIn(TOKEN, b)
            self.assertNotIn("ANTHROPIC_API_KEY", b)
            self.assertNotIn("sk-ant", b)

    def test_decisions_reelles_intactes_et_run_tests_non_branche(self):
        self.wait(self.start())
        self.assertEqual(self._hash_decisions(), self.decisions_avant)
        for f in glob.glob(os.path.join(REPO, "zakios", "pilote", "*.py")) + glob.glob(os.path.join(REPO, "zakios", "pilote", "static", "*")):
            with open(f, encoding="utf-8") as fh:
                txt = fh.read()
            self.assertNotIn("run-tests", txt.replace("Ne branche pas run-tests", "").replace("run-tests non branché", ""), f)
            self.assertNotIn("decisions/", txt.replace("decisions/*.json", ""), f)

    def test_redemarrage_marque_les_missions_interrompues(self):
        mid = self.start()
        self.wait(mid)
        p = os.path.join(self.data, "missions", mid, "etat.json")
        with open(p) as fh:
            st = json.load(fh)
        st["statut"] = "en_cours"
        with open(p, "w") as fh:
            json.dump(st, fh)
        Manager(self.cfg, base=os.path.join(self.tmp, "base"), components={"x": "0" * 16})
        self.assertEqual(self.req("GET", "/api/missions/" + mid)[1]["statut"], "interrompue")


if __name__ == "__main__":
    unittest.main()
