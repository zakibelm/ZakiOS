# Plan : correction du module de paiement (remise 0-100, SQL paramétré) — v2

## Planifier

**Situation initiale (faits lus dans le dépôt le 2026-10-26)**
- `src/pay.py` est le seul fichier Python. Il n'y a pas de dossier `tests/`. Grep ne trouve aucun appelant de `total()` ou `read_user()`. Il ne trouve aucune création ni import de `db`, ni référence à sqlite ou à un autre pilote. Il ne trouve que les définitions.
- `total(prices, discount)` calcule `sum(prices) * (1 - discount)`. Le commentaire dit « pourcentage 0-100 », mais la formule traite `discount` comme une fraction. Aujourd'hui, 100 donne `-99 × somme`.
- `read_user(db, name)` construit le SQL par concaténation : `"... WHERE name = '" + name + "'"`. Elle est injectable.

**Résultat attendu (mesurable)**
- `total([10.0, 20.0], 0)` vaut 30.0 et `total([10.0, 20.0], 100)` vaut 0.
- `read_user` passe `name` en paramètre et ne concatène plus.
- `python -m unittest discover tests` donne 0 échec après correction.

**Contraintes et périmètre autorisé**
- Fichiers touchés : `src/pay.py` et les nouveaux fichiers de `tests/`. Rien d'autre.
- Aucune dépendance nouvelle (unittest et sqlite3 de la bibliothèque standard).
- Les montants sont en $ CAD.

