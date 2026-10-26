# Plan : correction de src/pay.py (remise en pourcentage, requête paramétrée)

## Planifier

**Situation initiale (faits lus dans le dépôt)**
- `src/pay.py` est le seul fichier Python du dépôt. Il contient deux fonctions.
- `total(prices, discount)` retourne `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule l'utilise comme une fraction 0-1.
  - Avec `discount=100`, le résultat est `sum * -99`, donc négatif.
  - Avec `discount=0`, le résultat est correct par hasard.
- `read_user(db, name)` construit le SQL par concaténation de chaînes, ce qui permet une injection SQL.
- Une recherche de `total(`, `read_user` et `pay` ne trouve aucun appelant dans le dépôt. Il n'y a aucun test.
- Hypothèse : des appelants existent hors du dépôt, et la demande les appelle « appels existants ». Rien ne le prouve ici.
- Hypothèse à confirmer : le paramètre `db` est une connexion ou un curseur compatible DB-API. Le style de marqueur (`?` pour sqlite3, `%s` pour psycopg ou MySQL) n'est pas connu.

**Résultat attendu (mesurable)**
- `total([100], 0)` retourne 100 et `total([100], 100)` retourne 0.
- `total([100], 50)` retourne 50.
- `read_user` n'insère jamais `name` dans le texte SQL. La valeur est passée comme paramètre à `db.execute`.

**Contraintes**
- Périmètre : `src/pay.py` seulement, plus un fichier de test à créer, par exemple `tests/test_pay.py`.
- Signatures inchangées, pour éviter une régression (C3).
- Montants en $ CAD. Aucun changement de devise n'est prévu.

**Critères d'acceptation**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Décisions à confirmer avant d'exécuter**
1. Le style de marqueur de la base : `?` ou `%s`.
2. Le comportement hors bornes (`discount` < 0 ou > 100) : lever `ValueError` ou laisser passer. Je propose `ValueError`.
   - C3 est alors en tension avec cette proposition. Un appelant qui passe aujourd'hui une valeur hors bornes échouerait.
   - Comme la formule actuelle est fausse pour tout pourcentage, la rupture est assumée si la personne confirme.
3. Si des appelants existent hors du dépôt, ils passent peut-être déjà une fraction 0-1. Il faut le vérifier, car la correction changerait leur résultat.

## Exécuter

**Tâche 1 : écrire les tests avant la correction (risque réel : changement de sémantique)**
- Fichier touché : `tests/test_pay.py` (nouveau).
- Cas de test :
  - `total` aux valeurs 0, 50 et 100, plus le cas d'une liste vide.
  - `read_user` avec un faux `db` qui enregistre ses arguments. Le test vérifie que le SQL contient un marqueur et que `name` est passé en paramètre.
  - `read_user` avec `"x' OR '1'='1"`. Cette chaîne ne doit pas apparaître dans le texte SQL.
- Vérification : `python -m pytest tests/test_pay.py`. Les tests de C1 (borne 100) et C2 doivent échouer avant la correction.
- Périmètre : lecture et création de tests seulement.

**Tâche 2 : corriger `total`**
- Fichier touché : `src/pay.py`.
- Changement : `sum(prices) * (1 - discount / 100)`. Selon la décision 2, ajouter la validation `0 <= discount <= 100`.
- Vérification : `python -m pytest tests/test_pay.py -k total`.

**Tâche 3 : paramétrer `read_user`**
- Fichier touché : `src/pay.py`.
- Changement : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`, avec le marqueur confirmé en décision 1.
- Vérification : `python -m pytest tests/test_pay.py -k read_user`. Une recherche `grep -n "name = '" src/pay.py` ne doit rien retourner.

**Tâche 4 : contrôle de régression**
- Rechercher les appelants éventuels et relire les signatures (`grep -rn "total(\|read_user" .`).
- Vérification : `python -m pytest`.

## Vérifier

| Critère | Preuve attendue |
|---|---|
| C1 | Tests des bornes 0, 100 et d'une valeur intermédiaire verts. Sortie de pytest conservée. |
| C2 | Test avec faux `db` vert, et recherche montrant qu'aucune concaténation SQL ne reste. Un test sur une vraie base (sqlite3 en mémoire) est préférable si la base cible le permet. |
| C3 | Signatures inchangées (relecture du diff). Aucun appelant dans le dépôt, vérifié par recherche. Les appelants externes ne sont **pas vérifiés** : ce contrôle manque tant que la personne ne les fournit pas. |

Ce plan n'a rien exécuté. Tous les résultats ci-dessus sont **attendus**, pas **vérifiés**.

## Agir

- Si un test échoue, corriger puis relancer toute la suite.
- Si des appelants externes passent une fraction 0-1, signaler l'écart à la personne avant de livrer. Ne pas deviner de conversion.
- Si le marqueur de paramètre est mauvais, la base lèvera une erreur à l'exécution. Adapter le marqueur et reprendre la tâche 3.
- À standardiser : garder `tests/test_pay.py` dans le dépôt, et noter dans le docstring de `total` l'unité du paramètre (pourcentage 0-100).

**Exécution** : la personne ou un agent peut l'exécuter après avoir confirmé les décisions 1 à 3. L'enregistrement du plan et les modifications de fichiers restent sous le contrôle de la personne.
