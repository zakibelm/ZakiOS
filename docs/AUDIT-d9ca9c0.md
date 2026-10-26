# Cinquième audit externe (commit d9ca9c0)

L'audit a confirmé les 94 tests et les CI, puis reproduit trois scénarios qui violaient la promesse « aucune perte de fichier utilisateur et aucune écriture hors projet ». Chacun a maintenant un test qui échoue sur l'ancien code.

| Scénario | Correction (0.5.1) | Test |
|---|---|---|
| Fichier retiré par ZakiOS, recréé par l'utilisateur, puis `rollback` : le fichier de l'utilisateur était écrasé | avant toute restauration, l'emplacement doit être libre (ou contenir exactement l'ancien contenu) ; sinon conflit, sauvegardes conservées | `test_rollback_never_overwrites_a_file_recreated_by_the_user` |
| Dossier parent remplacé par un lien symbolique : le retrait supprimait un fichier extérieur | opérations par descripteurs de dossier sans suivre les liens ; plan et exécution refusent | `test_parent_replaced_by_symlink_never_deletes_outside_files` |
| `.zakios` pointant hors du projet : `project.lock` créé à l'extérieur, même pour un refus | état, journal, verrou et sauvegardes passent par le même accès confiné ; refus avant toute création | `test_state_directory_outside_the_project_is_refused_and_nothing_is_written_there`, `test_refused_apply_creates_no_state_directory_or_lock` |
| Reprise après interruption sans contrôle des modifications utilisateur | même comparaison que le retour arrière ; conflit signalé, sauvegardes gardées | `test_recovery_after_interruption_keeps_user_edits_made_in_between` |
| Vérification de chemin périmée entre l'aperçu et l'écriture | `O_NOFOLLOW` à chaque composant ; création sans écrasement (`link`) | `test_file_created_by_the_user_after_the_preview_is_never_overwritten`, `test_destination_parent_symlink_blocks_creation`, `test_unsafe_names_in_a_destination_are_never_followed` |

## Précision sur les garanties

`plan` n'écrit rien. `apply` valide d'abord sans écrire ; un refus évident ne laisse ni dossier d'état ni verrou. Seul un refus apparu sous verrou peut les laisser (annoncé dans `docs/ACTIVATION.md`).

## Limites restantes

Voir `docs/ACTIVATION.md` : projet racine suivi une fois s'il est un lien, fenêtre de quelques millisecondes pour l'annulation d'une mise à jour, Linux seulement. Toujours aucun composant réel validé.
