# Pilote privé ZakiOS — image d'exemple (NON testée ici : docker n'a pas été exécuté dans cet environnement).
FROM node:22-bookworm-slim
# Version de Claude Code FIXÉE (reconstructions reproductibles) ; la changer volontairement après vérification.
ARG CLAUDE_CODE_VERSION=2.1.311
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-yaml git ca-certificates && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}
WORKDIR /app
COPY . /app/ZakiOS
# Le moteur attend le dépôt zakibelm/ZakiOS au commit épinglé dans sources.json sous <sources-root>/zakibelm/ZakiOS
ARG PINNED_COMMIT
RUN mkdir -p /srv/sources/zakibelm \
 && git clone https://github.com/zakibelm/ZakiOS /srv/sources/zakibelm/ZakiOS \
 && git -C /srv/sources/zakibelm/ZakiOS checkout "$PINNED_COMMIT"
# le clone appartient à root alors que le pilote tourne en utilisateur « pilote » : git refuserait sinon (« dubious ownership »).
# Règle limitée à ce seul dépôt (pas de « * »).
RUN git config --system --add safe.directory /srv/sources/zakibelm/ZakiOS
RUN useradd -m pilote && mkdir -p /var/lib/zakios-pilote && chown pilote /var/lib/zakios-pilote
USER pilote
WORKDIR /app/ZakiOS
ENV ZAKIOS_SOURCES_ROOT=/srv/sources ZAKIOS_PILOT_DATA=/var/lib/zakios-pilote ZAKIOS_PILOT_SECURE_COOKIE=1
EXPOSE 8787
# secrets fournis à l'exécution (fichier hors image, ex. --env-file /etc/zakios/pilote.env) : ZAKIOS_PILOT_TOKEN et ANTHROPIC_API_KEY (jamais dans l'image)
# derrière nginx : ZAKIOS_PILOT_TRUSTED_PROXIES=<adresse vue par l'app, ex. 172.16.0.1> pour que X-Real-IP soit prise en compte
CMD ["python3", "-m", "zakios.pilote", "--host", "0.0.0.0", "--port", "8787"]
