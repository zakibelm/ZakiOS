"""Politique unique : familles, seuils, statuts et libellés.

La documentation, le code et les tests décrivent tous ce module.

Principe : le score TF-IDF est un outil de présélection. Il ne prouve ni la
nouveauté, ni l'équivalence. Les statuts le disent explicitement, et aucun
hook, plugin ou mod n'est jamais présenté comme « à adopter » automatiquement.
"""

SCHEMA_VERSION = "4"

# Un composant n'est comparé qu'aux composants de sa famille.
FAMILIES = {
    "agent": "agent", "embedded_agent": "agent",
    "skill": "skill",
    "command": "command",
    "hook": "behavior", "plugin": "behavior", "mod": "behavior",
    "framework_module": "framework",
}
# Ces types modifient le comportement du moteur : audit obligatoire.
BEHAVIOR_TYPES = {"hook", "plugin", "mod"}

THRESHOLDS = {
    "equivalence_candidate": 0.60,  # score >= : équivalence candidate
    "partial_overlap": 0.40,        # score >= : chevauchement partiel
    "neighbor": 0.45,               # voisin proche dans le même catalogue
}

STATUS_EQUIVALENCE = "equivalence_candidate"
STATUS_PARTIAL = "partial_overlap"
STATUS_NOVELTY = "novelty_to_review"
STATUS_BEHAVIOR = "behavior_audit_required"
STATUS_INSUFFICIENT = "insufficient_metadata"
STATUS_INVALID = "invalid_metadata"
STATUS_CROSS_LAYER = "cross_layer_overlap"
STATUSES = (STATUS_EQUIVALENCE, STATUS_PARTIAL, STATUS_NOVELTY, STATUS_BEHAVIOR, STATUS_INSUFFICIENT,
            STATUS_INVALID, STATUS_CROSS_LAYER)

# Familles comparées entre elles : une capacité peut vivre dans un agent, un skill ou une commande.
CONTENT_FAMILIES = ("agent", "skill", "command")
# Décisions humaines autorisées dans decisions/validated.json
ALLOWED_DECISIONS = ("conserver", "fusionner", "variante", "remplacer_par_socle", "archiver")
# Décisions qui autorisent l'installation d'un composant dans un projet.
INSTALLABLE_DECISIONS = ("conserver", "fusionner", "variante")

PROPOSALS = {
    STATUS_EQUIVALENCE: "Équivalence candidate : comparer mission, entrées, sorties et procédures avant tout remplacement",
    STATUS_PARTIAL: "Chevauchement partiel : comparaison fonctionnelle requise avant fusion ou variante",
    STATUS_NOVELTY: "Nouveauté à examiner : l'absence d'équivalent lexical ne prouve pas la nouveauté",
    STATUS_BEHAVIOR: "Audit par comportement requis (événements interceptés, effets de bord, conflits)",
    STATUS_INSUFFICIENT: "Métadonnées insuffisantes : lire le composant avant toute comparaison",
    STATUS_INVALID: "Métadonnées invalides — revue requise : le fichier n'a pas pu être lu correctement, aucune comparaison fiable",
    STATUS_CROSS_LAYER: "Chevauchement inter-couches : une capacité proche existe dans une autre famille (agent, skill ou commande), la lire avant de conclure à la nouveauté",
}
PROVISIONAL_REASON = "comparaison ZAKI OS manquante"


def family_of(component_type):
    return FAMILIES[component_type]


def status_for(component_type, score, has_text, invalid=False):
    """Statut d'évaluation. Les composants de comportement ne passent jamais par les seuils."""
    if invalid:
        return STATUS_INVALID
    if component_type in BEHAVIOR_TYPES:
        return STATUS_BEHAVIOR
    if not has_text:
        return STATUS_INSUFFICIENT
    if score >= THRESHOLDS["equivalence_candidate"]:
        return STATUS_EQUIVALENCE
    if score >= THRESHOLDS["partial_overlap"]:
        return STATUS_PARTIAL
    return STATUS_NOVELTY
