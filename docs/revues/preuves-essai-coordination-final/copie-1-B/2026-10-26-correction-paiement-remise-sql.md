# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

ZAKIOS-SOCLE v1 · PDCA

## Planifier
**Problème.** `src/pay.py` contient deux défauts (faits, relevés par lecture du fichier) :
- `total()` calcule `sum(prices) * (1 - discount)`, alors que le commentaire dit que `discount` est un pourcentage 0-100. À 100, le résultat est `-99 × somme`, ce qui est faux.
- `read_user()` construit le SQL par concaténation de `name`, donc le code est vulnérable à l'injection.

**Situation initiale (faits relevés).**
- `src/pay.py` est le seul fichier Python du dépôt.
- Grep ne trouve aucun appel de `total()` ni de `read_user()` dans le dépôt, hors leur définition.
- Il n'y a pas de répertoire `tests/`.
- Les « appels existants » du critère C3 ne sont donc pas visibles dans ce dépôt. Les appelants éventuels sont hors dépôt, et leurs valeurs de remise sont inconnues.

**Résultat attendu (mesurable).**
- `total([10, 20], 0) == 30`.
- `total([10, 20], 100) == 0`.
- `read_user(db, "' OR '1'='1")` renvoie 0 ligne.
- `read_user(db, "Alice")` renvoie 1 ligne.
- Les signatures `total(prices, discount)` et `read_user(db, name)` restent inchangées.

**Contraintes.**
- Périmètre autorisé : `src/pay.py` et de nouveaux fichiers dans `tests/`.
- Aucune autre modification.
- Aucune dépendance ajoutée (`unittest` et `sqlite3` de la bibliothèque standard).

**Critères d'acceptation.**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses.**
- H1 : la remise est un nombre de 0 à 100. Elle est confirmée par le commentaire du code. Si une personne ou un appelant utilise en réalité une fraction 0-1, arrêter et poser la question.
- H2 : les prix sont des int ou des float. Elle n'est pas vérifiable dans le dépôt, faute d'appelants. À confirmer par la personne.
- H3 (nouvelle) : l'ancienne sémantique de la remise (`1 - discount`) était une fraction 0-1. La correction la change volontairement pour tout appel avec remise non nulle. Seuls les appels à remise nulle sont donc garantis sans changement. Le plan le signale explicitement et ne le déclare pas « sans régression » pour les autres appels.

## Exécuter
1. **Relever les appels existants** (lecture seule).
   - Fichiers : aucun modifié.
   - Commande : Grep `total\(|read_user\(` sur tout le dépôt, y compris `src/` et `tests/`.
   - Relever pour chaque appel la valeur de `discount` passée à `total()`, et la forme de `name` passée à `read_user()`.
   - Si aucun appel n'est trouvé (cas actuel), le consigner et demander à la personne la liste des appelants externes et leurs remises.
   - **Signaler tout appel dont la remise est non nulle** : sa sémantique va changer (H3), et il faut une décision de la personne avant de continuer.
2. **Créer les tests** (fichiers : `tests/test_remise.py`, `tests/test_injection.py`).
   - `tests/test_remise.py` : `total([10, 20], 0)` et `total([10, 20], 100)`, ainsi qu'un cas intermédiaire `total([10, 20], 50) == 15`. Utiliser `assertAlmostEqual` (7 décimales) pour tous les cas non entiers, afin d'éviter les écarts d'arrondi des flottants. Les bornes sont aussi vérifiées en valeur, sans exiger un type précis.
   - `tests/test_injection.py` : base sqlite en mémoire, table `users` avec `Alice` et `Bob`. Compter les lignes avec `fetchall()`.
3. **Créer `tests/test_appels_existants.py`** (fichier : ce seul fichier).
   - Il reprend chaque appel relevé à l'étape 1 avec ses vraies valeurs de remise.
   - Pour la remise nulle, la valeur attendue est la somme des prix calculée à la main, indépendamment du code.
   - Pour une remise non nulle, la valeur attendue est notée comme « changement de sémantique voulu » (pourcentage) et non comme référence d'avant-correction.
   - Sans appel relevé, utiliser au minimum la forme de l'interface : `total(prices, 0)` avec des listes variées (vide, un élément, plusieurs, flottants) et `read_user(db, "Alice")` renvoyant bien une ligne.
4. **Mesurer le comportement d'origine, avant toute correction.**
   - Commande : `python -m unittest discover tests -v`.
   - Attendu : `test_appels_existants` passe pour les cas à remise nulle (référence). `test_remise` (borne 100 et cas 50) et `test_injection` échouent, ce qui prouve que les tests détectent les défauts.
   - Conserver la sortie complète comme trace.
5. **Corriger `total()`** (fichier : `src/pay.py`).
   - Code : `return sum(prices) * (100 - discount) / 100`.
   - Cette forme donne exactement 0 à la borne 100 et évite l'écart de `1 - discount / 100`.
   - Commande de vérification : `python -m unittest tests.test_remise`.
6. **Corriger `read_user()`** (fichier : `src/pay.py`).
   - Code : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
   - Commande de vérification : `python -m unittest tests.test_injection`.

## Vérifier
Chaque critère n'est déclaré satisfait qu'avec la sortie exécutée de sa commande.
- **C1** : `python -m unittest tests.test_remise`.
  - Attendu : `OK`.
  - `total([10, 20], 0)` vaut 30 et `total([10, 20], 100)` vaut 0 (`assertAlmostEqual`). Le cas 50 vaut 15.
  - Ce test a échoué à l'étape 4, avant correction.
- **C2** : `python -m unittest tests.test_injection`.
  - Attendu : `OK`.
  - `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, "Alice")` en renvoie 1.
  - Ce test a échoué à l'étape 4.
  - Contrôle complémentaire : Grep `"SELECT` dans `src/pay.py` ne doit montrer aucune concaténation `+` dans la requête.
- **C3** : `python -m unittest tests.test_appels_existants`.
  - Attendu : `OK`, avec les mêmes totaux qu'avant correction pour les appels à remise nulle (comparer à la sortie de l'étape 4).
  - Puis exécuter la suite entière : `python -m unittest discover tests -v`. Attendu : tous les tests `OK`, zéro échec.
  - Limite à dire clairement : C3 n'est prouvé que pour les appels relevés à l'étape 1 et pour la remise nulle. Tout appel à remise non nulle change de sémantique par conception. Si des appelants hors dépôt existent et n'ont pas été fournis, C3 reste **non vérifié** pour eux.

## Agir
- **Écart constaté** : corriger le code concerné dans `src/pay.py`, puis relancer la vérification du critère touché et ensuite la suite complète (`python -m unittest discover tests`).
- **Arrêt et compte rendu à la personne** si :
  - H1 ou H2 est contredite ;
  - un appel existant utilise une remise non nulle (décision requise : adapter l'appelant ou conserver l'ancienne sémantique) ;
  - une vérification échoue après deux corrections.
- **Standardiser** :
  - garder `tests/` dans le dépôt et lancer `python -m unittest discover tests` avant chaque modification de `src/pay.py` ;
  - noter dans le commentaire de `total()` que `discount` est un pourcentage 0-100 ;
  - toujours utiliser des requêtes paramétrées (`?`) pour toute nouvelle lecture en base.
- **Exécution** : le plan peut être exécuté par la personne ou par un agent disposant des droits d'écriture sur `src/pay.py` et `tests/`. Aucun skill particulier n'est requis.