**Hypothèses (aucune n'est prouvée)**
- H1 : la remise est un pourcentage de 0 à 100. Source : un commentaire du code, qui est un indice faible. La formule actuelle dit autre chose. **À confirmer par la personne avant l'étape 2.** Aucun test ni code ne s'appuie sur H1 avant cette confirmation.
- H2 : les prix sont des int ou des float. Rien dans le dépôt ne le confirme. À confirmer par la personne.
- H3 : des appelants extérieurs au dépôt passent peut-être une fraction (0,15 par exemple). Inconnu. Le changement de sens les casserait, et une fraction de 1 passerait de « 100 % » à « 1 % » sans erreur. **À trancher avant l'étape 5.** Les issues sont définies à l'étape 1.
- H4 : `db` est une connexion sqlite3 (marqueur `?`). **Non prouvée.** Le dépôt ne montre pas d'où vient `db`. Les tests sqlite en mémoire de l'étape 3 créent leur propre base. Ils ne disent rien sur la connexion réelle de production. Les autres pilotes utilisent d'autres marqueurs (`%s` pour psycopg ou MySQL, `:nom` ou `%(nom)s` selon le pilote). **La personne doit donner le type réel de connexion avant l'étape 6.**

**Hors périmètre ou à trancher**
- Comportement hors de 0-100 (remise négative ou supérieure à 100) : **à trancher par la personne**. Par défaut le plan ne modifie pas ce comportement et ne lève aucune exception. Si la personne veut une validation, on ajoute un critère et un test.

**Critères d'acceptation**
- C1 : remise correcte aux bornes. Remise 0 → somme des prix. Remise 100 → 0.
- C2 : requête SQL paramétrée. Avec un pilote dont le marqueur est confirmé (H4), une charge d'injection ne retourne aucune ligne et un nom normal retourne uniquement la ligne correspondante. Les tests sqlite en mémoire prouvent la logique de paramétrage sous sqlite. Ils ne prouvent pas la compatibilité avec la connexion de production tant que H4 n'est pas levée.
- C3 : aucune régression sur les appels existants. Le dépôt n'en contient aucun. Les cas testés sont donc des comportements actuels qui doivent rester identiques (étape 4). Le risque des appelants externes (H3) a une issue définie à l'étape 1.

## Exécuter

1. **Relevé et décisions (lecture seule, puis questions).**
   - Relire `src/pay.py`. Avec Grep, chercher `total(`, `read_user(`, ainsi que `sqlite`, `psycopg`, `mysql`, `connect(` et la création ou l'import de `db`, dans tout le dépôt (scripts, notebooks, docs compris). Écrire la liste des appelants et l'origine de `db` dans le compte rendu. Constat actuel : zéro appelant, origine de `db` introuvable.
   - Poser à la personne ces questions et consigner les réponses avant de continuer :
     - H1 : la remise est-elle un pourcentage 0-100 ?
     - H2 : quels types de prix ?
     - H3 : existe-t-il des appelants externes, et que passent-ils ?
     - H4 : quel est le type réel de connexion `db` ?
     - Que faire hors de 0-100 ?
   - **Issues pour H3 :**
     - Réponse « non, aucun appelant externe » : consigner l'accord, continuer.
     - Réponse « oui, ils passent des fractions » : **arrêter l'étape 5.** Proposer à la personne l'une des deux issues, qu'elle choisit : (a) migrer les appelants vers le pourcentage, avec la liste des appelants à modifier et leur propriétaire ; (b) garder le sens fraction pour eux, par exemple avec un nouveau paramètre ou une nouvelle fonction. Dans les deux cas, ajouter des cas de test pour ces appelants (étape 4).
     - Réponse « inconnu » : ne pas modifier `total()` tant que la personne n'a pas consigné par écrit qu'elle accepte le risque de rupture. Sans cet accord, l'exécution s'arrête à l'étape 4.
   - **Arrêt si H1 est infirmée** : revoir le plan. Les étapes 2 à 7 ne sont pas lancées.
   - **Arrêt si le pilote de H4 n'est pas sqlite3** (marqueur différent) : adapter le marqueur dans l'étape 6 (`%s`, `:nom`, etc.) et le test de C2 à ce pilote, après accord de la personne. Si le pilote de test n'est pas disponible sans dépendance nouvelle, arrêter et demander. C2 reste alors « non vérifié ».
   - Vérification : le compte rendu contient la liste des appelants, l'origine de `db` (ou « introuvable ») et les réponses de la personne.

2. **Tests de C1** (seulement après la réponse sur H1). Fichier `tests/test_remise.py`, avec `assertAlmostEqual` pour tous les flottants :
   - `total([10.0, 20.0], 0)` ≈ 30.0.
   - `total([10.0, 20.0], 100)` ≈ 0.
   - `total([10.0, 20.0], 50)` ≈ 15.0.
   - Un cas avec des entiers si H2 est confirmée.

3. **Tests de C2.** Fichier `tests/test_injection.py` : base `sqlite3` en mémoire, table `users(name)` avec `Alice` et `Bob` (ou le pilote confirmé en H4).
   - `read_user(db, "Alice").fetchall()` retourne **uniquement** la ligne Alice.
   - `read_user(db, "' OR '1'='1").fetchall()` retourne une liste vide.
   - `read_user(db, "Zoe").fetchall()` retourne une liste vide.
   - Limite à consigner : ces tests créent leur propre base. Ils ne vérifient pas la connexion de production.

4. **Tests de C3.** Fichier `tests/test_appels_existants.py` : comportements actuels qui doivent rester identiques.
   - `total([10.0, 20.0], 0)` ≈ 30.0 et `total([], 0)` == 0.
   - `read_user(db, "Alice").fetchall()` retourne la ligne Alice.
   - Ce qui change volontairement (le sens d'une remise non nulle) n'est pas une régression. Cela est documenté dans le compte rendu, sans test d'invariant.
   - Si l'étape 1 a trouvé des appelants réels, ou si la personne en a signalé d'externes (H3), ajouter leurs cas avec la valeur attendue calculée à la main, après la décision de la personne.

5. **Référence avant correction.** Lancer `python -m unittest discover tests` sur le code d'origine.
   - Attendu : `test_appels_existants` passe, `test_remise` échoue (cas 100 et 50), `test_injection` échoue (la charge retourne les deux lignes).
   - Si `test_remise` ou `test_injection` passent sur l'ancien code, le test ne détecte pas le défaut. Le corriger avant de continuer.
   - Si l'import `src.pay` échoue, ajuster l'import des tests (pas `src/pay.py`) et relancer.
   - **Barrière avant l'étape 6 :** H1 confirmée, issue de H3 consignée.

6. **Corriger `total()`** dans `src/pay.py` : `return sum(prices) * (1 - discount / 100)`. Mettre à jour le commentaire. Appliquer l'issue choisie pour H3 si elle impose autre chose.

7. **Corriger `read_user()`** dans `src/pay.py` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Le marqueur `?` n'est valable que si H4 confirme sqlite3 ; sinon utiliser celui du pilote confirmé.

8. **Vérification après correction.** Lancer `python -m unittest discover tests`.
   - Sortie attendue : les trois fichiers de test au vert, 0 échec, 0 erreur. Conserver la sortie complète comme trace.

## Vérifier

| Critère | Preuve attendue | Statut |
|---|---|---|
| C1 | Sortie de l'étape 8 : `test_remise` vert (bornes 0 et 100). Sortie de l'étape 5 : rouge avant correction. Réponse H1 consignée. | Attendu, non vérifié |
| C2 | Sortie de l'étape 8 : `test_injection` vert, rouge à l'étape 5. **Plus** : type réel de `db` (H4) consigné et marqueur identique à celui du code. Sans cette réponse, C2 est vérifié seulement sous sqlite en mémoire, et le compte rendu le dit. | Attendu, non vérifié |
| C3 | Sortie de l'étape 8 : `test_appels_existants` vert, comme à l'étape 5. Relevé de l'étape 1 (zéro appelant dans le dépôt). Issue de H3 consignée : migration, ou accord écrit de la personne. | Attendu, non vérifié |

- Un critère n'est déclaré satisfait que si la sortie exécutée de sa vérification est présente. Aucun test n'est lancé à ce stade.
- Limites connues : C3 ne couvre pas les appelants extérieurs sans la réponse de la personne sur H3. C2 ne couvre pas la connexion de production sans la réponse sur H4.

## Agir

- **Écart constaté :** corriger le code concerné, puis relancer `python -m unittest discover tests` et revérifier le critère touché.
- **Arrêt et compte rendu à la personne** dans ces cas :
  - H1 ou H2 contredite.
  - H3 : appelant externe en fraction, ou réponse « inconnu » sans accord écrit.
  - H4 : pilote différent de sqlite3, ou marqueur de paramètre qui diffère.
  - Hors-bornes à trancher.
  - Une vérification qui échoue encore après deux corrections.
- **Standardiser**, après accord de la personne :
  - Garder les trois fichiers de test dans `tests/`.
  - Lancer `python -m unittest discover tests` avant chaque modification de `src/pay.py`.
  - Interdire la concaténation dans les requêtes SQL.
- **Exécution :** la personne ou un agent peut exécuter ce plan. Les étapes 2, 3, 4, 6 et 7 modifient des fichiers et demandent un agent avec outil d'écriture, ou la personne.
