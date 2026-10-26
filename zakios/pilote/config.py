"""Configuration du pilote (variables d'environnement, jamais exposées au navigateur)."""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    data_dir: str
    sources_root: str
    token: str = ""                    # ZAKIOS_PILOT_TOKEN : secret d'accès (>= 16 caractères) ; jamais journalisé
    simulation: bool = False           # rôles simulés : aucun appel à un modèle (affiché comme tel dans l'interface)
    model: str = "sonnet"
    claude_bin: str = "claude"
    host: str = "127.0.0.1"
    port: int = 8787
    max_concurrent: int = 1            # missions simultanées (les autres reçoivent 429)
    mission_timeout: int = 1200        # durée maximale d'une mission (s)
    call_timeout: int = 420            # durée maximale d'un appel de rôle (s)
    max_calls: int = 10                # appels de rôles maximum par mission (tentatives techniques comprises)
    max_missions_per_hour: int = 12
    max_request_chars: int = 2000
    max_criteria: int = 8
    max_criterion_chars: int = 300
    max_body_bytes: int = 16384
    session_ttl: int = 8 * 3600
    login_failures_max: int = 5        # par adresse et par fenêtre de 10 minutes
    secure_cookie: bool = False        # True derrière HTTPS
    extra: dict = field(default_factory=dict)

    @staticmethod
    def from_env(**over):
        env = os.environ
        cfg = Config(data_dir=over.pop("data_dir", env.get("ZAKIOS_PILOT_DATA", "./pilote-data")),
                     sources_root=over.pop("sources_root", env.get("ZAKIOS_SOURCES_ROOT", "/home/claude")),
                     token=env.get("ZAKIOS_PILOT_TOKEN", ""),
                     simulation=env.get("ZAKIOS_PILOT_SIMULATION", "") == "1",
                     model=env.get("ZAKIOS_PILOT_MODEL", "sonnet"),
                     claude_bin=env.get("ZAKIOS_CLAUDE_BIN", "claude"),
                     secure_cookie=env.get("ZAKIOS_PILOT_SECURE_COOKIE", "") == "1")
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    def validate(self):
        if len(self.token) < 16:
            raise SystemExit("ZAKIOS_PILOT_TOKEN absent ou trop court (>= 16 caractères) : le pilote refuse de démarrer sans accès protégé")
