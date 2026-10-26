"use strict";
// Le navigateur n'applique aucune règle de coordination : il envoie la mission, affiche ce que le serveur rapporte et
// n'active « Confirmer » que si le serveur déclare la livraison possible. Tout texte venant du serveur est inséré avec
// textContent (jamais de balisage injecté).
const $ = (id) => document.getElementById(id);
const H = {"X-Zakios-Pilote": "1", "Content-Type": "application/json"};
let timer = null, enCours = false;

function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) { if (k === "class") e.className = v; else e.setAttribute(k, v); }
  for (const k of kids) e.append(k);
  return e;
}
async function api(path, opts) {
  const r = await fetch(path, Object.assign({headers: H, credentials: "same-origin"}, opts || {}));
  let data = null;
  try { data = await r.json(); } catch (_) { /* contenu non JSON */ }
  return {ok: r.ok, status: r.status, data};
}
function show(id, on) { $(id).hidden = !on; }

async function init() {
  const s = await api("/api/sante");
  const m = $("mode");
  m.textContent = s.data && s.data.mode === "simulation" ? "SIMULATION — aucun modèle n'est appelé" : "Mode réel — appels à de vrais agents";
  m.className = "mode " + (s.data ? s.data.mode : "");
  const e = await api("/api/etat");
  if (!e.ok) { show("vue-connexion", true); show("vue-app", false); return; }
  show("vue-connexion", false); show("vue-app", true);
  $("exemple").textContent = Object.entries(e.data.exemple).map(([f, c]) => "# " + f + "\n" + c).join("\n");
  const l = e.data.limites;
  $("limites").textContent = "Limites : " + l.missions_simultanees + " mission(s) simultanée(s), " + Math.round(l.duree_max_mission_s / 60) + " min max, " + l.appels_max + " appels d'agents max, " + l.missions_par_heure + " missions/heure.";
  if (!$("demande").value) {
    $("demande").value = "Planifie la correction du module de paiement src/pay.py : la remise est un pourcentage 0-100 et la lecture d'un utilisateur doit utiliser une requête paramétrée.";
    $("criteres").value = "C1 remise correcte aux bornes 0 et 100\nC2 requête SQL paramétrée\nC3 aucune régression sur les appels existants";
  }
  const id = location.hash.replace("#", "");
  if (/^p-[0-9a-f]{10}$/.test(id)) ouvrir(id);
}

$("form-connexion").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const r = await api("/api/connexion", {method: "POST", body: JSON.stringify({jeton: $("jeton").value})});
  $("jeton").value = "";
  if (r.ok) { $("erreur-connexion").textContent = ""; init(); } else { $("erreur-connexion").textContent = (r.data && r.data.erreur) || "échec de connexion"; }
});

$("form-mission").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (enCours) return;           // double clic : une seule création côté navigateur
  enCours = true; $("lancer").disabled = true; $("erreur-mission").textContent = "";
  const criteres = $("criteres").value.split("\n").map((x) => x.trim()).filter(Boolean);
  const r = await api("/api/missions", {method: "POST", body: JSON.stringify({demande: $("demande").value, criteres})});
  enCours = false; $("lancer").disabled = false;
  if (r.ok) { ouvrir(r.data.id); } else { $("erreur-mission").textContent = (r.data && r.data.erreur) || "échec (" + r.status + ")"; }
});

$("btn-nouvelle").addEventListener("click", () => { clearTimeout(timer); location.hash = ""; show("vue-mission", false); show("vue-saisie", true); });
$("btn-trace").addEventListener("click", () => preuve("trace"));
$("btn-audit").addEventListener("click", () => preuve("audit"));

