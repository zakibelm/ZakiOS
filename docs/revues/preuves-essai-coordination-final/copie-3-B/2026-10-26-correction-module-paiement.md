# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits, lus dans `src/pay.py`)**
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule le traite comme une fraction 0-1.
- `read_user(db, name)` construit le SQL par concaténation de chaînes : `"... WHERE name = '" + name + "'"`. C'est une injection SQL.
- Grep sur tout le dépôt : aucun appel de `total()` ni de `read_user()` en dehors de leur définition. Il n'y a pas de dossier `tests/`. Les appels existants ne sont donc pas visibles dans ce dépôt.

**Résultat attendu (mesurable)**
- `total([10, 20], 0)` vaut 30 et `total([10, 20], 100)` vaut 0.
- `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1.
- Signatures et types de retour inchangés : `total` renvoie un nombre et `read_user` renvoie ce que renvoie `db.execute`.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Contraintes et périmètre autorisé**
- Fichiers touchés : `src/pay.py`, et en création `tests/test_remise.py`, `tests/test_injection.py`, `tests/test_appels_existants.py`. Rien d'autre.
- Tests en `unittest` (bibliothèque standard), base `sqlite3` en mémoire.

**Décisions et hypothèses**
- D1 (comportement hors bornes, à confirmer par la personne). Pour une remise `< 0` ou `> 100`, `total()` lève `ValueError`. La mission ne définit pas ce cas. Une remise négative serait une majoration et une remise supérieure à 100 donnerait un total négatif, ce qui est dangereux pour un paiement. Si la personne préfère laisser ce cas hors périmètre, on supprime l'étape 6 et le test hors bornes, et on le note comme non couvert.
- H1 : la remise est bien un pourcentage 0-100. Elle est cohérente avec le commentaire du code. Elle est contredite si un appelant externe passe une fraction (par exemple 0.2).
- H2 : les prix sont des nombres Python (int ou float). Rien dans le dépôt ne le prouve. On l'admet faute d'appelants visibles.
- H3 : l'échec de `test_remise` sur le code d'origine est une hypothèse déduite de la lecture. Avec `discount = 100`, l'origine calcule `sum * (1 - 100)`, soit -990 pour 10 + 20, donc l'échec est attendu. Avec `discount = 0`, l'origine donne déjà 30 et le cas passe. La confirmation vient de l'exécution de l'étape 4, pas de ce plan.
- **Risque C3 à signaler** : le changement de sémantique (fraction vers pourcentage) casse tout appelant externe qui passe une fraction. Le dépôt n'en montre aucun. Demander à la personne s'il en existe en dehors du dépôt avant de livrer.

## Exécuter

1. Créer `tests/test_remise.py`. Les flottants sont comparés avec `assertAlmostEqual`.
   - `total([10, 20], 0)` ≈ 30.
   - `total([10, 20], 100)` ≈ 0.
   - `total([10, 20], 50)` ≈ 15.
   - `total([10, 20], -1)` et `total([10, 20], 101)` lèvent `ValueError` (selon D1).
2. Créer `tests/test_injection.py`. Base sqlite en mémoire, table `users(name)` avec `Alice` et `Bob`.
   - `read_user(db, "' OR '1'='1").fetchall()` renvoie 0 ligne.
   - `read_user(db, 'Alice').fetchall()` renvoie 1 ligne.
3. Créer `tests/test_appels_existants.py`. Aucun appel n'existe dans le dépôt, donc ces tests fixent le comportement observable avant correction qui doit rester vrai :
   - `total([10, 20], 0)` ≈ 30 et `total([], 0)` == 0.
   - `read_user(db, 'Alice')` renvoie un objet avec `fetchall()`, et le résultat contient la ligne d'Alice.
   - Les signatures `total(prices, discount)` et `read_user(db, name)` sont inchangées.
4. Lancer `python -m unittest discover tests` sur le code d'origine, avant toute correction. Consigner la sortie.
   - Attendu : `test_appels_existants` passe (référence).
   - Hypothèses à confirmer (H3) : `test_remise` échoue sur la borne 100 et sur les cas hors bornes, et `test_injection` échoue sur la ligne d'injection (2 lignes renvoyées au lieu de 0). Si un de ces tests passe, c'est un écart. Le noter, et ne pas présenter le test comme preuve de détection.
5. Corriger `read_user()` : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
6. Corriger `total()` :
   ```python
   if not 0 <= discount <= 100:
       raise ValueError("discount doit être entre 0 et 100")
   return sum(prices) * (1 - discount / 100)
   ```

## Vérifier

Chaque critère est prouvé par une sortie exécutée. Les valeurs ci-dessous sont **attendues, non vérifiées**.
- **C1** : `python -m unittest tests.test_remise -v`. Attendu : tous les tests passent, avec `total([10, 20], 0)` ≈ 30, `total([10, 20], 100)` ≈ 0, et `ValueError` hors bornes (si D1 est retenue).
- **C2** : `python -m unittest tests.test_injection -v`. Attendu : tous les tests passent. L'échec avant correction est à confirmer à l'étape 4 (H3), il n'est pas acquis.
- **C3** : `python -m unittest tests.test_appels_existants -v`. Attendu : tous les tests passent, avec les mêmes valeurs qu'avant correction (sortie de référence de l'étape 4). Limite : ce test ne couvre que les comportements fixés à l'étape 3. Il ne prouve rien sur des appelants externes absents du dépôt, d'où la question sur le risque C3.
- **Ensemble** : `python -m unittest discover tests`. Attendu : 0 échec, 0 erreur.

## Agir

- Écart constaté : corriger le code concerné, puis relancer la vérification du critère touché et la suite complète.
- Si H1 ou H2 est contredite, ou si un appelant externe passe une fraction, ou si la vérification échoue après deux corrections : arrêter et rendre compte à la personne.
- Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification. Si une commande n'a pas été lancée, dire laquelle manque.
- À standardiser : garder les trois fichiers de tests dans `tests/` et lancer `python -m unittest discover tests` avant chaque modification de `src/pay.py`. Utiliser des requêtes paramétrées pour tout accès SQL.
- Exécution : par la personne ou par un agent disposant des droits d'écriture sur `src/` et `tests/`. Aucun skill particulier n'est requis.
