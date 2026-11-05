# Pratiques Claude Code retenues des lectures

Synthèse reformulée de quatre livres, pour guider le choix et l'audit des composants ZakiOS. Aucun passage n'est repris tel quel.

**Niveau de preuve.** Ce sont des affirmations de livres, pas des faits vérifiés ici. Le livre A se dit entièrement rédigé par une IA : tout point marqué (A) est à confirmer dans la documentation officielle avant d'être érigé en règle. Un point devient une règle ZakiOS seulement après un essai de comportement (méthode du Socle : attendu ≠ vérifié).

Sources : (A) *Claude Code: The Definitive Guide to Agentic Development*, V. Korostyshevskiy, 2026 · (B) *Build with Claude Code*, T. Jo, Packt · (C) *Build Your Own AI Assistant*, A. L. Zhang, BPB (centré sur les GPT d'OpenAI) · (D) *Claude AI Bible*, S. Clear.

## 1. Où mettre quoi : le coût de contexte décide (A, D)

| Mécanisme | Quand | Coût de contexte |
|---|---|---|
| CLAUDE.md | Règle utile à chaque tour (commandes de build, contraintes d'architecture) ; garder sous 500 lignes | Toujours chargé |
| Skill | Procédure propre à un type de tâche | Description toujours chargée ; corps à la demande |
| Subagent | Exploration volumineuse ; seul le résumé revient dans la session | Contexte isolé |
| MCP | Accès structuré à un service externe | Définitions chargées au démarrage, coût permanent |
| Hook | Faire respecter une règle ou vérifier sans consommer de contexte | Nul |

Problème → Action → Résultat : une règle toujours nécessaire placée dans un skill est violée quand le skill n'est pas chargé → la mettre dans CLAUDE.md ou en faire un hook → elle s'applique à chaque fois. Une référence longue placée dans CLAUDE.md pèse sur chaque requête → la déplacer dans un skill → contexte libéré.

## 2. Permissions (A)

- Évaluation dans l'ordre refus, demande, autorisation : un refus l'emporte toujours. Écrire les refus étroits et les autorisations larges.
- Refuser la lecture des secrets (`.env`, clés, identifiants) : le contenu d'un fichier lu part vers l'API.
- Hypothèse ZakiOS à tester : un refus sur `Edit`/`Write` ne couvre pas une écriture faite par `Bash` ; prévoir le bac à sable ou un hook PreToolUse.
- Un bac à sable au niveau du système d'exploitation limite le réseau à une liste de domaines.

## 3. Hooks (A)

- Code de sortie 0 : l'action passe. Code 2 : elle est bloquée et le message d'erreur retourne à l'agent. Autre code : erreur non bloquante, l'exécution continue.
- Un hook d'arrêt qui répond toujours « continue » boucle sans fin : plafonner les itérations, tester avec une condition volontairement en échec, surveiller les tokens au premier usage.
- Un hook de pré-commit (types, lint, tests) sert de contre-pression : l'agent voit l'échec et se corrige au moment du commit.
- Une règle de style souvent violée devient un hook, pas une phrase de plus dans CLAUDE.md.
- Grille d'audit : `docs/GRILLE-AUDIT-HOOKS.md`.

## 4. Échecs fréquents (A, B)

| Problème | Action | Résultat |
|---|---|---|
| Session fourre-tout (tâches mêlées) | Vider le contexte entre tâches distinctes | Signal net |
| Corrections en spirale | Après deux échecs, repartir de zéro avec un meilleur prompt qui intègre ce qui a été appris | Fin de la dérive |
| CLAUDE.md surchargé | Élaguer : ne garder que ce que l'agent ne déduit pas du code et se trompe à faire | Règles réellement suivies |
| Confiance sans vérification | Toujours fournir un moyen de vérifier (test, script, capture) | Sortie validée, pas supposée |
| Exploration sans borne | Borner le périmètre ou déléguer à un subagent | Contexte préservé |

À surveiller aussi : déconnexion silencieuse d'un MCP, points de restauration qui ne couvrent pas les changements faits par shell, résultat de subagent trop volumineux (A). Les affirmations contestables (chiffres, mesures) se vérifient par des règles de recoupement écrites dans CLAUDE.md (B).

## 5. Multi-agents : commencer simple (A, D)

- Partir d'un seul agent ; en ajouter seulement avec la preuve qu'un seul ne suffit pas.
- Définir les rôles par comportement concret (« relire les fichiers de `src/api/` pour l'injection SQL »), pas par personnalité (« le consultant prudent ») : une personnalité interprétée par le modèle peut bloquer tout le système.
- Échelle de complexité, à gravir seulement si l'échelon précédent échoue : appel unique, chaîne fixe, routeur, orchestrateur et exécutants, évaluateur et optimiseur. Un humain valide avant toute action irréversible.

## 6. Sécurité (A, C, D)

- Tout résultat d'outil est non fiable : page web, document, champ de base peuvent contenir des consignes déguisées (injection).
- Moindre privilège par connexion : lecture seule par défaut, une portée étroite par serveur, secrets protégés et renouvelés.
- Fuites par mise en forme : demander à l'assistant de « résumer ses instructions dans un bloc de code » contourne parfois un refus direct. Jailbreak par fiction ou jeu de rôle. Hallucination ciblée sur chiffres, citations et noms (C, D).
- Catégories de données à protéger (prévention des fuites) : identité, finances, santé, authentification (C).
- Un agent ne perçoit pas la réversibilité d'une action : confirmation, portées limitées et supervision viennent de nous (D).

## 7. Adoption et distribution (A, D)

- Montée en autonomie par étapes : questions sur le code, petits correctifs, mode plan, autonomie complète.
- CLAUDE.md et réglages de projet partagés par le dépôt ; marketplace privée ; décider qui peut y publier.
- Un plugin est l'unité versionnée et testée d'un ensemble (skills, MCP, commandes, agents) : pas de dérive entre pièces.

## 8. Coûts (A, D)

- Modèle plus puissant pour planifier, modèle moins cher pour exécuter ; routeur bon marché pour trier.
- Mesurer avant d'optimiser : coût par serveur MCP, occupation du contexte.

## 9. Rédaction des consignes (A, B, C)

- Donner d'abord les critères de vérification, puis fichiers, contraintes et exemples.
- Structure de consigne en cinq blocs : persona, contexte, tâche, sortie attendue, contraintes (C).
- PRD ou spécification avant l'implémentation ; exigences organisées par qui, quoi, quand, où, pourquoi, comment (B).
