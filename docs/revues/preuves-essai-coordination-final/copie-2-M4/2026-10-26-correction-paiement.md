# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré)

## Planifier

**Besoin.** `total()` doit traiter la remise comme un pourcentage de 0 à 100. `read_user()` doit utiliser une requête paramétrée.

**Situation initiale (faits lus dans le projet).**
- `src/pay.py` est le seul fichier Python. Il contient deux fonctions.
- `total(prices, discount)` retourne `sum(prices) * (1 - discount)`. Le commentaire annonce un pourcentage 0-100, mais le calcul traite la remise comme une fraction 0-1. Avec `discount=100`, le résultat est `-99 × somme`.
- `read_user(db, name)` construit le SQL par concaténation : `"... WHERE name = '" + name + "'"`. C'est une injection SQL possible.
- Une recherche (Grep `total(` et `read_user(`) ne trouve **aucun appel** dans le dépôt, hors les définitions.
- Il n'y a pas de dossier `tests/` (aucun fichier `.py` hors `src/pay.py`).

**Conséquence pour C3 (fait, puis hypothèse).** Aucun appel existant n'est visible dans le dépôt. Il est impossible de prouver l'absence de régression chez des appelants externes.
- Hypothèse H1 : d'éventuels appelants externes existent et passent une remise de sens inconnu. À confirmer par la personne.
- Hypothèse H2 : les prix sont des nombres Python (int ou float). Rien ne la contredit dans le code. Elle est vérifiée par les tests, qui n'utilisent que ces types.

**Changement de sens à signaler.** Le passage de la fraction (0-1) au pourcentage (0-100) change le résultat de tout appelant qui passe une remise non nulle avec l'ancienne sémantique. Exemple : `discount=0.1` valait 10 % et vaudra 0,1 %. Seule la remise 0 donne le même résultat avant et après. Cela relève d'une décision de la personne, pas du plan.

**Résultat attendu (mesurable).**
- `total([10, 20, 30], 0)` donne `60`.
- `total([10, 20, 30], 100)` donne `0`.
- `read_user(db, "' OR '1'='1")` retourne 0 ligne.
- `read_user(db, "Alice")` retourne la ligne d'Alice.

**Contraintes.**
- Périmètre autorisé : `src/pay.py` (2 lignes modifiées) et de nouveaux fichiers sous `tests/`.
- Les signatures `total(prices, discount)` et `read_user(db, name)` restent inchangées.
- Aucune validation de plage (remise < 0 ou > 100) n'est ajoutée, car la mission ne la demande pas. Voir la question Q1.

**Critères d'acceptation (repris de la mission).**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Questions pour la personne (hors périmètre du plan, non bloquantes pour C1 et C2).**
- Q1 : faut-il rejeter une remise hors de 0-100 (par exemple avec une exception) ?
- Q2 : existe-t-il des appelants hors de ce dépôt ? Si oui, quelle remise passent-ils, fraction ou pourcentage ?

## Exécuter

Chaque tâche indique ses fichiers, sa commande de vérification et son périmètre. Les commandes se lancent depuis la racine du projet. `PYTHONPATH=src` permet les imports `from pay import ...`.

