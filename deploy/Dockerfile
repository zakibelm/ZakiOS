# Pilote privé ZakiOS — image d'exemple (NON testée ici : docker n'a pas été exécuté dans cet environnement).
FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 git ca-certificates && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code
WORKDIR /app
COPY . /app/ZakiOS
# Le moteur attend le dépôt zakibelm/ZakiOS au commit épinglé dans sources.json sous <sources-root>/zakibelm/ZakiOS
ARG PINNED_COMMIT
RUN mkdir -p /srv/sources/zakibelm \
 && git clone https://github.com/zakibelm/ZakiOS /srv/sources/zakibelm/ZakiOS \
 && git -C /srv/sources/zakibelm/ZakiOS checkout "$PINNED_COMMIT"
RUN useradd -m pilote && mkdir -p /var/lib/zakios-pilote && chown pilote /var/lib/zakios-pilote
USER pilote
WORKDIR /app/ZakiOS
ENV ZAKIOS_SOURCES_ROOT=/srv/sources ZAKIOS_PILOT_DATA=/var/lib/zakios-pilote ZAKIOS_PILOT_SECURE_COOKIE=1
EXPOSE 8787
# secrets fournis à l'exécution : ZAKIOS_PILOT_TOKEN et ANTHROPIC_API_KEY (jamais dans l'image)
CMD ["python3", "-m", "zakios.pilote", "--host", "0.0.0.0", "--port", "8787"]
