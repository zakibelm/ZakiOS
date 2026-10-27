# Pilote privé ZakiOS

Interface web minimale branchée sur le **coordinateur existant** (`zakios/mission.py`). Le navigateur n'applique aucune
règle de coordination : il envoie la mission, affiche ce que le serveur rapporte, et n'active « Confirmer » que si le
serveur déclare la livraison possible.

## Lancer

```
export ZAKIOS_PILOT_TOKEN='<au moins 16 caractères, secret>'
export ZAKIOS_SOURCES_ROOT=/chemin/avec/zakibelm/ZakiOS   # checkout du dépôt au commit épinglé dans sources.json
python3 -m zakios.pilote --data /var/lib/zakios-pilote --port 8787      # réel : appelle `claude -p`
python3 -m zakios.pilote --simulation ...                               # simulé : aucun modèle appelé
```

Prérequis du mode réel : CLI `claude` installé et authentifié **sur le serveur** (par exemple `ANTHROPIC_API_KEY` dans
l'environnement du processus). Les clés et appels de modèle restent côté serveur ; le navigateur ne les voit jamais.
Placer le pilote derrière un proxy HTTPS (et `ZAKIOS_PILOT_SECURE_COOKIE=1`).

## Garde-fous

- Accès : jeton (cookie HttpOnly/SameSite=Strict ou `Authorization: Bearer`), 5 échecs de connexion → blocage 10 min,
  en-tête `X-Zakios-Pilote: 1` exigé sur tout POST (anti-CSRF), CSP sans script en ligne, corps ≤ 16 Ko.
- Isolation : chaque mission s'exécute dans une copie jetable d'un projet d'exemple ; rôles installés par le moteur avec
  des décisions/licences **locales au pilote** (« PILOTE (non réel) ») ; `decisions/*.json` et licences réelles ne sont
  jamais lus ni écrits ; `run-tests` n'est pas branché.
- Limites : 1 mission simultanée (429 sinon), 12 missions/heure, 20 min par mission, 10 appels d'agents par mission,
  demande ≤ 2000 caractères, ≤ 8 critères.
- Livraison : le coordinateur tourne en mode « différé » : rien n'est écrit tant que la personne n'a pas vu l'aperçu exact
  et confirmé ; l'enregistrement exige que l'empreinte confirmée soit celle de l'aperçu, que le dernier verdict soit
  ACCEPTE et couvre tous les critères ; double clic idempotent ; refus d'écraser un fichier existant.
  Clarification, erreur technique et plafond atteint n'offrent aucune livraison.

## Interface (habillage issu de ZakiOS_Frontend.zip)

Le design du zip (barre latérale sombre, surfaces neutres, accent vert, roue PDCA) habille le vrai pilote ; ses données de
démonstration et ses « livraisons » dans le navigateur ont été supprimées. Le coordinateur reste la seule autorité pour les
verdicts et la livraison : le navigateur n'active « Confirmer » que si le serveur le déclare possible.

- Pages : vue d'ensemble, atelier de mission (saisie, suivi, plans, revues, aperçu exact, confirmation, preuves de la
  mission), preuves **par campagne** (`/api/campagnes`, généré par `scripts/generer_campagnes.py` depuis les preuves ;
  C3 et son échec conservés ; aucun taux agrégé), bibliothèque (rôles et socle lus dans le dépôt, lecture seule).
- Verdicts distincts avec icône + texte + couleur : ✔ ACCEPTÉ, ↻ À CORRIGER, ? CLARIFICATION REQUISE ; issues : ■ PLAFOND
  ATTEINT, ⚠ ERREUR TECHNIQUE. Erreurs techniques et écarts comportementaux toujours affichés (ou « aucun »).
- Aucune dépendance externe : police système, GSAP 3.12.5 embarqué (licence GreenSock standard), CSP sans script ni style
  en ligne. Animations discrètes, désactivées par `prefers-reduced-motion`.
- Différences volontaires avec le zip : tailles de texte relevées (le zip descendait à 7–11 px), thème clair conservé,
  Google Fonts retirées, page « Bibliothèque » alimentée par le dépôt et non par un `data.json` figé à un autre commit.

## Preuves

