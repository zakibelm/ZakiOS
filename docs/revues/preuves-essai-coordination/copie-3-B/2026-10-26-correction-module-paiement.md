# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier
**Situation initiale (faits lus dans le projet)**
- `src/pay.py` est le seul fichier Python. Il contient `total(prices, discount)` et `read_user(db, name)`.
- `total()` calcule `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100. Avec 100, le résultat est donc `-99 * sum`, ce qui est faux. Avec 0, il est correct par hasard.
- `read_user()` concatène `name` dans la requête SQL (injection possible).
- Un Grep sur `total(` et `read_user(` ne trouve aucun appel dans le dépôt, hors les définitions. Il n'y a pas de dossier `tests/`.
- Conséquence pour C3 : « les appels existants » ne sont pas visibles dans ce dépôt. Les appelants éventuels sont hors dépôt et inconnus.

**Résultat attendu (mesurable)**
- `total([10, 20], 0) == 30`, `total([10, 20], 50) == 15` et `total([10, 20], 100) == 0`.
- `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1.
- Les signatures et le type de retour restent inchangés. `read_user` renvoie toujours ce que renvoie `db.execute`.

**Hypothèses (à confirmer, non prouvées)**
- H1 : `discount` est un pourcentage de 0 à 100. Source : le commentaire. Si un appelant externe passe une fraction 0-1, la correction change son résultat. C'est un risque de régression que ce dépôt ne permet pas de mesurer. À demander à la personne.
- H2 : les prix sont des int ou des float.
- H3 (décision demandée à la personne avant l'étape 5) : une remise hors de 0-100 est **rejetée** par `ValueError`. Défaut proposé, parce qu'un calcul silencieux de montant négatif ou supérieur au prix est plus dangereux pour un paiement. Autre choix possible : hors périmètre, sans test ni contrôle. Sans réponse, le plan applique le défaut et le signale dans le compte rendu.
- H4 : l'arrondi monétaire (en $ CAD, au cent) est hors périmètre. Les tests comparent avec `assertAlmostEqual` (7 décimales), pour ne pas dépendre des erreurs d'arrondi des flottants. À confirmer.

**Contraintes**
- Périmètre : `src/pay.py` et de nouveaux fichiers sous `tests/`. Aucun autre fichier n'est modifié.
- Aucune dépendance ajoutée (`unittest` et `sqlite3` de la bibliothèque standard).

**Critères d'acceptation**
- C1 : remise correcte aux bornes 0 et 100, et à une valeur intermédiaire (50). Le comportement hors bornes est décidé selon H3.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants. Le périmètre vérifiable est celui des tests de caractérisation de l'étape 3, et non les appelants externes inconnus (voir H1).

## Exécuter
1. Relire `src/pay.py` et refaire le Grep de `total(` et `read_user(` sur tout le dépôt. Si des appelants apparaissent, les ajouter à l'étape 3. Si le code contredit H1 ou H2, arrêter et poser la question à la personne.
2. Créer `tests/test_remise.py` avec les cas suivants :
   - `total([10, 20], 0) == 30`
   - `total([10, 20], 50) == 15`
   - `total([10, 20], 100) == 0`
   - selon H3, `-1` et `101` lèvent `ValueError`.
3. Créer `tests/test_injection.py` : base sqlite en mémoire, table `users` avec `Alice` et `Bob`. Les tests appellent `.fetchall()` sur le retour de `read_user`, qui est un curseur. Cas : `'Alice'` donne 1 ligne, `"' OR '1'='1"` donne 0 ligne, `"Bob"` donne 1 ligne.
4. Créer `tests/test_appels_existants.py` (caractérisation du comportement à conserver). Comme aucun appel n'existe dans le dépôt, utiliser des appels construits sur les signatures actuelles, avec valeur attendue calculée à la main :
   - `total([10, 20], 0) == 30`, `total([], 0) == 0`, `total([5], 0) == 5`
   - `read_user(db, 'Alice')` renvoie un objet avec `fetchall()`, et la ligne obtenue est identique à celle du code d'origine.
5. Lancer `python -m unittest discover tests` **sur le code d'origine**, avant toute correction, et conserver la sortie. Attendu :
   - `test_appels_existants` : tous les cas passent (référence).
   - `test_remise` : les cas 50 et 100 échouent. Le cas 0 passe déjà, car `1 - 0 == 1` : c'est normal et c'est consigné. Les cas `ValueError` échouent aussi.
   - `test_injection` : le cas d'injection échoue (il renvoie 2 lignes).
   - Les règles d'arrêt de la section Agir s'appliquent à ce résultat.
6. Corriger `total()` : `sum(prices) * (1 - discount / 100)`, précédé, selon H3, de `if not 0 <= discount <= 100: raise ValueError("discount doit être entre 0 et 100")`.
7. Corriger `read_user()` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
8. Lancer la vérification de la section suivante.

## Vérifier
Chaque critère est déclaré satisfait seulement avec la sortie exécutée de sa commande.
- **C1** : `python -m unittest tests.test_remise -v`. Attendu : tous les cas passent (0 → 30, 50 → 15, 100 → 0 et, selon H3, rejet de -1 et 101). Preuve : sortie `OK`. Un cas qui échouait à l'étape 5 doit maintenant passer.
- **C2** : `python -m unittest tests.test_injection -v`. Attendu : l'injection renvoie 0 ligne, `Alice` et `Bob` renvoient 1 ligne chacun. Complément par Grep : aucune concaténation `+ name` dans `src/pay.py`. Preuve : sortie `OK` et résultat du Grep.
- **C3** :
  - `python -m unittest tests.test_appels_existants -v`. Attendu : tous les tests passent, comme à l'étape 5 sur le code d'origine.
  - `python -m unittest discover tests`. Attendu : tous les tests de la suite passent, avec `OK` et aucun échec ni erreur.
  - Limite déclarée : cette preuve couvre les appels de caractérisation, pas les appelants externes. Tant que H1 n'est pas confirmée, C3 est « vérifié pour les cas testés » et non « vérifié pour tous les appelants ».

## Agir
**Règles d'arrêt (à l'étape 5, avant toute correction).** Arrêter, ne rien corriger et rendre compte à la personne avec la sortie obtenue si :
- `test_appels_existants` échoue sur le code d'origine : la référence est invalide, car le test ou l'hypothèse sur le comportement actuel est faux ;
- le cas 50 ou 100 de `test_remise`, ou le cas d'injection de `test_injection`, passe déjà : le test ne détecte pas le défaut, ou le défaut est absent ;
- H1 ou H2 est contredite par la lecture du code.

Le cas 0 de `test_remise` qui passe avant correction est attendu. Il ne déclenche pas l'arrêt.

**Écart après correction.**
- Corriger le code concerné, puis relancer la vérification du critère touché et la suite complète.
- Après deux corrections infructueuses sur un même critère, arrêter et rendre compte à la personne.
- Si la suite complète révèle une régression sur un critère déjà vérifié, relancer aussi la vérification de ce critère.

**Standardiser.**
- Conserver `tests/` et la commande `python -m unittest discover tests` comme contrôle de non-régression du module.
- Consigner la décision H3, l'arrondi H4 et la limite de C3.
- Consigner la sortie du lancement de référence de l'étape 5.

**Exécution.** La personne ou un agent peut exécuter ce plan. L'agent n'a pas d'outil d'écriture dans ce rôle de planification : un agent d'exécution doit recevoir une permission explicite pour écrire dans `src/pay.py` et `tests/`.
