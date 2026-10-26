# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier
Critères d'acceptation donnés par la mission :
- C1 — remise correcte aux bornes 0 et 100.
- C2 — requête SQL paramétrée.
- C3 — aucune régression sur les appels existants.

Hypothèse H1 : la remise est un nombre de 0 à 100 (le commentaire de `src/pay.py` le dit) ; elle est confirmée à l'étape 1 par lecture du code, et le plan s'arrête avec une question à la personne si le code contredit cela.
Hypothèse H2 : les prix sont des nombres Python (int ou float) ; confirmée à l'étape 1 par les appels relevés.

## Exécuter
1. Lire `src/pay.py` (Read) et relever avec Grep tous les appels de `total()` et `read_user()` dans `src/` et `tests/`.
2. Créer `tests/test_remise.py` (bornes 0 et 100) et `tests/test_injection.py` (base sqlite en mémoire, table `users` de deux lignes `Alice` et `Bob`).
3. Créer `tests/test_appels_existants.py` : les appels relevés à l'étape 1, avec remise nulle, et pour valeur attendue la somme des prix calculée à la main.
4. Lancer `python -m unittest discover tests` sur le code d'origine, avant toute correction : `test_appels_existants` doit passer (référence) ; `test_remise` et `test_injection` doivent échouer (preuve que les tests détectent les défauts).
5. Corriger `total()` : `sum(prices) * (1 - discount / 100)`.
6. Corriger `read_user()` : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.

## Vérifier
- C1 : `python -m unittest tests.test_remise` ; attendu : `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`.
- C2 : `python -m unittest tests.test_injection` ; attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1 ; ce test a échoué avant correction.
- C3 : `python -m unittest tests.test_appels_existants` après correction ; attendu : mêmes valeurs qu'avant correction (référence de l'étape 4), aucune différence.

## Agir
Si un écart est constaté : action corrective = corriger le code concerné puis relancer la vérification du critère touché. Si une hypothèse H1 ou H2 est contredite, ou si une vérification échoue après deux corrections, arrêter et rendre compte à la personne. Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification.
