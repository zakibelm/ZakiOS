# Méthodologie

Comment ZakiOS passe d'un catalogue brut à une décision par composant.

## 1. Figer la source

Chaque dépôt est cloné en lecture seule et son commit est enregistré (`SOURCES.md`). Un résultat peut ainsi être reproduit exactement, et on sait toujours à quelle version il se rapporte.

## 2. Inventorier les composants réels

Les scripts parcourent les dépôts et reconnaissent cinq familles :

| Famille | Comment elle est reconnue |
|---|---|
| Skill | un fichier `SKILL.md` |
| Agent | un fichier `.md` dans un dossier `agents` ou `subagents`, ou dans `categories/` (cas de VoltAgent) |
| Commande | un fichier `.md` dans un dossier `commands` |
| Hook | un script `.py`, `.js`, `.sh` ou `.ts` dans un dossier `hooks`, ou un `plugin.json` sous `plugins/` (cas de karanb192) |
| Mod | le `README.md` d'un dossier de `mods/` |

Les fichiers annexes (images, tests, configurations, licences) ne sont pas comptés comme composants. C'est pourquoi aitmpl affiche des milliers de fichiers pour 1 856 composants.

Les agents d'aitmpl sont comptés 431 dans le croisement et 422 dans le rapport de doublons : le croisement inclut 9 agents embarqués dans des skills (`comparator`, `grader` et `analyzer`, en trois exemplaires, copies d'un skill d'Anthropic).

Deux dépôts du Socle ne sont pas des collections : `affaan-m/claude-swarm` est un petit framework d'orchestration (4 modules) et `netresearch/claude-code-marketplace` est un site de catalogue sans composants propres.

## 3. Lire la fonction réelle

Pour chaque composant on extrait le nom et la description du frontmatter YAML (en gérant les descriptions sur plusieurs lignes), puis le début du contenu (environ 2 000 à 2 500 caractères). Pour un hook, on prend le commentaire d'en-tête ou la description du `plugin.json`.

## 4. Mesurer la proximité

La similarité est une mesure TF-IDF par cosinus, calculée sur le texte extrait :

- Les mots très fréquents sont retirés, les mots rares pèsent plus.
- Un composant n'est comparé qu'aux composants de la même famille (agent avec agent, skill avec skill, commande avec commande). Les mods sont comparés aux hooks.
- Pour chaque composant d'aitmpl, on garde le meilleur équivalent du Socle et son score.

Deux seuils servent aux décisions automatiques :

| Score | Décision proposée |
|---|---|
| 0,60 ou plus | Remplacer par le Socle (ou écarter) |
| de 0,40 à 0,60 | Fusionner ou garder en variante |
| moins de 0,40 | Adopter (apport unique probable) |

Pour détecter les doublons à l'intérieur d'aitmpl (rapport des agents), le seuil est de 0,45, avec en plus la fusion des noms identiques.

## 5. Cas particuliers

- **Commandes** : même règle, avec 0,40 comme seul seuil (en dessous, adopter ; au-dessus, fusionner).
- **Hooks et mods** : pas de décision automatique. Leur texte décrit peu ce qu'ils font réellement, donc la similarité est trompeuse. Ils sont marqués « À auditer par comportement ».

## 6. Trier les faux positifs

Les groupes détectés sont relus à la main. Exemple : `project-manager` et `scrum-master` sont proches par le vocabulaire mais ont des fonctions distinctes ; ils ne sont pas fusionnés. Dans les agents, 23 groupes ont été détectés, dont 15 sont de vrais doublons (voir `catalog/agents_report.md`).

## Limites

- **La mesure est lexicale.** Deux composants qui font la même chose avec des mots différents peuvent passer pour distincts. « Adopter » est donc une indication à confirmer par lecture.
- **La taille ne dit pas la qualité.** Les versions canoniques proposées dans le rapport des agents se basent sur la taille et la catégorie, pas sur une lecture complète. Elles sont provisoires.
- **ZAKI OS n'est pas encore dans la comparaison.** Un composant jugé nouveau peut déjà exister dans tes agents et skills.
- **Les hooks et mods ne sont pas audités.** Il manque la lecture de ce qu'ils interceptent ou bloquent, et la matrice de conflits.

## Critères de choix d'une version canonique

Précision de la mission, compatibilité avec l'environnement cible, validation par un test réel. La longueur du fichier n'est pas un critère.
