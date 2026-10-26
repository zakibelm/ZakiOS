# Bibliothèque agents — rapport de redondance (aitmpl / claude-code-templates)

Base : 422 agents (.md) répartis en 28 catégories. Méthode : noms identiques + similarité TF-IDF des descriptions et du début du contenu (seuil 0,45), puis tri manuel des 23 groupes détectés.

## A. Vrais doublons (même fonction) — 15 groupes, 31 agents → 15 à garder
Action : garder une version canonique par groupe, fusionner les points forts de l'autre. Bénéfice : -16 agents sans perte de capacité.

| Groupe | Versions | Base proposée (à confirmer après lecture) |
|---|---|---|
| accessibility-tester | accessibility/ (16k), development-tools/ (9k), web-tools/web-accessibility-checker (1k) | accessibility/accessibility-tester |
| prompt-engineer | ai-specialists/ (19k), data-ai/ (8k) | ai-specialists/ |
| legal-advisor | business-marketing/ (6k), expert-advisors/ (9k) | expert-advisors/ |
| blueprint-mode | data-ai/blueprint-mode (10k), blueprint-mode-codex (6k) | blueprint-mode + variante codex en option |
| data-analyst | data-ai/ (11k), deep-research-team/ (6k) | data-ai/ |
| quant-analyst | finance/ (9k), data-ai/ (1k) | finance/ |
| devops-engineer | development-team/ (23k), devops-infrastructure/ (10k) | development-team/ |
| architect-review | development-tools/architect-reviewer (11k), expert-advisors/architect-review (3k) | development-tools/ |
| context-manager | expert-advisors/ (11k), development-tools/ (1k) | expert-advisors/ |
| dependency-manager | development-tools/ (8k), expert-advisors/ (3k) | development-tools/ |
| performance-engineer | development-tools/ (9k), performance-testing/ (1k) | development-tools/ |
| test-automator | development-tools/ (9k), performance-testing/ (1k) | development-tools/ |
| incident-responder | devops-infrastructure/ (9k), security/ (1k) | devops-infrastructure/ |
| security-engineer | devops-infrastructure/ (33k), security/ (11k) | devops-infrastructure/ (à alléger) |
| 4.1-Beast | expert-advisors/4.1-Beast (11k), programming-languages/rust-gpt-4.1-beast-mode (14k) | 4.1-Beast générique + variante Rust en option |

## B. Faux positifs (domaine proche, fonctions distinctes) — à garder tous
Action : conserver, mais les relier par catégorie. Bénéfice : pas de perte de spécialisation.
- microsoft-agent-framework et semantic-kernel (variantes .NET et Python)
- competitive-analyst, market-researcher, product-strategist
- project-manager, scrum-master
- ms-sql-dba, postgresql-dba
- frontend-developer, ui-designer
- azure-verified-modules bicep et terraform
- episode-orchestrator, project-supervisor-orchestrator
- java-architect, spring-boot-engineer

## Résultat
422 agents → environ 406 après fusion (≈ 4 % de redondance réelle). Les agents sont peu redondants entre eux ; le vrai gisement est à chercher dans les skills (5 694 fichiers) et les mods (352), et surtout dans le recoupement avec le Socle .claude.

## Limites
Les bases proposées reposent sur la taille et la catégorie, pas sur une lecture complète. Aucun fichier n'a été fusionné ni modifié.
