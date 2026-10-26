Chemin proposé : docs/plans/2026-10-26-paiement-remise.md
=== DEBUT DU PLAN ZAKIOS ===
# Plan : correction du module de paiement (remise 0-100, SQL paramétré)

## Planifier
Critères d'acceptation donnés par la mission :
- C1 — remise correcte aux bornes 0 et 100.
- C2 — requête SQL paramétrée.

Hypothèse à confirmer : la remise est un pourcentage entier de 0 à 100.

## Exécuter
1. Corriger `total()` : `sum(prices) * (1 - discount / 100)`.
2. Réécrire `read_user()` avec une requête paramétrée.
3. Créer `tests/test_remise.py` (bornes 0 et 100, injection).

## Vérifier
- C1 : `pytest tests/test_remise.py` couvre les bornes 0 et 100 ; attendu : total(prix,0)==somme et total(prix,100)==0.
- C2 : `grep -n "execute(" src/pay.py` ne montre aucune concaténation ; test d'injection `' OR '1'='1` sans effet.

## Agir
Si un écart est constaté : action corrective = corriger puis relancer la vérification concernée ; ne rien déclarer terminé tant que chaque critère n'a pas de preuve exécutée.
=== FIN DU PLAN ZAKIOS ===
