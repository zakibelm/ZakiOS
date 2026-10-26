# Plan : gestion de prices=None dans total() (src/pay.py)

## 1. Planifier

**Situation initiale (faits lus dans le projet)**
- `src/pay.py` : `total(prices, discount)` fait `sum(prices) * (1 - discount)`.
- Avec `prices=None`, `sum(None)` lève déjà un `TypeError` (comportement attendu de Python, non exécuté ici).
- Aucun fichier de test n'existe dans le projet (Glob `**/*test*` : aucun résultat).

**Résultat attendu**
Un comportement défini et testé de `total()` quand `prices` vaut `None`.

**Blocage : contradiction entre critères**
- K1 : `total()` ne lève jamais d'exception, même si `prices` vaut `None`.
- K2 : `total()` lève `TypeError` si `prices` vaut `None`.
Les deux ne peuvent pas être vrais en même temps. Décision requise de la personne avant toute exécution :
- **Option A (conforme à K2)** : lever un `TypeError` explicite (message clair) pour `None`. K1 est alors reformulé en « aucune exception pour une liste valide ».
- **Option B (conforme à K1)** : traiter `None` comme une liste vide et retourner `0`. K2 est alors retiré ou inversé.
- Option C : autre comportement, à préciser par la personne.

**Contraintes**
- Périmètre autorisé : la fonction `total()` dans `src/pay.py`, plus un fichier de test à créer, une fois la décision prise.
- Ne pas modifier `read_user` ni la sémantique de `discount`.

**Critères d'acceptation (à figer après décision)**
- Après décision, un seul comportement pour `None` est retenu et testé.
- Les entrées valides (ex. `total([10, 20], 0)` donne `30`) restent inchangées.

## 2. Exécuter (seulement après la décision)

Tâche 0 : la personne choisit A, B ou C et corrige K1 ou K2 en conséquence. Aucun fichier touché.

Tâche 1 : modifier `total()`.
- Fichier : `src/pay.py`.
- Option A : ajouter en tête `if prices is None: raise TypeError("prices ne doit pas être None")`.
- Option B : ajouter en tête `if prices is None: return 0`.
- Vérification : `python -c "from src.pay import total; print(total([10,20],0))"` doit afficher `30`.

Tâche 2 : ajouter un test.
- Fichier à créer : `tests/test_pay.py` (emplacement à confirmer).
- Contenu : un cas `prices=None` selon l'option retenue (`pytest.raises(TypeError)` pour A, résultat `0` pour B), plus un cas valide.
- Vérification : `python -m pytest tests/test_pay.py`.

## 3. Vérifier
- Contradiction levée : preuve = critères K1/K2 reformulés, validés par la personne.
- Cas `None` : preuve = sortie de pytest sur le test de la tâche 2. Attendu : non vérifié tant que la commande n'a pas été exécutée.
- Non-régression : preuve = le cas valide passe.
- Aucune validation n'est annoncée avant l'exécution réelle de ces commandes.

## 4. Agir
- Écart sur un test : corriger `total()`, relancer pytest, consigner le résultat.
- Standardiser : garder le test comme garde-fou ; écrire les critères sans contradiction à l'avenir.
- Observations hors périmètre, à traiter dans des missions séparées :
  - Le commentaire dit que `discount` est un pourcentage 0-100, mais la formule `1 - discount` suppose une fraction 0-1.
  - `read_user` construit une requête SQL par concaténation, ce qui expose à l'injection SQL.

Exécution : la personne ou un agent peut l'effectuer une fois l'option choisie. Aucun skill particulier n'est requis.
