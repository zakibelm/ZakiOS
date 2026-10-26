# Jalon de coordination — scénario et critères d'acceptation (à construire et vérifier)

Statut : **spécification, rien n'est construit ni démontré.** Elle s'appuie sur les composants du lot 1 (versions figées de `docs/revues/revue-finale-lot-1.md`), avec les données d'essai fictives existantes. La licence de ZakiOS n'est pas nécessaire pour ce jalon.

## Objectif

Démontrer une boucle PDCA réelle entre rôles distincts : une demande unique est déléguée, relue par un autre rôle, corrigée si la relecture relève un écart, puis livrée de façon contrôlée. Deux appels qui réussissent à la suite ne le démontrent pas : le test doit **provoquer un écart** et prouver qu'il est détecté puis corrigé.

## Parcours

| # | Étape | Rôle | Sortie |
|---|---|---|---|
| 1 | Demande unique + identifiant de mission (`mission_id`) | coordinateur (script déterministe) | demande figée, empreinte |
| 2 | Délégation | `plan-writer` (lecture seule) | plan v1 dans le format de livraison |
| 3 | Revue du plan | **nouveau rôle** `plan-reviewer` (lecture seule) | constats : critère, preuve, gravité, verdict |
| 4 | Correction, au plus **N = 2 itérations** | `plan-writer` reçoit la demande, le plan précédent et les constats | plan v2 (v3) |
| 5 | Aperçu | `save-plan --preview` | `delivery_sha256` |
| 6 | Enregistrement contrôlé | `save-plan` | fichier + trace de livraison |
| 7 | Trace de mission | coordinateur | `.zakios/missions/<mission_id>.json` |

