# Plan : correction de src/pay.py (remise en pourcentage, requête paramétrée)

## 1. Planifier
**Situation initiale (faits, lus dans src/pay.py)**
- `total(prices, discount)` retourne `sum(prices) * (1 - discount)`. Avec un pourcentage 0-100, le résultat est faux. Exemple : discount=10 donne sum*(-9). Aux bornes, 0 donne sum (correct par hasard) et 100 donne sum*(-99).
- `read_user(db, name)` construit le SQL par concaténation : injection SQL possible.
- Aucun test ni appelant n'existe dans le dépôt (Grep).

**Résultat attendu (mesurable)**
- `total([100], 0) == 100`, `total([100], 100) == 0`, `total([100], 10) == 90`.
- `read_user` envoie une requête avec marqueur et paramètre séparé, sans concaténation de `name`.

**Contraintes**
- Périmètre : `src/pay.py` et un nouveau fichier de test. Rien d'autre.
- Signatures inchangées : `total(prices, discount)` et `read_user(db, name)`.
- Montants en $ CAD.

**Hypothèses à confirmer avant d'exécuter**
- H1 : le style de paramètre du pilote de `db` (`?` ou `%s`). Sans cette information, on ne choisit pas.
- H2 : aucun appelant externe ne passe une fraction 0-1.
- H3 : comportement voulu hors 0-100 (voir tâche 1).

**Critères d'acceptation**
- C1 remise correcte aux bornes 0 et 100.
- C2 requête SQL paramétrée.
- C3 aucune régression sur les appels existants.

## 2. Exécuter
Changement mineur : deux corrections locales, un test.

**Tâche 0 : confirmer H1 et H2** (lecture seule)
- Chercher le type de `db` et les appelants hors du dépôt. Si introuvables, demander à la personne.

**Tâche 1 : corriger `total`**
- Fichier : `src/pay.py`.
- Changement : `sum(prices) * (1 - discount / 100)`.
- Décision à prendre (H3) : lever `ValueError` si `discount` n'est pas dans [0, 100]. C'est plus sûr, mais cela change le comportement hors bornes. À valider avec la personne.
- Vérification : `python -m pytest tests/test_pay.py -q`.

**Tâche 2 : paramétrer `read_user`**
- Fichier : `src/pay.py`.
- Changement (si pilote sqlite3) : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Utiliser `%s` si H1 l'indique.
- Vérification : test avec une base sqlite en mémoire, voir la tâche 3.

**Tâche 3 : tests (le risque le justifie : argent et sécurité)**
- Fichier créé : `tests/test_pay.py`.
- Cas pour C1 : remise 0, 100, 10, et une liste vide.
- Cas pour C2 : `name = "x' OR '1'='1"` ne doit renvoyer aucune ligne. Un faux `db` enregistreur peut aussi vérifier que le SQL contient le marqueur et que `name` est passé en paramètre.
- Périmètre autorisé : `src/pay.py` et `tests/test_pay.py` seulement.

## 3. Vérifier
- **C1** : exécuter les tests des bornes. Preuve : sortie pytest avec 0 → somme, 100 → 0, 10 → 90 %.
- **C2** : le test d'injection passe, et `grep -n "WHERE name = '" src/pay.py` ne retourne rien. Preuve : sortie des deux commandes.
- **C3** : les signatures sont identiques (`git diff` limité aux corps de fonction). Pour les appelants, une preuve complète n'existe que si H2 est confirmée. Sinon, noter C3 « vérifié sur le dépôt seulement, appelants externes non contrôlés ».
- Ne rien annoncer comme validé tant que pytest n'a pas été exécuté. Distinguer « attendu » de « vérifié ».

## 4. Agir
- **Écart sur C1** : si un appelant passait déjà une fraction 0-1, le corriger ou ajouter une conversion explicite avec la personne. Ne pas deviner.
- **Écart sur C2** : si le marqueur est rejeté par le pilote, passer à l'autre style (H1) et relancer les tests.
- **Standardiser** : garder `tests/test_pay.py` dans le dépôt. Ajouter la règle « aucun SQL par concaténation » à la revue de code.
- **Suite** : la personne ou un agent exécute ce plan après confirmation de H1, H2 et H3.
