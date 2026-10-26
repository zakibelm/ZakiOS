"""Pilote supervisé : interface web + API autour du coordinateur existant (`zakios.mission`).

Principe : le navigateur n'implémente AUCUNE règle de coordination. Il envoie une mission, affiche ce que le serveur
rapporte et n'expose une action (confirmer l'enregistrement) que si le serveur la déclare possible. Clés, appels aux
modèles et enregistrement restent côté serveur ; chaque mission s'exécute dans un espace jetable."""
