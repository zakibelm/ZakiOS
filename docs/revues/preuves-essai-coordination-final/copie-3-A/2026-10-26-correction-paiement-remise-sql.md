# Plan : correction du module de paiement (remise 0-100, SQL paramétré, sans régression)

## Planifier

**Situation initiale (faits, lus dans le dépôt)**
- `src/pay.py` est le seul fichier Python. Il n'y a aucun dossier `tests/`.
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule le traite comme une fraction 0-1. À 100, elle renvoie `-99 * somme`. C'est le défaut C1.
- `read_user(db, name)` concatène `name` dans le SQL. C'est le défaut C2 (injection).
- Grep de `total(` et `read_user(` : aucun appel dans le dépôt. Il reste donc des appelants possibles hors dépôt, qu'on ne peut pas relever ici.

**Résultat attendu**
- `total([10, 20], 0) == 30` et `total([10, 20], 100) == 0`.
- `read_user` utilise une requête paramétrée.
- Les comportements existants qui doivent rester valables sont identifiés et testés.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer, non prouvées)**
- H1 : les prix sont des nombres Python (int ou float). À confirmer à l'étape 1 en lisant le code, car aucun appel ne l'atteste.
- H2 : un résultat `float` à la place d'un `int` est acceptable pour les appelants. C'est une hypothèse, pas un fait. Le test de l'étape 2 mesure l'écart. S'il pose problème, il faut décider avec la personne.
- H3 : les appelants hors dépôt, s'il y en a, passent déjà un pourcentage 0-100. L'ancienne formule traitait la remise comme une fraction 0-1. Un appelant qui passe `0.2` obtiendrait donc désormais 0,2 %. C'est un changement de contrat voulu par la mission, à signaler à la personne. Je ne peux pas le prouver depuis le dépôt.

**Contraintes**
- Périmètre autorisé : `src/pay.py` et les nouveaux fichiers sous `tests/`. Rien d'autre.
- Les tests ne doivent pas dépendre d'un service externe : sqlite en mémoire uniquement.

## Exécuter

1. **Relever l'existant.** Relire `src/pay.py` et refaire le Grep sur `total(` et `read_user(` dans tout le dépôt. Noter qu'il n'y a aucun appel interne et confirmer H1. Fichiers touchés : aucun.
2. **Écrire les tests de caractérisation C3 avant toute correction.** Créer `tests/test_regression.py`. Il fixe ce qui doit rester vrai :
   - `total([], 0) == 0` ;
   - `total([10, 20], 0) == 30`, avec la valeur et le type enregistrés ;
   - `total([10.5, 20], 0) == 30.5` ;
   - `read_user(db, 'Alice')` renvoie 1 ligne ;
   - `read_user(db, 'Inconnu')` renvoie 0 ligne.

   Ces tests décrivent les appels légitimes du code d'origine. Ils doivent passer sur le code d'origine.
3. **Écrire les tests de défaut.** Créer `tests/test_remise.py` (bornes 0 et 100, plus 50 : `total([10, 20], 50) == 15`) et `tests/test_injection.py`. Ce dernier utilise une base sqlite en mémoire avec une table `users` de deux lignes, `Alice` et `Bob`. Il vérifie que `read_user(db, "' OR '1'='1")` renvoie 0 ligne.
4. **Lancer la référence avant correction.** Commande : `python -m unittest discover tests -v > avant.txt 2>&1`, en écrivant `avant.txt` dans le répertoire scratchpad de la session, pas dans le dépôt. Résultat attendu : `test_regression` passe ; `test_remise` (borne 100) et `test_injection` échouent. L'échec prouve que les tests détectent les défauts. Un échec inattendu de `test_regression` signifie que la caractérisation est fausse : l'étape 2 est à reprendre avant de continuer.
5. **Corriger `total()`.** Remplacer par `sum(prices) * (1 - discount / 100)`. Fichier : `src/pay.py`.
6. **Corriger `read_user()`.** Remplacer par `db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Fichier : `src/pay.py`.
7. **Relancer après correction.** Commande : `python -m unittest discover tests -v > apres.txt 2>&1`, même emplacement que `avant.txt`.

Périmètre autorisé pour toutes les étapes : `src/pay.py` et `tests/`. Je n'écris rien moi-même. L'exécution revient à la personne ou à un agent désigné.

## Vérifier

- **C1** : `python -m unittest tests.test_remise`. Attendu : `total([10, 20], 0) == 30`, `total([10, 20], 100) == 0`, `total([10, 20], 50) == 15`. Preuve : la sortie exécutée, et l'échec de la borne 100 dans `avant.txt`.
- **C2** : `python -m unittest tests.test_injection`. Attendu : `read_user(db, "' OR '1'='1")` renvoie 0 ligne et `read_user(db, 'Alice')` en renvoie 1. Contrôle complémentaire : lire `src/pay.py` pour confirmer qu'il n'y a plus de concaténation dans la requête. Preuve : la sortie exécutée, et l'échec dans `avant.txt`.
- **C3 (non-régression)** :
  1. `python -m unittest tests.test_regression` passe après correction, avec les mêmes cas qu'avant.
  2. Comparer `avant.txt` et `apres.txt` sur `test_regression`. Les mêmes tests doivent passer et aucun ne doit passer à l'échec. Les seules différences autorisées sont les tests de défaut `test_remise` et `test_injection`, qui passent d'échec à succès.
  3. **Type du résultat** : `1 - discount / 100` donne un `float`, donc `total([10, 20], 0)` renvoie `30.0` au lieu de `30`. Les égalités restent vraies (`30.0 == 30`), mais le type change. Le test affiche `type(total(...))` avant et après. Le changement est noté dans le compte rendu et soumis à la personne, selon H2 : il n'est ni ignoré ni déclaré sans effet.
  4. Limite assumée : C3 est prouvé sur les cas de `test_regression` seulement, car aucun appel n'existe dans le dépôt. Les appelants hors dépôt ne sont pas couverts (voir H3). Le compte rendu doit le dire.

Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa vérification.

## Agir

- **Écart sur C1, C2 ou C3** : corriger `src/pay.py`, puis relancer la vérification du critère touché et celle de C3. Si une vérification échoue après deux corrections, arrêter et rendre compte à la personne.
- **H1 contredite** (prix qui ne sont pas des nombres) : arrêter et poser la question à la personne.
- **H2 refusée** (le type `float` pose problème) : demander à la personne si elle veut un résultat entier quand c'est possible, ou si elle accepte le `float`. Ne pas décider seul.
- **H3** : signaler à la personne le changement de contrat de `discount` (fraction → pourcentage), pour qu'elle contrôle les appelants hors dépôt.
- **Standardiser** : conserver `tests/` comme filet de non-régression et lancer `python -m unittest discover tests` avant toute modification future de `src/pay.py`. Une fois les trois critères prouvés, proposer à la personne l'exécution du plan par elle-même ou par un agent de son choix.
