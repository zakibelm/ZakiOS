# Plan : correction de src/pay.py (remise en pourcentage, requête paramétrée)

## Planifier

**Situation initiale (faits lus dans `src/pay.py`)**
- `total(prices, discount)` : le commentaire dit « pourcentage 0-100 », mais le code calcule `sum(prices) * (1 - discount)`. Avec `discount=10`, le résultat est `sum * -9`, donc négatif. Le code ne traite la remise ni comme un pourcentage, ni comme une borne.
- `read_user(db, name)` : la requête est construite par concaténation (`"... '" + name + "'"`). C'est une injection SQL possible.
- Aucun fichier de test n'existe dans le projet (Glob `**/*test*` : aucun résultat).
- Non vérifié : outil indisponible. Je n'ai pas lu l'historique git. Je ne sais pas non plus quel pilote de base de données est utilisé, donc je ne connais pas son style de paramètre.

**Résultat attendu (mesurable)**
- `total([100], 10)` renvoie 90.0, `total([100], 0)` renvoie 100.0 et `total([100], 100)` renvoie 0.0.
- Une remise inférieure à 0 ou supérieure à 100 est refusée.
- `read_user` envoie le nom comme paramètre lié et non concaténé dans le SQL.

**Contraintes**
- Périmètre : `src/pay.py` et un nouveau fichier de test. Rien d'autre.
- Montants en $ CAD.
- Le plan n'écrit rien lui-même. La personne ou un agent autorisé l'exécute.

**Critères d'acceptation (repris tels quels)**
- C1 : la remise est traitée comme un pourcentage de 0 à 100, bornes comprises.
- C2 : la requête de lecture d'utilisateur est paramétrée.
- C3 : le plan nomme au moins un test de régression à exécuter par la personne.

**Hypothèses à confirmer par la personne**
- H1 : une remise hors de 0-100 doit lever `ValueError`. L'alternative serait de la borner silencieusement. Je recommande l'exception, parce que borner masque les erreurs. C1 n'impose pas ce choix, donc une confirmation est utile.
- H2 : le style de paramètre dépend du pilote. `?` convient à sqlite3, `%s` à psycopg ou MySQL. Ce plan suppose `?` et `db.execute(sql, params)` ; à confirmer.

## Exécuter

**Tâche 1 : corriger `total` (C1)**
- Fichier touché : `src/pay.py`.
- Changement : valider `0 <= discount <= 100`, sinon lever `ValueError`. Calculer ensuite `sum(prices) * (1 - discount / 100)`.
- Périmètre : cette fonction seulement.

**Tâche 2 : paramétrer `read_user` (C2)**
- Fichier touché : `src/pay.py`.
- Changement : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`, sans concaténation.
- Périmètre : cette fonction seulement.

**Tâche 3 : ajouter les tests de régression (C3)**
- Fichier créé : `tests/test_pay.py` (pytest, à créer).
- Tests :
  - `test_total_remise_10_pct` : `total([100], 10) == 90`.
  - `test_total_bornes` : remise 0 donne 100, remise 100 donne 0.
  - `test_total_remise_invalide` : -1 et 101 lèvent `ValueError`.
  - `test_read_user_parametre` : avec une base sqlite3 en mémoire, `read_user(db, "x' OR '1'='1")` ne renvoie aucune ligne. L'ancien code renvoyait toutes les lignes.
- Ordre : écrire d'abord les tests de la tâche 3, parce qu'ils échouent sur le code actuel. Cela prouve la régression. Appliquer ensuite les tâches 1 et 2.

**Commande de vérification (à lancer par la personne)** : `python -m pytest tests/test_pay.py -v`
- Non vérifié : outil indisponible. Je ne sais pas si pytest est installé. Sinon, écrire les tests avec `unittest` et lancer `python -m unittest`.

## Vérifier

| Critère | Preuve attendue |
|---|---|
| C1 | `test_total_remise_10_pct`, `test_total_bornes` et `test_total_remise_invalide` passent. Les bornes 0 et 100 sont acceptées, -1 et 101 sont refusés. |
| C2 | `test_read_user_parametre` passe. Relecture de `src/pay.py` : aucune concaténation de `name` dans le SQL. |
| C3 | Le fichier `tests/test_pay.py` existe et la personne a lancé `python -m pytest tests/test_pay.py -v`. |

Statut actuel : tout est **attendu**, rien n'est **vérifié**. Aucun test n'a été exécuté. Il faut montrer la sortie de pytest avant de déclarer une validation.

## Agir

- Si un test échoue : corriger la tâche concernée, relancer la commande et noter l'écart.
- Si le pilote n'accepte pas `?` : adapter le marqueur (H2) sans repasser à la concaténation.
- Si H1 est infirmée (borner au lieu de lever) : adapter `test_total_remise_invalide`.
- À standardiser : lancer `python -m pytest` avant chaque modification de `src/pay.py`. Interdire la concaténation dans le SQL lors des revues.
- Hors périmètre, à signaler : la question de savoir si d'autres appelants passent encore une remise en fraction (0-1). Une recherche Grep des appels à `total` est à faire avant la fusion.

**Exécution proposée** : par la personne, ou par un agent disposant d'un outil d'écriture que la personne autorise. Dans les deux cas, la personne lance les tests de la section Vérifier.
