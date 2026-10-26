# Plan : correction du module de paiement `src/pay.py` (remise 0-100, SQL paramétré, sans régression)

ZAKIOS-SOCLE v1 · PDCA

## Planifier

**Situation initiale (faits lus dans le code le 2026-10-26)**
- `src/pay.py` contient deux fonctions :
  - `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100. Avec cette formule, `discount=0` donne `sum`, mais `discount=100` donne `-99 * sum`. Le défaut est donc établi par lecture du code. Il reste à le confirmer en exécutant le test.
  - `read_user(db, name)` concatène `name` dans le SQL, ce qui permet l'injection. Il renvoie le résultat de `db.execute(...)`, c'est-à-dire un curseur.
- Recherche des appelants (Grep sur tout le dépôt) : **aucun appel** de `total()` ou `read_user()` en dehors de leur définition. Il n'y a pas de dossier `tests/`. Il n'y a donc aucun appel existant à rejouer.
- Les types de retour d'origine sont des faits : `total` renvoie `int` si les prix sont des `int` et si `discount` est un `int`. `read_user` renvoie un curseur.

**Hypothèses (à confirmer ou infirmer à l'étape 1)**
- H1 : `discount` est un nombre de 0 à 100. Le commentaire le dit. Si une autre lecture montre que la remise est une fraction 0-1, on s'arrête et on pose la question à la personne.
- H2 : les prix sont des `int` ou des `float`. Aucun appelant ne l'infirme ni ne le confirme. À valider avec la personne.
- H3 : des appelants peuvent exister hors du dépôt (autre dépôt, service). Le Grep ne le voit pas. À demander à la personne.

**Résultat attendu (mesurable)**
- `total([10, 20], 0) == 30`, `total([10, 20], 100) == 0`, et `total([10, 20], 50) ≈ 15`.
- `read_user` utilise une requête paramétrée. Une entrée d'injection ne renvoie aucune ligne.
- Le comportement observable des appels existants est défini avant correction, puis reste identique ou documenté (voir C3).

**Contraintes**
- Périmètre : `src/pay.py` et les nouveaux fichiers sous `tests/`. Rien d'autre.
- Les signatures `total(prices, discount)` et `read_user(db, name)` ne changent pas.
- Le type de retour de `read_user` reste un curseur. On ne le remplace pas par une liste de lignes.

**Critères d'acceptation (repris de la mission)**
- C1 : remise correcte aux bornes 0 et 100, et à une valeur intermédiaire.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

## Exécuter

1. **Relever les appels et figer le comportement attendu** (Read, Grep).
   - Fichiers touchés : aucun.
   - Constat déjà fait : zéro appelant dans le dépôt. Redemander à la personne s'il existe des appelants externes (H3).
   - Définir le contrat de non-régression :
     - `total` : le type de retour reste numérique (`int` ou `float`). Pour `discount=0`, la valeur est égale à `sum(prices)`.
     - `read_user` : le retour reste un curseur qui expose `fetchall()`. Sur une entrée normale, il renvoie les mêmes lignes qu'avant.
     - Écart voulu et documenté : `total` renvoie désormais un `float` quand `discount` est un `int`. Exemple : `30` devient `30.0`. La comparaison par valeur reste vraie (`30 == 30.0`). Si un appelant externe dépend du type `int`, on le signale à la personne avant livraison.

2. **Écrire les tests** (aucune correction à ce stade).
   - `tests/test_remise.py` :
     - bornes 0 et 100, et cas intermédiaire 50 ;
     - comparaison avec `assertAlmostEqual` pour tous les cas, car le résultat peut être un `float`.
     - cas avec prix `float`, par exemple `[10.5, 20.25]` avec remise 10.
   - `tests/test_injection.py` : base sqlite en mémoire, table `users` avec `Alice` et `Bob`.
     - `read_user(db, "' OR '1'='1")` : 0 ligne.
     - `read_user(db, "Alice")` : 1 ligne.
   - `tests/test_non_regression.py` (C3) :
     - `total([10, 20], 0)` est égal à `30` ;
     - le retour de `total` est un nombre (`isinstance(x, (int, float))`) ;
     - `read_user(db, "Bob").fetchall()` renvoie la ligne de `Bob` ;
     - le retour de `read_user` expose `fetchall`.
   - Ajouter `tests/__init__.py` vide si `python -m unittest discover tests` ne trouve pas les modules. Le test importe `src.pay` ; vérifier le chemin d'import à ce moment.

3. **Lancer la suite sur le code d'origine** : `python -m unittest discover tests`.
   - Attendu (non vérifié tant que la commande n'a pas tourné) : `test_remise` échoue (bornes 100 et 50) et `test_injection` échoue. `test_non_regression` passe, car il décrit le comportement d'origine encore valide.
   - **Condition d'arrêt** : si `test_remise` ou `test_injection` passe sur le code d'origine, on s'arrête et on réexamine le test ou le diagnostic. On ne corrige pas tant que le test ne détecte pas le défaut. Si `test_non_regression` échoue sur le code d'origine, le contrat du point 1 est faux. On le corrige avant de continuer.
   - Conserver la sortie complète de la commande.

4. **Corriger `total()`** dans `src/pay.py` : `return sum(prices) * (1 - discount / 100)`. Commande : `python -m unittest tests.test_remise`.

5. **Corriger `read_user()`** dans `src/pay.py` : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`. Commande : `python -m unittest tests.test_injection`.

