# Plan : docstring et test minimal pour total(prices, discount) (src/pay.py)

## 1. Planifier
**Situation initiale (faits lus)**
- `src/pay.py` contient `total(prices, discount)` : un commentaire dit « pourcentage 0-100 », sans docstring. Le calcul est `sum(prices) * (1 - discount)`.
- Aucun fichier de test trouvé dans le projet (Glob `**/*test*` vide). Outil de test non confirmé (hypothèse : pytest).
- Le même fichier contient `read_user`, qui concatène `name` dans du SQL (risque d'injection). C'est hors mission : signalé, non touché.

**Écart bloquant (fait)** : avec le code actuel, `discount=100` donne `sum * -99`, et `discount=50` donne `sum * -49`. Le code est cohérent avec une fraction 0-1, pas avec un pourcentage 0-100. Une docstring conforme à R1 serait donc fausse tant que le code n'est pas corrigé.

**Décision requise de la personne (avant Exécuter)**
- Option A (recommandée) : autoriser la correction minimale `sum(prices) * (1 - discount / 100)`. La docstring, le test et le code deviennent alors cohérents.
- Option B : ne pas toucher au code. La docstring décrit R1, et le test `discount=100` est marqué `xfail` avec la raison. L'écart reste documenté mais non corrigé.

**Résultat attendu (mesurable)**
- `total` a une docstring qui décrit `discount` comme un pourcentage de 0 à 100.
- Un test couvre `discount=0` et `discount=100`.

**Contraintes**
- Périmètre : `src/pay.py` (docstring, et correction seulement avec l'accord de l'option A) et un nouveau fichier de test. Ne pas toucher `read_user`.
- Pas d'écriture par l'agent de planification.

**Critères d'acceptation**
- R1 : la docstring décrit discount comme un pourcentage de 0 à 100.
- R2 : un test couvre au moins discount=0 et discount=100.

## 2. Exécuter
1. **Confirmer l'option A ou B** avec la personne. Fichiers touchés : aucun.
2. **Docstring** : remplacer le commentaire par une docstring. Elle indique que `prices` est un itérable de nombres, que `discount` est un pourcentage de 0 à 100, et que la fonction renvoie la somme moins ce pourcentage. Fichier : `src/pay.py`. Vérification : `python -c "import sys; sys.path.insert(0,'src'); import pay; print(pay.total.__doc__)"`.
3. **(Option A seulement)** Corriger le calcul en `sum(prices) * (1 - discount / 100)`. Fichier : `src/pay.py`.
4. **Test minimal** : créer `tests/test_pay.py` (chemin à confirmer).
   - `total([10, 20], 0) == 30`
   - `total([10, 20], 100) == 0`
   - Option B : le second test est marqué `xfail` avec la raison « code utilise une fraction, pas un pourcentage ».
   - Vérification : `python -m pytest tests/test_pay.py -v`. Si pytest est absent, utiliser `python -m unittest` et adapter le fichier.

## 3. Vérifier
- R1 : lire la docstring affichée à l'étape 2 et y trouver « pourcentage » et « 0 à 100 ». Preuve : sortie de la commande.
- R2 : sortie de pytest montrant les deux cas exécutés. Option A : deux réussites. Option B : une réussite et un `xfail` explicite.
- Contrôle de périmètre : `git diff --stat` ne doit lister que `src/pay.py` et le fichier de test, et `read_user` doit rester inchangé.
- Tant que ces commandes ne sont pas exécutées, rien n'est « vérifié », seulement « attendu ».

## 4. Agir
- Si `discount=100` échoue en option A : revoir la formule, puis relancer le test.
- Si pytest est absent ou si le dossier de tests diffère : adapter l'outil et le chemin, puis le noter.
- À standardiser : toute fonction publique reçoit une docstring qui précise l'unité et la plage de ses paramètres.
- À traiter séparément (hors mission) : ouvrir une tâche pour l'injection SQL de `read_user` (requête paramétrée).

Exécution proposée : par la personne ou par un agent disposant des droits d'écriture, après la décision A/B.
