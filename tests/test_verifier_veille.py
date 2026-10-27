import datetime, json, os, sys, tempfile, unittest, urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import verifier_veille as v

DEP = {"nom": "x/y", "lien": "https://github.com/x/y", "licence": "MIT", "etoiles_declarees": 1000, "preselection": True}
AUJ = datetime.date(2026, 10, 27)


def api(**kw):
    j = {"full_name": "x/y", "license": {"spdx_id": "MIT"}, "stargazers_count": 1100, "pushed_at": "2026-10-20T00:00:00Z", "archived": False}
    j.update(kw)
    return j


class VerifierVeille(unittest.TestCase):
    def test_conforme(self):
        self.assertTrue(v.constat(DEP, api(), AUJ)["conforme"])

    def test_ecarts_detectes(self):
        self.assertIn("ARCHIVÉ", v.constat(DEP, api(archived=True), AUJ)["ecarts"])
        self.assertTrue(any("≠" in e for e in v.constat(DEP, api(license={"spdx_id": "Apache-2.0"}), AUJ)["ecarts"]))
        self.assertTrue(any("NON permissive" in e for e in v.constat(DEP, api(license={"spdx_id": "AGPL-3.0"}), AUJ)["ecarts"]))
        self.assertTrue(any("non détectée" in e for e in v.constat(DEP, api(license=None), AUJ)["ecarts"]))
        self.assertTrue(any("inactif" in e for e in v.constat(DEP, api(pushed_at="2025-01-01T00:00:00Z"), AUJ)["ecarts"]))
        self.assertTrue(any("renommé" in e for e in v.constat(DEP, api(full_name="z/y"), AUJ)["ecarts"]))
        self.assertTrue(any("étoiles" in e for e in v.constat(DEP, api(stargazers_count=50), AUJ)["ecarts"]))

    def test_licence_a_verifier_n_est_jamais_conforme(self):
        d = dict(DEP, licence="À vérifier")
        self.assertFalse(v.constat(d, api(), AUJ)["conforme"])

    def test_main_hors_ligne_rapporte_les_erreurs_sans_les_cacher(self):
        def faux(repo):
            if repo == "langfuse/langfuse":
                raise urllib.error.HTTPError("u", 404, "nf", {}, None)
            return api(full_name=repo)
        with tempfile.TemporaryDirectory() as t:
            sortie = os.path.join(t, "r.json")
            code = v.main(["--sortie", sortie], fetch=faux, today=AUJ, pause=0)
            r = json.load(open(sortie))
        self.assertEqual(code, 2)
        self.assertIn({"nom": "OpenDataLoader PDF (Hancom)", "erreur": "pas de lien dans la feuille"}, r["erreurs"])
        self.assertIn({"nom": "langfuse/langfuse", "erreur": "HTTP 404"}, r["erreurs"])
        self.assertEqual(r["verifies"] + len(r["erreurs"]), 43)


if __name__ == "__main__":
    unittest.main()
