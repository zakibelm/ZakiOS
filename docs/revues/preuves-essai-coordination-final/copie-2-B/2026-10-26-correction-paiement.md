# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits lus dans le dépôt)**
- `src/pay.py` est le seul fichier Python du dépôt. Il contient deux fonctions.
- `total(prices, discount)` : le commentaire dit « pourcentage 0-100 », mais le code calcule `sum(prices) * (1 - discount)`. Avec `discount=50`, le résultat est `-49 × somme`. Avec `discount=100`, c'est `-99 × somme`. Le défaut est donc établi par lecture.
- `read_user(db, name)` concatène `name` dans le SQL. C'est une injection SQL.
- Une recherche de `total(` et `read_user(` dans tout le dépôt ne trouve que les deux définitions. Il n'y a ni appelant, ni dossier `tests/`.

**Conséquence pour C3 (fait, puis hypothèse)**
- Fait : aucun appel existant n'est visible dans ce dépôt.
- Hypothèse H3, non prouvée : des appelants existent hors de ce dépôt. Leur échelle de remise est inconnue (0, 0-1 ou 0-100).
- Le plan ne peut donc prouver C3 que pour les comportements qui doivent rester identiques. Ce sont `total` avec remise 0 et `read_user` avec un nom ordinaire. Il ne peut rien prouver sur des appelants non visibles. Ce point est signalé à la personne dans la section Agir.

**Hypothèses**
- H1 : la remise est un nombre de 0 à 100 (c'est ce que dit le commentaire et ce que demande la mission). Elle est confirmée à l'étape 1. Si le code ou les appelants relevés contredisent H1, on s'arrête et on pose la question à la personne.
- H2 : les prix sont des `int` ou des `float`. Elle est confirmée à l'étape 1.

**Résultat attendu (mesurable)**
- `total([10, 20], 0)` vaut 30 et `total([10, 20], 100)` vaut 0.
- `total([10, 20], 50)` vaut 15.
- `read_user(db, "' OR '1'='1")` renvoie 0 ligne, et `read_user(db, 'Alice')` en renvoie 1.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`. Aucun autre fichier n'est modifié.
- Aucune validation de plage n'est ajoutée à `total()`, car la mission ne la demande pas (voir la question Q1 dans Agir).
- Outils : `python -m unittest`, bibliothèque standard uniquement (`sqlite3` en mémoire).

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

## Exécuter

1. **Relevé (lecture seule).** Lire `src/pay.py`. Relancer Grep sur `total(` et `read_user(` dans tout le dépôt, y compris les fichiers non Python (scripts, docs). Pour chaque appel trouvé, noter :
   - le fichier et la ligne ;
   - l'échelle de remise réellement passée : 0, fraction 0-1 ou pourcentage 0-100, et si la valeur est une constante ou une variable ;
   - le type des prix passés (confirme H2).

   Règle de décision : si un appel passe une remise non nulle en échelle 0-1 (par exemple `0.2`), la nouvelle formule le ferait régresser. Dans ce cas, arrêt et question à la personne avant toute correction. Si le relevé ne trouve aucun appel, le noter tel quel (C3 est alors limité, voir Planifier).
2. **Créer les tests** (fichiers touchés : `tests/test_remise.py`, `tests/test_injection.py`, `tests/test_appels_existants.py`).
   - `tests/test_remise.py` : bornes 0 et 100, plus le milieu 50. Comparer avec `assertAlmostEqual`, pour ne pas dépendre du type `int` ou `float`.
   - `tests/test_injection.py` : base sqlite en mémoire, table `users` avec deux lignes `Alice` et `Bob`. Contrôler le nombre de lignes renvoyées (`fetchall()`).
   - `tests/test_appels_existants.py` : un cas pour chaque appel relevé à l'étape 1 qui reste valide (remise nulle). S'il n'y a aucun appel relevé, des cas de caractérisation :
     - `total([10, 20], 0)` vaut 30, valeur calculée à la main ;
     - `read_user(db, 'Alice')` renvoie la même ligne qu'avant correction.
3. **Référence avant correction.** Lancer `python -m unittest discover tests` sur le code d'origine.
   - `test_appels_existants` doit passer (c'est la référence de C3) ; sa sortie est conservée.
   - `test_remise` (bornes 100 et 50) et `test_injection` doivent échouer. Cela prouve que les tests détectent les défauts.
   - Si `test_appels_existants` échoue sur le code d'origine, ses valeurs attendues sont fausses : les corriger avant de continuer.
4. **Corriger `total()`** dans `src/pay.py` : `return sum(prices) * (1 - discount / 100)`.
5. **Corriger `read_user()`** dans `src/pay.py` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
6. **Relancer** `python -m unittest discover tests` et conserver la sortie complète.

## Vérifier

- **C1** : `python -m unittest tests.test_remise`.
  - Attendu : tous les tests passent (`OK`).
  - Les comparaisons utilisent `assertAlmostEqual`. Cela évite toute ambiguïté entre `int` et `float`. En Python, `30.0 == 30` est de toute façon vrai.
  - Valeurs attendues : 30 pour la remise 0, 0 pour la remise 100, 15 pour la remise 50.
  - Preuve de détection : ce test a échoué à l'étape 3.
- **C2** : `python -m unittest tests.test_injection`.
  - Attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1. Ce test a échoué à l'étape 3.
  - Contrôle complémentaire par lecture : `Grep` de `"' *\+|\+ *name"` dans `src/pay.py`. Attendu : aucune concaténation de `name` dans le SQL.
- **C3** : `python -m unittest tests.test_appels_existants` après correction.
  - Attendu : tous les tests passent, avec les mêmes valeurs que la sortie de référence de l'étape 3.
  - Complément : le relevé de l'étape 1 ne montre aucun appel avec une remise non nulle en échelle 0-1.
  - Limite : si le relevé est vide, C3 est prouvé seulement pour les comportements de caractérisation. Il n'est pas prouvé pour des appelants hors dépôt.
- Statut : tout ce qui précède est **attendu, non vérifié** tant que les sorties n'ont pas été exécutées. Aucun critère n'est déclaré satisfait sans la sortie de sa commande.

## Agir

- **Écart constaté** : corriger le code concerné, puis relancer la vérification du critère touché et `python -m unittest discover tests`.
- **Arrêt avec rapport à la personne** si :
  - H1 ou H2 est contredite ;
  - un appel existant passe une remise non nulle en échelle 0-1 ;
  - une vérification échoue encore après deux corrections.
- **Questions à confirmer par la personne (hors périmètre, non décidées ici)**
  - Q1 : faut-il rejeter une remise hors de 0-100 (par exemple avec `ValueError`) ? Le plan ne l'ajoute pas sans accord.
  - Q2 : existe-t-il des appelants hors de ce dépôt, et dans quelle échelle passent-ils la remise ?
- **Standardiser** : conserver `tests/` comme garde-fou. Noter dans le commentaire de `total()` que la remise est un pourcentage 0-100.
- **Exécution** : la personne ou un agent peut exécuter ce plan. Il ne demande aucun skill particulier.
