"""Serveur HTTP du pilote (bibliothèque standard uniquement) : accès protégé, API JSON, pages statiques.

Sécurité : jeton d'accès obligatoire (cookie de session HttpOnly/SameSite=Strict ou en-tête Bearer), limitation des
essais de connexion, en-tête `X-Zakios-Pilote` exigé sur les POST (anti-CSRF), CSP stricte sans script en ligne, corps
de requête borné, aucune clé ni variable d'environnement renvoyée au navigateur."""
import hmac
import ipaddress
import json
import os
import re
import secrets
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import Config
from .missions import Busy, Conflict, Invalid, Manager, NotFound

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TYPES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8", "gsap.min.js": "text/javascript; charset=utf-8"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
MID = r"(p-[0-9a-f]{10})"


class Pilot:
    def __init__(self, cfg, manager=None):
        cfg.validate()
        self.cfg = cfg
        self.manager = manager or Manager(cfg)
        self.sessions = {}      # id de session -> expiration
        self.failures = {}      # adresse -> [horodatages d'échecs de connexion]
        self.lock = __import__("threading").Lock()

    def check_token(self, candidate):
        return isinstance(candidate, str) and hmac.compare_digest(candidate.encode(), self.cfg.token.encode())

    def new_session(self):
        sid = secrets.token_urlsafe(32)
        with self.lock:
            now = time.time()
            self.sessions = {k: v for k, v in self.sessions.items() if v > now}
            self.sessions[sid] = now + self.cfg.session_ttl
        return sid

    def session_ok(self, sid):
        with self.lock:
            return bool(sid) and self.sessions.get(sid, 0) > time.time()

    def drop_session(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)

    def too_many_failures(self, ip):
        with self.lock:
            now = time.time()
            self.failures[ip] = [t for t in self.failures.get(ip, []) if now - t < 600]
            return len(self.failures[ip]) >= self.cfg.login_failures_max

    def note_failure(self, ip):
        with self.lock:
            self.failures.setdefault(ip, []).append(time.time())


def bibliotheque():
    """Rôles et règles du moteur lus dans le dépôt (lecture seule) : nom, description, empreinte, texte source."""
    import hashlib
    out = []
    for rel in ["socle/REGLES.md"] + ["variantes/agents/%s" % f for f in sorted(os.listdir(os.path.join(REPO, "variantes", "agents")))]:
        with open(os.path.join(REPO, rel), "rb") as fh:
            raw = fh.read()
        text = raw.decode("utf-8")
        name, desc = os.path.basename(rel), ""
        if text.startswith("---"):
            head = text.split("---", 2)[1]
            for line in head.splitlines():
                if line.startswith("name:"):
                    name = line[5:].strip()
                if line.startswith("description:"):
                    desc = line[12:].strip().strip('"')
        out.append({"chemin": rel, "nom": name, "type": "Socle" if rel.startswith("socle") else "Agent", "description": desc,
                    "sha256": hashlib.sha256(raw).hexdigest(), "texte": text})
    return out


