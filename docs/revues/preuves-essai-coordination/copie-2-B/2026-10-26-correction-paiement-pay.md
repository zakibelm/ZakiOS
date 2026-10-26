# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits lus dans `src/pay.py`)**
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, donc la formule est fausse. Exemple : `discount=100` donne `sum * -99`.
- `read_user(db, name)` concatène `name` dans la requête SQL (`"... WHERE name = '" + name + "'"`). C'est une injection SQL possible.
- Un Grep sur tout le dépôt ne trouve aucun appel de `total()` ni de `read_user()` en dehors de leurs définitions. Il n'y a pas non plus de dossier `tests/` ni de `docs/plans/` existant. Ces deux points sont des faits relevés à la date du plan, à revérifier à l'étape 1.

**Résultat attendu (mesurable)**
- `total` applique la remise en pourcentage : 0 donne la somme, 100 donne 0.
- `read_user` utilise une requête paramétrée.
- Le comportement hors du cas corrigé ne change pas.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer à l'étape 1, non prouvées à ce jour)**
- H1 : la remise est un nombre de 0 à 100. Le commentaire le dit. Si le code ou un appelant contredit cela, arrêt et question à la personne.
- H2 : les prix sont des nombres Python (int ou float). Le résultat de `total` peut donc être un float. Les comparaisons de C1 se font avec tolérance (`assertAlmostEqual`), pas avec `==` strict.
- H3 : `db` est une connexion ou un curseur `sqlite3` avec la méthode `execute`, et le style de paramètre est `?`. Le style dépend du pilote : `%s` pour psycopg ou MySQL, `:nom` ou `?` pour sqlite3. Si le pilote réel est autre, la syntaxe du paramètre change et le plan est révisé avant toute modification. Le Grep actuel ne montre aucun appelant qui l'établisse.
- H4 (décision de la personne) : comportement hors 0-100 (−1, 101, non numérique). Proposition par défaut : lever `ValueError` si `discount < 0` ou `discount > 100`. Ce choix change le comportement pour ces valeurs, qui sont déjà invalides selon le commentaire. La personne confirme ou choisit autre chose (par exemple écrêtage à 0-100). Aucune modification de `total()` n'est faite avant cette réponse.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et de nouveaux fichiers dans `tests/`. Rien d'autre n'est modifié.
- `CLAUDE.md` (racine) et `.claude/` ne sont pas touchés.
- Les signatures `total(prices, discount)` et `read_user(db, name)` restent identiques.

## Exécuter

1. **Confirmer la situation initiale.** Relire `src/pay.py` (Read) et refaire le Grep de `total(` et `read_user(` dans tout le dépôt. Établir H1, H2 et H3 à partir des appelants trouvés, de la création de la connexion et des imports. Poser la question H4 à la personne et attendre sa réponse. Aucun fichier n'est modifié. Condition d'arrêt : H1 ou H3 contredite, ou H4 sans réponse.
2. **Créer `tests/test_remise.py`** (C1).
   - `total([10, 20], 0)` ≈ 30.
   - `total([10, 20], 100)` ≈ 0.
   - Voisinage : `total([10, 20], 50)` ≈ 15.
   - Hors bornes selon H4 (par défaut : `total([10, 20], -1)` et `total([10, 20], 101)` lèvent `ValueError`).
   - Toutes les comparaisons numériques utilisent `assertAlmostEqual`.
3. **Créer `tests/test_injection.py`** (C2). Base sqlite en mémoire avec une table `users` de deux lignes, `Alice` et `Bob`. Contrôles :
   - `read_user(db, "' OR '1'='1")` renvoie 0 ligne.
   - `read_user(db, 'Alice')` en renvoie 1.
4. **Créer `tests/test_appels_existants.py`** (C3). L'étape 1 a relevé les appels existants. Si le dépôt n'en contient aucun, comme le Grep l'indique à ce jour, ce test fixe le comportement actuel qui doit rester stable :
   - `total([10, 20], 0)` ≈ 30, valeur calculée à la main.
   - `total([], 0)` ≈ 0.
   - `read_user(db, 'Alice')` renvoie la même ligne qu'avant la correction.
   Si des appels existants sont trouvés à l'étape 1, ils remplacent ou complètent ces cas. La valeur attendue est calculée à la main avec une remise nulle, pas à partir de la sortie du code corrigé. Limite à noter : sans appelant réel, C3 ne couvre que ces cas de référence.
5. **Établir la référence sur le code d'origine, avant correction.** Lancer `python -m unittest discover tests -v` et conserver la sortie.
   - `test_appels_existants` doit passer. C'est la référence de C3.
   - Dans `test_remise`, le cas `100` et les cas hors bornes doivent échouer. Le cas `0` passe déjà, car la formule d'origine donne `sum * 1`.
   - `test_injection` doit échouer, ce qui prouve que le test détecte le défaut.
   - Si un test attendu en échec passe, le test est mal conçu : le corriger avant d'avancer.
6. **Corriger `total()`** : valider `0 <= discount <= 100` selon H4, puis `return sum(prices) * (1 - discount / 100)`.
7. **Corriger `read_user()`** : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`, sous réserve que H3 soit confirmée.

## Vérifier

Chaque critère est déclaré satisfait seulement avec la sortie exécutée de sa commande.
- **C1** : `python -m unittest tests.test_remise -v`. Attendu : `total([10, 20], 0)` ≈ 30 et `total([10, 20], 100)` ≈ 0, comparés avec `assertAlmostEqual`. `-1` et `101` se comportent comme décidé en H4. Tous les tests passent.
- **C2** : `python -m unittest tests.test_injection -v`. Attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1. Ce test a échoué à l'étape 5. Contrôle complémentaire : `grep -n "WHERE name" src/pay.py` ne montre plus de concaténation.
- **C3** : `python -m unittest tests.test_appels_existants -v`. Attendu : le même résultat qu'à l'étape 5 (tous les tests passent, valeurs inchangées).
- **Non-régression globale** : relancer `python -m unittest discover tests -v` après les étapes 6 et 7. Attendu : tous les tests passent. Comparer avec la sortie de l'étape 5 : seuls les tests qui échouaient volontairement ont changé d'état, et `test_appels_existants` est identique.
- **Hypothèses** : H1, H2, H3 et H4 sont confirmées ou infirmées par écrit dans le compte rendu. Une hypothèse non confirmée reste signalée comme telle.

## Agir

- **Écart sur un critère** : corriger le code concerné, puis relancer la vérification de ce critère et la suite complète.
- **Arrêt et compte rendu à la personne** si :
  - H1 ou H3 est contredite ;
  - H4 n'a pas reçu de réponse ;
  - une vérification échoue après deux corrections ;
  - un test attendu en échec à l'étape 5 passe.
- **Standardiser** : conserver les trois fichiers de tests dans `tests/` et garder `python -m unittest discover tests` comme commande de contrôle du module. Consigner la décision H4 dans le compte rendu.
- **Exécution** : ce plan peut être exécuté par la personne ou par un agent, sans skill particulier. L'agent ne démarre qu'après la réponse à H4 et dans le périmètre autorisé.
