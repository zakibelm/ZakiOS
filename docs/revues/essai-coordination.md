# Essai du jalon de coordination — compte rendu (mesuré, non acquis)

## Essai définitif du 2026-10-26 (appels réels à `claude` 2.1.310, modèle `claude-sonnet-5-5`)

Commit testé : `5c19e0e` (script et plans de test inchangés depuis `dc82281` ; rôle `plan-reviewer` révisé deux fois, voir plus bas). Source épinglée dans `sources.json` : même commit. `decisions/*.json` non modifiés (vides, comme avant). Aucune installation réelle ; installation d'essai uniquement dans le dossier de travail.

**Appels réels, pas de simulation de modèle.** Les 32 appels d'agents de l'essai définitif (27 pour A/B/M4, 1 par témoin, 2 pour le naturel) sont de vrais appels `claude -p --agent …` ; leurs journaux sont dans `docs/revues/preuves-essai-coordination-final/journaux-agents/`. Les plans v1 de A, B, M4 et du témoin sont **injectés** (fichiers de test, comptés comme « injecté » dans les appels), et ne sont pas écrits par le modèle. Les tests simulés (faux rôles) sont uniquement `tests/test_mission.py`.

| Étape | Commande | Code | Dossier |
|---|---|---|---|
| Rodage 1 (`7f83943`) | `python3 scripts/essai_coordination.py --work … --passes 1` | 1 (témoin refusé au 1er tour) | `/home/claude/essai-coord-rodage-1793025036` |
| Rodage 2 (`6969cc2`) | idem | 1 (M4 accepté à tort) | `/home/claude/essai-coord-rodage2-1793025419` |
| Rodage 3 (`5c19e0e`) | idem | 0 | `/home/claude/essai-coord-rodage3-1793025688` |
| **Définitif** (`5c19e0e`) | `python3 scripts/essai_coordination.py --work /home/claude/essai-coord-final-1793025912 --sources-root /home/claude --passes 3 --natural` | **0** | résultats : `/home/claude/essai-coord-final-1793025912/resultats.json` (copie dans `docs/revues/preuves-essai-coordination-final/`) |

### Deux défauts du rôle trouvés au rodage et corrigés (aucun critère assoupli)

1. **Gravités floues** (rodage 1) : le témoin était refusé pour un « majeur » portant sur un cas supplémentaire souhaitable. Correction : définitions strictes de `bloquant` / `majeur` / `mineur` dans `plan-reviewer.md` (`6969cc2`).
2. **Structure PDCA non contrôlée** (rodage 2) : avec ces définitions, un plan sans section « Vérifier » mais avec des tests dans « Exécuter » était accepté. Correction : contrôle explicite des quatre phases, phase absente = majeur (`5c19e0e`).
Les critères, les plans de test et le script n'ont pas été modifiés pour obtenir le résultat. **Réserve** : le rôle a été ajusté à partir de ces échecs, puis évalué sur les mêmes scénarios ; les scénarios A/B/M4/témoin ne sont donc plus un test indépendant de ces deux règles.

### Résultats par passage — scénarios injectés (défaut certain)

| Scénario | P1 | P2 | P3 |
|---|---|---|---|
| A — C3 oublié | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE |
| B — vérification invérifiable | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE |
| M4 — section « Vérifier » absente | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE |
| Témoin — plan complet | ACCEPTE (1 tour) | ACCEPTE (1 tour) | ACCEPTE (1 tour) |

Chaque défaut injecté : verdict A_CORRIGER au 1er tour avec un constat « majeur » ; toutes les missions corrigées en 2 tours (plafond : 2 corrections, 3 plans).

### Scénario naturel (rapporté, non exigé) — 1 seul passage

Le modèle a écrit lui-même v1 : ACCEPTE au 1er tour (4 constats mineurs), aucune correction. Aucun écart naturel observé ; cela ne prouve rien sur la détection d'écarts naturels (n = 1).

### Contrôles indépendants du verdict du script (refaits sur les artefacts, 13 missions)

- Outils effectifs de `plan-writer` et `plan-reviewer` : `Glob, Grep, Read` dans les 32 appels réels ; aucun outil modifiant utilisé.
- Chaque revue porte `plan_examine_sha256` = `plan_sha256` du plan examiné (tous les tours).
- Plan accepté, aperçu et enregistré : `content_sha256` de la livraison = empreinte du fichier enregistré ; `delivery_sha256` de la trace de mission = celui de la livraison ; trace de livraison contenant l'identifiant de mission ; exactement un plan par mission acceptée ; dernière revue = ACCEPTE.
- Aucun fichier du projet modifié ou supprimé ; seuls le plan et `.zakios/` sont ajoutés.
- Plafond respecté (max. 2 tours observés).

### Ce que l'essai n'a PAS exercé en réel