- `tests/test_pilote.py` : 23 tests **simulés** (rôles simulés, aucun modèle appelé) via un vrai serveur HTTP.
- `tests/test_pilote_navigateur.py` : 12 tests **simulés dans un vrai Chromium** (parcours, verdicts, double clic, refus d'écrasement, 390/820/1440 px, clavier, focus, mouvement réduit, contrastes WCAG AA calculés).
- `scripts/essai_pilote_reel.py` : parcours **réel** dans Chromium avec de vrais agents ; résultats sous
  `docs/revues/preuves-pilote/`.

## Résultat du premier essai réel (reel-1, Chromium 420 px, vrais agents)

- Mauvais jeton refusé ; bon jeton accepté ; bandeau « Mode réel ».
- Mission acceptée : 1 plan, 1 revue, verdict ACCEPTE, aperçu exact, double clic réel sur « Confirmer » → un seul
  enregistrement (`enregistre`), trace et recoupement trace/journaux concordants (0 incohérence, 0 écart comportemental).
- Mission contradictoire : CLARIFICATION_REQUISE, aucun bouton de confirmation, aucun fichier livré.
- **Limites de cet essai** : un seul passage par cas (pas de campagne statistique) ; pannes, plafond et refus d'écrasement
  ne sont prouvés qu'en simulation ; exécuté depuis le bac à sable de développement, pas depuis un hôte déployé.

## Défaut trouvé par la CI et corrigé

Le premier push a fait échouer la CI : le test de double confirmation concurrente de `confirmer_livraison` (écrit avant le
pilote) était intermittent — course réelle dans `deliver.save_plan` entre la vérification d'existence et l'écriture. Corrigé
par un verrou par mission dans le processus (une seule instance de serveur supposée). Sans le verrou, le test échoue
environ 1 fois sur 3 : il détecte la régression de façon probabiliste, pas déterministe.

## Essai réel n°2 (reel-2, nouvelle interface, vrais agents, Chromium 820 px + captures 390/820/1440)

Mauvais jeton refusé ; mission acceptée (verdict ✔ ACCEPTÉ, aperçu exact, double clic réel → un seul enregistrement,
trace/journaux concordants) ; mission contradictoire (? CLARIFICATION REQUISE, aucun bouton de livraison) ; aucun
débordement horizontal à 390/820/1440 px sur l'accueil, la mission et les preuves. Un passage par cas ; pannes, plafond,
écart comportemental et refus d'écrasement restent prouvés en simulation (tests navigateur simulés). Bug trouvé par les tests
et corrigé : le message de refus d'écrasement était effacé par le rafraîchissement de la mission.
Limites : contrastes calculés sur les couples texte/fond du DOM (pas d'audit lecteur d'écran réel) ; thème clair seulement ;
`reel-1` (ancienne interface) est conservé tel quel.

## Veille outils (liste de candidats open source)

La page `#/veille` (API `GET /api/veille`) affiche les 124 dépôts GitHub de la feuille « Veille GitHub - Repos et valeur
ajoutée » (instantané du 2026-10-27 : `docs/veille/feuille-2026-10-27.psv`, converti par `scripts/importer_veille.py`
en `zakios/pilote/veille.json`, `--check` testé). C'est une **liste de propositions pour choisir** les outils des
prochaines générations de produits.

Limites : les licences, étoiles et maturités sont ceux de la feuille, **non vérifiés** (38 dépôts ont une licence « À
vérifier » ou vide ; plusieurs sont AGPL, à examiner avant tout usage) ; 3 entrées n'ont pas de lien ; les statuts
(« À tester » / « Évalué ») sont reproduits sans être inventés ; rien n'est installé, retenu ni validé, et le catalogue
du moteur (`catalog/`, `decisions/`) n'est pas touché. Pour mettre à jour : remplacer le .psv puis relancer le script.

### Présélection (critères)

Chaque dépôt porte quatre critères calculés par `scripts/importer_veille.py` (jamais dans le navigateur) : licence
permissive déclarée (MIT, Apache 2.0, BSD-2-Clause), maturité Très actif/Stable, usage « Brique à intégrer » ou « À
installer et utiliser », projet concerné identifié. Les 43 dépôts qui satisfont les quatre sont marqués « présélectionnés ».
Les AGPL, MPL, licences « À vérifier », Alpha/sans maturité et simples annuaires/références restent visibles mais hors
présélection. Limite : tout repose sur les valeurs déclarées de la feuille, non vérifiées ; la présélection n'est ni un
choix, ni une validation, ni une autorisation d'installer.

## Correctifs issus de l'audit du 2026-10-27 (red team du déploiement zakios.xtream.space)

| Constat | Correctif dans le code | Test |
|---|---|---|
| Derrière nginx, tous les visiteurs ont la même adresse : 5 faux jetons bloquaient tout le monde | `X-Real-IP` n'est crue que si le pair est un proxy de confiance (`ZAKIOS_PILOT_TRUSTED_PROXIES`, boucle locale par défaut) ; sinon ignorée (anti-falsification) | 3 tests (+ mutation détectée) |
| Seule la config des agents limitait Claude à la lecture | `claude -p` reçoit aussi `--allowedTools=Read,Glob,Grep` et `--disallowedTools=Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch` (forme « = » : option variadique qui avalerait le prompt) ; vérifié avec la vraie CLI 2.1.311 : Bash/Write/Edit absents de la liste d'outils | test d'arguments + mutation détectée |
| Pas de déconnexion, session de 8 h | `POST /api/deconnexion` (session invalidée côté serveur) + bouton « Se déconnecter » | API + navigateur |
| `HEAD` répondait 501 | `do_HEAD` : mêmes en-têtes que GET, sans corps | 1 test |
| HSTS | en-tête ajouté par l'app quand `ZAKIOS_PILOT_SECURE_COOKIE=1` (nginx l'ajoute déjà) | 1 test |
| Dockerfile : dernière version de Claude Code, PyYAML absent | version fixée (`CLAUDE_CODE_VERSION=2.1.311`), `python3-yaml`, `.dockerignore` (exclut `.git`, `*.env`, `pilote.env`) | 1 test |

Limites : l'image Docker n'a toujours pas été construite ici (le VPS l'a fait avec ses propres corrections) ; la « règle git »
mentionnée dans le rapport d'audit n'est pas décrite, donc non reportée ; sur le VPS il faut ajouter
`ZAKIOS_PILOT_TRUSTED_PROXIES=172.16.0.1` (adresse vue par l'app derrière nginx) pour que la limite d'essais soit par visiteur.

### Vérification en direct des présélectionnés

`python3 scripts/verifier_veille.py` (à lancer là où internet est ouvert, par ex. le VPS) interroge l'API publique GitHub
(anonyme, lecture seule, 43 requêtes < 60/h) et écrit `docs/veille/verification-AAAA-MM-JJ.json` : licence réelle, étoiles,
dernier push, archivage, renommage, et les écarts avec la feuille. `veille.json` n'est pas modifié : c'est un constat
séparé. Une licence « À vérifier » n'est jamais « conforme ». Testé hors ligne (données simulées) ; jamais exécuté contre GitHub
depuis cet environnement, dont le réseau refuse api.github.com et github.com.
