# ZakiOS : mémoire de projet pour Claude Code

Catalogue de composants Claude Code (agents, skills, commandes, hooks, mods) sans redondance, avec provenance vérifiable. Statut : catalogue exploratoire en lecture seule, avec validation humaine. Lis `README.md` pour l'état chiffré et `docs/METHODOLOGIE.md` pour la méthode REA.

## Commandes
- Tests (270) : `python3 -m unittest discover -s tests -t .`
- Revalider le catalogue : `python3 -m zakios verify`
- Régénérer : `python3 -m zakios build` (exige `sources/<owner>/<repo>` cloné aux commits de `sources.json`)
- Dépendance unique : PyYAML (`pip install -r requirements.txt`). Plateforme : Linux seulement.

## Règles non négociables
- Les sources ne sont jamais modifiées. `catalog/` est généré : on ne l'édite pas à la main (régénérer puis `verify`).
- Aucun composant tiers n'est copié sans licence vérifiée et attribution. Chaque fiche garde source, commit complet (40 caractères) et empreinte SHA-256.
- Un hook, un plugin ou un mod n'est jamais décidé par un score : audit par comportement obligatoire.
- Un composant au YAML invalide n'est jamais utilisé comme référence.
- Une décision humaine est liée à l'empreinte du paquet : si le contenu change, la validation est périmée. Ne touche pas à `decisions/validated.json` ni `decisions/licenses.json` sans demande explicite de la personne.
- Un score de similarité est un indice de lecture, jamais une preuve d'équivalence ni de nouveauté.

## Façon de travailler
- Méthode PDCA du Socle (`socle/REGLES.md`) : distinguer fait, hypothèse et preuve ; attendu et vérifié. Ne jamais annoncer « validé » sans avoir exécuté le contrôle.
- Format de présentation : Problème → Action → Résultat. Montants en $ CAD.
- Toute modification du moteur (`zakios/`) vient avec un test ; la suite complète et `verify` doivent passer avant de proposer un commit.
- Une variante ZakiOS (`variantes/`) est un brouillon de contenu original : en-tête de provenance, première ligne `ZAKIOS-SOCLE v1 · PDCA`, outils au minimum nécessaire, test associé.
- Avant de proposer un composant : chercher s'il en existe déjà un équivalent dans le Socle (règle sans redondance).

## Décisions qui attendent la personne
- Choix de la licence du code de ZakiOS (ne pas en choisir une).
- Validation humaine des lots de variantes avant toute installation réelle.

## Pour aller plus loin
`docs/FEUILLE-DE-ROUTE.md` (étapes restantes), `docs/ACTIVATION.md` (installation par projet), `docs/CIBLE.md` (architecture visée), `docs/PROFIL.md` (profil de travail), `docs/PRATIQUES.md` (où mettre quoi, échecs fréquents, sécurité), `docs/GRILLE-AUDIT-HOOKS.md` (audit des hooks).
