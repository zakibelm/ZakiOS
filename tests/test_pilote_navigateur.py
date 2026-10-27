"""Pilote — parcours DANS UN VRAI NAVIGATEUR (Chromium via Playwright), rôles SIMULÉS (aucun modèle appelé).

Prouve l'interface : affichage distinct des verdicts, aperçu exact, confirmation, double clic, refus d'écrasement, absence
de livraison hors acceptation, écrans 390/820/1440 px, clavier, focus, mouvement réduit, contrastes. Le même parcours avec
de VRAIS agents est dans scripts/essai_pilote_reel.py. Ignoré si Playwright/Chromium est absent."""
import json
import os
import shutil
import tempfile
import threading
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

from zakios.pilote.config import Config
from zakios.pilote.missions import Manager
from zakios.pilote.server import serve

TOKEN = "jeton-navigateur-0123456789"

CONTRASTE_JS = """() => {
  const lum = (r,g,b) => { const f = v => { v/=255; return v<=.03928 ? v/12.92 : Math.pow((v+.055)/1.055,2.4); }; return .2126*f(r)+.7152*f(g)+.0722*f(b); };
  const rgb = s => (s.match(/[\\d.]+/g) || []).map(Number);
  const fond = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length >= 3 && (c.length < 4 || c[3] > 0.99)) return c; } return [255,255,255]; };
  const out = [];
  const sels = ["h1", ".lead", ".note", "nav a", "nav a.active", ".mode", ".notice", ".v", ".banner", ".banner p", "button", "button.primary", ".err", "label", "th", "td", "footer", ".crumbs", ".side-foot a", ".eyebrow", ".hash"];
  for (const s of sels) for (const el of document.querySelectorAll(s)) {
    if (!el.offsetParent && getComputedStyle(el).position !== "fixed") continue;
    const c = rgb(getComputedStyle(el).color), b = fond(el);
    const L1 = lum(c[0],c[1],c[2]), L2 = lum(b[0],b[1],b[2]);
    const ratio = (Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
    out.push([s, Math.round(ratio*100)/100, (el.textContent||"").trim().slice(0,30), el.disabled === true]);
  }
  return out;
}"""


