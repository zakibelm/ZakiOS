# Plan : correction du module de paiement (remise 0-100, SQL paramétré, sans régression)

## Planifier

**Situation initiale (faits lus dans `src/pay.py`, 6 lignes)**
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit « pourcentage 0-100 », mais le code traite `discount` comme une fraction 0-1. Le commentaire et le code se contredisent. Avec `discount=100`, le résultat est `-99 * sum(prices)`.
- `read_user(db, name)` construit la requête par concaténation de chaînes, donc elle est vulnérable à l'injection SQL.
- Un Grep sur tout le dépôt ne trouve que ces deux fonctions. Il n'y a aucun appelant dans `src/`, aucun répertoire `tests/` et aucun autre `execute(` ni requête SQL. C'est un fait observé le 2026-10-26. L'étape 1 le revérifie avant toute modification.

**Résultat attendu (mesurable)**
- `total()` applique une remise en pourcentage de 0 à 100.
- `read_user()` n'utilise que des paramètres liés.
- Le comportement des appels valides existants est conservé, sauf le défaut corrigé.

**Hypothèses (à confirmer, non prouvées)**
- H1 : l'intention est un pourcentage de 0 à 100. Source : le commentaire et la mission. Le code contredit le commentaire, donc le comportement actuel prouve seulement qu'il est faux. La confirmation vient de la mission (donnée par la personne) et des appels relevés à l'étape 1. Si un appelant passe une fraction 0-1, arrêter et poser la question à la personne.
- H2 : les prix sont des `int` ou des `float`. Comme les `float` sont possibles, les tests utilisent `assertAlmostEqual`.
- H3 : `db` est une connexion ou un curseur compatible `sqlite3` avec le style `?`. Si le pilote réel est autre (par exemple `%s`), adapter le marqueur et le dire à la personne.

**Décision sur les valeurs hors bornes (à confirmer par la personne)**
- Proposition : `total()` lève `ValueError` si `discount < 0` ou `discount > 100`. Les bornes 0 et 100 sont acceptées.
- Raison : une remise hors bornes donnerait un total supérieur à la somme ou négatif, et ce silence serait un risque dans un module de paiement.
- Si la personne préfère accepter ces valeurs, supprimer le contrôle et le test hors bornes.
- Conséquence pour C3 : le rejet change le comportement pour les appels hors bornes. Aucun appelant n'existe dans le dépôt, et ce changement est signalé à la personne.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers `tests/test_remise.py`, `tests/test_injection.py` et `tests/test_regression.py`.
- Aucune autre modification.
- Bibliothèque standard uniquement (`unittest`, `sqlite3`).
- La signature des fonctions reste inchangée.

**Critères d'acceptation**
- C1 : la remise est correcte aux bornes 0 et 100, à une valeur intermédiaire, sur une liste vide, et le comportement hors bornes est explicite et testé.
- C2 : toutes les requêtes SQL de `src/pay.py` sont paramétrées et résistent à plusieurs chaînes d'injection.
- C3 : aucune régression sur les appels existants. La suite complète passe après correction, et les sorties des appels valides sont identiques avant et après, hors le défaut corrigé.

## Exécuter

1. **Relevé (lecture seule)**
   - Read `src/pay.py`.
   - Grep `total\(|read_user\(` sur tout le dépôt, en incluant `tests/` et les scripts.
   - Grep `execute\(|SELECT|INSERT|UPDATE|DELETE` pour relever toutes les requêtes SQL.
   - Noter la liste des appels et des requêtes. Contrôler H1 et H3, puis arrêter avec une question si l'un est contredit.
   - Commande de vérification : les sorties des Grep sont conservées dans le compte rendu.

2. **Référence avant correction (C3)**
   - Créer `tests/test_regression.py`, qui rejoue des appels valides et compare leurs résultats à des valeurs attendues figées.
   - Cas pour `total` : `total([10, 20], 0)` et `total([], 0)`.
   - Cas pour `read_user` : `read_user(db, 'Alice')` renvoie 1 ligne, et `'Zoe'` (absent) renvoie 0 ligne.
   - Les appels relevés à l'étape 1 s'ajoutent s'il y en a. Il n'y en a aucun à ce jour.
   - Les valeurs attendues sont calculées à la main. Elles ne sont pas copiées de la sortie du code d'origine quand celle-ci est fausse.
   - Lancer ces appels sur le code d'origine et conserver les sorties (« avant »).
   - Commande : `python -m unittest tests.test_regression`.

