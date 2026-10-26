ZAKIOS-SOCLE v1 · PDCA

# Plan : correction de `src/pay.py`

## 1. Planifier

**Situation initiale (fait, lu dans `src/pay.py`)**
- `total(prices, discount)` : le commentaire dit « pourcentage 0-100 », mais le code calcule `sum(prices) * (1 - discount)`. Avec `discount=10`, le résultat est `-9 × somme`. Le calcul est faux.
- `read_user(db, name)` : la requête est construite par concaténation de chaînes. `name = "' OR '1'='1"` renvoie tous les utilisateurs (injection SQL).

**Hypothèses (non vérifiées)**
- H1 : `db` est une connexion ou un curseur DB-API. Le style de paramètre (`?` pour sqlite3, `%s` pour psycopg) est inconnu. Le plan utilise `?` par défaut.
- H2 : aucun autre appelant ne dépend du comportement actuel. Il n'y a pas encore eu de recherche des appelants.
- H3 : aucun test existant (non vérifié).

**Résultat attendu**
- `total` applique une remise en pourcentage 0-100.
- `read_user` n'interpole plus `name` dans le SQL.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et un nouveau fichier de test `tests/test_pay.py`.
- Montants en $ CAD.
- Pas de changement de signature des deux fonctions.

**Décision à confirmer** : que fait `total` si `discount` est hors de 0-100 ? Proposition : lever `ValueError`. Le choix revient à la personne ; sans réponse, ce plan applique la proposition.

**Critères d'acceptation (mesurables)**

| # | Critère | Mesure |
|---|---|---|
| C1 | `total([100, 50], 0) == 150` | assertion |
| C2 | `total([100, 50], 10) == 135` (tolérance `pytest.approx`) | assertion |
| C3 | `total([100, 50], 100) == 0` | assertion |
| C4 | `total([100], -1)` et `total([100], 101)` lèvent `ValueError` | `pytest.raises` |
| C5 | `total([], 20) == 0` | assertion |
| C6 | `read_user` n'utilise aucune concaténation ni f-string dans le SQL : la requête est une constante et `name` est passé en paramètre | inspection du code + test avec une fausse `db` qui enregistre `(sql, params)` : `params == (name,)` et `name` absent de `sql` |
| C7 | `read_user(db, "' OR '1'='1")` sur une vraie base sqlite en mémoire (2 utilisateurs) renvoie 0 ligne | test d'intégration |
| C8 | `read_user(db, "alice")` renvoie la ligne d'`alice` | test d'intégration |
| C9 | Tous les tests passent, 0 échec | `python -m pytest tests/test_pay.py -q` |

## 2. Exécuter

**T1 : Filet de tests** (risque : la correction touche un calcul d'argent et un accès aux données, donc test d'abord)
- Fichier touché : `tests/test_pay.py` (nouveau).
- Écrire les tests C1 à C8. Utiliser `sqlite3` en mémoire pour C7 et C8.
- Vérification : `python -m pytest tests/test_pay.py -q`. Attendu avant correction : C2, C3, C4, C7 en échec. Cet échec prouve que les tests détectent les défauts.

**T2 : Corriger `total`**
- Fichier touché : `src/pay.py`.
- Valider `0 <= discount <= 100` (sinon `ValueError`), puis retourner `sum(prices) * (1 - discount / 100)`.
- Vérification : tests C1 à C5 au vert.

**T3 : Paramétrer `read_user`**
- Fichier touché : `src/pay.py`.
- Remplacer par `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
- Vérification : tests C6 à C8 au vert.
- Si la base réelle n'est pas sqlite, adapter le marqueur (`%s`) après avoir confirmé H1.

**T4 : Recherche des appelants** (lecture seule)
- Commande : `grep -rn "pay\|total(\|read_user(" --include=*.py .`
- Vérification : confirmer H2 et lister les appels qui passaient une remise en fraction (0-1). Ces appels deviendraient faux.

## 3. Vérifier

| Critère | Preuve attendue |
|---|---|
| C1 à C5, C7, C8 | sortie de `pytest` collée dans le compte rendu |
| C6 | sortie de `pytest` + `grep -nE "\"\s*\+|f\"" src/pay.py` sans résultat dans `read_user` |
| C9 | ligne de synthèse `pytest` : `N passed, 0 failed` |
| H1, H2 | résultat de T4 et type réel de `db` confirmé par la personne |

Statut actuel : tout est **attendu**, rien n'est **vérifié**. Aucun test n'a été exécuté.

## 4. Agir

- Écart sur C2/C3 : revoir la formule et les arrondis. Le plan ne traite pas l'arrondi au cent ; si un montant est affiché ou facturé, ouvrir une tâche dédiée.
- Écart sur C7 : le paramétrage n'est pas effectif. Vérifier le style de paramètre du pilote.
- Appel existant avec une remise en fraction (T4) : le signaler avant de le modifier, car c'est hors périmètre.
- À standardiser : garder `tests/test_pay.py` dans la suite, et interdire la concaténation SQL (revue de code ou règle de lint).

## Exécution

Ce plan peut être exécuté par la personne ou par un agent, par exemple avec `code-reviewer` pour relire le diff en lecture seule ensuite. Aucun skill particulier n'est requis.
