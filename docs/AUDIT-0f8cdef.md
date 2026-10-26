# Sixième audit externe (commit 0f8cdef)

L'audit a confirmé les 102 tests, la CI et le confinement, puis reproduit un défaut d'ordre dans la reprise : validation préalable, puis verrou, puis récupération. Avec des fichiers déjà écrits, un journal `started` et l'ancien état d'installation, la validation refusait ces fichiers comme « non gérés » avant que la récupération s'exécute.

| Défaut | Correction (0.5.2) | Test |
|---|---|---|
| Récupération appelée après une validation qui la rendait inutile | détection sans écriture d'un journal `started` ; si présent : verrou, reprise sécurisée, puis plan normal ; sinon validation préalable sans écriture | `test_same_selection_resumes_after_interruption_with_old_install_state` |
| Conflit pendant la reprise | installation bloquée avec message clair, journal `conflict`, sauvegardes conservées | `test_same_selection_after_interruption_and_user_edit_is_blocked_with_backups_kept` |
| Preuve limitée à des exceptions rattrapables | sous-processus réellement tué par SIGKILL au milieu de l'installation, puis `apply` : reprise, installation complète, état stable | `test_process_killed_for_real_is_recovered_by_the_next_apply`, `test_process_killed_for_real_then_user_edit_is_blocked` |
| Interruption invisible dans l'aperçu | `plan` note « Installation interrompue détectée » | même premier test |

Les deux premiers tests échouent sur le commit 0f8cdef.

## Limites restantes

Celles de `docs/ACTIVATION.md`. Toujours aucun composant réel validé : la prochaine étape est la revue d'un petit lot réel sur un projet jetable.
