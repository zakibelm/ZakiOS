# Plan : correction du module de paiement (remise 0-100, SQL paramétré), v2

## Planifier

**Situation initiale (faits lus dans le dépôt le 2026-10-26)**
- `src/pay.py` est le seul fichier Python du dépôt. Il n'y a pas de dossier `tests/`.
- `total(prices, discount)` calcule `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, donc la formule est fausse. Avec `discount = 50`, le résultat est `-49 × la somme`.
- `read_user(db, name)` concatène `name` dans le SQL, ce qui permet l'injection.
- Grep de `total(` et `read_user(` dans tout le dépôt : seules les deux définitions sortent. **Aucun appelant n'existe dans le dépôt.** Les appels existants (C3) ne peuvent donc pas être relevés. Des appelants externes peuvent exister : c'est une hypothèse non vérifiable ici.

**Résultat attendu (mesurable)**
- `total([10, 20], 0) == 30`, `total([10, 20], 50) == 15` et `total([10, 20], 100) == 0`.
- `read_user` utilise une requête paramétrée : `'Alice'` renvoie 1 ligne, `"' OR '1'='1"` en renvoie 0.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et de nouveaux fichiers dans `tests/`. Rien d'autre n'est modifié.
- Bibliothèque standard uniquement (`unittest`, `sqlite3`).
- Les tests se lancent avec `PYTHONPATH=src` pour importer `pay`.

**Critères d'acceptation**
- C1 : remise correcte aux bornes 0 et 100, avec un cas intermédiaire (50). Comportement hors bornes défini ci-dessous.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants. Le périmètre est défini ci-dessous.

**Décisions de périmètre (à confirmer par la personne avant l'étape 5)**
- D1, remise hors de 0-100 (négative ou supérieure à 100) : `total` lève `ValueError`. C'est une décision proposée, pas un fait : le code d'origine ne dit rien là-dessus. Si la personne préfère laisser le comportement non défini, supprimer le test hors bornes et la garde de l'étape 5.
- D2, types non numériques (chaînes, `None`) : **hors périmètre**, aucun comportement n'est garanti ni testé.
- D3, `Decimal` : hors périmètre tant que H2 n'est pas confirmée. Mélanger `Decimal` et `float` lève `TypeError` en Python. Ce cas n'est pas traité ici.

**Hypothèses**
- H1 : `discount` est un nombre de 0 à 100. Source : le commentaire de `src/pay.py` (lu, donc un fait sur le code, pas une preuve sur les appelants). Si la personne indique une autre convention, arrêter et lui poser la question.
- H2 : les prix sont des `int` ou des `float`. **Statut : NON CONFIRMÉE.** Le dépôt ne contient aucun appelant ni aucune source de prix, donc la lecture des littéraux et des sources des prix ne donne rien. Les tests utiliseront des `int` et des `float` seulement. Si la personne fournit les appelants externes, relire leurs littéraux et leurs sources de prix. Si des `Decimal` ou des chaînes y apparaissent, arrêter et rendre compte avant de corriger : D3 devrait alors être traitée.

**Limite de C3 (déclarée)**
Faute d'appelants dans le dépôt, C3 sera prouvée uniquement sur le comportement de référence défini par les tests de l'étape 3 : `total(prices, 0)` et `read_user` avec un nom ordinaire. Cela ne prouve rien sur des appelants externes qui passeraient une remise en fraction (ex. `0.1`) : leur résultat changera, c'est le but de la correction. À signaler à la personne.

## Exécuter
1. Relire `src/pay.py` et refaire le Grep de `total(` et `read_user(` sur tout le dépôt. Si un appelant apparaît, l'ajouter aux tests de l'étape 3 et réévaluer H2 sur ses littéraux. Fichiers touchés : aucun.
2. Créer `tests/test_remise.py` avec trois cas : `total([10, 20], 0) == 30`, `total([10, 20], 50) == 15` et `total([10, 20], 100) == 0`. Ajouter, sous réserve de D1, `assertRaises(ValueError)` pour `-1` et `101`. Commande : `PYTHONPATH=src python -m unittest tests.test_remise`.
3. Créer `tests/test_injection.py`, avec une base sqlite en mémoire et une table `users` de deux lignes (`Alice`, `Bob`). Créer aussi `tests/test_appels_existants.py`, avec le comportement de référence relié à C3 :
   - `total([10, 20], 0) == 30` et `total([5.5, 4.5], 0) == 10.0` ;
   - `total([], 0) == 0` ;
   - `read_user(db, 'Alice').fetchall()` renvoie 1 ligne dont le nom est `Alice`.

   Commandes : `PYTHONPATH=src python -m unittest tests.test_injection` et `PYTHONPATH=src python -m unittest tests.test_appels_existants`.
4. **Référence avant correction.** Lancer `PYTHONPATH=src python -m unittest discover tests` sur le code d'origine. Garder la sortie. Attendu :
   - `test_appels_existants` passe en entier ;
   - `test_remise` échoue (cas 50, et hors bornes si D1 est retenue) ;
   - `test_injection` échoue.

   Si `test_appels_existants` échoue sur le code d'origine, le test est faux : le corriger avant d'aller plus loin. Si `test_remise` ou `test_injection` passe, le test ne détecte pas le défaut : le corriger aussi.
5. Corriger `total()` dans `src/pay.py`. Si D1 est retenue, ajouter avant le calcul `if not 0 <= discount <= 100: raise ValueError("discount doit être entre 0 et 100")`. Puis `return sum(prices) * (1 - discount / 100)`.
6. Corriger `read_user()` : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
7. Relancer toute la suite : `PYTHONPATH=src python -m unittest discover tests`. Garder la sortie.

## Vérifier
- **C1** : `PYTHONPATH=src python -m unittest tests.test_remise`. Attendu : tous les tests passent (0, 50, 100, et hors bornes si D1). Preuve avant/après : ces tests ont échoué à l'étape 4 et passent à l'étape 7.
- **C2** : `PYTHONPATH=src python -m unittest tests.test_injection`. Attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1. Preuve avant/après : échec à l'étape 4, succès à l'étape 7. Contrôle complémentaire : Grep de `" + name` et de `'" +` dans `src/pay.py`, attendu 0 résultat.
- **C3** : `PYTHONPATH=src python -m unittest tests.test_appels_existants`. Attendu : tous les tests passent, comme à l'étape 4 sur le code d'origine. La preuve est la comparaison des deux sorties (avant/après), dans la limite déclarée plus haut : aucun appelant dans le dépôt, donc aucune garantie sur des appelants externes.
- **H2** : reste « non confirmée » dans le compte rendu, sauf si des appelants ont été fournis et lus.

## Agir
- Si un test échoue après correction : corriger le code concerné, puis relancer la vérification du critère touché et la suite complète. Après deux corrections sans succès, arrêter et rendre compte à la personne.
- Si H1 est contredite, ou si H2 est contredite par des appelants fournis (`Decimal`, chaînes) : arrêter et rendre compte.
- Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa commande. Le compte rendu distingue ce qui est attendu de ce qui est vérifié, et dit quel contrôle manque, notamment pour C3 et H2.
- À standardiser : garder `tests/` et la commande `PYTHONPATH=src python -m unittest discover tests` comme contrôle de non-régression. Utiliser des requêtes paramétrées pour tout nouvel accès SQL.
- Prochaine étape proposée : exécution par la personne ou par un agent disposant des droits d'écriture, après confirmation de D1.
