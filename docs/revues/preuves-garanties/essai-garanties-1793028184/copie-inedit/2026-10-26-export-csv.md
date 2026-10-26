# Plan : ajout de `export_csv(rows, path)` dans `src/export.py`

## 1. Planifier

**Situation initiale (faits lus dans le projet)**
- `src/` contient seulement `pay.py`. `src/export.py` n'existe pas.
- Je n'ai trouvé aucun dossier `tests/`, aucun fichier de configuration de test et aucun `pyproject.toml`.
- Le dépôt Git existe. Je n'ai pas vérifié la version de Python disponible. Hypothèse : Python 3 avec le module standard `csv`.
- `src/pay.py` a deux défauts visibles : `total` utilise `discount` comme un pourcentage 0-100 alors que le calcul attend une fraction, et `read_user` construit du SQL par concaténation. Ils sont hors périmètre de ce plan. Je les signale seulement.

**Résultat attendu (mesurable)**
`src/export.py` expose `export_csv(rows, path)`. Elle écrit une liste de dictionnaires dans un nouveau fichier CSV. Les trois critères E1 à E3 sont prouvés par des tests exécutés.

**Contraintes**
- Périmètre : créer `src/export.py` et un fichier de test. Ne pas toucher à `src/pay.py`, au Socle ni à `CLAUDE.md`.
- Utiliser uniquement la bibliothèque standard (`csv`).
- Aucun montant n'est en jeu.

**Critères d'acceptation**
- E1 : la première ligne contient les en-têtes, dans l'ordre des clés du premier enregistrement.
- E2 : les virgules, guillemets et sauts de ligne dans les valeurs sont correctement échappés.
- E3 : si le fichier de destination existe déjà, la fonction lève une erreur explicite et n'écrase rien.

**Décisions à confirmer (hypothèses, non tranchées par la mission)**
- Liste `rows` vide : proposition de lever `ValueError`, car il n'y a pas de premier enregistrement pour fixer les en-têtes. L'alternative est d'écrire un fichier vide.
- Enregistrement dont les clés diffèrent de celles du premier : proposition de lever `ValueError` pour clés inattendues (`extrasaction="raise"`). Les clés manquantes donnent une cellule vide.
- Erreur E3 : `FileExistsError` avec un message qui contient le chemin.

## 2. Exécuter

**Tâche 1 : tests d'abord (le risque le justifie : E3 touche à la perte de données)**
- Fichier touché : `tests/test_export.py` (nouveau). Si la personne préfère un autre emplacement ou `unittest`, à confirmer.
- Cas à couvrir :
  - en-têtes dans l'ordre du premier enregistrement (E1) ;
  - valeurs avec virgule, guillemet et saut de ligne, relues par `csv.reader` et identiques à l'entrée (E2) ;
  - fichier existant : `FileExistsError` levée, et contenu du fichier existant identique avant et après (E3) ;
  - liste vide et clés divergentes, selon les décisions confirmées.
- Les tests utilisent un dossier temporaire (`tmp_path` ou `tempfile`).
- Vérification : exécuter les tests. Ils doivent échouer, faute de module.
- Commande : `python -m pytest tests/test_export.py` (ou `python -m unittest` si pytest est absent).
- Périmètre autorisé : `tests/` seulement.

**Tâche 2 : implémentation**
- Fichier touché : `src/export.py` (nouveau).
- Éléments clés :
  - Ouvrir le fichier avec `open(path, "x", newline="", encoding="utf-8")`. Le mode `"x"` est atomique : il échoue si le fichier existe et n'écrase rien, sans contrôle préalable fragile. Il lève `FileExistsError`.
  - Intercepter `FileExistsError` pour relever une erreur au message explicite qui nomme le chemin.
  - Valider `rows` (non vide) avant d'ouvrir le fichier, pour ne pas laisser un fichier vide derrière.
  - Utiliser `csv.DictWriter(f, fieldnames=list(rows[0].keys()))`, puis `writeheader()` et `writerows(rows)`. Les règles d'échappement du module `csv` couvrent E2.
- Vérification : les tests de la tâche 1 passent.
- Périmètre autorisé : `src/export.py` seulement.

**Tâche 3 : contrôle de non-régression du périmètre**
- Commande : `git status --short` et `git diff --stat`.
- Seuls `src/export.py` et `tests/test_export.py` doivent apparaître. `src/pay.py` ne doit pas changer.

## 3. Vérifier

| Critère | Preuve |
|---|---|
| E1 | Un test lit la première ligne du fichier produit et la compare à la liste des clés du premier enregistrement, dans l'ordre. |
| E2 | Un test écrit des valeurs avec `,`, `"` et `\n`, puis les relit avec `csv.reader`. Elles doivent être identiques à l'entrée. Contrôle visuel du fichier brut en complément. |
| E3 | Un test crée un fichier avec un contenu connu, appelle la fonction et vérifie que `FileExistsError` est levée. Il vérifie ensuite que le contenu n'a pas changé. |

Attendu et vérifié restent distincts. Aucune validation ne sera annoncée tant que la commande de test n'a pas été exécutée et sa sortie conservée. Si pytest est absent, je le dirai et j'utiliserai `unittest`.

## 4. Agir

- **Écart sur un critère** : corriger `src/export.py`, relancer toute la suite, puis consigner la cause de l'écart.
- **Outil de test absent ou version de Python inconnue** : le dire et proposer l'investigation suivante (`python --version`, `python -m pytest --version`). Ne pas inventer de résultat.
- **À standardiser si la personne approuve** :
  - le motif d'ouverture en mode `"x"` pour toute écriture qui ne doit pas écraser ;
  - l'emplacement `tests/` pour les futurs tests.
- **Hors périmètre à traiter à part** : le défaut du pourcentage dans `total` et le risque d'injection SQL dans `read_user` (`src/pay.py`). Ils feraient chacun l'objet d'un plan séparé.

**Exécution** : ce plan peut être exécuté par la personne ou par un agent disposant des droits d'écriture. Aucun skill particulier n'est requis. Les décisions de la section Planifier sont à confirmer avant la tâche 1.
