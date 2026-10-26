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
