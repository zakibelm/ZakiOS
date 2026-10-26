# Architecture cible

ZakiOS organise la bibliothèque en couches. Chaque capacité appartient à une seule couche, pour éviter les répétitions.

## Les couches

| Couche | Rôle | Exemples |
|---|---|---|
| Socle commun | règles partagées : qualité, sécurité, mémoire, validation, coordination | le Socle .claude, ses règles transversales |
| Agents | responsabilités distinctes | architecte, développeur, analyste, QA, marketing |
| Skills | méthodes spécialisées, chargées selon la tâche | un skill par méthode |
| Commandes | raccourcis qui déclenchent un workflow précis | `/commande` |
| Hooks et mods | automatismes techniques, retenus après vérification de compatibilité | gardes de sécurité, journal d'audit |
| Index central | permet à l'orchestrateur de choisir les composants adaptés | catalogue de ce dépôt |

## Réserve et activation

- **La réserve** : tout le catalogue, complet et indexé. Rien n'y est actif.
- **L'activation** : pour chaque projet, on active seulement les composants nécessaires.

Bénéfice : un contexte léger, peu de répétitions, et une sélection d'agents plus précise.

## Où placer une capacité

Pour chaque composant retenu, trois questions décident de sa couche :

1. Quelle capacité nouvelle apporte-t-il ?
2. Appartient-elle à un agent, à un skill ou au Socle ?
3. Est-il compatible avec l'environnement cible ?

Une instruction qui s'applique à tous les agents va dans le Socle commun, pas dans chaque agent.

## Règles transversales : les centraliser ne suffit pas

Centraliser une règle dans le Socle ne garantit pas que chaque agent la reçoit quand il s'exécute. Il faut un test : lancer un agent de contrôle et vérifier que la règle est bien présente dans son contexte. Ce test n'est pas encore fait (voir la feuille de route).

## Hooks et mods : un cas à part

Un hook ou un mod modifie le fonctionnement du moteur, il ne se contente pas de décrire une tâche. On les audite donc par comportement :

- ce qu'ils interceptent, modifient ou bloquent ;
- leurs effets de bord ;
- leurs interactions entre eux.

Deux mods proches peuvent être complémentaires. Deux mods différents peuvent agir sur la même opération et se contredire. D'où la matrice de conflits et de dépendances prévue.

Exemple relevé : le pack de gardes de `karanb192/claude-code-hooks` regroupe sept gardes en un seul processus. L'installer avec les gardes individuels les ferait s'exécuter deux fois.

## Provenance

Chaque composant garde sa source, son commit et sa licence. Un composant sans licence vérifiée n'est pas copié dans la bibliothèque.
