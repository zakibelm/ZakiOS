# Plan : correction du module de paiement (remise 0-100, SQL paramétré), version 2

## Planifier

**Situation initiale (faits, lus dans le dépôt)**
- `src/pay.py` contient `total(prices, discount)` : `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule le traite comme une fraction. Avec 100, le résultat est négatif.
- `read_user(db, name)` concatène `name` dans le SQL, donc la requête est injectable.
- Le dépôt ne contient aucun répertoire `tests/` et aucun appel de `total()` ou `read_user()` en dehors de leur définition (Grep sur tout le dépôt). Il n'y a donc pas de suite existante à comparer. Des appelants hors dépôt sont possibles, mais non vérifiables d'ici (hypothèse).
- Comportement d'origine de `total()` : le type retourné suit les opérandes. Avec des entiers, le résultat est un `int` (`total([10, 20], 0) == 30`). Il n'y a aucun rejet des valeurs hors 0-100.

**Résultat attendu**
- `total(prices, discount)` renvoie `sum(prices) * (100 - discount) / 100` pour `0 <= discount <= 100`.
- `read_user` utilise une requête paramétrée.
- Aucune régression mesurable sur les comportements que le code d'origine réalisait correctement.

**Décisions de conception (hypothèses à confirmer par la personne avant l'étape 4)**
- D1 — Type de retour : un `float` est accepté. `30 == 30.0` en Python, donc les comparaisons de valeur ne changent pas. Seuls un `isinstance(..., int)` ou un affichage dépendant du type de l'appelant changeraient. Si le type `int` doit être conservé, le dire : il faudra alors une autre implémentation (par exemple `Decimal` ou arrondi explicite).
- D2 — Hors bornes (`discount < 0` ou `> 100`) : lever `ValueError`. Ce comportement est nouveau, car l'origine acceptait tout. À confirmer. L'alternative est de ne pas rejeter et de documenter le comportement.
- H1 : la remise est un nombre de 0 à 100 (commentaire de `src/pay.py`, confirmé par lecture). Si la personne dit le contraire, le plan s'arrête.
- H2 : les prix sont des nombres Python (int ou float). Aucun appel dans le dépôt ne permet de le confirmer ; c'est une hypothèse.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`. Rien d'autre n'est modifié.
- Aucune dépendance externe : `unittest` et `sqlite3` de la bibliothèque standard.

**Critères d'acceptation (donnés par la mission)**
- C1 — remise correcte aux bornes 0 et 100.
- C2 — requête SQL paramétrée.
- C3 — aucune régression sur les appels existants.

## Exécuter
1. Relever l'état de référence. Relire `src/pay.py` et relancer `grep -rn "total(\|read_user(" .` pour confirmer qu'aucun appelant n'existe (déjà constaté). Noter la sortie de `python -m unittest discover tests` sur le code d'origine. Attendu : erreur car `tests/` n'existe pas, ce qui prouve qu'il n'y a pas de suite préexistante. C3 repose alors sur les tests de caractérisation de l'étape 2.
2. Créer les tests, sans toucher `src/` :
   - `tests/test_remise.py` : bornes `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`, valeur intermédiaire `total([10, 20], 50) == 15`, liste vide `total([], 50) == 0`, et cas hors bornes (`-1` et `101`) selon D2.
   - `tests/test_injection.py` : base sqlite en mémoire, table `users` avec `Alice` et `Bob`. Charges utiles : `' OR '1'='1`, `x'; DROP TABLE users; --`, et un nom contenant un guillemet double (`"`). Attendu : 0 ligne pour chaque charge ; `Alice` renvoie 1 ligne ; un nom avec apostrophe légitime (`O'Brien`, inséré au préalable) renvoie 1 ligne ; la table `users` existe toujours après les charges.
   - `tests/test_non_regression.py` (C3) : caractérise le comportement d'origine qui doit rester identique. `total([10, 20], 0) == 30`, `total([5], 0) == 5` et `read_user(db, 'Alice')` renvoie la même ligne qu'avant. Chaque valeur attendue est calculée à la main avant la correction, puis comparée à la sortie de l'ancien code à l'étape 3.
3. Lancer `python -m unittest discover tests -v` sur le code d'origine et conserver la sortie.
   - Attendu en échec : `test_remise` (bornes 100 et 50, hors bornes) et `test_injection` (chaque charge qui réussit l'injection).
   - Attendu en succès : `test_non_regression`, qui décrit le comportement à préserver.
   - Un test attendu en échec qui réussit déjà, ou un test de non-régression qui échoue sur le code d'origine, est traité dans « Agir ».
4. Après confirmation de D1 et D2 par la personne, corriger `total()` :
   ```python
   if not 0 <= discount <= 100:
       raise ValueError("discount doit être entre 0 et 100")
   return sum(prices) * (100 - discount) / 100
   ```
5. Corriger `read_user()` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
6. Relancer `python -m unittest discover tests -v` et conserver la sortie.

## Vérifier
- **C1** : `python -m unittest tests.test_remise`. Attendu : 0, 50 et 100 donnent 30, 15 et 0 ; les valeurs hors bornes lèvent `ValueError` (si D2 est confirmée). Le test de 100 a échoué à l'étape 3.
- **C2** : `python -m unittest tests.test_injection`. Attendu : les trois charges renvoient 0 ligne, `Alice` et `O'Brien` renvoient 1 ligne, la table `users` subsiste. Contrôle complémentaire : `grep -n "execute" src/pay.py` ne montre plus de concaténation (`+`) dans la requête.
- **C3** : `python -m unittest tests.test_non_regression`, puis la suite complète. Attendu : mêmes résultats avant et après pour les cas de caractérisation (sorties des étapes 3 et 6 comparées). Limite connue : la preuve couvre les cas testés et le dépôt, pas d'éventuels appelants externes. Le changement de type `int` vers `float` n'est mesuré que par valeur (D1). La non-régression reste non vérifiée tant que ces sorties n'existent pas.

## Agir
- **Écart sur un critère** : corriger le code concerné, puis relancer la vérification du critère touché et la suite complète.
- **Test attendu en échec qui réussit sur le code d'origine** (étape 3) : le test est invalide ou ne cible pas le défaut. Le revoir (charge utile, assertion, données) et le relancer sur le code d'origine jusqu'à ce qu'il échoue. Ne pas passer à l'étape 4 avant.
- **Test de non-régression qui échoue sur le code d'origine** : l'attendu calculé à la main est faux ou le comportement d'origine est déjà défectueux. Corriger le test ou le déclarer comme écart explicite à la personne.
- **Hypothèse contredite (H1, H2) ou D1 ou D2 refusée** : arrêter et rendre compte à la personne avant de poursuivre. Si une vérification échoue après deux corrections, arrêter et rendre compte.
- **Régression de type ou d'appelant externe signalée** : traiter comme écart de C3 et revoir D1.
- **Standardiser** : conserver les trois fichiers de tests comme garde-fou et lancer `python -m unittest discover tests` avant toute modification de `src/pay.py`. Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification.

**Exécution** : par la personne ou par un agent disposant des droits d'écriture, après réponse sur D1 et D2.
