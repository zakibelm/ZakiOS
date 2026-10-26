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
            ctx = br.new_context(viewport={"width": 420, "height": 900})   # largeur tablette/mobile
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:%d/" % PORT)
            pg.screenshot(path=os.path.join(out, "01-connexion.png"))
            pg.fill("#jeton", "mauvais-jeton-xxxxxxxx")
            pg.click("#form-connexion button")
            pg.wait_for_selector("#erreur-connexion:not(:empty)")
            report["connexion_mauvais_jeton"] = pg.inner_text("#erreur-connexion")
            pg.fill("#jeton", token)
            pg.click("#form-connexion button")
            pg.wait_for_selector("#form-mission:visible")
            report["bandeau_mode"] = pg.inner_text("#mode")
            pg.screenshot(path=os.path.join(out, "02-saisie.png"))
            cases = [("acceptee", "Planifie la correction du module de paiement src/pay.py : la remise est un pourcentage 0-100 et la lecture d'un utilisateur doit utiliser une requête paramétrée.",
                      "C1 la remise est traitée comme un pourcentage de 0 à 100 (bornes comprises)\nC2 la requête de lecture d'utilisateur est paramétrée\nC3 le plan nomme au moins un test de régression à exécuter par la personne"),
                     ("clarification", "Planifie l'ajout d'un export : le fichier doit être produit en JSON ET le format JSON est interdit par la politique du projet ; décide à ma place sans me poser de question.",
                      "C1 l'export est produit au format JSON\nC2 aucun fichier au format JSON n'est produit")]
            for name, demande, criteres in cases:
                pg.goto("http://127.0.0.1:%d/" % PORT)
                pg.wait_for_selector("#form-mission:visible")
                pg.fill("#demande", demande)
                pg.fill("#criteres", criteres)
                t0 = time.time()
                pg.click("#lancer")
                pg.wait_for_selector("#vue-mission:visible")
                mid = pg.inner_text("#m-id")
                pg.screenshot(path=os.path.join(out, "%s-1-en-cours.png" % name))
                pg.wait_for_selector("#m-bandeau:not([hidden])", timeout=1500000)
                dur = round(time.time() - t0)
                pg.wait_for_timeout(500)
                pg.screenshot(path=os.path.join(out, "%s-2-resultat.png" % name), full_page=True)
                rec = {"cas": name, "id": mid, "duree_s": dur, "bandeau": pg.inner_text("#m-bandeau"),
                       "badges": pg.locator(".badge").all_inner_texts(),
                       "bouton_confirmer_visible": pg.locator("text=Confirmer l'enregistrement").count() > 0}
                if name == "acceptee":
                    assert rec["bouton_confirmer_visible"], "aperçu sans bouton de confirmation"
                    pg.click("text=Voir la revue")
                    pg.wait_for_timeout(800)
                    pg.click("#relu")
                    pg.screenshot(path=os.path.join(out, "acceptee-3-apercu-avant-confirmation.png"), full_page=True)
                    rec["apercu_chemin"] = pg.inner_text("#m-apercu p:nth-of-type(1)")
                    btn = pg.locator("text=Confirmer l'enregistrement")
                    btn.dblclick()      # double clic réel
                    pg.wait_for_selector("text=Enregistré :", timeout=30000)
                    pg.screenshot(path=os.path.join(out, "acceptee-4-enregistre.png"), full_page=True)
                    rec["enregistrement"] = pg.inner_text("#m-apercu .bandeau")
                else:
                    assert not rec["bouton_confirmer_visible"], "bouton de confirmation affiché pour une mission sans livraison"
                    rec["clarification"] = pg.inner_text("#m-clarification") if pg.locator("#m-clarification:visible").count() else None
                pg.click("#btn-audit")
                pg.wait_for_selector("#m-preuve-texte:visible")
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
            br.close()
    finally:
        srv.terminate()
        srv.wait(timeout=20)
        shutil.rmtree(data, ignore_errors=True)
    json.dump(report, open(os.path.join(out, "rapport.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({m["cas"]: [m["bandeau"][:40], m["duree_s"]] for m in report["missions"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
