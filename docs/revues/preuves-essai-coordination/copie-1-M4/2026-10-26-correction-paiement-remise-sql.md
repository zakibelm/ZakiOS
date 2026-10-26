# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier

**Situation initiale (faits, relevés par lecture le 2026-10-26)**
- `src/pay.py` est le seul fichier Python du dépôt. Il contient deux fonctions.
- `total(prices, discount)` renvoie `sum(prices) * (1 - discount)`. Le commentaire dit que `discount` est un pourcentage 0-100. Pour 0 ≤ d ≤ 100, la formule est fausse : `d=100` donne `-99 × somme`, et `d=20` donne `-19 × somme`. Seul `d=0` est correct.
- `read_user(db, name)` construit la requête par concaténation : `"SELECT * FROM users WHERE name = '" + name + "'"`. Elle est donc injectable.
- Un Grep de `total(` et `read_user(` ne trouve que les deux définitions. Il n'y a aucun appel dans le dépôt, et aucun dossier `tests/` n'a été trouvé (le Glob ne cherchait que `*.py` : à reconfirmer à l'étape 1).

**Résultat attendu (mesurable)**
- `total([100], 0) == 100`, `total([100], 100) == 0`, `total([100], 20) == 80`.
- `read_user` avec la charge `' OR '1'='1` ne renvoie aucune ligne. Avec `Alice`, elle renvoie la seule ligne d'Alice.

**Critères d'acceptation (donnés par la mission)**
- C1 : remise correcte aux bornes 0 et 100.
- C2 : requête SQL paramétrée.
- C3 : aucune régression sur les appels existants.

**Hypothèses (à confirmer à l'étape 1 ; si l'une est contredite, arrêter et poser la question à la personne)**
- H1 : la remise est un nombre de 0 à 100. Cela est confirmé par le commentaire, mais pas par un appelant, car aucun appel n'est visible.
- H2 : les prix sont des nombres Python (int ou float). Non confirmée : aucun appel ne le montre.
- H3 : `db` est un objet qui expose `execute(sql, params)` à la façon de `sqlite3` (connexion ou curseur), et `name` est une chaîne. La forme actuelle `db.execute(...)` est lue dans le code. Le style de paramètre `?` n'est valable que pour sqlite3 : un autre pilote (`%s`, `:name`) exigerait un autre marqueur. Confirmée à l'étape 1 par lecture du code et des appelants.
- H4 : aucun appelant externe au dépôt ne passe une remise sous forme de fraction (0.2 pour 20 %). Non vérifiable ici. C'est le risque principal de C3 (voir étape 3).

**Contraintes**
- Périmètre autorisé : `src/pay.py` et la création de fichiers sous `tests/`. Aucun autre fichier n'est modifié.
- Aucune validation de plage (rejet des remises < 0 ou > 100) n'est ajoutée sans décision de la personne (question Q1).
- Comparaison de flottants avec `assertAlmostEqual`.

**Questions pour la personne**
- Q1 : une remise hors de 0-100 doit-elle lever une erreur, ou rester non contrôlée comme aujourd'hui ?
- Q2 : existe-t-il des appelants hors dépôt, notamment avec une remise non nulle ? Si oui, quelle valeur passent-ils (fraction ou pourcentage) ?

## Exécuter

1. **Relever la situation.** Fichiers : aucun modifié. Commandes : Read de `src/pay.py`, Grep de `total\(|read_user\(` dans tout le dépôt, Glob de `tests/**` et de `**/*test*`. Relever chaque appel avec sa valeur de remise, séparer les remises nulles et non nulles, et confirmer H1 à H3.
   - **Si un appel avec remise non nulle existe :** le signaler à la personne avant toute correction. Sa sémantique change avec la nouvelle formule.
   - **S'il n'y en a aucun dans le dépôt :** le noter tel quel et poser Q2.
2. **Écrire les tests** (fichiers créés : `tests/test_remise.py`, `tests/test_injection.py`, `tests/test_appels_existants.py`). Ajouter un `tests/__init__.py` vide si `discover` n'importe pas `src`.
   - `test_remise.py` :
     - `total([100], 0) == 100` ;
     - `total([100], 100) == 0` ;
     - `total([50, 50], 20) == 80`.
   - `test_injection.py` :
     - base `sqlite3` en mémoire, table `users(name)` avec deux lignes, `Alice` et `Bob` ;
     - charge malveillante `' OR '1'='1` : l'assertion est `fetchall() == []` ;
     - nom légitime `Alice` : l'assertion est `fetchall()` ne contient que la ligne d'Alice ;
     - nom contenant une apostrophe (`O'Brien`) : aucune exception levée, aucune ligne.
   - `test_appels_existants.py` :
     - un test par appel relevé à l'étape 1, avec remise nulle, la valeur attendue étant la somme des prix calculée à la main ;
     - un test par appel à remise non nulle relevé, avec le résultat attendu convenu avec la personne (Q2).
     - Faute d'appel relevé, un test de caractérisation de remise non nulle : `total([100], 20) == 80`. Il est étiqueté comme dérivé du contrat du commentaire, et non d'un appelant réel.
3. **Mesurer avant correction.** Commande : `python -m unittest discover tests`, sur le code d'origine, sortie conservée (fichier `avant.txt` dans le scratchpad).
   - Attendu : les tests de remise 0 passent (référence) ;
   - Attendu : les tests de remise 100, de remise non nulle et d'injection échouent. Cela prouve que les tests détectent les défauts.
   - Si un test attendu en échec passe, corriger le test avant de continuer.
4. **Corriger `total()`** (fichier : `src/pay.py`) : `return sum(prices) * (1 - discount / 100)`.
5. **Corriger `read_user()`** (fichier : `src/pay.py`) : `return db.execute("SELECT * FROM users WHERE name = ?", (name,))`.
6. **Relancer après correction.** Commande : `python -m unittest discover tests`, sortie conservée (fichier `apres.txt`). Attendu : « OK », tous les tests passent. La sortie est conservée comme preuve, par critère (tableau de l'étape Vérifier).
7. **Contrôle de la portée.** Commande : `git diff --stat`. Attendu : seul `src/pay.py` est modifié, plus les fichiers de `tests/` créés.

## Vérifier

| Critère | Preuve attendue | Statut tant que l'étape 6 n'est pas exécutée |
|---|---|---|
| C1 | `test_remise` : OK dans `apres.txt` (bornes 0 et 100, plus un cas intermédiaire). Dans `avant.txt`, le test de borne 100 échouait. | attendu, non vérifié |
| C2 | `test_injection` : OK dans `apres.txt` (charge malveillante → aucune ligne ; `Alice` → sa ligne ; apostrophe → aucune erreur). Dans `avant.txt`, la charge renvoyait des lignes. Relecture du diff : plus de concaténation dans la requête. | attendu, non vérifié |
| C3 | `test_appels_existants` : OK avant et après (remise nulle inchangée). Les appels à remise non nulle sont listés et signalés à la personne ; leur test passe avec le résultat convenu. | attendu, non vérifié |

- Aucun critère n'est déclaré satisfait sans la sortie exécutée correspondante.
- **Limite de C3 :** il n'est prouvé que pour les appels relevés dans le dépôt et pour les tests écrits. Les appelants externes ne sont pas couverts tant que Q2 n'a pas de réponse.

## Agir

- **Écart constaté** : un test échoue dans `apres.txt`, ou le comportement avant/après de l'étape 3 diffère de l'attendu. Action : corriger le code ou le test concerné, relancer `python -m unittest discover tests`, et conserver la nouvelle sortie.
- **Arrêt et compte rendu à la personne :**
  - une hypothèse H1 à H4 est contredite ;
  - une vérification échoue encore après deux corrections ;
  - un appel à remise non nulle est trouvé, ou H4 reste non vérifiée (pour décision sur la sémantique).
- **À standardiser, si la personne l'accepte :**
  - garder les trois fichiers de tests dans `tests/` ;
  - y ajouter la commande `python -m unittest discover tests` comme contrôle avant tout changement de `src/pay.py` ;
  - si Q1 conduit à une validation de plage, ajouter un test dédié.

**Exécution proposée :** par la personne, ou par un agent doté d'outils d'écriture et d'exécution, dans le périmètre ci-dessus. L'enregistrement de ce plan est fait par la personne ou par un mécanisme contrôlé.