def make_handler(pilot):
    cfg = pilot.cfg

    class H(BaseHTTPRequestHandler):
        server_version = "ZakiOSPilote"
        sys_version = ""

        def log_message(self, fmt, *args):  # pas de journalisation des URL (pas de jeton dans les journaux)
            pass

        # --- utilitaires -------------------------------------------------------------------------------------
        def _headers(self, code, ctype, length, extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            if cfg.secure_cookie:
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()

        def _client_ip(self):
            """Adresse réelle du visiteur : X-Real-IP n'est crue que si la requête vient d'un proxy de confiance, sinon un
            attaquant pourrait la falsifier pour contourner (ou faire subir à autrui) la limite d'essais."""
            peer = self.client_address[0]
            if peer in cfg.trusted_proxies:
                try:
                    return str(ipaddress.ip_address((self.headers.get("X-Real-IP") or "").strip()))
                except ValueError:
                    pass
            return peer

        def _json(self, code, obj, extra=()):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._headers(code, "application/json; charset=utf-8", len(body), extra)
            self.wfile.write(body)

        def _err(self, code, msg, extra=()):
            self._json(code, {"erreur": msg}, extra)

        def _cookie(self):
            raw = self.headers.get("Cookie", "")
            m = re.search(r"(?:^|;\s*)zakios_pilote=([A-Za-z0-9_-]+)", raw)
            return m.group(1) if m else None

        def _authed(self):
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer ") and pilot.check_token(auth[7:]):
                return True
            return pilot.session_ok(self._cookie())

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > cfg.max_body_bytes:
                raise Invalid("corps de requête trop grand")
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                raise Invalid("JSON invalide")

        def _csrf_ok(self):
            if self.headers.get("X-Zakios-Pilote") != "1":
                return False
            origin = self.headers.get("Origin")
            return origin is None or urlparse(origin).netloc == self.headers.get("Host")

        # --- routes ------------------------------------------------------------------------------------------
        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path in ("/", "/index.html"):
                    return self._static("index.html")
                if path in ("/app.js", "/style.css", "/gsap.min.js"):
                    return self._static(path[1:])
                if path == "/api/sante":
                    return self._json(200, {"ok": True, "mode": pilot.manager.mode, "connecte": self._authed()})
                if not self._authed():
                    return self._err(401, "accès non autorisé")
                if path == "/api/etat":
                    return self._json(200, {"mode": pilot.manager.mode, "limites": pilot.manager.limites(),
                                            "exemple": {"src/pay.py": __import__("zakios.pilote.missions", fromlist=["x"]).SAMPLE_PAY}})
                if path == "/api/missions":
                    return self._json(200, {"missions": pilot.manager.lister()})
                if path == "/api/campagnes":
                    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "campagnes.json"), encoding="utf-8") as fh:
                        return self._json(200, json.load(fh))
                if path == "/api/veille":
                    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "veille.json"), encoding="utf-8") as fh:
                        return self._json(200, json.load(fh))
                if path == "/api/bibliotheque":
                    return self._json(200, {"composants": bibliotheque()})
                m = re.fullmatch(r"/api/missions/%s" % MID, path)
                if m:
                    return self._json(200, pilot.manager.get(m.group(1)))
                m = re.fullmatch(r"/api/missions/%s/(trace|audit|livrable)" % MID, path)
                if m:
                    mid, what = m.groups()
                    if what == "trace":
                        return self._json(200, pilot.manager.trace(mid))
                    if what == "audit":
                        return self._json(200, pilot.manager.audit(mid))
                    name, data = pilot.manager.delivered_file(mid)
                    self._headers(200, "text/markdown; charset=utf-8", len(data),
                                  [("Content-Disposition", 'attachment; filename="%s"' % name)])
                    return self.wfile.write(data)
                m = re.fullmatch(r"/api/missions/%s/(plan|revue)/([1-9])" % MID, path)
                if m:
                    mid, what, tour = m.group(1), m.group(2), int(m.group(3))
                    text = pilot.manager.plan(mid, tour) if what == "plan" else pilot.manager.review(mid, tour)
                    return self._json(200, {"tour": tour, "texte": text})
                return self._err(404, "introuvable")
            except NotFound:
                return self._err(404, "introuvable")
            except Invalid as exc:
                return self._err(400, str(exc))

        def _static(self, name):
            with open(os.path.join(STATIC, name), "rb") as fh:
                data = fh.read()
            self._headers(200, TYPES[name], len(data))
            self.wfile.write(data)

        def do_HEAD(self):
            """Mêmes en-têtes que GET (dont Content-Length), sans corps : sondes de disponibilité."""
            class _SansCorps:
                def __init__(self, w):
                    self.w, self.n = w, 0

                def write(self, data):
                    self.n += 1
                    return self.w.write(data) if self.n == 1 else len(data)     # 1re écriture = en-têtes ; le reste = corps, ignoré

                def flush(self):
                    self.w.flush()
            vrai = self.wfile
            self.wfile = _SansCorps(vrai)
            try:
                self.do_GET()
            finally:
                self.wfile = vrai

        def do_POST(self):
            path = urlparse(self.path).path
            ip = self._client_ip()
            try:
                if not self._csrf_ok():
                    return self._err(403, "requête refusée (en-tête de protection absent)")
                if path == "/api/connexion":
                    if pilot.too_many_failures(ip):
                        return self._err(429, "trop d'essais ; réessayez plus tard")
                    body = self._body()
                    if not pilot.check_token(body.get("jeton")):
                        pilot.note_failure(ip)
                        return self._err(401, "jeton invalide")
                    sid = pilot.new_session()
                    flags = "HttpOnly; SameSite=Strict; Path=/; Max-Age=%d%s" % (cfg.session_ttl, "; Secure" if cfg.secure_cookie else "")
                    return self._json(200, {"ok": True}, [("Set-Cookie", "zakios_pilote=%s; %s" % (sid, flags))])
                if path == "/api/deconnexion":
                    pilot.drop_session(self._cookie())
                    return self._json(200, {"ok": True}, [("Set-Cookie", "zakios_pilote=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0%s" % ("; Secure" if cfg.secure_cookie else ""))])
                if not self._authed():
                    return self._err(401, "accès non autorisé")
                if path == "/api/missions":
                    body = self._body()
                    mid = pilot.manager.create(body.get("demande"), body.get("criteres"))
                    return self._json(202, {"id": mid})
                m = re.fullmatch(r"/api/missions/%s/confirmer" % MID, path)
                if m:
                    body = self._body()
                    if not isinstance(body.get("delivery_sha256"), str):
                        raise Invalid("empreinte de livraison manquante")
                    return self._json(200, pilot.manager.confirm(m.group(1), body["delivery_sha256"]))
                return self._err(404, "introuvable")
            except Invalid as exc:
                return self._err(400, str(exc))
            except Busy as exc:
                return self._err(429, str(exc))
            except Conflict as exc:
                return self._err(409, str(exc))
            except NotFound:
                return self._err(404, "introuvable")

    return H


def serve(cfg, manager=None):
    pilot = Pilot(cfg, manager)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(pilot))
    httpd.daemon_threads = True
    return httpd, pilot


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Pilote supervisé ZakiOS (jeton d'accès dans ZAKIOS_PILOT_TOKEN)")
    ap.add_argument("--data", default=None)
    ap.add_argument("--sources-root", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--simulation", action="store_true", help="rôles simulés : aucun appel à un modèle")
    a = ap.parse_args(argv)
    over = {"host": a.host, "port": a.port}
    if a.data:
        over["data_dir"] = a.data
    if a.sources_root:
        over["sources_root"] = a.sources_root
    cfg = Config.from_env(**over)
    if a.simulation:
        cfg.simulation = True
    httpd, pilot = serve(cfg)
    print("Pilote ZakiOS (%s) sur http://%s:%d — accès par jeton" % (pilot.manager.mode, cfg.host, cfg.port), flush=True)
    httpd.serve_forever()
