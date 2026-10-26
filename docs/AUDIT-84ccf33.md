# Quatrième audit externe (commit 84ccf33)

L'audit a confirmé les 60 tests, la CI réussie et les corrections de 0.4.0, et trouvé une limite silencieuse : le parcours des dépendances s'arrêtait à 300 fichiers. Pour un skill de 303 fichiers important un auxiliaire extérieur, l'auxiliaire était absent de l'empreinte.

| Défaut | Correction (0.4.1) | Test |
|---|---|---|
| Parcours arrêté à 300 fichiers | plus de limite de paquet ; cycles gérés ; garde-fou de ressources à 20 000 fichiers | `test_large_skill_still_follows_imports_outside_its_folder`, `test_import_cycles_do_not_loop` |
| Limite atteinte sans le dire | `fingerprint_complete: false`, fichiers non explorés listés, rapport `incomplete_fingerprints` | `test_incomplete_fingerprint_is_declared_and_blocks_validation` |
| Validation réappliquée sur une empreinte douteuse | refusée au build (« empreinte incomplète ») et rejetée par `verify` | `test_verify_rejects_validation_on_incomplete_fingerprint` |
| Détection présentée comme complète | `docs/METHODOLOGIE.md` : dépendances détectables, sans garantie de couvrir tous les comportements | |

## Suite recommandée par l'audit

Pilote d'activation contrôlé sur un projet Linux isolé : aperçu, installation de composants sélectionnés et validés, vérification des dépendances, conflits et licences, réexécution sans duplication, retour arrière testé après échec simulé. Pas d'installation autonome en production à ce stade.