@unittest.skipIf(sync_playwright is None, "Playwright absent")
class Navigateur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        base = os.path.join(cls.tmp, "base")
        os.makedirs(os.path.join(base, "src"))
        with open(os.path.join(base, "src/pay.py"), "w") as fh:
            fh.write("def total(p, d):\n    return sum(p)\n")
        cfg = Config(data_dir=os.path.join(cls.tmp, "data"), sources_root=cls.tmp, token=TOKEN, simulation=True, port=0, max_missions_per_hour=200)
        cls.cfg = cfg
        cls.mgr = Manager(cfg, base=base, components={"x": "0" * 16})
        cls.httpd, _ = serve(cfg, cls.mgr)
        cls.url = "http://127.0.0.1:%d/" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as exc:  # pragma: no cover
            cls.pw.stop()
            cls.httpd.shutdown()
            raise unittest.SkipTest("Chromium indisponible : %s" % exc)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, width=1440, height=900, **ctx):
        c = self.browser.new_context(viewport={"width": width, "height": height}, **ctx)
        self.addCleanup(c.close)
        pg = c.new_page()
        self.erreurs = []
        pg.on("console", lambda m: self.erreurs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: self.erreurs.append(str(e)))
        pg.goto(self.url)
        pg.fill("#jeton", TOKEN)
        pg.click("#form-connexion button")
        pg.wait_for_selector("text=Missions de ce pilote")
        return pg

    def lancer(self, pg, demande=None):
        pg.goto(self.url + "#/mission")
        pg.wait_for_selector("#form-mission")
        if demande:
            pg.fill("#demande", demande)
        pg.click("#lancer")
        pg.wait_for_selector("#m-bandeau", timeout=60000)
        return pg.inner_text("#m-id")

    # --- parcours -----------------------------------------------------------------------------------------
    def test_mauvais_jeton_puis_acceptee_apercu_confirmation_double_clic(self):
        c = self.browser.new_context()
        self.addCleanup(c.close)
        pg = c.new_page()
        pg.goto(self.url)
        pg.fill("#jeton", "mauvais-jeton-xxxxxxxxx")
        pg.click("#form-connexion button")
        pg.wait_for_selector("#form-connexion .err:not(:empty)")
        self.assertIn("invalide", pg.inner_text("#form-connexion .err"))
        pg = self.page()
        mid = self.lancer(pg)
        self.assertEqual(pg.locator("#m-bandeau").get_attribute("class").split()[-1], "accepte")
        self.assertIn("ACCEPTÉ", pg.inner_text("#m-bandeau"))
        self.assertTrue(pg.locator("[data-verdict=ACCEPTE]").count() >= 1)
        apercu = pg.inner_text("#m-apercu pre")
        self.assertTrue(pg.locator("#confirmer").is_disabled())          # pas de confirmation sans relecture cochée
        self.assertEqual(pg.locator("#m-enregistre").count(), 0)
        pg.check("#relu")
        self.assertFalse(pg.locator("#confirmer").is_disabled())
        pg.locator("#confirmer").dblclick()                               # double clic réel
        pg.wait_for_selector("#m-enregistre")
        self.assertIn("enregistre", pg.inner_text("#m-enregistre"))
        d = os.path.join(self.cfg.data_dir, "missions", mid, "projet")
        fichiers = [os.path.join(dp, f) for dp, _, fs in os.walk(d) for f in fs if dp.endswith(os.path.join("docs", "plans"))]
        self.assertEqual(len(fichiers), 1)
        with open(fichiers[0], encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), apercu.strip())          # octets enregistrés = aperçu montré
        pg.reload()
        pg.wait_for_selector("#m-enregistre")                             # état restitué par le serveur, pas par le navigateur
        self.assertEqual(pg.locator("#confirmer").count(), 0)
        self.assertEqual(self.erreurs, [])

    def test_clarification_aucun_bouton_de_livraison(self):
        pg = self.page()
        self.lancer(pg, "Cas contradictoire : contradict")
        self.assertEqual(pg.locator("[data-issue=clarification_requise]").count(), 1)
        self.assertIn("CLARIFICATION REQUISE", pg.inner_text("#m-bandeau"))
        self.assertTrue(pg.locator("[data-verdict=CLARIFICATION_REQUISE]").count() >= 1)
        self.assertEqual(pg.locator("#m-clarification").count(), 1)
        for sel in ("#confirmer", "#m-apercu", "text=Télécharger", "#relu"):
            self.assertEqual(pg.locator(sel).count(), 0, sel)

    def test_panne_erreur_technique_visible_sans_livraison(self):
        pg = self.page()
        self.lancer(pg, "Provoque une panne")
        self.assertIn("ERREUR TECHNIQUE", pg.inner_text("#m-bandeau"))
        self.assertNotIn("Aucune erreur technique", pg.inner_text("#m-erreurs"))
        self.assertIn("panne simulée", pg.inner_text("#m-erreurs"))
        for sel in ("#confirmer", "#m-apercu", "text=Télécharger"):
            self.assertEqual(pg.locator(sel).count(), 0, sel)

    def test_plafond_trois_a_corriger_sans_livraison(self):
        pg = self.page()
        self.lancer(pg, "Cas de plafond")
        self.assertIn("PLAFOND ATTEINT", pg.inner_text("#m-bandeau"))
        self.assertEqual(pg.locator("article [data-verdict=A_CORRIGER]").count(), 3)
        self.assertIn("À CORRIGER", pg.locator("article [data-verdict=A_CORRIGER]").first.inner_text())
        for sel in ("#confirmer", "#m-apercu", "text=Télécharger"):
            self.assertEqual(pg.locator(sel).count(), 0, sel)

    def test_ecart_comportemental_visible(self):
        pg = self.page()
        self.lancer(pg, "Tentative d'outil interdit")
        self.assertIn("Bash", pg.inner_text("#m-ecarts"))
        self.assertIn("demande refusée", pg.inner_text("#m-ecarts"))
        self.assertEqual(pg.locator("#confirmer").count(), 1)             # refus plateforme : visible, non bloquant

    def test_refus_d_ecrasement_dans_l_interface(self):
        pg = self.page()
        mid = self.lancer(pg)
        chemin = pg.inner_text("#m-apercu p:nth-of-type(1) code")
        cible = os.path.join(self.cfg.data_dir, "missions", mid, "projet", chemin)
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        with open(cible, "w") as fh:
            fh.write("contenu de la personne\n")
        pg.check("#relu")
        pg.click("#confirmer")
        pg.wait_for_selector("text=Enregistrement refusé")
        self.assertEqual(pg.locator("#m-enregistre").count(), 0)
        with open(cible) as fh:
            self.assertEqual(fh.read(), "contenu de la personne\n")

    def test_preuves_par_campagne_c3_visible_et_sans_taux(self):
        pg = self.page()
        pg.goto(self.url + "#/preuves")
        pg.wait_for_selector("#campagne-C3")
        txt = pg.inner_text("#main")
        self.assertIn("outil modifiant utilisé par plan-writer", txt)
        self.assertIn("Critères non tous satisfaits", pg.inner_text("#campagne-C3"))
        self.assertIn("Critères satisfaits", pg.inner_text("#campagne-C4"))
        self.assertEqual(pg.locator("article[id^=campagne-]").count(), 5)
        self.assertNotRegex(txt, r"\d+\s?%")                              # aucun pourcentage agrégé

    def test_bibliotheque_lit_la_source_exacte(self):
        pg = self.page()
        pg.goto(self.url + "#/bibliotheque")
        pg.wait_for_selector("#grille article")
        pg.fill("#recherche", "plan-reviewer")
        self.assertEqual(pg.locator("#grille article").count(), 1)
        pg.click("#grille button")
        pg.wait_for_selector("dialog[open]")
        self.assertIn("plan", pg.inner_text("#detail-text").lower())
        pg.keyboard.press("Escape")
        self.assertEqual(pg.locator("dialog[open]").count(), 0)

    def test_veille_filtres_et_avertissement(self):
        pg = self.page()
        pg.goto(self.url + "#/veille")
        pg.wait_for_selector("#veille-lignes tr")
        self.assertEqual(pg.locator("#veille-lignes tr").count(), 124)
        self.assertIn("rien n", pg.inner_text("#veille-avert").lower())
        pg.select_option("#veille-prio", "Haute")
        self.assertEqual(pg.locator("#veille-lignes tr").count(), 22)
        pg.select_option("#veille-statut", "Évalué")
        self.assertEqual(pg.locator("#veille-lignes tr").count(), 0)
        pg.select_option("#veille-statut", "")
        pg.select_option("#veille-prio", "")
        pg.select_option("#veille-pre", "oui")
        n = pg.locator("#veille-lignes tr").count()
        self.assertEqual(n, int(pg.inner_text("#veille-regle").split("dépôt(s) sur")[0].split()[-1]))
        self.assertEqual(pg.locator("#veille-lignes [data-presel=non]").count(), 0)
        self.assertIn("ni une validation", pg.inner_text("#veille-regle"))
        pg.select_option("#veille-pre", "")
        pg.fill("#veille-q", "langfuse")
        self.assertEqual(pg.locator("#veille-lignes tr").count(), 1)
        self.assertEqual(pg.locator("#veille-lignes a[rel~=noopener]").count(), 1)
        self.assertEqual(self.erreurs, [])

    # --- écrans, clavier, mouvement, contrastes ------------------------------------------------------------------------
    def test_trois_largeurs_sans_debordement_ni_erreur(self):
        for largeur, hauteur in ((390, 844), (820, 1100), (1440, 900)):
            pg = self.page(largeur, hauteur)
            for route in ("", "mission", "preuves", "bibliotheque", "veille"):
                pg.goto(self.url + "#/" + route)
                pg.wait_for_selector("#main h1")
                self.assertLessEqual(pg.evaluate("document.documentElement.scrollWidth"), largeur, "%dpx #/%s" % (largeur, route))
                trop_petits = pg.evaluate("""() => [...document.querySelectorAll('button, nav a, .btn, input[type=checkbox]')]
                    .filter(e => e.offsetParent && e.getBoundingClientRect().height < 22).map(e => e.textContent.trim().slice(0, 20))""")
                self.assertEqual(trop_petits, [], "cibles tactiles trop petites %dpx" % largeur)
            self.assertEqual(self.erreurs, [], largeur)

    def test_clavier_focus_visible_et_lien_d_evitement(self):
        pg = self.page(820, 1100)
        pg.goto(self.url + "#/mission")
        pg.wait_for_selector("#form-mission")
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        vus = []
        for _ in range(18):
            pg.keyboard.press("Tab")
            info = pg.evaluate("""() => { const e = document.activeElement; const s = getComputedStyle(e);
                return {id: e.id || e.tagName + ':' + (e.textContent || '').trim().slice(0, 20), w: parseFloat(s.outlineWidth), st: s.outlineStyle}; }""")
            if info["id"].startswith("BODY"):
                continue
            self.assertEqual(info["st"], "solid", info)
            self.assertGreaterEqual(info["w"], 3, info)
            vus.append(info["id"])
        self.assertTrue(any("Aller au contenu" in v for v in vus), vus)
        for attendu in ("demande", "criteres", "lancer"):
            self.assertIn(attendu, vus)

    def test_mouvement_reduit_desactive_les_animations(self):
        pg = self.page(1440, 900, reduced_motion="reduce")
        self.assertEqual(pg.evaluate("getComputedStyle(document.querySelector('.ring')).animationName"), "none")
        pg2 = self.page(1440, 900, reduced_motion="no-preference")
        self.assertNotEqual(pg2.evaluate("getComputedStyle(document.querySelector('.ring')).animationName"), "none")

    def test_contrastes_wcag_aa(self):
        pg = self.page(1440, 900)
        self.lancer(pg, "Cas de plafond")
        manques = []
        for route in ("", "mission", "preuves"):
            pg.goto(self.url + "#/" + route) if route != "mission" else None
            if route != "mission":
                pg.wait_for_selector("#main h1")
            for sel, ratio, txt, desactive in pg.evaluate(CONTRASTE_JS):
                if ratio < 4.5 and not desactive:
                    manques.append((route, sel, ratio, txt))
        self.assertEqual(manques, [])
        pg.goto(self.url + "#/mission")                                  # mission acceptée : bouton principal, bandeau vert
        self.lancer(pg)
        pg.check("#relu")
        for sel, ratio, txt, desactive in pg.evaluate(CONTRASTE_JS):
            self.assertGreaterEqual(ratio, 4.5, (sel, txt))


if __name__ == "__main__":
    unittest.main()