3. **Tests des défauts, écrits avant correction**
   - `tests/test_remise.py`, avec `assertAlmostEqual`.
     - `total([10, 20], 0) == 30`
     - `total([10, 20], 100) == 0`
     - `total([10, 20], 50) == 15`
     - `total([], 50) == 0`
     - `total([0.1, 0.2], 50) ≈ 0.15`
     - `assertRaises(ValueError)` pour `-1` et `101`, si la décision de rejet est confirmée
   - `tests/test_injection.py` : base `sqlite3` en mémoire, table `users` avec `Alice` et `Bob`.
     - Chaîne `"' OR '1'='1"` : 0 ligne attendue.
     - Chaîne `"x'; DROP TABLE users;--"` : 0 ligne attendue, et la table `users` existe toujours avec 2 lignes après l'appel.
     - Chaîne `'Alice'` : 1 ligne attendue.
   - Le rejet de l'injection par exécution multiple est vérifié sur `sqlite3`, qui refuse plusieurs instructions dans `execute`. Le test contrôle donc surtout l'absence d'effet. Il n'est pas la seule preuve de C2 : l'inspection du code à l'étape 5 la complète.

4. **Contrôle de détection (avant correction)**
   - Commande : `python -m unittest discover tests`.
   - Attendu sur le code d'origine :
     - `test_remise` échoue (preuve que le test détecte le défaut).
     - Le cas `' OR '1'='1` de `test_injection` échoue (il renvoie 2 lignes).
     - `test_regression` passe.
   - Si un test censé échouer passe, corriger le test avant de continuer.

5. **Corrections dans `src/pay.py`**
   - `total()` :
     - lever `ValueError` si `not 0 <= discount <= 100` ;
     - sinon `return sum(prices) * (1 - discount / 100)` ;
     - corriger le commentaire pour qu'il corresponde au code.
   - `read_user()` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
   - Aucune autre ligne n'est modifiée.

6. **Contrôle après correction**
   - Relancer `python -m unittest discover tests`.
   - Rejouer les appels de l'étape 2 et comparer avec les sorties « avant ».
   - Relire le diff pour confirmer que seul `src/pay.py` a changé, hors nouveaux tests.
   - Relancer Grep sur `execute\(` et sur la concaténation SQL (`"\s*\+`, `%`, `f"`). Aucune requête construite par concaténation ne doit rester.

## Vérifier

- **C1** : `python -m unittest tests.test_remise` doit réussir (0, 50, 100, liste vide, flottants, hors bornes). Ce test a échoué à l'étape 4.
- **C2** :
  - `python -m unittest tests.test_injection` doit réussir avec les deux chaînes malveillantes et le cas `Alice`. Ce test a échoué à l'étape 4.
  - Le Grep de l'étape 6 doit montrer que toutes les requêtes du module utilisent `?` et un tuple de paramètres.
- **C3** :
  - `python -m unittest discover tests` doit réussir en entier après les étapes 5 et 6.
  - `tests/test_regression.py` doit donner les mêmes sorties avant et après pour les appels valides.
  - Écart attendu et signalé : `total` avec une remise non nulle change de valeur, car c'est le défaut corrigé. Une remise hors bornes est désormais rejetée si la décision est confirmée.
  - Tout autre écart est une régression.
- Une preuve est la sortie exécutée de la commande. Ces vérifications sont **attendues** tant qu'elles ne sont pas lancées. Aucun critère n'est déclaré **vérifié** sans cette sortie.

## Agir

- **Écart constaté** : corriger le code ou le test concerné, puis relancer la vérification du critère touché et la suite complète (C3).
- **Arrêt** : arrêter et rendre compte à la personne dans ces cas :
  - H1, H2 ou H3 est contredite ;
  - une vérification échoue encore après deux corrections ;
  - un appelant existant dépend du comportement hors bornes ;
  - un autre pilote SQL est utilisé.
- **Standardiser** :
  - garder les trois fichiers de tests dans `tests/` ;
  - conserver la règle « requête SQL = paramètres liés » ;
  - proposer à la personne d'ajouter `python -m unittest discover tests` à son contrôle avant livraison.
- **Exécution** : ce plan peut être exécuté par la personne ou par un agent disposant des droits d'écriture, avec la décision hors bornes confirmée au préalable.