6. **Lancer la suite complète** : `python -m unittest discover tests`. Conserver la sortie.

## Vérifier

- **C1** : `python -m unittest tests.test_remise`.
  - Attendu : `total([10, 20], 0) ≈ 30`, `total([10, 20], 50) ≈ 15`, `total([10, 20], 100) ≈ 0`, plus le cas `float`. Tous passent.
  - Preuve de détection : ce test a échoué à l'étape 3.
- **C2** : `python -m unittest tests.test_injection`.
  - Attendu : l'entrée d'injection renvoie 0 ligne, `Alice` en renvoie 1. Ce test a échoué à l'étape 3.
  - Contrôle de lecture : le code contient `?` et un tuple de paramètres, sans concaténation de `name`. Vérifier avec `Grep` sur `src/pay.py` (motif `+ name`) : aucune occurrence attendue.
- **C3** : `python -m unittest discover tests`.
  - Attendu : 0 échec et 0 erreur, avec `test_non_regression` passé avant (étape 3) et après (étape 6).
  - Limite à écrire dans le compte rendu : ce contrôle ne couvre que le contrat défini à l'étape 1. Les appelants externes (H3) ne sont pas testés. C3 n'est déclaré satisfait que pour les appels connus du dépôt, qui sont au nombre de zéro. Dans ce cas, la personne doit confirmer l'absence d'appelants externes.
- Aucun critère n'est déclaré satisfait sans la sortie exécutée de sa commande. Si une commande n'a pas tourné, le compte rendu dit laquelle manque.

## Agir

- **Écart sur C1, C2 ou C3** : corriger le code concerné, puis relancer la vérification du critère touché et la suite complète.
- **Hypothèse contredite** (H1 ou H2) : arrêter et poser la question à la personne.
- **Test qui passe sur le code d'origine** (étape 3) : arrêter, réexaminer le test ou le diagnostic, ne pas corriger.
- **Deux corrections sans succès** sur la même vérification : arrêter et rendre compte à la personne avec les sorties obtenues.
- **Changement de type de `total`** (`int` vers `float`) : le mentionner dans le compte rendu. Si un appelant externe en dépend, demander la décision à la personne.
- **Standardiser** : garder les trois fichiers de test dans `tests/` et lancer `python -m unittest discover tests` avant chaque modification de `src/pay.py`. Règle de revue proposée : toute requête SQL de `src/` est paramétrée.

**Exécution** : ce plan peut être exécuté par la personne ou par un agent disposant d'un droit d'écriture sur `src/pay.py` et `tests/`. Cette autorisation est à donner par la personne. L'agent de planification ne peut pas écrire.
