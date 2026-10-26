# Méthodologie

## Principe

REA : lire ce que fait réellement chaque composant, le situer dans une couche, le comparer à ce qui existe, et ne retenir que ce qu'il apporte en plus. Le moteur prépare ce travail ; l'humain décide.

## Étapes du moteur

1. **Manifeste** (`sources.json`) : dépôts, rôle (catalogue, socle, existant), commit complet.
2. **Vérification** : dépôt présent, HEAD égal au commit de 40 caractères, arbre propre. Sinon le build s'arrête (une source facultative absente est notée, pas fatale).
3. **Inventaire** : `git ls-files`, donc déterministe. Les tests, `node_modules`, docs et fichiers annexes sont exclus. Un mod = son README seul ; un hook `.json` et son script compagnon = un composant.
4. **Lecture** : frontmatter lu avec `yaml.safe_load` ; un YAML invalide est signalé dans le rapport, jamais ignoré en silence. Les descriptions multi-lignes (`>-`, `|`) sont lues correctement.
5. **Présélection** : TF-IDF et cosinus, en Python pur. Le meilleur candidat est cherché dans la même famille (agents, skills, commandes) parmi le Socle et l'existant ; les voisins proches dans le catalogue (≥ 0,45) et les homonymes sont notés.
6. **Statut proposé** selon `zakios/policy.py`. Hooks, plugins et mods : toujours « audit par comportement ».
7. **Sortie déterministe** (JSON trié) : deux builds sur les mêmes sources donnent des fichiers identiques octet pour octet.
8. **Validation puis remplacement atomique** du dossier `catalog/`.

## Ce qu'un score ne dit pas

Un score lexical mesure un vocabulaire commun. Un score élevé peut cacher des missions différentes ; un score bas peut cacher une même mission écrite autrement. C'est pourquoi les statuts parlent de « candidate » et de « à examiner », et pourquoi aucune étape ne conclut « adopter » ou « supprimer » toute seule.

## Récupération après incident

Si le build est interrompu pendant le remplacement, le prochain lancement restaure `catalog.bak` automatiquement. Un dossier `catalog.tmp` résiduel est supprimé au démarrage.
