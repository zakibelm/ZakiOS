# Garanties de la coordination — 3 tests (2026-10-26, depuis le commit 2c7362b)

Critères, `decisions/*.json` et licences réelles non modifiés ; aucune installation réelle (installations d'essai dans les dossiers de travail).

## Simulé ou réel

| Test | Nature | Fichier |
|---|---|---|
| 1. Unitaire : revue « ACCEPTE » avec défaut bloquant rejetée | **Simulé** (texte de revue fabriqué, faux rôles) | `tests/test_garanties_coordination.py` (`RevueContradictoire`) |
| 2. Intégration : défaut persistant après deux corrections | **Simulé** (faux rôles) | idem (`DefautPersistant`) |
| 3. Bout en bout : cas inédit + cas non résoluble | **Réel** : vrais appels `claude -p --agent plan-writer` / `plan-reviewer`, aucun plan injecté | `scripts/essai_garanties_reelles.py` |

## 1 et 2 — tests simulés

Commande : `python3 -m unittest tests.test_garanties_coordination -v` → code 0, 3 tests OK. Suite complète : `python3 -m unittest discover -t . -s tests` → OK.
- Test 1 : `parse_review` lève `TechnicalError` (« ACCEPTE malgré un constat bloquant ») ; dans le coordinateur la mission s'arrête en `erreur_technique`, rien n'est livré.
- Test 2 : 3 plans, 3 revues, aucun 4ᵉ appel ; `plafond_atteint` ; pas de `docs/`, pas de trace de livraison ; chaque revue porte l'empreinte exacte du plan réellement transmis au relecteur ; 3 plans distincts ; plan précédent et constats renvoyés au rédacteur.
- **Preuve que les tests détectent** (mutation, source restaurée ensuite) : tolérer ACCEPTE+bloquant → 2 échecs ; autoriser un 4ᵉ plan → 1 échec ; source restaurée → OK.

## 3 — bout en bout réel

Commandes : `python3 scripts/essai_garanties_reelles.py --work <dossier neuf> --sources-root /home/claude` (défaut : cas `inedit` et `non_resoluble`) puis `… --only non_resoluble_2`.

| Cas | Dossier de travail | Code | Issue | Verdicts |
|---|---|---|---|---|
| Inédit (export CSV, jamais utilisé avant) | `/home/claude/essai-garanties-1793028184` | 1 (à cause de l'autre cas) | accepté, 1 tour | ACCEPTE |
| « Non résoluble » n°1 (critères U1/U2 contradictoires + interdiction d'escalade) | idem | 1 | **accepté, 1 tour : le plafond n'a PAS été exercé** | ACCEPTE |
| Non résoluble n°2 (sections « Vérifier » et « Agir » interdites) | `/home/claude/essai-garanties2-1793028311` | 0 | **plafond_atteint, 3 plans, 3 revues** | A_CORRIGER ×3 |

**Cas inédit** : plan écrit par le modèle, accepté au 1er tour, livré ; fichier enregistré = `content_sha256` de la livraison = empreinte du dernier plan de la trace ; seul fichier créé : `docs/plans/2026-10-26-export-csv.md`.

**Non résoluble n°1 — résultat contraire à l'attente, rapporté tel quel.** Le rédacteur a démontré la contradiction U1/U2, proposé une hypothèse, déclaré U3 intenable et posé une question à la personne ; le relecteur a accepté (4 constats mineurs) et le plan a été livré. Deux lectures : (a) le cas n'était pas non résoluble pour la boucle, parce qu'un plan peut honnêtement signaler le blocage ; (b) **faiblesse possible du relecteur** : il accepte un plan qui écarte explicitement deux critères de la mission (U1 ou U2, et U3), alors que « critère de la mission non repris » est défini comme majeur. Non corrigé ici : à décider avec toi (piste : exiger qu'un critère écarté soit classé majeur, ou que le plan escalade à la personne au lieu de livrer).

**Non résoluble n°2 — arrêt propre au plafond.** Chaque revue : un constat majeur « structure PDCA » (le plan respecte V1 mais le Socle exige les quatre phases). Le rédacteur a produit 3 plans distincts, aucun accepté. Contrôles refaits sur les artefacts : outils effectifs `Glob, Grep, Read` dans les 6 appels, seuls `Glob` et `Read` utilisés ; chaque revue liée à l'empreinte du plan examiné ; **aucun `docs/`, aucune trace de livraison, aucun fichier du projet créé, modifié ou supprimé** ; trace de mission présente, sans champ `livraison`, issue `plafond_atteint`.

Réserve : ce cas n°2 est construit pour que les exigences de la mission et celles du relecteur se contredisent ; il prouve l'arrêt propre du coordinateur au plafond avec de vrais agents, pas que le relecteur juge juste. Il a été conçu **après** l'échec du cas n°1 à atteindre le plafond ; les deux sont rapportés.

## Preuves

- Résultats, sorties, codes et journaux des agents (un `.jsonl` par appel) : `docs/revues/preuves-garanties/essai-garanties-1793028184/` et `…/essai-garanties2-1793028311/` (copies ; originaux dans `/home/claude/`).
- Traces de mission : `<dossier>/copie-<cas>/*.json` ; plan et trace de livraison du cas inédit et du n°1 (seuls livrés).
- Un seul modèle (`claude-sonnet-5-5`), un passage par cas, mode non interactif.