1. **Écrire les tests de caractérisation, avant toute correction.**
   - Fichiers créés : `tests/test_remise.py`, `tests/test_injection.py`, `tests/test_appels_existants.py`.
   - Périmètre : `tests/` seulement.
   - `tests/test_remise.py` (C1), avec `prices = [10, 20, 30]` :
     - remise 0 → attendu `60` ;
     - remise 100 → attendu `0` ;
     - remise 50 → attendu `30` (valeur intermédiaire, pour écarter un calcul qui ne serait juste qu'aux bornes) ;
     - comparaison par `assertAlmostEqual`.
   - `tests/test_injection.py` (C2) : base `sqlite3` en mémoire, table `users(name)` avec deux lignes `Alice` et `Bob`.
     - Entrée malveillante `' OR '1'='1` → attendu : `fetchall()` retourne `[]` (0 ligne).
     - Entrée normale `Alice` → attendu : exactement 1 ligne, celle d'Alice.
     - Entrée `Bob'--` (variante) → attendu : 0 ligne.
   - `tests/test_appels_existants.py` (C3) : sans appel trouvé dans le dépôt, ce fichier fixe le comportement conservé.
     - Signatures : `total(prices, discount)` et `read_user(db, name)` s'appellent en positionnel, comme avant.
     - `total([10, 20, 30], 0)` → `60` ; `total([], 0)` → `0` ; `total([5.5, 4.5], 0)` → `10`.
     - `read_user(db, "Alice")` retourne la ligne d'Alice, comme avant (comportement légitime inchangé).
     - Un commentaire du fichier rappelle que la remise non nulle change de sens, selon la section Planifier.
   - Vérification de la tâche : `PYTHONPATH=src python -m unittest discover -s tests -v` doit collecter les trois fichiers, sans erreur d'import.

2. **Lancer les tests sur le code d'origine (référence).**
   - Aucun fichier modifié. Garder la sortie comme trace.
   - Attendu : `test_appels_existants` passe en entier, sauf peut-être la partie injection. `test_remise` échoue sur la remise 100 (résultat `-5940` au lieu de `0`) et sur la remise 50. `test_injection` échoue sur `' OR '1'='1` (2 lignes retournées au lieu de 0).
   - Cette étape prouve que les tests détectent les défauts. Si un test censé échouer passe, il est inutile : le corriger avant de continuer.

3. **Corriger `total()`.**
   - Fichier : `src/pay.py`. Périmètre : la ligne du `return` de `total()`.
   - Nouveau code : `return sum(prices) * (1 - discount / 100)`.
   - Vérification : `PYTHONPATH=src python -m unittest tests.test_remise tests.test_appels_existants -v`.

4. **Corriger `read_user()`.**
   - Fichier : `src/pay.py`. Périmètre : la ligne du `return` de `read_user()`.
   - Nouveau code : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
   - Vérification : `PYTHONPATH=src python -m unittest tests.test_injection tests.test_appels_existants -v`.

5. **Relancer toute la suite après les étapes 3 et 4.**
   - Commande : `PYTHONPATH=src python -m unittest discover -s tests -v`.
   - Garder la sortie complète comme preuve pour la section Vérifier.

6. **Contrôle du périmètre.** Commande : `git status` et `git diff -- src/pay.py`. Attendu : seul `src/pay.py` est modifié, de 2 lignes de code, et seuls des fichiers de `tests/` sont ajoutés.

## Vérifier

Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa commande. Aujourd'hui, rien n'a été exécuté : tout ce qui suit est **attendu**, pas **vérifié**.

| Critère | Preuve | Commande | Sortie attendue |
|---|---|---|---|
| C1 remise aux bornes | `tests/test_remise.py` | `PYTHONPATH=src python -m unittest tests.test_remise -v` | remise 0 → 60, remise 100 → 0, remise 50 → 30 ; tous les tests `ok`. Avant correction : échec sur 100 et 50 (étape 2). |
| C2 SQL paramétré | `tests/test_injection.py` + lecture du code | `PYTHONPATH=src python -m unittest tests.test_injection -v` ; `grep -n "?" src/pay.py` | `' OR '1'='1` → 0 ligne, `Alice` → 1 ligne ; `src/pay.py` contient le marqueur `?` et plus aucune concaténation de `name` dans le SQL. Avant correction : 2 lignes retournées pour l'injection. |
| C3 pas de régression | `tests/test_appels_existants.py` + recherche d'appels | `PYTHONPATH=src python -m unittest tests.test_appels_existants -v` ; Grep `total(\|read_user(` | Les tests passent avant (étape 2) et après (étape 5), avec les mêmes valeurs. Grep : aucun appel hors définitions, fait constaté. |
| Suite complète | toutes les preuves | `PYTHONPATH=src python -m unittest discover -s tests -v` | `OK`, 0 échec, 0 erreur, après les étapes 3 et 4. |

**Limite de la preuve pour C3.** Les tests couvrent les appels que le plan a pu relever, c'est-à-dire aucun dans le dépôt, plus les cas conservés ci-dessus. Ils ne couvrent pas les appelants externes avec une remise non nulle. C3 est donc **vérifié** pour la remise 0, pour les signatures et pour le comportement légitime de `read_user()`. Il reste **non vérifié** pour toute remise non nulle à l'ancienne sémantique, tant que Q2 n'a pas de réponse. Le rapport final doit le dire ainsi, sans conclure « aucune régression » sans réserve.

## Agir

**En cas d'écart.**
- Corriger le code concerné, puis relancer la commande du critère touché et la suite complète.
- Si un test censé échouer sur le code d'origine passe (étape 2), corriger le test avant toute modification de `src/pay.py`.
- Si un critère échoue après deux corrections, arrêter et rendre compte à la personne avec les sorties.
- Si la personne signale des appelants externes avec l'ancienne sémantique (Q2), ne pas décider seul. Proposer soit de migrer ces appels (valeur × 100), soit d'accepter le changement de sens. La personne choisit.
- Si la personne répond oui à Q1, ajouter un test de remise hors plage, puis la validation correspondante dans un cycle séparé.

**À standardiser.**
- Conserver les trois fichiers de `tests/` comme filet de non-régression du module.
- Consigner dans le rapport final : le changement de sens de la remise, la limite de preuve de C3 et les sorties de commandes.
- Les fichiers `tests/` s'enregistrent dans le dépôt. L'enregistrement de ce plan et du code se fait par la personne ou par un mécanisme contrôlé.

**Exécution proposée.** La personne ou un agent disposant des outils d'écriture et d'exécution peut dérouler les étapes 1 à 6 dans l'ordre. Aucun skill particulier n'est requis. Les réponses à Q1 et Q2 sont utiles avant l'étape 3.
