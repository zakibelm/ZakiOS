# Essai — CLARIFICATION_REQUISE et critères obligatoires abandonnés

Compte rendu des résultats **observés**. Ce document ne déclare pas la solution prête pour la production.

## 1. Identifiants testés
| Élément | Valeur |
|---|---|
| Référence de départ | 1b38847 |
| Code + tests + rôles (C2) | 64d7d18 ; épinglage de la source : 8c45301 (campagne C2 lancée à 8c45301) |
| plan-reviewer.md | sha256 67149be0c72cb593e3c4f52a91bb3afab36aded36a6dae7c138a7b868c7b0f1f |
| plan-writer.md | 0d97e4816a4e01cbf9956029edfcad6b5287937fb6c7b7764890d60dc0fe1d47 |
| zakios/mission.py | b46866071d0e833971e5687c7cd17b2aa8af6b4b2e979683ed651884fdaa4011 |
| essai_coordination.py | 2031b6b99e645044f2bb16ee9b64f91cb786485bbfa4524da661329e5604734c |
| essai_garanties_reelles.py | 9563c051b51567be1604b7d02b86c84ce097b1fdbf9d5964362a5ac0a25fa418 |
Les empreintes ont été revérifiées identiques après C2 (`sha256sum -c`) : rien n'a été modifié pendant la campagne. Modèle : claude-sonnet-5-5 ; claude 2.1.310.

## 2. Trois campagnes, séparées
- **Avant** (fe16781, `preuves-clarification/avant/`) : contradictoire_2 (K1/K2) ACCEPTÉ et livré ; le plan abandonnait un critère.
- **C1** (b78dd67, `preuves-clarification/campagne-C1/`) — intermédiaire, antérieure à la spécification complète. Échecs conservés :
  - `temoin_resoluble` → clarification_requise (attendu accepte). Cause : le **cas** était défectueux (le code traite `discount` en fraction 0‑1 ; « pourcentage 0‑100 » et un test à 100 étaient insatisfaisables sans modifier le code). Le relecteur avait raison.
  - `non_resoluble_2` → clarification_requise (attendu plafond). Cause : le **cas** contredisait le Socle PDCA ; il reste valable comme preuve de clarification sans livraison, pas de plafond.
  - Coordination, passage 1, cas B : **échec d'exécution** (erreur technique) — le relecteur a inséré la ligne `ZAKIOS-SOCLE v1 · PDCA` dans son bloc, refusée deux fois par le contrôle strict. Aucune livraison incorrecte, mais l'échec est comptabilisé.
  - Les cas ont été corrigés sous de nouveaux noms (`temoin_resoluble_2`) ; `non_resoluble_2` retiré de la liste par défaut.
- **C2** (campagne finale, rôles/coordinateur/critères/cas figés) : ci‑dessous.

## 3. Commandes et codes de sortie (C2)
- `python3 -B scripts/essai_coordination.py --work <dir> --sources-root /home/claude --passes 3 --natural` → **0**
- `python3 -B scripts/essai_garanties_reelles.py --work <dir> --sources-root /home/claude --passes 3` → **1** (une attente non satisfaite, §5)
- `python3 -B scripts/audit_artefacts.py <dir>` : coordination → **0** (aucune divergence) ; garanties → **1** (1 divergence)
- `python3 -B -m unittest discover -t . -s tests` → 0, **182 tests OK** (relancé en clôture, observé)
- `python3 -B scripts/verifier_mutations.py` → 0 : base OK, **10 mutations sur 10 détectées**, restauration OK, sans cache (-B). Dont : acceptation incohérente, livraison après clarification, plafond de corrections.
- `python3 -B -m zakios verify` → catalogue valide (3333 composants).

## 4. Résultats par scénario et passage
### Coordination (plan 1 **injecté** pour A, B, M4, témoin ; **produit par le modèle** pour naturel)
| Scénario | p1 | p2 | p3 |
|---|---|---|---|
| A (C3 oublié) | A_CORRIGER → ACCEPTE (2 tours) | idem | idem |
| B (invérifiable) | idem | idem | idem |
| M4 (Vérifier absent) | idem | idem | idem |
| Témoin complet | ACCEPTE (1 tour) | idem | idem |
| Naturel (modèle) | ACCEPTE (1 tour) | — | — |
Les corrections (plan 2) sont produites par le modèle ; une seule correction a suffi chaque fois (plafond de 2 non atteint). Audit : 13 missions, 32 appels réels, 22 liens revue→plan, 13 livraisons vérifiées (plan accepté = aperçu = fichier = trace), aucune divergence.

