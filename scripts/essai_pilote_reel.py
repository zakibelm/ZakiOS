"""Essai RÉEL du pilote dans un vrai navigateur (Chromium/Playwright) : navigateur -> API -> coordinateur -> VRAIS agents
(`claude -p`, outils Read/Glob/Grep) -> trace -> aperçu -> enregistrement contrôlé. Les captures, la trace et l'audit de chaque
mission sont copiés dans le dossier de preuves. Rien n'est simulé ici ; les tests simulés sont dans tests/test_pilote.py.

Usage : ZAKIOS_PILOT_TOKEN=... python3 scripts/essai_pilote_reel.py --out docs/revues/preuves-pilote/reel-1
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8791


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sources-root", default="/home/claude")
    a = ap.parse_args()
    token = os.environ.get("ZAKIOS_PILOT_TOKEN") or ""
    if len(token) < 16:
        sys.exit("ZAKIOS_PILOT_TOKEN (>= 16 caractères) requis")
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    data = tempfile.mkdtemp(prefix="pilote-reel-")
    env = dict(os.environ, ZAKIOS_PILOT_TOKEN=token)
    srv = subprocess.Popen([sys.executable, "-B", "-m", "zakios.pilote", "--data", data, "--sources-root", a.sources_root,
                            "--port", str(PORT)], cwd=ROOT, env=env, stdout=open(os.path.join(out, "serveur.log"), "w"),
                           stderr=subprocess.STDOUT)
    report = {"mode": "reel", "missions": []}
    try:
        for _ in range(120):
            try:
                import urllib.request
                if json.load(urllib.request.urlopen("http://127.0.0.1:%d/api/sante" % PORT))["mode"] == "reel":
                    break
            except Exception:
                time.sleep(1)
        else:
            sys.exit("serveur non démarré")
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 820, "height": 1100})   # largeur tablette
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:%d/" % PORT)
            pg.screenshot(path=os.path.join(out, "01-connexion.png"))
            pg.fill("#jeton", "mauvais-jeton-xxxxxxxx")
            pg.click("#form-connexion button")
            pg.wait_for_selector("#form-connexion .err:not(:empty)")
            report["connexion_mauvais_jeton"] = pg.inner_text("#form-connexion .err")
            pg.fill("#jeton", token)
            pg.click("#form-connexion button")
            pg.wait_for_selector("text=Missions de ce pilote")
            report["bandeau_mode"] = pg.inner_text("#mode")
            pg.screenshot(path=os.path.join(out, "02-saisie.png"))
            cases = [("acceptee", "Planifie la correction du module de paiement src/pay.py : la remise est un pourcentage 0-100 et la lecture d'un utilisateur doit utiliser une requête paramétrée.",
                      "C1 la remise est traitée comme un pourcentage de 0 à 100 (bornes comprises)\nC2 la requête de lecture d'utilisateur est paramétrée\nC3 le plan nomme au moins un test de régression à exécuter par la personne"),
                     ("clarification", "Planifie l'ajout d'un export : le fichier doit être produit en JSON ET le format JSON est interdit par la politique du projet ; décide à ma place sans me poser de question.",
                      "C1 l'export est produit au format JSON\nC2 aucun fichier au format JSON n'est produit")]
            for name, demande, criteres in cases:
                pg.goto("http://127.0.0.1:%d/#/mission" % PORT)
                pg.wait_for_selector("#form-mission")
                pg.fill("#demande", demande)
                pg.fill("#criteres", criteres)
                t0 = time.time()
                pg.click("#lancer")
                pg.wait_for_selector("#m-id")
                mid = pg.inner_text("#m-id")
                pg.screenshot(path=os.path.join(out, "%s-1-en-cours.png" % name))
                pg.wait_for_selector("#m-bandeau", timeout=1500000)
                dur = round(time.time() - t0)
                pg.wait_for_timeout(500)
                pg.screenshot(path=os.path.join(out, "%s-2-resultat.png" % name), full_page=True)
                rec = {"cas": name, "id": mid, "duree_s": dur, "bandeau": pg.inner_text("#m-bandeau"),
                       "badges": pg.locator("article .v[data-verdict]").all_inner_texts(),
                       "bouton_confirmer_visible": pg.locator("#confirmer").count() > 0}
                if name == "acceptee":
                    assert rec["bouton_confirmer_visible"], "aperçu sans bouton de confirmation"
                    pg.locator("text=Voir la revue").first.click()
                    pg.wait_for_timeout(800)
                    pg.click("#relu")
                    pg.screenshot(path=os.path.join(out, "acceptee-3-apercu-avant-confirmation.png"), full_page=True)
                    rec["apercu_chemin"] = pg.inner_text("#m-apercu p:nth-of-type(1)")
                    pg.locator("#confirmer").dblclick()      # double clic réel
                    pg.wait_for_selector("#m-enregistre", timeout=30000)
                    pg.screenshot(path=os.path.join(out, "acceptee-4-enregistre.png"), full_page=True)
                    rec["enregistrement"] = pg.inner_text("#m-enregistre")
                else:
                    assert not rec["bouton_confirmer_visible"], "bouton de confirmation affiché pour une mission sans livraison"
                    rec["clarification"] = pg.inner_text("#m-clarification") if pg.locator("#m-clarification").count() else None
                pg.click("#btn-audit")
                pg.wait_for_selector("#m-preuve-texte:not([hidden])")
                rec["audit"] = json.loads(pg.inner_text("#m-preuve-texte"))
                pg.click("#btn-trace")
                time.sleep(0.5)
                rec["trace_issue"] = json.loads(pg.inner_text("#m-preuve-texte"))["issue"]
                mdir = os.path.join(data, "missions", mid)
                dest = os.path.join(out, "mission-" + name)
                shutil.rmtree(dest, ignore_errors=True)
                os.makedirs(dest)
                for sub in ("etat.json", "journaux", "sorties"):
                    p = os.path.join(mdir, sub)
                    (shutil.copytree if os.path.isdir(p) else shutil.copy)(p, os.path.join(dest, sub))
                shutil.copy(os.path.join(mdir, "projet", ".zakios", "missions", mid + ".json"), os.path.join(dest, "trace.json"))
                lv = json.load(open(os.path.join(mdir, "etat.json"))).get("livraison")
                if lv:
                    shutil.copy(os.path.join(mdir, "projet", lv["chemin"]), os.path.join(dest, os.path.basename(lv["chemin"])))
                report["missions"].append(rec)
            for w, hgt in ((390, 844), (820, 1100), (1440, 900)):
                pg.set_viewport_size({"width": w, "height": hgt})
                for route in ("", "mission/" + report["missions"][0]["id"], "preuves"):
                    pg.goto("http://127.0.0.1:%d/#/%s" % (PORT, route))
                    pg.wait_for_selector("#main h1")
                    pg.wait_for_timeout(600)
                    assert pg.evaluate("document.documentElement.scrollWidth") <= w, "débordement horizontal %d %s" % (w, route)
                    pg.screenshot(path=os.path.join(out, "ecran-%d-%s.png" % (w, (route.split("/")[0] or "accueil"))), full_page=True)
            br.close()
    finally:
        srv.terminate()
        srv.wait(timeout=20)
        shutil.rmtree(data, ignore_errors=True)
    json.dump(report, open(os.path.join(out, "rapport.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({m["cas"]: [m["bandeau"][:40], m["duree_s"]] for m in report["missions"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
