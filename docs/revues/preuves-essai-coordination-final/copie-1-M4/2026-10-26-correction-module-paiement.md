# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits lus dans le code, Read et Grep) :**
- `src/pay.py` contient deux fonctions.
  - `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, donc la formule est fausse. À 100, elle donne `sum * -99`. À 0, elle donne le bon résultat.
  - `read_user(db, name)` concatène `name` dans le SQL : `"... WHERE name = '" + name + "'"`. C'est une injection SQL.
- Aucun appel de `total()` ni de `read_user()` n'existe dans le dépôt. Le Grep ne trouve que les deux définitions. Il n'y a pas de dossier `tests/` (à créer).
- Les appels existants ne sont donc pas relevables dans le dépôt. Ils sont peut-être hors dépôt.

**Hypothèses (à confirmer, non prouvées) :**
- H1 : `discount` est un pourcentage de 0 à 100. Le commentaire le dit et la mission le confirme.
- H2 : `prices` est un itérable de nombres Python (int ou float).
- H3 : `db` est une connexion `sqlite3`, car `db.execute(...)` existe sur `sqlite3.Connection`. Le style de paramètre `?` en dépend. Si la vraie base est autre, le style de paramètre change (`%s`, etc.).
- H4 : des appelants hors dépôt peuvent exister. S'ils passent la remise en fraction (0.2 pour 20 %), la correction change le sens de leur appel. C'est inhérent à la mission. Le plan ne peut ni le prouver ni l'exclure.

**Résultat attendu (mesurable) :**
- `total([10, 20], 0)` = 30.
- `total([10, 20], 100)` = 0.
- `total([10, 20], 50)` = 15.
- `read_user` envoie le nom comme paramètre lié, et une entrée malveillante ne renvoie aucune ligne.

**Contraintes :**
- Périmètre autorisé : `src/pay.py` (2 lignes) et nouveaux fichiers dans `tests/`.
- Les signatures `total(prices, discount)` et `read_user(db, name)` sont conservées.
- Aucune validation de plage ni nouvelle fonctionnalité n'est ajoutée. Elles ne sont pas demandées.
- Rien n'est écrit hors du périmètre.

**Critères d'acceptation (mission) :**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

## Exécuter

1. **Relever les appels.** Relancer `Grep "total\(|read_user\("` sur tout le dépôt, y compris les fichiers non `.py`, et noter le résultat.
   - Si des appels apparaissent, relever les valeurs de remise réellement passées (nulle, non nulle, fraction) et les ajouter à l'étape 3.
   - S'il n'y en a toujours aucun, le consigner tel quel : le périmètre de C3 est alors limité aux signatures et aux cas définis à l'étape 3, et la question H4 est posée à la personne.
2. **Créer les tests de défaut** (fichiers touchés : `tests/test_remise.py`, `tests/test_injection.py`).
   - `tests/test_remise.py` vérifie :
     - `total([10, 20], 0) == 30` ;
     - `total([10, 20], 100) == 0` ;
     - `total([10, 20], 50) == 15`, avec `assertAlmostEqual`.
   - `tests/test_injection.py` utilise une base sqlite en mémoire avec une table `users(name)` de deux lignes, `Alice` et `Bob`.
     - Entrée malveillante : `"x' OR '1'='1"`. Résultat attendu : `fetchall()` renvoie une liste vide.
     - Cas témoin : `read_user(db, "Alice")` renvoie exactement une ligne, `Alice`.
3. **Créer le test de non-régression** (fichier touché : `tests/test_appels_existants.py`).
   - Il contient les cas qui doivent donner le même résultat avant et après correction :
     - `total([10, 20], 0) == 30` ;
     - `total([], 0) == 0` ;
     - `read_user(db, "Alice")` renvoie une ligne ;
     - `read_user(db, "Inconnu")` renvoie zéro ligne.
   - Il ajoute les appels relevés à l'étape 1 avec leurs remises réelles.
   - Pour chaque appel relevé à remise non nulle ou en fraction, il documente l'écart de sens. L'attendu de ces cas est calculé à la main sous le sens « pourcentage 0-100 ».
4. **Référence avant correction** (commande : `python -m unittest discover tests -v`, sur le code d'origine, avant les étapes 5 et 6) :
   - `test_appels_existants` doit passer (référence de non-régression) ;
   - dans `test_remise`, les cas 100 et 50 doivent échouer ;
   - dans `test_injection`, le cas malveillant doit échouer (il renvoie 2 lignes) ;
   - conserver la sortie complète comme trace.
   - Si un test de défaut passe sur le code d'origine, il ne détecte rien : le corriger avant de continuer.
5. **Corriger `total()`** dans `src/pay.py` : `return sum(prices) * (1 - discount / 100)`.
6. **Corriger `read_user()`** dans `src/pay.py` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.

## Vérifier

Après les étapes 5 et 6, relancer `python -m unittest discover tests -v` et conserver la sortie. Tant que cette sortie n'existe pas, les critères restent « attendus » et non « vérifiés ».

| Critère | Preuve attendue | Statut |
|---|---|---|
| C1 | `test_remise` passe : 0 → 30, 100 → 0, 50 → 15. | attendu, non vérifié |
| C2 | `test_injection` passe : l'entrée `"x' OR '1'='1"` renvoie aucune ligne et `Alice` renvoie une ligne. Contrôle complémentaire : `git diff src/pay.py` ne montre plus de concaténation de `name` dans le SQL. | attendu, non vérifié |
| C3 | `test_appels_existants` reste vert, comme à l'étape 4. Les appels relevés à l'étape 1, ou leur absence, sont consignés. | attendu, non vérifié |

Limite connue de C3 : si l'étape 1 ne trouve aucun appel, C3 est prouvé seulement sur les cas de l'étape 3. Il ne prouve rien pour d'éventuels appelants hors dépôt (H4).

## Agir

- **Écart constaté :** corriger le code concerné, puis relancer la vérification du critère touché et la suite complète.
- **Hypothèse contredite :** H1, H2 ou H3 contredite à l'étape 1 ou 4, ou vérification en échec après deux corrections. Dans ces cas, arrêter et rendre compte à la personne.
- **Appelants avec remise en fraction (H4) :** ne pas les modifier sans accord, car c'est hors périmètre. Les signaler à la personne.
- **Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification.**
- **À standardiser :** garder les trois fichiers de test dans `tests/` comme contrôle permanent. Utiliser des requêtes paramétrées pour tout accès SQL du module.

Exécution proposée : par la personne, ou par un agent disposant des droits d'écriture sur `src/` et `tests/`. Cette permission relève de la personne.
