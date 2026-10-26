# Troisième audit externe (commit 8e6bc0b)

L'audit a confirmé les 50 tests, la CI réussie et les protections de 0.3.0, et en a trouvé deux incomplètes ainsi que des précisions sur le remplacement. Il n'a pas reconstruit les onze sources. Chaque point a un test.

| Défaut | Correction (0.4.0) | Test |
|---|---|---|
| Un composant du Socle au YAML invalide restait sélectionnable comme équivalent (score 0,99) | exclu des index : référence, voisins, homonymes, inter-couches ; `verify` rejette toute référence vers un composant invalide | `test_invalid_socle_component_is_never_a_reference`, `test_invalid_reference_is_rejected_by_verify` |
| Un fichier importé par un hook ou un script de skill ne changeait pas l'empreinte | empreinte du paquet complet : dossier du skill ou du mod, scripts cités par la configuration d'un hook, imports locaux python, js/ts et shell, transitivement | `test_fingerprint_follows_local_imports_of_hook_scripts`, `…_js_requires_and_transitive_imports`, `test_hook_config_referencing_a_script_in_another_folder`, `test_skill_fingerprint_covers_its_scripts_and_resources` |
| Lecture pouvant mélanger ancien registre et nouveau rapport | lecture par descripteur de dossier unique ; `registry_sha256` dans le rapport ; génération précédente gardée dans `catalog.prev` | `test_reader_keeps_a_consistent_generation_during_an_update`, `test_report_from_another_generation_is_detected` |
| Verrou inactif sans `fcntl` | le build refuse de démarrer ; plateforme prise en charge : Linux | `test_missing_fcntl_refuses_to_build` |

## Limites restantes

- Les dépendances détectées sont les imports locaux et chemins cités. Les paquets installés (npm, pip), les appels dynamiques et les variables d'environnement ne sont pas suivis.
- Une lecture qui ouvre `catalog/` fichier par fichier, sans passer par `read_generation`, peut encore voir deux générations.
- Les chiffres du catalogue restent ceux de la dernière génération locale ; personne n'a refait la reconstruction indépendante.
- L'activation par projet n'existe pas.
