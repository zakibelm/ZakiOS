# Essai du jalon de coordination — compte rendu (mesuré, non acquis)

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