### Garanties (plans **produits par le modèle**, 3 passages, sessions neuves)
| Cas | Attendu | p1 | p2 | p3 |
|---|---|---|---|---|
| non_resoluble (U1/U2/U3, contradiction) | clarification, sans livraison | OK | OK | OK |
| temoin_resoluble_2 | accepte + livraison | OK | OK | OK |
| omission_corrigeable | accepte après correction | accepté au tour 1 | idem | idem |
| contradiction_inedite (T1/T2) | clarification | OK | OK | OK |
| information_manquante (M1) | clarification ciblée M1 | OK | OK | **attente non satisfaite** (script) |
- **omission_corrigeable : NON EXERCÉ ×3** — le modèle n'a pas commis l'omission au premier jet ; la boucle de correction n'est donc pas démontrée sur ce cas inédit (elle l'est sur A/B/M4, plans injectés).
- Clarifications : 9/9 ciblent le bon critère, posent une question précise, aucun plan écrit, aucune livraison, projet inchangé.

## 5. Échec observé en C2 : information_manquante / passage 3
Le script annonce « appels après la clarification » (2 appels relecteur pour 1 tour). L'examen des journaux montre : le **premier** avis du relecteur était hors contrat (couverture nommée `C1/C2` au lieu de `M1/M2`), refusé par le contrôle strict ; une relance technique (prévue, bornée à 1) a donné un avis valide (CLARIFICATION_REQUISE sur M1) ; **aucun appel après la clarification**, aucune livraison. Deux constats distincts :
1. L'exécution n'a pas réussi du premier coup : le relecteur peut encore sortir des identifiants incorrects (variance du modèle). Comptabilisé comme échec de la passe, non masqué.
2. **Défaut de traçabilité** : la tentative refusée puis relancée n'apparaît pas dans `erreurs_techniques` de la trace (seul le compteur `relances_relecteur` et le nombre d'appels l'indiquent). L'audit indépendant l'a trouvé seul (« revue réelle invalide sans erreur technique tracée »).
Le contrôle du script (appels = tours) ignore aussi les relances techniques légitimes : défaut du script, pas du coordinateur. Aucune correction n'a été faite pendant C2.

## 6. Simulé, injecté, réel
- **Simulé** (182 tests, rôles factices) : verdicts et refus de formats, liaison à l'empreinte, plafond exactement 3 plans/3 revues sans livraison, clarification au tour 1 et après correction, livraison unique, erreur technique sans livraison, fichiers préexistants identiques, traces distinctes.
- **Injecté** (vrais agents, plan 1 imposé) : A, B, M4, témoin.
- **Réel** (plan 1 du modèle) : naturel et les 5 cas de garanties.
- **Plafond en réel** : la preuve réelle date de l'ancienne version (essai-garanties.md). Sur C2, la non‑régression du plafond repose **uniquement** sur les tests simulés et la mutation `plafond_de_corrections`.

## 7. Limites et défauts restants
- Couverture sémantique = jugement du relecteur, pas une garantie technique ; deux défauts de cas (C1) montrent que les fixtures doivent être vérifiées avant campagne.
- Variance du relecteur : erreurs de format (C1 B/p1 ; C2 information_manquante/p3). Les relances et le refus strict évitent toute livraison incorrecte mais coûtent des appels et des échecs.
- Trace : tentative technique réussie après relance non détaillée (voir §5).
- Script de garanties : contrôle « appels = tours » trop strict.
- omission_corrigeable non exercé en réel ; plafond non rejoué en réel.
- Échantillon : n=3 par cas, n=1 pour naturel, un seul modèle, projets jetables minuscules.
- Corrections à décider après lecture de ce rapport ; toute correction implique une campagne C3 identifiée.

## 8. Preuves
`docs/revues/preuves-clarification/{avant,campagne-C1,campagne-C2}/` : resultats.json, .out, .exit, journaux d'agents (outils effectifs Read/Glob/Grep), traces de mission, livrables, `audit-*.json|txt` ; `mutations.json|txt`.

## 9. Jalon suivant (préparé, non implémenté)
Connecter l'interface au moteur pour un pilote supervisé : affichage distinct des trois verdicts, aucune livraison sur clarification (question affichée à la personne). À n'engager qu'après décision sur les défauts du §7.