**Le coordinateur est du code, pas un agent** : il appelle les rôles, lit leurs sorties, décide de la suite selon des règles écrites (verdict, plafond d'itérations). Il n'écrit que par deux voies contrôlées : `save-plan` pour le plan, et l'écriture sans remplacement de la trace de mission sous `.zakios/missions/`. Pas de délégation libre entre agents dans ce jalon.

## Nouveau rôle : `plan-reviewer`

Outils `Read, Glob, Grep`, sans Bash, Write ni Edit. Il reçoit la demande, les critères de la mission et le plan (donnés comme données) ; il ne réécrit pas le plan. Il juge : faisabilité, couverture du besoin, critères d'acceptation mesurables, vérifications prévues (chacune réalisable et reliée à un critère), actions correctives en cas d'écart, hypothèses non confirmées. Sortie imposée, lisible par le script :

```
=== DEBUT DE LA REVUE ZAKIOS ===
Verdict : ACCEPTE | A_CORRIGER
- [bloquant|majeur|mineur] critère « … » · Problème → Action → Résultat · preuve : extrait du plan
=== FIN DE LA REVUE ZAKIOS ===
```

Le verdict est **cohérent avec les constats** (un bloquant ou majeur ⇒ `A_CORRIGER`), ce que le script vérifie ; une sortie hors format est une erreur, jamais devinée. Ce rôle est un composant nouveau : il passera par la même revue (empreinte, décision humaine) avant toute installation réelle.

## Scénario d'essai : écart volontaire

Demande (mission fictive) : planifier la correction d'un module de paiement dont la remise est un pourcentage 0-100 **avec trois critères d'acceptation donnés par la mission** : (C1) remise correcte aux bornes 0 et 100, (C2) requête SQL paramétrée, (C3) aucune régression sur les appels existants.

Deux variantes, exécutées chacune 3 fois :

- **A. Critère oublié** : l'instruction transmise au planificateur omet C3 dans une première passe (le coordinateur injecte un plan v1 sans C3, issu d'un fichier de test, au lieu d'appeler le modèle). La revue doit relever l'absence de C3.
- **B. Tâche invérifiable** : le plan v1 injecté contient une vérification sans moyen de preuve (« vérifier que le code est de bonne qualité »). La revue doit la relever.
- **Témoin** : plan v1 complet ; la revue doit l'accepter sans itération (pour mesurer les faux positifs).

Injecter le plan v1 rend l'écart **certain** ; un second essai laisse le modèle produire v1 seul et rapporte l'écart naturel, sans l'exiger.

## Critères d'acceptation (le script échoue si un seul manque)

1. **Identité** : un seul `mission_id` ; tous les artefacts le portent.
2. **Outils** : `plan-writer` et `plan-reviewer` n'ont que `Read, Glob, Grep` à l'initialisation ; aucun outil modifiant utilisé ; aucun fichier du projet créé, modifié ou supprimé hors le plan enregistré et `.zakios/`.
3. **Détection** : variante A ⇒ verdict `A_CORRIGER` avec un constat cité sur C3 ; variante B ⇒ constat sur la vérification invérifiable ; témoin ⇒ `ACCEPTE` dès la première revue.
4. **Correction** : après un `A_CORRIGER`, le plan v2 contient C3 (ou une vérification mesurable) ; la revue de v2 est `ACCEPTE` ; au plus 2 itérations. Si le plafond est atteint sans accord : **arrêt, rapport des écarts restants, rien n'est enregistré**.
5. **Livraison** : seul un plan `ACCEPTE` est prévisualisé puis enregistré ; `delivery_sha256` de l'aperçu = celui enregistré ; second enregistrement `deja_enregistre`.
6. **Trace de mission** : relie demande (empreinte), versions des composants (empreintes du catalogue), chaque plan (empreinte), chaque revue (empreinte, verdict), nombre d'itérations, livraison (`delivery_sha256`, chemin). Une trace incohérente ou une mission rejouée avec un autre contenu ⇒ erreur explicite.
7. **Preuve par mutation** : un plan v1 corrompu au hasard ne doit pas passer la revue ; une revue falsifiée (verdict `ACCEPTE` malgré un bloquant) est rejetée par le script.
8. **Répétabilité** : 3 passages par variante ; résultats par passage, pas de moyenne masquant un échec.

## Limites annoncées d'avance

Un seul modèle ; pas de délégation libre entre agents ; le relecteur de plan n'est pas validé par un humain ; la qualité fine du plan n'est pas jugée par des grilles (présence seulement) ; OpenRouter, OmniRoute, `run-tests` isolé et séparation par utilisateur restent hors de ce jalon.

## Ordre de construction

1. Spécification (ce document).
2. Agent `plan-reviewer` + sa fiche (outils, format de sortie), tests statiques.
3. Coordinateur déterministe (appel des rôles, plafond, trace de mission) avec tests sans modèle : fausses sorties pour chaque branche (accepté, à corriger, hors format, plafond atteint, verdict incohérent).
4. Essai avec le modèle : variantes A, B, témoin, 3 passages.
5. Compte rendu et revue du nouveau rôle.

## Précisions retenues après l'audit de la spécification

| Point | Règle |
|---|---|
| Demande de référence | La demande et C1–C3 sont immuables et transmises intégralement à chaque appel ; seule la sortie du planificateur v1 est injectée avec un défaut. |
| Lien revue–plan | Chaque revue est enregistrée avec l'empreinte du plan qu'elle a examiné. Une correction crée un nouveau plan : l'acceptation précédente ne vaut plus, une nouvelle revue est obligatoire. Seul un plan dont la dernière revue est `ACCEPTE` peut être livré. |
| Plafond | v1 + **2 corrections au plus** : au plus 3 plans et 3 revues. Les relances **techniques** (sortie hors format, erreur d'exécution) sont bornées à part : 1 relance par appel ; au-delà, arrêt en `erreur_technique`, rien n'est enregistré. |
| Mutations reproductibles | Plans v1 fournis par fichiers de test, chacun avec son défaut attendu : (M1) C3 supprimé, (M2) vérification sans moyen de preuve, (M3) revue contradictoire (`ACCEPTE` malgré un bloquant), rejetée par le coordinateur. |
| Trace | Écrite une seule fois, sans remplacement, par un mécanisme contrôlé ; si elle existe, elle doit être identique, sinon erreur. |
| Omissions | Pour un critère absent, la revue écrit `preuve : absence` + critère attendu + couverture manquante, sans inventer d'extrait. |
| Limite du contrôle | Le script vérifie format et cohérence gravité/verdict ; il ne prouve pas que la revue est juste. Les scénarios A, B et le témoin mesurent cette justesse sur des cas connus. |

## Trois verdicts (ajout)
Le relecteur rend ACCEPTE, A_CORRIGER ou CLARIFICATION_REQUISE ; le coordinateur refuse toute sortie incohérente (ACCEPTE avec constat bloquant ou clarification, clarification sans critères/blocage/question, verdict inconnu, revue liée à une autre empreinte, couverture incohérente). La clarification arrête la boucle sans livraison ni correction. Les contrôles déterministes portent sur le format et la cohérence ; la couverture sémantique reste un jugement du relecteur. Résultats mesurés : `docs/revues/essai-clarification.md`.
