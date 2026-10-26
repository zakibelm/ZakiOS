# Méthodologie

## Principe

REA : lire ce que fait réellement chaque composant, le situer dans une couche, le comparer à ce qui existe, et ne retenir que ce qu'il apporte en plus. Le moteur prépare ce travail ; l'humain décide.

## Étapes du moteur

1. **Manifeste** (`sources.json`) : dépôts, rôle (catalogue, socle, existant), commit complet.
2. **Vérification** : dépôt présent, HEAD égal au commit de 40 caractères, arbre propre. Sinon le build s'arrête (une source facultative absente est notée, pas fatale).
3. **Inventaire** : `git ls-files`, donc déterministe. Les tests, `node_modules`, docs et fichiers annexes sont exclus. Un mod = son README seul ; un hook `.json` et son script compagnon = un composant.
4. **Lecture** : frontmatter lu avec `yaml.safe_load` ; un YAML invalide est signalé dans le rapport, jamais ignoré en silence. Les descriptions multi-lignes (`>-`, `|`) sont lues correctement.
5. **Présélection** (les composants aux métadonnées invalides en sont exclus, comme référence, voisin ou homonyme) : TF-IDF et cosinus, en Python pur. Le meilleur candidat est cherché dans la même famille (agents, skills, commandes) parmi le Socle et l'existant ; les voisins proches dans le catalogue (≥ 0,45) et les homonymes sont notés.
6. **Statut proposé** selon `zakios/policy.py`. Hooks, plugins et mods : toujours « audit par comportement ». Un fichier à métadonnées invalides est mis en quarantaine. Un composant sans équivalent dans sa famille est aussi cherché dans les deux autres (agent, skill, commande) : s'il y en a un, il devient « chevauchement inter-couches ».
7. **Sortie déterministe** (JSON trié) : deux builds sur les mêmes sources donnent des fichiers identiques octet pour octet.
8. **Validation** (schéma, types, empreintes, références, comptes, CSV recalculé) puis **échange atomique** du dossier `catalog/`. Sans échange atomique disponible, repli sur deux renommages avec restauration immédiate en cas d'erreur.
9. **Empreinte et validation humaine** : une approbation est liée à l'empreinte du composant et devient périmée si elle change.

## Ce qu'un score ne dit pas

Un score lexical mesure un vocabulaire commun. Un score élevé peut cacher des missions différentes ; un score bas peut cacher une même mission écrite autrement. C'est pourquoi les statuts parlent de « candidate » et de « à examiner », et pourquoi aucune étape ne conclut « adopter » ou « supprimer » toute seule.

## Récupération après incident

La génération précédente reste dans `catalog.prev` : un lecteur qui avait ouvert l'ancienne génération la lit jusqu'au bout. `verify` ouvre le dossier une seule fois et vérifie que le rapport correspond au registre lu (`registry_sha256`). Un verrou (`catalog.lock`, Linux) interdit deux générations simultanées. Les dossiers temporaires ont un nom unique (`catalog.tmp-…`) ; ceux d'une génération interrompue sont supprimés au prochain lancement. Si le repli par renommages a laissé `catalog.bak` sans `catalog/`, le prochain lancement le restaure.

## Ce que couvre l'empreinte

L'empreinte d'un composant couvre son paquet : fichiers du composant et dépendances locales **détectables** par expressions régulières (imports python, require/import js et ts, source shell, chemins cités dans la configuration d'un hook). C'est une analyse des dépendances détectables, sans garantie de couvrir tous les comportements : paquets installés, appels dynamiques et variables d'environnement ne sont pas suivis. Le parcours n'a pas de limite de taille de paquet ; seul un garde-fou de ressources (20 000 fichiers explorés) peut l'interrompre. Dans ce cas l'empreinte est déclarée incomplète (`fingerprint_complete: false`), les fichiers non explorés sont listés, et aucune validation humaine n'est réappliquée sur elle.