let courant = null;
function ouvrir(id) {
  courant = id; location.hash = id;
  show("vue-saisie", false); show("vue-mission", true);
  $("m-id").textContent = id;
  $("m-resultat").hidden = true; $("m-bandeau").hidden = true; $("m-preuve-texte").hidden = true;
  suivre();
}
async function suivre() {
  clearTimeout(timer);
  const r = await api("/api/missions/" + courant);
  if (!r.ok) { $("m-statut").textContent = "Mission introuvable."; return; }
  rendre(r.data);
  if (r.data.statut === "en_cours") timer = setTimeout(suivre, 2000);
}

const LIBELLES = {accepte: ["accepte", "ACCEPTÉ — le plan a été validé par le relecteur. Rien n'est enregistré avant votre confirmation."],
  clarification_requise: ["clarification", "CLARIFICATION REQUISE — une décision de votre part est nécessaire. Aucun plan n'est livré."],
  plafond_atteint: ["plafond", "PLAFOND ATTEINT — trois plans ont été refusés (A_CORRIGER). Aucun plan n'est livré."],
  erreur_technique: ["erreur", "ERREUR TECHNIQUE — la mission s'est arrêtée sur un dysfonctionnement. Aucun plan n'est livré."]};

function rendre(m) {
  const lib = {en_cours: "Mission en cours…", termine: "Mission terminée.", interrompue: "Mission interrompue (redémarrage du serveur).", defaut_pilote: "Défaut du pilote : " + (m.defaut_pilote || "")};
  $("m-statut").textContent = (lib[m.statut] || m.statut) + (m.mode === "simulation" ? " (simulation)" : "");
  const ev = $("m-evenements"); ev.replaceChildren();
  for (const e of m.evenements) ev.append(el("li", {}, e.t.slice(11, 19) + " — " + e.texte));
  if (!m.etat_final) { show("m-resultat", false); show("m-bandeau", false); return; }
  const b = $("m-bandeau"); const [cls, txt] = LIBELLES[m.etat_final];
  b.className = "bandeau " + cls; b.textContent = txt; b.hidden = false;
  show("m-resultat", true);
  // clarification
  const c = $("m-clarification"); c.replaceChildren();
  if (m.clarification) {
    c.hidden = false;
    c.append(el("h3", {}, "Question posée"), el("p", {}, "Critères concernés : " + m.clarification.criteres.join(", ")));
    const ul = el("ul", {class: "liste"}); m.clarification.blocages.forEach((x) => ul.append(el("li", {}, "Blocage : " + x)));
    m.clarification.questions.forEach((x) => ul.append(el("li", {}, "Question : " + x))); c.append(ul);
  } else c.hidden = true;
  // aperçu + confirmation (uniquement si le serveur déclare la livraison possible)
  const a = $("m-apercu"); a.replaceChildren();
  if (m.apercu) {
    a.hidden = false;
    a.append(el("h3", {}, "Aperçu exact de l'enregistrement"), el("p", {}, "Fichier : " + m.apercu.chemin),
      el("p", {class: "note"}, "Empreinte de livraison : " + m.apercu.delivery_sha256), el("pre", {}, m.apercu.plan || "(plan indisponible)"));
    if (m.livraison) {
      a.append(el("p", {class: "bandeau accepte"}, "Enregistré : " + m.livraison.chemin + " (" + m.livraison.statut + ")"));
      const lien = el("a", {href: "/api/missions/" + m.id + "/livrable"}, "Télécharger le plan enregistré"); a.append(el("p", {}, lien));
    } else if (m.livraison_possible) {
      const cb = el("input", {type: "checkbox", id: "relu"}); const lab = el("label", {for: "relu"}, " J'ai relu l'aperçu exact ci-dessus");
      const btn = el("button", {type: "button", class: "primaire", disabled: "disabled"}, "Confirmer l'enregistrement");
      cb.addEventListener("change", () => { btn.disabled = !cb.checked; });
      btn.addEventListener("click", async () => {
        if (btn.disabled) return; btn.disabled = true; cb.disabled = true;      // double clic : désactivé aussitôt
        const r = await api("/api/missions/" + m.id + "/confirmer", {method: "POST", body: JSON.stringify({delivery_sha256: m.apercu.delivery_sha256})});
        if (!r.ok) a.append(el("p", {class: "erreur", role: "alert"}, "Enregistrement refusé : " + ((r.data && r.data.erreur) || r.status)));
        suivre();
      });
      a.append(el("p", {}, cb, lab), btn);
    }
  } else a.hidden = true;
  // tours
  const t = $("m-tours"); t.replaceChildren();
  for (const tour of m.tours) {
    const card = el("div", {class: "carte"});
    card.append(el("strong", {}, "Plan " + tour.tour + " "), el("span", {class: "badge " + tour.verdict}, tour.verdict || "sans revue"));
    const cov = Object.entries(tour.couverture).map(([k, v]) => k + " : " + v).join(" · ");
    if (cov) card.append(el("p", {class: "note"}, "Couverture — " + cov));
    if (tour.relances["plan-writer"] || tour.relances["plan-reviewer"]) card.append(el("p", {class: "ligne-warn"}, "Relances techniques : rédacteur " + tour.relances["plan-writer"] + ", relecteur " + tour.relances["plan-reviewer"]));
    const ul = el("ul", {class: "liste"}); tour.constats.forEach((f) => ul.append(el("li", {}, "[" + f.gravite + "] " + f.texte))); card.append(ul);
    const pre = el("pre", {hidden: "hidden"});
    const bp = el("button", {type: "button"}, "Voir le plan"), br = el("button", {type: "button"}, "Voir la revue");
    for (const [btn, kind] of [[bp, "plan"], [br, "revue"]]) btn.addEventListener("click", async () => {
      const r = await api("/api/missions/" + m.id + "/" + kind + "/" + tour.tour);
      pre.textContent = r.ok ? r.data.texte : "indisponible"; pre.hidden = false;
    });
    card.append(bp, br, pre); t.append(card);
  }
  // erreurs techniques, écarts comportementaux, incohérences
  const er = $("m-erreurs"); er.replaceChildren();
  if (m.erreurs_techniques.length || m.incoherences_de_trace.length) {
    er.hidden = false; er.append(el("h3", {}, "Erreurs techniques"));
    const ul = el("ul", {class: "liste"});
    m.erreurs_techniques.forEach((x) => ul.append(el("li", {class: "ligne-err"}, x.role + ", tour " + x.tour + ", tentative " + x.tentative + " (" + x.categorie + ") : " + x.cause + (x.recuperee ? " — récupérée par une relance" : " — non récupérée") + (x.journal ? " [journal " + x.journal + "]" : ""))));
    m.incoherences_de_trace.forEach((x) => ul.append(el("li", {class: "ligne-err"}, "Incohérence de trace : " + x)));
    er.append(ul);
  } else er.hidden = true;
  const ec = $("m-ecarts"); ec.replaceChildren();
  if (m.ecarts_comportementaux.length) {
    ec.hidden = false; ec.append(el("h3", {}, "Écarts comportementaux (outils interdits demandés)"));
    const ul = el("ul", {class: "liste"});
    const SENS = {demande_refusee: "demande refusée par la plateforme (sans effet)", execution_confirmee: "EXÉCUTION CONFIRMÉE — mission arrêtée", indetermine: "RÉSULTAT INDÉTERMINÉ — mission arrêtée"};
    m.ecarts_comportementaux.forEach((x) => ul.append(el("li", {class: x.statut === "demande_refusee" ? "ligne-warn" : "ligne-err"}, x.role + " tour " + x.tour + " : " + x.outil + " — " + (SENS[x.statut] || x.statut))));
    ec.append(ul);
  } else ec.hidden = true;
}
async function preuve(kind) {
  const r = await api("/api/missions/" + courant + "/" + kind);
  const p = $("m-preuve-texte"); p.textContent = JSON.stringify(r.data, null, 1); p.hidden = false;
}
init();
