# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier
**Situation initiale (faits lus dans `src/pay.py`)**
- `total(prices, discount)` retourne `sum(prices) * (1 - discount)`. Le commentaire annonce un pourcentage 0-100, mais la formule suppose 0-1. À 100, elle donne `-99 * sum`, ce qui est faux.
- `read_user(db, name)` concatène `name` dans le SQL, donc la requête est injectable.
- Aucun test et aucun appelant dans le dépôt (seul `src/pay.py` existe en `.py`). Les appelants éventuels sont donc inconnus.

**Résultat attendu mesurable**
- `total(prices, 0) == sum(prices)`.
- `total(prices, 100) == 0`.
- `total(prices, 50) == sum(prices) / 2`.
- `read_user` ne retourne aucune ligne pour l'entrée `' OR '1'='1`.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`.
- Aucune autre modification.
- Aucun outil d'écriture pour l'agent qui rédige ce plan. L'exécution revient à la personne ou à un agent désigné.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Décisions et hypothèses**
- D1 (décision proposée, à confirmer par la personne) : une remise hors de 0-100 (négative ou supérieure à 100) lève `ValueError`. Elle n'est pas ignorée silencieusement, pour ne pas masquer une ancienne remise sur l'échelle 0-1.
- H1 : la remise est un nombre de 0 à 100. Le commentaire du code le dit. Si l'étape 1 montre des appelants sur l'échelle 0-1, arrêter et poser la question (voir Agir).
- H2 : les prix sont des nombres Python (int ou float). Elle est confirmée par les appels relevés à l'étape 1.
- Limite connue sur C3 : le passage de l'échelle 0-1 à l'échelle 0-100 change par construction le résultat des appels à remise non nulle sur l'ancienne échelle. Ce n'est pas une régression si l'appel est migré. C'est un écart à signaler, pas à masquer.

## Exécuter
1. **Relever la situation.** Lire `src/pay.py` (Read). Relever avec Grep tous les appels de `total(` et `read_user(` dans le dépôt, y compris hors `src/` et `tests/`, avec la valeur de remise de chacun.
   - Si aucun appelant n'existe, le consigner : C3 est alors couvert par les seuls cas de référence de l'étape 3 et le dit explicitement.
   - Si un appelant utilise une remise sur l'échelle 0-1, arrêter (voir Agir).
2. **Créer `tests/test_remise.py`** (C1). Cas attendus :
   - `total([10, 20], 0) == 30`
   - `total([10, 20], 100) == 0`
   - `total([10, 20], 50) == 15`
   - `total([10, 20], -1)` lève `ValueError`
   - `total([10, 20], 101)` lève `ValueError`
3. **Créer `tests/test_injection.py`** (C2). Base sqlite en mémoire, table `users(name)` avec deux lignes, `Alice` et `Bob`. Cas attendus :
   - `read_user(db, "Alice")` retourne exactement 1 ligne, `Alice`.
   - `read_user(db, "' OR '1'='1")` retourne 0 ligne. Sur le code d'origine, cette entrée retourne les 2 lignes, ce qui prouve que le test détecte l'injection.
   - `read_user(db, "x'; DROP TABLE users; --")` ne détruit pas la table. Un `SELECT` sur `users` après l'appel retourne encore 2 lignes.
4. **Créer `tests/test_appels_existants.py`** (C3). Un cas par appel relevé à l'étape 1, remises nulles et non nulles, avec la valeur attendue calculée à la main et consignée dans le test.
   - Pour un appel à remise non nulle sur l'échelle 0-100, la valeur attendue est `sum(prices) * (1 - d/100)`.
   - Pour un appel sur l'échelle 0-1, voir Agir.
   - Sans appelant, y mettre deux cas de référence de signature : `total([10, 20], 0) == 30` et `read_user(db, "Alice")` retourne `Alice`.
5. **Vérification avant correction (référence).** Lancer `python -m unittest discover tests` sur le code d'origine et consigner la sortie.
   - Attendu : les cas de `test_appels_existants` à remise nulle passent.
   - Attendu : `test_remise` (bornes 100, 50, hors bornes) et `test_injection` (entrée malveillante) échouent.
   - Si l'un de ces tests passe sur le code d'origine, il ne détecte pas le défaut : le corriger avant d'aller plus loin.
6. **Corriger `total()` dans `src/pay.py`.** Lever `ValueError` si `not 0 <= discount <= 100`, puis retourner `sum(prices) * (1 - discount / 100)`.
7. **Corriger `read_user()` dans `src/pay.py`** : `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.

## Vérifier
Lancer `python -m unittest discover tests` après les étapes 6 et 7, puis consigner la sortie complète. Comparer chaque critère à son test :

| Critère | Preuve | Résultat attendu |
|---|---|---|
| C1 | `test_remise` | Remise 0 donne le total, remise 100 donne 0, remise 50 donne la moitié. -1 et 101 lèvent `ValueError`. |
| C2 | `test_injection` + relecture du code | `' OR '1'='1` retourne 0 ligne. La table reste intacte. La relecture de `read_user` confirme `?` et un tuple de paramètres, sans concaténation. |
| C3 | `test_appels_existants` | Tous les cas passent avec les mêmes valeurs qu'avant la correction (remise nulle) ou avec les valeurs calculées à la main (remise non nulle). |

- Contrôle complémentaire pour C2 : `git diff src/pay.py` ne doit montrer aucun `+` de concaténation dans la requête.
- Un critère n'est déclaré satisfait que si sa sortie exécutée est consignée. Sans exécution, le rapport écrit « attendu, non vérifié » et nomme le contrôle manquant.
- Écarts : les expliquer un par un, avec la sortie en preuve.

## Agir
- **Écart sur un critère** : corriger le code concerné, puis relancer la commande de la section Vérifier en entier.
- **Hypothèse contredite** : si H1 ou H2 est contredite (par exemple un appelant utilise l'échelle 0-1), arrêter avant la correction du code et poser la question à la personne. Options à lui présenter : migrer les appelants vers l'échelle 0-100, ou garder la compatibilité. La décision lui revient.
- **Décision D1** : si la personne préfère ignorer ou borner une remise hors de 0-100 au lieu de lever `ValueError`, ajuster l'étape 6 et le test hors bornes, puis relancer la vérification.
- **Échec persistant** : si une vérification échoue après deux corrections, arrêter et rendre compte avec les sorties.
- **Standardiser** : garder les trois fichiers de tests dans `tests/` et lancer `python -m unittest discover tests` avant toute modification future de `src/pay.py`. Consigner la sortie de référence (avant) et la sortie finale (après).
- **Exécution** : ce plan peut être exécuté par la personne ou par un agent disposant d'un outil d'écriture, après sa validation des décisions D1 et H1.
