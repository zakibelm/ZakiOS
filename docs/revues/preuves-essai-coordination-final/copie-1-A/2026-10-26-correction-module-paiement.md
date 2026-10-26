# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré, sans régression)

## Planifier

**Situation initiale (faits lus dans le dépôt)**
- `src/pay.py` contient deux fonctions.
  - `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100. La formule le traite comme une fraction 0-1. Défaut : avec `discount=100`, le résultat est `-99 * sum`, au lieu de 0.
  - `read_user(db, name)` construit le SQL par concaténation : `"... WHERE name = '" + name + "'"`. Défaut : injection SQL.
- Le Grep sur `total(` et `read_user(` ne trouve aucun appel dans le dépôt, hors les définitions. Il n'y a pas de dossier `tests/`, et `src/pay.py` est le seul fichier `.py`.
- Conséquence pour C3 : on ne peut pas rejouer d'appels existants dans le dépôt. Les appels externes éventuels sont inconnus (hypothèse H3 ci-dessous). Le plan couvre C3 avec des tests de caractérisation et le maintien des signatures.

**Résultat attendu mesurable**
- `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`.
- `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1.
- Les signatures `total(prices, discount)` et `read_user(db, name)` sont inchangées. Les comportements qui étaient corrects avant la correction restent identiques.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer à l'exécution)**
- H1 : la remise est un nombre de 0 à 100. Le commentaire du code le dit. Si une lecture ou une information externe le contredit, arrêter et poser la question à la personne.
- H2 : les prix sont des nombres Python (int ou float).
- H3 : aucun appelant externe au dépôt ne dépend de l'ancien comportement de `total()` avec une remise comprise entre 0 et 1 (fraction). Le dépôt ne permet pas de le prouver. À confirmer par la personne avant livraison. Voir Agir.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`. Aucun autre fichier n'est modifié.
- Signatures publiques inchangées.
- Python standard uniquement (`unittest`, `sqlite3`).

## Exécuter
1. **Confirmer l'état initial.** Relire `src/pay.py` et refaire `Grep "total\(|read_user\("` sur tout le dépôt. Fichiers touchés : aucun. Contrôle : la sortie est identique à la situation initiale ci-dessus.
2. **Créer les tests** (fichiers nouveaux) :
   - `tests/test_remise.py` (C1). Compare par égalité numérique avec `assertEqual`. Python juge `0.0 == 0` vrai, donc le float `0.0` renvoyé à 100 % passe contre l'attendu `0`. Pour les valeurs intermédiaires, utiliser `assertAlmostEqual` : `total([10, 20], 50)` ≈ 15 et `total([10, 20], 25)` ≈ 22.5. Ne pas tester le type de retour.
   - `tests/test_injection.py` (C2). Base sqlite en mémoire, table `users` avec `Alice` et `Bob`. Lire le résultat avec `.fetchall()`, car `db.execute` renvoie un curseur.
   - `tests/test_non_regression.py` (C3). Teste le comportement déjà correct avant la correction :
     - `total([10, 20], 0) == 30`, `total([], 0) == 0` et `total([5], 0) == 5`.
     - `read_user(db, 'Alice')` renvoie la ligne d'Alice et `read_user(db, 'Inconnu')` renvoie 0 ligne.
     - `inspect.signature` de `total` donne `(prices, discount)` et celle de `read_user` donne `(db, name)`.
     - Chaque fonction renvoie le même type qu'avant : un nombre pour `total`, un curseur pour `read_user`.
3. **Mesurer la ligne de base sur le code d'origine** : `python -m unittest discover tests -v`.
   - Attendu avant correction : `test_remise` (borne 100) et `test_injection` échouent. `test_non_regression` passe en entier.
   - Si `test_non_regression` échoue sur le code d'origine, le test est mal écrit. Le corriger avant de continuer.
4. **Corriger `total()`** : `return sum(prices) * (1 - discount / 100)`. Commande : `python -m unittest tests.test_remise`.
5. **Corriger `read_user()`** : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Commande : `python -m unittest tests.test_injection`.

## Vérifier
- **C1** : `python -m unittest tests.test_remise -v`. Attendu : 0 échec ; `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0` par égalité numérique (le `0.0` flottant égale `0`) ; 50 % et 25 % corrects à la tolérance près. Preuve de détection : le test de la borne 100 a échoué à l'étape 3.
- **C2** : `python -m unittest tests.test_injection -v`. Attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1. Ce test a échoué à l'étape 3. Contrôle complémentaire : `Grep` sur `src/pay.py` ne trouve aucune concaténation `+ name` dans une requête SQL.
- **C3** : `python -m unittest discover tests -v` complet, après les étapes 4 et 5. Attendu : 0 échec, 0 erreur, y compris `test_non_regression` qui passait déjà à l'étape 3. Contrôles complémentaires :
  - `git diff -- src/pay.py` ne montre que les deux lignes `return` modifiées, signatures intactes ;
  - le Grep de l'étape 1 est rejoué et ne trouve aucun nouvel appelant cassé.
- **Limite de C3, à dire telle quelle** : C3 n'est prouvé que pour les comportements couverts par `test_non_regression`. Les appelants externes au dépôt ne sont pas vérifiés (H3). Tant que la personne ne l'a pas confirmé, C3 est « vérifié dans le dépôt, non vérifié hors dépôt ».
- Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa commande.

## Agir
- **Écart sur C1, C2 ou C3** : corriger le code concerné, puis relancer la commande du critère touché et `python -m unittest discover tests`. Si la vérification échoue encore après deux corrections, arrêter et rendre compte à la personne.
- **Contradiction de H1, H2 ou H3** : arrêter et poser la question. Cas particulier de H3 : si des appelants externes passent une remise en fraction (0-1), le changement de sens de `discount` est une rupture de contrat. La personne décide alors de la migration, par exemple en prévenant les appelants ou en versionnant la fonction.
- **Standardiser** : garder les trois fichiers de tests dans `tests/`. Retenir la règle « SQL toujours paramétré avec `?` ». Ajouter `python -m unittest discover tests` comme commande de contrôle avant toute modification de `src/pay.py`.
- **Exécution** : proposée à la personne, ou à un agent qui a le droit d'écrire dans `src/` et `tests/`. Ce plan n'est pas enregistré tant que la personne ne l'a pas fait.
