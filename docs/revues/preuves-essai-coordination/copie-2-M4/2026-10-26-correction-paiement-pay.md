# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits lus dans le projet)**
- `src/pay.py` contient deux fonctions seulement.
  - `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit « pourcentage 0-100 », mais le code se comporte comme une fraction 0-1. Avec `discount=100`, il renvoie `-99 × somme`. Avec `discount=1`, il renvoie 0.
  - `read_user(db, name)` construit la requête par concaténation : `"SELECT * FROM users WHERE name = '" + name + "'"`.
- Grep de `total(` et `read_user(` : **aucun appel dans le dépôt**, seulement les deux définitions. Il n'y a pas de dossier `tests/` ni d'autre fichier `.py`.
- Conséquence pour C3 : aucun appelant interne n'est à protéger. Les appelants externes éventuels sont inconnus. La non-régression porte donc sur les signatures et sur les comportements qui doivent rester identiques (voir ci-dessous).

**Résultat attendu**
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount/100)` pour `discount` entre 0 et 100.
- `read_user(db, name)` utilise une requête paramétrée et traite `name` comme une donnée.

**Hypothèses (à confirmer, pas des faits)**
- H1 : la remise est un nombre de 0 à 100. Le commentaire le dit, mais le code actuel contredit ce commentaire (comportement en fraction 0-1). C'est un changement de sémantique volontaire, voulu par la mission. Un appelant externe qui passe une fraction 0-1 verrait son résultat changer : par exemple 0,2 deviendrait 0,2 % et non 20 %. **Ce risque est signalé à la personne avant la correction (étape 1).** Seule la personne peut confirmer qu'aucun appelant externe ne passe de fraction.
- H2 : les prix sont des nombres Python (int ou float). Aucun appel dans le dépôt ne permet de le vérifier. Les tests couvrent int et float.
- H3 : `db` est une connexion ou un curseur de type sqlite3 (`execute` avec paramètre `?`). Si la base réelle utilise un autre style de paramètres (`%s`, `:nom`), la requête s'adapte. Cette information n'est pas dans le dépôt : question à la personne.

**Périmètre**
- Autorisé : `src/pay.py` et de nouveaux fichiers dans `tests/`.
- Hors périmètre :
  - Une remise hors de 0-100 (négative, supérieure à 100, non numérique). Le comportement actuel n'est pas durci et n'est pas testé. Le signaler à la personne comme décision à prendre (lever une erreur ou borner). Ne rien inventer.
  - Tout autre fichier.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Mesures retenues**
- C1 : `total([10, 20], 0)` = 30 ; `total([10, 20], 100)` = 0 ; cas intermédiaire `total([10, 20], 50)` = 15. Comparaison avec `assertAlmostEqual` pour les float, par exemple `total([0.1, 0.2], 0)` ≈ 0.3.
- C2 : charge `x' OR '1'='1` sur une table `users` de deux lignes (`Alice`, `Bob`). Attendu : **aucune ligne**. Pour `name="Alice"` : exactement la ligne d'Alice. Contrôle statique complémentaire par Grep.
- C3 : voir étape 3.

## Exécuter

1. **Constat et question à la personne** (lecture seule).
   - Relire `src/pay.py` et refaire Grep de `total(` et `read_user(` dans tout le dépôt (src, tests, scripts, docs). Résultat connu à la date du plan : aucun appel.
   - Poser à la personne les questions H1 (appelants externes, fraction 0-1 ou pourcentage) et H3 (style de paramètre de la base).
   - Le plan s'arrête et attend la réponse si un appelant externe passe une fraction.
   - Vérification : sortie de Grep conservée.
2. **Créer les tests** (fichiers touchés : `tests/test_remise.py`, `tests/test_injection.py`). Utiliser `unittest` et une base `sqlite3` en mémoire.
   - `test_remise` : remise 0 → somme ; remise 100 → 0 ; remise 50 → moitié ; prix int et float, avec `assertAlmostEqual`.
   - `test_injection` : table `users(name)` avec `Alice` et `Bob`. Entrée `x' OR '1'='1` → liste vide. Entrée `Alice` → exactement la ligne d'Alice.
3. **Créer le test de non-régression** (fichier touché : `tests/test_appels_existants.py`). Comme il n'existe aucun appel dans le dépôt, il fige le comportement à conserver, calculé à la main :
   - `total` avec remise 0 → somme des prix (prix int et float, liste vide → 0).
   - `read_user` avec un nom présent (`Bob`) → sa ligne ; avec un nom absent → aucune ligne.
   - Signatures inchangées : `total(prices, discount)` et `read_user(db, name)`.
   - Si la personne indique des appels externes avec remise non nulle, ajouter un cas par appel avec valeur attendue calculée à la main, ou consigner le changement de sémantique accepté.
4. **Mesurer l'état avant correction** : `python -m unittest discover tests -v`, sortie conservée dans un fichier de trace.
   - Attendu : `test_appels_existants` passe (référence), `test_remise` échoue sur la borne 100, `test_injection` échoue sur la charge.
   - Un écart avec cet attendu signifie que le test ne détecte pas le défaut : corriger le test avant d'aller plus loin.
5. **Corriger `total()`** (fichier touché : `src/pay.py`) : `return sum(prices) * (1 - discount / 100)`. Corriger aussi le commentaire si nécessaire.
6. **Corriger `read_user()`** (fichier touché : `src/pay.py`) : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Adapter le marqueur si H3 l'exige.
7. **Revérifier après correction** : relancer `python -m unittest discover tests -v` et conserver la sortie.
   - Attendu : `test_remise`, `test_injection` et `test_appels_existants` tous au vert.
   - Cet attendu n'est qu'un **attendu** tant que la sortie n'a pas été obtenue.
8. **Contrôle statique C2** : `Grep` dans `src/pay.py` des motifs de construction de requête (`" + `, `%` sur une chaîne SQL, `.format(`, `f"` ou `f'` contenant `SELECT`). Attendu : aucune occurrence dans une requête.

## Vérifier

| Critère | Preuve exécutée | Attendu | Vérifié |
|---|---|---|---|
| C1 | `test_remise` après l'étape 7 (bornes 0 et 100, cas 50) | vert | à remplir avec la sortie de l'étape 7 |
| C2 | `test_injection` après l'étape 7 et Grep de l'étape 8 | vert, 0 occurrence | à remplir avec les sorties |
| C3 | `test_appels_existants` après l'étape 7, comparé à l'étape 4 (vert avant et après) | vert avant et après | à remplir avec les deux sorties |

- Le test échoue avant correction et passe après : c'est la preuve que le test mesure le défaut. Les deux sorties (étapes 4 et 7) sont conservées.
- Limite connue de C3 : sans appel dans le dépôt, il ne prouve la non-régression que pour les comportements figés à l'étape 3. Il ne couvre pas les appelants externes inconnus.
- Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification. Si un contrôle n'a pas été exécuté, dire lequel manque.

## Agir

- En cas d'écart : corriger le code ou le test concerné, puis relancer la vérification du critère touché.
- Arrêt et compte rendu à la personne si :
  - H1, H2 ou H3 est contredite ;
  - un appelant externe passe une fraction 0-1 (changement de sémantique à valider) ;
  - une vérification échoue encore après deux corrections.
- Décision laissée à la personne : traitement des remises hors de 0-100, hors périmètre de ce plan.
- Standardiser :
  - garder `tests/` et la commande `python -m unittest discover tests` comme contrôle de ce module ;
  - interdire dans la revue toute requête SQL construite par concaténation ou formatage ;
  - conserver les sorties des étapes 4, 7 et 8 comme traces.

**Exécution** : ce plan peut être exécuté par la personne ou par un agent disposant des droits d'écriture sur `src/` et `tests/`. L'agent planificateur n'a pas ces droits. Seule la personne peut les accorder.
