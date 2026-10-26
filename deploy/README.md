# Déployer le pilote (à faire sur un hôte avec processus persistant)

Manquant dans l'environnement de développement (donc **non déployé**) : un hôte joignable en HTTPS, `ANTHROPIC_API_KEY`
(ou CLI `claude` connecté) pour les appels réels, et `ZAKIOS_PILOT_TOKEN` choisi par vous.

1. `docker build --build-arg PINNED_COMMIT=$(python3 -c "import json;print(next(s['commit'] for s in json.load(open('sources.json'))['sources'] if s['repo']=='zakibelm/ZakiOS'))") -f deploy/Dockerfile -t zakios-pilote .`
2. `docker run -d --restart=always -p 127.0.0.1:8787:8787 -e ZAKIOS_PILOT_TOKEN=… -e ANTHROPIC_API_KEY=… -v zakios-data:/var/lib/zakios-pilote zakios-pilote`
3. Proxy HTTPS devant le port 8787 (Caddy : `pilote.exemple.tld { reverse_proxy 127.0.0.1:8787 }`).
4. Vérifier : `curl https://pilote.exemple.tld/api/sante` puis rejouer `scripts/essai_pilote_reel.py` contre l'URL.

Le serveur est une seule instance (état sur disque) : pas de multi-réplica.