- **Plafond atteint / erreur technique** : aucune mission réelle n'a atteint le plafond ni échoué techniquement. « Rien n'est enregistré après un échec ou un plafond » est prouvé par `tests/test_mission.py` (faux rôles), **pas** par un appel réel.
- Un seul modèle, 3 passages, 1 passage naturel, mode non interactif, défauts injectés ; le relecteur a été ajusté après échec (réserve ci-dessus) ; `plan-reviewer` n'est pas validé par un humain ; pas de délégation libre entre agents.

### Conclusion

Les preuves de l'essai réel permettent de dire : **sur ces scénarios et ce modèle, la boucle plan → revue indépendante → correction → livraison contrôlée fonctionne, avec outils restreints et traçabilité vérifiée**. Elles ne permettent pas de dire que toute omission est détectée, ni que la boucle tient hors de ces cas ou avec un autre modèle. Jalon : démontré dans ce périmètre étroit, non généralisé.

---

# Historique : essai précédent (même jour, avant révision du rôle)


Script : `scripts/essai_coordination.py` (3 passages ; modèle `claude-sonnet-5-5`, mode non interactif, un seul modèle). Preuves : `docs/revues/preuves-essai-coordination/` (résultats, traces de mission, traces de livraison, plans enregistrés). Les décisions et licences de l'essai sont **fictives** (propres au dossier de travail) ; rien n'est enregistré dans `decisions/*.json`.

## Résultat par passage (verdicts successifs de la revue)

| Scénario | Passage 1 | Passage 2 | Passage 3 |
|---|---|---|---|
| A — critère C3 oublié (v1 injecté) | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE |
| B — vérification invérifiable (v1 injecté) | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE |
| M4 — section « Vérifier » supprimée | A_CORRIGER → ACCEPTE | A_CORRIGER → ACCEPTE | A_CORRIGER ×2 → ACCEPTE (3 tours) |
| Témoin — plan complet | **A_CORRIGER → ACCEPTE (faux positif)** | ACCEPTE dès le 1er tour | ACCEPTE dès le 1er tour |
| Naturel — le modèle écrit v1 seul | ACCEPTE (1 tour, rapporté, non exigé) | — | — |

## Critères d'acceptation

| # | Critère | Résultat |
|---|---|---|
| 1 | Identité de mission | Satisfait sur les 13 missions. |
| 2 | Outils `Read, Glob, Grep` à l'initialisation, aucun outil modifiant, aucun fichier changé hors plan enregistré | Satisfait sur tous les appels réels. |
| 3 | Détection (A : constat sur C3 ; B : constat sur la vérification ; témoin accepté au 1er tour) | A, B, M4 satisfaits 3/3. **Témoin : 2/3 — critère non satisfait.** |
| 4 | Correction en 2 itérations au plus | Satisfait 9/9 (M4 passage 3 : 3 plans, dans le plafond). |
| 5 | Livraison seulement après ACCEPTE, aperçu = enregistrement, second enregistrement `deja_enregistre` | Satisfait. |
| 6 | Trace de mission (revue liée à l'empreinte du plan examiné, composants, livraison) | Satisfait ; le rejet d'une trace différente est prouvé par les tests sans modèle. |
| 7 | Revue falsifiée rejetée | Satisfait (test déterministe) ; M4 jamais accepté en v1. |
| 8 | Résultats par passage | Ci-dessus, sans moyenne. |

**Le script sort en échec (code 1) : un critère sur huit n'est pas satisfait.** Ce n'est pas masqué.

## Faux positif du témoin (passage 1)

Même plan, trois revues : une a refusé (2 constats majeurs), deux ont accepté. Les constats refusés sont argumentés (la non-régression C3 n'est vérifiée qu'avec une remise nulle ; `read_user()` n'a pas de test hors injection). Ils ne sont pas absurdes, mais le plan satisfait la lettre des critères.

- **Problème** : le relecteur est plus strict qu'attendu et variable d'un appel à l'autre sur un même plan ; un seuil « majeur » élevé coûte une itération inutile.
- **Action possible (non faite)** : ajouter au rôle une règle explicite « un constat majeur doit se rattacher à un critère de la mission non couvert ou à une vérification infaisable, pas à un cas supplémentaire souhaitable » ; puis refaire les 3 passages. Je ne l'ai pas introduite pour ne pas ajuster le relecteur afin d'obtenir 3/3 sur ce seul essai.
- **Bénéfice** : moins de faux refus, sans perdre A/B/M4 (à mesurer par un nouvel essai).

Note d'honnêteté sur les plans de test : un premier témoin était réellement défaillant (étape conditionnelle, renvoi à une mauvaise étape, référence relevée après la correction) ; le relecteur l'a refusé à bon droit, et j'ai corrigé le **plan**, pas le relecteur.

## Limites

Un seul modèle ; 3 passages ; défauts injectés, donc détection mesurée sur cas connus (pas de preuve que toute omission est détectée) ; essai naturel : un seul passage, sans écart ; mode non interactif ; la qualité du plan n'est pas jugée par des grilles ; `plan-reviewer` n'est pas validé par un humain (même revue que le lot 1 avant installation réelle) ; OpenRouter/OmniRoute, `run-tests` isolé et séparation par utilisateur restent hors de ce jalon.
