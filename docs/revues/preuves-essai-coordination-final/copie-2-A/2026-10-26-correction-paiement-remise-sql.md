# Plan : correction du module de paiement (remise 0-100, SQL paramétré, sans régression)

## Planifier

**Situation initiale (faits relevés par lecture le 2026-10-26)**
- `src/pay.py` est le seul fichier Python du dépôt. Il n'y a ni dossier `tests/` ni test existant.
- `total(prices, discount)` fait `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule le traite comme une fraction. Avec `discount=100`, elle donne `sum * -99`.
- `read_user(db, name)` concatène `name` dans le SQL, ce qui permet l'injection.
- Grep de `total(` et `read_user(` dans le dépôt : aucun appelant, seulement les deux définitions. Les appels « existants » ne sont donc pas visibles dans ce dépôt.

**Résultat attendu mesurable**
- `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`.
- `read_user` utilise un paramètre lié. Une entrée d'injection renvoie 0 ligne et `Alice` en renvoie 1.
- Les signatures `total(prices, discount)` et `read_user(db, name)` restent identiques, et `read_user` renvoie toujours le résultat de `db.execute(...)`.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer, non prouvées)**
- H1 : la remise est un nombre de 0 à 100. Le commentaire et la mission le disent, et l'étape 1 le reconfirme dans le code.
- H2 : les prix sont des int ou des float.
- H3 : des appelants existent hors de ce dépôt.
  - Si un appelant passe aujourd'hui une fraction (ex. `0.2`), le passage à 0-100 change son résultat. Ce changement est voulu par la mission. Il se signale, il ne se corrige pas.
- H4 : un retour de type `float` (au lieu de `int` pour `discount=0` avec des prix entiers) est acceptable. L'égalité numérique est conservée (`30.0 == 30`). Si la personne exige le type `int`, elle le dit avant l'étape 5.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`. Rien d'autre.
- Aucun montant en devise n'est introduit. Si des montants apparaissent, ils sont en $ CAD.
- Aucun nouvel outil externe : `unittest` et `sqlite3` de la bibliothèque standard.

## Exécuter

1. **Relever la situation (lecture seule).** Relire `src/pay.py` et refaire `Grep` de `total(|read_user(` dans tout le dépôt. Consigner le résultat (aujourd'hui : aucun appelant). Si des appelants apparaissent, les ajouter au test de non-régression de l'étape 2.
2. **Écrire les tests.** Fichiers créés : `tests/test_remise.py`, `tests/test_injection.py`, `tests/test_non_regression.py`.
   - `test_remise` : bornes 0 et 100, plus une valeur intermédiaire (ex. `total([10, 20], 50) == 15`).
   - `test_injection` : base sqlite en mémoire, table `users` avec `Alice` et `Bob`. `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1.
   - `test_non_regression` (C3) couvre quatre points :
     - signatures inchangées, vérifiées avec `inspect.signature` ;
     - `read_user(db, 'Alice')` et `read_user(db, 'Bob')` renvoient la même ligne qu avant correction (cas légitimes) ;
     - `total` renvoie une valeur numérique égale à `sum(prices)` pour `discount=0`, avec prix int et prix float ;
     - le type de retour de `total` est affirmé (`isinstance(..., (int, float))`) et consigné.
   - Ces tests sont écrits avant la correction parce que le risque (paiement, injection) le justifie.
3. **Exécuter la référence sur le code d'origine** : `python -m unittest discover tests -v 2>&1 | tee <scratchpad>/reference_avant.txt`.
   - Attendu : `test_remise` (borne 100) et `test_injection` échouent, ce qui prouve que les tests détectent les défauts.
   - Attendu : les cas légitimes de `test_non_regression` passent. Ils fixent le comportement de référence.
   - Conserver la sortie réelle (fichier `reference_avant.txt`) comme trace. Un échec attendu n'est une preuve que si la sortie réelle est conservée.
   - Relever aussi le type de retour d'origine : `python -c "from src.pay import total; print(type(total([10,20],0)))"` → noter le résultat (attendu `int`).
4. **Corriger `total()`** dans `src/pay.py` : `return sum(prices) * (1 - discount / 100)`. Le commentaire reste. La signature est inchangée.
5. **Corriger `read_user()`** dans `src/pay.py` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`. La signature est inchangée.
6. **Rejouer la suite** : `python -m unittest discover tests -v 2>&1 | tee <scratchpad>/apres.txt`, puis comparer avec la référence : `diff <scratchpad>/reference_avant.txt <scratchpad>/apres.txt`.

## Vérifier

| Critère | Preuve | Attendu |
|---|---|---|
| C1 | `python -m unittest tests.test_remise` | `total([10,20],0)==30`, `total([10,20],100)==0`, `total([10,20],50)==15` |
| C2 | `python -m unittest tests.test_injection` | injection → 0 ligne, `Alice` → 1 ligne. Échec constaté dans `reference_avant.txt`, réussite dans `apres.txt` |
| C3 | `python -m unittest tests.test_non_regression` et `diff` de l'étape 6 | Tous les tests de non-régression passent. Les seuls tests qui changent d'état entre avant et après sont ceux de C1 et C2 (échec → réussite). Aucun test passant avant ne devient échec. |

- **C3, type de retour.** Comparer le type relevé à l'étape 3 (`int`) au type après correction (`float`). Tout écart est consigné et soumis à H4. Il n'est ni masqué ni déclaré sans effet.
- **C3, limite connue.** Aucun appelant n'existe dans le dépôt. C3 est donc prouvé uniquement pour le comportement caractérisé par `test_non_regression`, pas pour des appelants externes (H3). Dans le compte rendu, C3 est « vérifié sur le comportement testé » et non « vérifié sur tous les appels ».
- **Distinction attendu / vérifié.** Un critère n'est déclaré vérifié qu'avec la sortie exécutée de sa commande. Sinon le compte rendu écrit « attendu, non vérifié » et nomme le contrôle manquant.

## Agir

- **Écart sur un critère** : corriger le code concerné, puis relancer la vérification du critère touché et la suite complète (C3).
- **Arrêt et compte rendu à la personne** dans trois cas :
  - H1 ou H2 est contredite ;
  - une vérification échoue après deux corrections ;
  - l'écart de type de retour (H4) ou un appelant passant une fraction (H3) est constaté.
- **Standardiser** : conserver `tests/` comme suite de non-régression du module de paiement, avec la commande `python -m unittest discover tests`. Conserver les traces `reference_avant.txt` et `apres.txt` dans le compte rendu.
- **Exécution** : la personne ou un agent peut exécuter ce plan. L'enregistrement du plan et les modifications de `src/pay.py` ne se font qu'avec son accord.
