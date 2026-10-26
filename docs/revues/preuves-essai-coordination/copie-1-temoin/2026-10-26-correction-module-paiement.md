# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré) — v2

## Planifier

**Situation initiale (faits, lus dans le projet)**
- `src/pay.py` contient deux fonctions :
  - `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire annonce un pourcentage 0-100, mais la formule traite `discount` comme une fraction 0-1. Défaut : `total([10, 20], 100)` donne `-2970`, et non `0`.
  - `read_user(db, name)` renvoie `db.execute("SELECT * FROM users WHERE name = '" + name + "'")`. Le nom est concaténé dans la requête : injection SQL possible.
- Le Grep sur tout le dépôt ne trouve aucun appel de `total()` ni de `read_user()` hors de leur définition. Il n'y a ni dossier `tests/` ni test existant.
- Conséquence : les « appels existants » du critère C3 ne sont pas connus dans ce dépôt. Le périmètre de C3 est donc à confirmer avec la personne (voir H4).

**Résultat attendu (mesurable)**
- `total(prices, d)` renvoie `sum(prices) * (1 - d/100)` pour `d` entre 0 et 100 inclus.
- `read_user(db, name)` passe `name` en paramètre de la requête, jamais par concaténation.

**Contraintes**
- Périmètre d'écriture : `src/pay.py` et le dossier `tests/` (nouveaux fichiers). Rien d'autre.
- Les valeurs de remise hors de 0-100 sont **hors périmètre** de C1. Elles ne sont ni testées ni corrigées. Si la personne veut un rejet explicite (exception), c'est une demande séparée.
- Changement de comportement **voulu** : pour toute remise non nulle, le résultat change (ancienne sémantique 0-1, nouvelle 0-100). C'est l'objet de la correction. Il doit être signalé à la personne (étape 3).

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer à l'étape 1 ; si l'une est contredite, arrêt et question à la personne)**
- H1 : la remise est un nombre de 0 à 100. Le commentaire du code le dit. Il faut confirmer qu'aucun appelant externe ne passe une fraction 0-1.
- H2 : les prix sont des nombres Python (int ou float).
- H3 : `db` est une connexion ou un curseur DB-API de type sqlite3, avec `db.execute(sql, params)` et le marqueur `?`. `read_user(db, name)` garde sa signature et renvoie ce que renvoie `db.execute(...)` (un curseur), sans transformation. Le nom des paramètres reste `prices`, `discount`, `db`, `name`. Si le pilote réel utilise un autre marqueur (`%s`, `:name`), le marqueur de l'étape 6 est adapté.
- H4 : les appelants existants se trouvent hors de ce dépôt ou n'existent pas. Dans ce cas, C3 est couvert par des appels représentatifs que la personne valide, et non par des appels réels. C'est une limite à déclarer, pas un détail.

## Exécuter

1. **Lecture et inventaire** (lecture seule). Relire `src/pay.py`. Faire un Grep de `total(` et `read_user(` sur tout le dépôt, y compris les fichiers non Python. Dresser la liste des appels trouvés, avec remise nulle ou non. Si la liste est vide, le dire et demander à la personne les appels réels ou un échantillon représentatif (H4). Vérifier H1 à H3.
2. **Tests de référence C3** : créer `tests/test_appels_existants.py`, avec des valeurs attendues fixées **avant** correction.
   - `total`, remise nulle : somme des prix calculée à la main (par exemple `total([10, 20], 0) == 30`).
   - `total`, remise non nulle : pour chaque appel relevé, valeur attendue sous la sémantique 0-100 (par exemple `total([10, 20], 50) == 15`). L'ancien code donne un autre résultat pour ces cas. C'est un écart **voulu**, noté pour l'étape 3.
   - `read_user` : base sqlite en mémoire, table `users` (`Alice`, `Bob`). Appel avec un nom existant : 1 ligne ; avec un nom absent : 0 ligne. Vérifier le type de retour (curseur) et le contenu via `fetchall()`.
3. **Tests C1** : créer `tests/test_remise.py`. Bornes 0 et 100 : `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`. Cas intermédiaires 50 et 33 avec `assertAlmostEqual` (par exemple `places=7`). Aucun test hors de 0-100.
4. **Tests C2** : créer `tests/test_injection.py` avec une base sqlite en mémoire. `read_user(db, "' OR '1'='1")` doit renvoyer 0 ligne ; `read_user(db, 'Alice')` doit en renvoyer 1.
5. **Référence avant correction** : lancer `python -m unittest discover tests` sur le code d'origine. Attendu :
   - réussissent : `test_appels_existants` pour les cas à remise nulle et pour `read_user` (nom existant ou absent) ;
   - échouent : `test_remise` (bornes et cas intermédiaires non nuls), `test_injection`, et les cas de `test_appels_existants` à remise non nulle (ancienne sémantique).
   Garder la sortie complète comme trace. Un test censé échouer qui passe est un défaut du test : le corriger avant de continuer.
6. **Corriger `total()`** : `return sum(prices) * (1 - discount / 100)`. Fichier touché : `src/pay.py`.
7. **Corriger `read_user()`** : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))` (marqueur adapté si H3 est contredite). Fichier touché : `src/pay.py`.

## Vérifier

Chaque critère est déclaré satisfait seulement avec la sortie réellement exécutée de sa commande, citée dans le compte rendu.
- **C1** : `python -m unittest tests.test_remise`. Attendu : bornes 0 et 100 exactes, cas 50 et 33 dans la tolérance. Périmètre déclaré : 0-100 uniquement.
- **C2** : `python -m unittest tests.test_injection`. Attendu : 0 ligne pour l'entrée d'injection, 1 ligne pour `Alice`. Ce test a échoué à l'étape 5. Contrôle complémentaire : Grep qui confirme qu'aucune concaténation SQL ne reste dans `src/pay.py`.
- **C3** : `python -m unittest tests.test_appels_existants`, puis la **suite complète** `python -m unittest discover tests`. Attendu :
  - `read_user` et `total` à remise nulle : valeurs identiques avant et après (référence de l'étape 5) ;
  - `total` à remise non nulle : écart par rapport à l'ancien code, **voulu**, listé un par un avec ancienne et nouvelle valeur ;
  - suite complète : 0 échec. Citer la sortie finale (nombre de tests, résultat).
- **Rapport à la personne** : liste des appels dont le résultat change à cause de la nouvelle sémantique 0-100, avec la demande de confirmer que l'écart est voulu. Rappeler la limite H4 si aucun appelant réel n'a été trouvé. Dire aussi ce qui n'est pas vérifié (valeurs hors 0-100, pilote de base autre que sqlite).

## Agir

- **Écart constaté** : corriger le code ou le test concerné, puis relancer la vérification du critère touché **et** la suite complète.
- **Hypothèse contredite** (H1 à H4) ou **échec persistant après deux corrections** : arrêter et rendre compte à la personne. Ne pas inventer de solution.
- **Standardiser** : garder les tests dans `tests/` et lancer `python -m unittest discover tests` avant chaque modification de `src/pay.py`. Toute nouvelle requête SQL du projet utilise des paramètres liés. Si la personne le souhaite, ouvrir une demande séparée pour valider la plage 0-100.
- **Exécution** : la personne ou un agent peut exécuter ce plan. L'enregistrement du fichier plan et les écritures dans `tests/` et `src/` sont à autoriser par la personne.
