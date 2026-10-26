"use strict";
// Le navigateur n'applique AUCUNE règle de coordination : verdicts, issue, livraison possible, aperçu et enregistrement
// viennent exclusivement du serveur. Tout texte venant du serveur est inséré avec textContent (jamais de balisage injecté).
const $ = (s) => document.querySelector(s);
const HDR = {"X-Zakios-Pilote": "1", "Content-Type": "application/json"};
const REDUIT = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let timer = null, MODE = "reel", ROUTE_ID = 0;

function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v; else if (k === "on") for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn); else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}
async function api(path, opts) {
  const r = await fetch(path, Object.assign({headers: HDR, credentials: "same-origin"}, opts || {}));
  let data = null; try { data = await r.json(); } catch (_) { /* non JSON */ }
  return {ok: r.ok, status: r.status, data};
}
const post = (p, body) => api(p, {method: "POST", body: JSON.stringify(body)});
function anim(root) {
  if (REDUIT || typeof gsap === "undefined") return;
  const cibles = root.querySelectorAll(".reveal");
  if (!cibles.length) return;
  gsap.from(cibles, {y: 10, opacity: 0, duration: .35, stagger: .05, ease: "power1.out", clearProps: "all"});
}

// ---- verdicts : icône + texte + couleur (jamais la couleur seule) ----------------------------------------------------
const VERDICT = {ACCEPTE: ["✔", "ACCEPTÉ"], A_CORRIGER: ["↻", "À CORRIGER"], CLARIFICATION_REQUISE: ["?", "CLARIFICATION REQUISE"]};
const ISSUE = {
  accepte: ["✔", "ACCEPTÉ", "Le relecteur a validé le plan. Rien n'est enregistré avant votre confirmation explicite."],
  clarification_requise: ["?", "CLARIFICATION REQUISE", "Une décision de votre part est nécessaire. Aucune livraison n'est proposée."],
  plafond_atteint: ["■", "PLAFOND ATTEINT", "Trois plans ont été refusés (À CORRIGER). Aucune livraison n'est proposée."],
  erreur_technique: ["⚠", "ERREUR TECHNIQUE", "La mission s'est arrêtée sur un dysfonctionnement. Aucune livraison n'est proposée."]};
const vbadge = (v) => { const [i, t] = VERDICT[v] || ["–", "SANS REVUE"]; return h("span", {class: "v " + (v || "neutre"), "data-verdict": v || "aucun"}, h("i", {"aria-hidden": "true"}, i), t); };
const ibadge = (k) => { const [i, t] = ISSUE[k]; return h("span", {class: "v " + k, "data-issue": k}, h("i", {"aria-hidden": "true"}, i), t); };

// ---- routage ---------------------------------------------------------------------------------------------------------
const CRUMB = {dashboard: "Vue d’ensemble", mission: "Atelier de mission", preuves: "Preuves par campagne", bibliotheque: "Bibliothèque"};
function parse() {
  const p = location.hash.replace(/^#\/?/, "").split("/");
  return {page: ["mission", "preuves", "bibliotheque"].includes(p[0]) ? p[0] : "dashboard", id: p[1] || ""};
}
async function route() {
  clearTimeout(timer); const my = ++ROUTE_ID;
  const {page, id} = parse();
  const main = $("#main");
  document.querySelectorAll("#nav a").forEach((a) => { const on = a.dataset.nav === page; a.classList.toggle("active", on); on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"); });
  $("#crumb").textContent = CRUMB[page];
  document.title = CRUMB[page] + " — ZakiOS";
  const s = await api("/api/sante");          // sonde non authentifiée : évite une erreur 401 dans la console avant connexion
  if (my !== ROUTE_ID) return;
  if (s.data) modeBadge({mode: s.data.mode});
  if (!(s.data && s.data.connecte)) return connexion(main);
  const e = await api("/api/etat");
  if (!e.ok) return connexion(main);
  MODE = e.data.mode; modeBadge(e.data);
  main.replaceChildren();
  const root = h("div", {});
  main.append(root);
  if (page === "dashboard") await dashboard(root, e.data);
  else if (page === "mission") await mission(root, e.data, id, my);
  else if (page === "preuves") await preuves(root);
  else await bibliotheque(root);
  if (my !== ROUTE_ID) return;
  anim(root);
  main.focus({preventScroll: true});
}
function modeBadge(d) {
  const m = $("#mode"); m.className = "mode " + d.mode;
  m.textContent = d.mode === "simulation" ? "SIMULATION — aucun modèle n'est appelé" : "Mode réel — appels à de vrais agents";
}
const intro = (eyebrow, title, lead) => [h("span", {class: "eyebrow reveal"}, eyebrow), h("h1", {class: "reveal"}, title), h("p", {class: "lead reveal"}, lead)];
function modeNotice() {
  return MODE === "simulation"
    ? h("div", {class: "notice sim reveal", role: "note"}, h("span", {"aria-hidden": "true"}, "◉"), h("div", {}, h("strong", {}, "Mode simulation. "), "Les rôles sont simulés : aucun modèle n'est appelé et les résultats ne prouvent rien sur les vrais agents."))
    : h("div", {class: "notice reveal", role: "note"}, h("span", {"aria-hidden": "true"}, "◉"), h("div", {}, h("strong", {}, "Appels réels. "), "Les agents sont de vrais appels à Claude (outils Read, Glob, Grep). Rien n'est écrit dans un projet réel : chaque mission s'exécute dans une copie jetable."));
}

// ---- connexion -------------------------------------------------------------------------------------------------------
function connexion(main) {
  const err = h("p", {class: "err", role: "alert"});
  const inp = h("input", {id: "jeton", type: "password", autocomplete: "current-password", required: true});
  main.replaceChildren(h("div", {class: "panel"}, h("h1", {}, "Accès au pilote"), h("p", {class: "lead"}, "Ce pilote est privé : saisissez le jeton d'accès."),
    h("form", {id: "form-connexion", on: {submit: async (ev) => {
      ev.preventDefault();
      const r = await post("/api/connexion", {jeton: inp.value}); inp.value = "";
      if (r.ok) route(); else err.textContent = (r.data && r.data.erreur) || "échec de connexion";
    }}}, h("label", {for: "jeton"}, "Jeton d'accès"), inp, h("p", {}, h("button", {type: "submit"}, "Entrer")), err)));
  api("/api/sante").then((s) => { if (s.data) modeBadge(s.data); });
  inp.focus();
}

// ---- vue d'ensemble --------------------------------------------------------------------------------------------------
async function dashboard(root, etat) {
  const l = await api("/api/missions"); const ms = (l.data && l.data.missions) || [];
  const n = (k) => ms.filter((m) => m.etat_final === k).length;
  root.append(...intro("Votre poste de pilotage", "Une méthode claire. Des missions qui avancent.", "Lancez une mission, suivez les agents, relisez le plan et ses revues, puis enregistrez seulement après confirmation."),
    modeNotice(),
    h("section", {class: "hero reveal", "aria-label": "Méthode PDCA"}, h("div", {class: "hero-copy"}, h("h2", {}, "Du besoin au résultat, preuve après preuve."), h("p", {}, "Un plan est écrit, relu indépendamment, corrigé au plus deux fois, puis livré — ou arrêté s'il faut une décision de votre part."),
      h("a", {class: "btn primary", href: "#/mission"}, "Lancer une mission ", h("span", {"aria-hidden": "true"}, "↗"))),
      h("div", {class: "ring-wrap", "aria-hidden": "true"}, h("div", {class: "ring"}, h("b", {}, "Planifier"), h("b", {}, "Exécuter"), h("b", {}, "Vérifier"), h("b", {}, "Agir"), h("div", {class: "ring-core"}, "PDCA")))),
    h("h2", {class: "reveal"}, "Missions de ce pilote"),
    h("div", {class: "grid c4 reveal"}, stat(ms.length, "missions au total"), stat(n("accepte"), "acceptées"), stat(n("clarification_requise"), "clarifications requises"), stat(n("plafond_atteint") + n("erreur_technique"), "plafonds ou erreurs techniques")),
    h("p", {class: "note reveal"}, "Ces nombres décrivent uniquement les missions lancées sur ce pilote, pas les campagnes de preuve (voir « Preuves par campagne », séparées)."),
    h("section", {class: "panel reveal"}, h("h2", {}, "Dernières missions"),
      ms.length ? h("ul", {class: "mlist"}, ms.slice(0, 8).map((m) => h("li", {}, h("a", {href: "#/mission/" + m.id}, m.id), m.etat_final ? ibadge(m.etat_final) : h("span", {class: "v neutre"}, m.statut), m.livre ? h("span", {class: "v accepte"}, h("i", {"aria-hidden": "true"}, "✔"), "enregistré") : null, h("span", {class: "note"}, m.demande))))
        : h("p", {class: "note"}, "Aucune mission pour l'instant.")));
}
const stat = (v, t) => h("div", {class: "stat"}, h("strong", {}, String(v)), h("span", {}, t));

// ---- atelier : formulaire + suivi ------------------------------------------------------------------------------------
async function mission(root, etat, id, my) {
  root.append(...intro("Atelier de mission", "Confiez une mission aux agents.", "Chaque mission s'exécute dans une copie jetable d'un projet d'exemple ; vous gardez la main sur l'enregistrement."), modeNotice());
  if (id) { const box = h("div", {id: "suivi"}); root.append(box); return suivre(box, id, my); }
  const err = h("p", {class: "err", role: "alert", id: "erreur-mission"});
  let busy = false;
  const dem = h("textarea", {id: "demande", rows: "4", maxlength: "2000", required: true}, "Planifie la correction du module de paiement src/pay.py : la remise est un pourcentage 0-100 et la lecture d'un utilisateur doit utiliser une requête paramétrée.");
  const cri = h("textarea", {id: "criteres", rows: "5", required: true}, "C1 remise correcte aux bornes 0 et 100\nC2 requête SQL paramétrée\nC3 aucune régression sur les appels existants");
  const btn = h("button", {type: "submit", id: "lancer"}, "Lancer la mission");
  const l = etat.limites;
  root.append(h("form", {id: "form-mission", class: "panel reveal", on: {submit: async (ev) => {
      ev.preventDefault(); if (busy) return; busy = true; btn.disabled = true; err.textContent = "";
      const r = await post("/api/missions", {demande: dem.value, criteres: cri.value.split("\n").map((x) => x.trim()).filter(Boolean)});
      busy = false; btn.disabled = false;
      if (r.ok) location.hash = "#/mission/" + r.data.id; else err.textContent = (r.data && r.data.erreur) || "échec (" + r.status + ")";
    }}},
    h("label", {for: "demande"}, "Demande"), dem,
    h("label", {for: "criteres"}, "Critères obligatoires (un par ligne, chacun commence par un identifiant : C1, C2…)"), cri,
    h("p", {}, btn), err,
    h("p", {class: "note"}, "Limites : " + l.missions_simultanees + " mission simultanée, " + Math.round(l.duree_max_mission_s / 60) + " min max, " + l.appels_max + " appels d'agents max, " + l.missions_par_heure + " missions par heure.")),
    h("details", {class: "panel reveal"}, h("summary", {}, "Projet d'exemple (lecture seule pour les agents)"), h("pre", {}, Object.entries(etat.exemple).map(([f, c]) => "# " + f + "\n" + c).join("\n"))));
  dem.focus();
}
async function suivre(box, id, my) {
  clearTimeout(timer);
  const r = await api("/api/missions/" + id);
  if (my !== ROUTE_ID) return;
  if (!r.ok) { box.replaceChildren(h("p", {class: "err", role: "alert"}, "Mission introuvable.")); return; }
  if (r.data.statut === "en_cours") {
    rendreEnCours(box, r.data);
    timer = setTimeout(() => suivre(box, id, my), 2000);
  } else rendreFinal(box, r.data, id, my);
}
function enTete(m) {
  return h("div", {class: "row between"}, h("h2", {}, "Mission ", h("code", {id: "m-id"}, m.id)), h("span", {class: "v " + (m.mode === "simulation" ? "neutre" : "accepte")}, m.mode === "simulation" ? "SIMULATION" : "RÉEL"));
}
function evenements(m, ouvert) {
  return h("details", {class: "panel", open: ouvert}, h("summary", {}, "Déroulement (" + m.evenements.length + " événements)"), h("ol", {class: "events", id: "m-evenements"}, m.evenements.map((e) => h("li", {}, e.t.slice(11, 19) + " — " + e.texte))));
}
function rendreEnCours(box, m) {
  box.replaceChildren(enTete(m), h("p", {class: "note", id: "m-statut", role: "status"}, "Mission en cours… les agents travaillent (rédaction, relecture, éventuelles corrections)."), evenements(m, true));
}
function rendreFinal(box, m, id, my) {
  const kids = [enTete(m)];
  kids.push(h("p", {class: "note", id: "m-statut", role: "status"}, m.statut === "termine" ? "Mission terminée." : m.statut === "interrompue" ? "Mission interrompue (redémarrage du serveur). Aucune livraison." : "Défaut du pilote : " + (m.defaut_pilote || "") + ". Aucune livraison."));
  if (m.etat_final) {
    const [i, t, ex] = ISSUE[m.etat_final];
    kids.push(h("div", {class: "banner " + m.etat_final, id: "m-bandeau", role: "status", "data-issue": m.etat_final}, h("span", {class: "big", "aria-hidden": "true"}, i), h("div", {}, h("strong", {}, t), h("p", {}, ex))));
    if (m.clarification) kids.push(clarification(m.clarification));
    if (m.apercu) kids.push(apercu(m, box, id, my));
    kids.push(h("h3", {}, "Plans et revues"), ...m.tours.map((t) => tour(m, t)));
    kids.push(erreurs(m), ecarts(m), preuvesMission(m));
  }
  kids.push(evenements(m, false), h("p", {}, h("a", {class: "btn", href: "#/mission"}, "Nouvelle mission")));
  box.replaceChildren(...kids);
  anim(box);
}
function clarification(c) {
  return h("section", {class: "card", id: "m-clarification"}, h("h3", {}, "Question posée"), h("p", {}, "Critères concernés : " + c.criteres.join(", ")),
    h("ul", {class: "list"}, c.blocages.map((x) => h("li", {}, "Blocage : " + x)), c.questions.map((x) => h("li", {}, "Question : " + x))));
}
function apercu(m, box, id, my) {
  const ap = m.apercu, sec = h("section", {class: "card", id: "m-apercu"});
  sec.append(h("h3", {}, "Aperçu exact de l'enregistrement"), h("p", {}, "Fichier : ", h("code", {}, ap.chemin)), h("p", {class: "hash"}, "Empreinte de livraison : " + ap.delivery_sha256), h("pre", {tabindex: "0", "aria-label": "Contenu exact qui sera enregistré"}, ap.plan || "(plan indisponible)"));
  if (m.livraison) {
    sec.append(h("div", {class: "banner accepte", role: "status", id: "m-enregistre"}, h("span", {class: "big", "aria-hidden": "true"}, "✔"), h("div", {}, h("strong", {}, "Enregistré (" + m.livraison.statut + ")"), h("p", {}, m.livraison.chemin))),
      h("p", {}, h("a", {class: "btn", href: "/api/missions/" + m.id + "/livrable"}, "Télécharger le plan enregistré")));
  } else if (m.livraison_possible) {   // le serveur est la seule autorité : pas d'indicateur => pas de bouton
    const msg = h("p", {class: "err", role: "alert"});
    const cb = h("input", {type: "checkbox", id: "relu"});
    const btn = h("button", {type: "button", class: "primary", id: "confirmer", disabled: true}, "Confirmer l'enregistrement");
    cb.addEventListener("change", () => { btn.disabled = !cb.checked; });
    btn.addEventListener("click", async () => {
      if (btn.disabled) return; btn.disabled = true; cb.disabled = true;   // double clic : désactivé aussitôt (le serveur garantit aussi l'idempotence)
      const r = await post("/api/missions/" + m.id + "/confirmer", {delivery_sha256: ap.delivery_sha256});
      if (!r.ok) { msg.textContent = "Enregistrement refusé : " + ((r.data && r.data.erreur) || r.status); cb.disabled = false; btn.disabled = !cb.checked; return; }
      suivre(box, id, my);
    });
    sec.append(h("label", {class: "check", for: "relu"}, cb, "J'ai relu l'aperçu exact ci-dessus"), btn, msg);
  }
  return sec;
}
function tour(m, t) {
  const pre = h("pre", {hidden: true, tabindex: "0"});
  const voir = (kind, label) => h("button", {type: "button", on: {click: async () => {
    const r = await api("/api/missions/" + m.id + "/" + kind + "/" + t.tour); pre.textContent = r.ok ? r.data.texte : "indisponible"; pre.hidden = false;
  }}}, label);
  const cov = Object.entries(t.couverture).map(([k, v]) => k + " : " + v).join(" · ");
  return h("article", {class: "card tour " + t.verdict}, h("div", {class: "row"}, h("strong", {}, "Plan " + t.tour), vbadge(t.verdict)),
    cov ? h("p", {class: "note"}, "Couverture — " + cov) : null,
    (t.relances["plan-writer"] || t.relances["plan-reviewer"]) ? h("p", {class: "note"}, "Relances techniques : rédacteur " + t.relances["plan-writer"] + ", relecteur " + t.relances["plan-reviewer"]) : null,
    h("ul", {class: "list"}, t.constats.map((f) => h("li", {}, "[" + f.gravite + "] " + f.texte))),
    h("div", {class: "row"}, voir("plan", "Voir le plan"), voir("revue", "Voir la revue")), pre);
}
function erreurs(m) {
  const items = m.erreurs_techniques.map((x) => h("li", {}, x.role + ", tour " + x.tour + ", tentative " + x.tentative + " (" + x.categorie + ") : " + x.cause + (x.recuperee ? " — récupérée par une relance" : " — non récupérée") + (x.journal ? " [journal " + x.journal + "]" : "")))
    .concat(m.incoherences_de_trace.map((x) => h("li", {}, "Incohérence de trace : " + x)));
  return h("section", {class: "card", id: "m-erreurs"}, h("h3", {}, "Erreurs techniques"), items.length ? h("ul", {class: "list"}, items) : h("p", {class: "note"}, "Aucune erreur technique ni incohérence de trace."));
}
function ecarts(m) {
  const SENS = {demande_refusee: "demande refusée par la plateforme (sans effet, visible)", execution_confirmee: "EXÉCUTION CONFIRMÉE — mission arrêtée", indetermine: "RÉSULTAT INDÉTERMINÉ — mission arrêtée"};
  return h("section", {class: "card", id: "m-ecarts"}, h("h3", {}, "Écarts comportementaux (outils interdits demandés)"),
    m.ecarts_comportementaux.length ? [h("ul", {class: "list"}, m.ecarts_comportementaux.map((x) => h("li", {}, x.role + ", tour " + x.tour + " : " + x.outil + " — " + (SENS[x.statut] || x.statut)))),
      h("p", {class: "note"}, "Tentative refusée par la plateforme : sans effet, la livraison reste possible. Une exécution interdite confirmée ou indéterminée arrête la mission sans aucune livraison.")] : h("p", {class: "note"}, "Aucun écart comportemental."));
}
function preuvesMission(m) {
  const pre = h("pre", {hidden: true, id: "m-preuve-texte", tabindex: "0"});
  const b = (kind, label) => h("button", {type: "button", id: "btn-" + kind, on: {click: async () => { const r = await api("/api/missions/" + m.id + "/" + kind); pre.textContent = JSON.stringify(r.data, null, 1); pre.hidden = false; }}}, label);
  return h("section", {class: "card"}, h("h3", {}, "Preuves de cette mission"), h("div", {class: "row"}, b("trace", "Voir la trace de mission"), b("audit", "Voir le recoupement trace/journaux")), pre);
}

// ---- preuves par campagne (jamais agrégées) --------------------------------------------------------------------------
async function preuves(root) {
  const r = await api("/api/campagnes"); const d = r.data;
  root.append(...intro("Preuves par campagne", "Chaque campagne, séparément.", d.avertissement),
    h("div", {class: "notice reveal", role: "note"}, h("span", {"aria-hidden": "true"}, "◉"), h("div", {}, h("strong", {}, "Simulé ou réel. "), "Ces campagnes sont des appels réels (un seul modèle, quelques passages). Les tests du pilote lui-même (tests/test_pilote.py) sont simulés ; l'essai navigateur (scripts/essai_pilote_reel.py) est réel.")),
    ...d.campagnes.map(campagne));
}
function campagne(c) {
  const ok = c.criteres_satisfaits;
  return h("article", {class: "card cmp reveal", id: "campagne-" + c.id}, h("div", {class: "row between"}, h("h2", {}, c.titre),
      h("span", {class: "v " + (ok ? "accepte" : "echec"), "data-campagne": c.id}, h("i", {"aria-hidden": "true"}, ok ? "✔" : "✖"), ok ? "Critères satisfaits" : "Critères non tous satisfaits")),
    h("p", {class: "note"}, "Commit testé : " + c.commit_teste), h("p", {}, c.perimetre),
    h("table", {}, h("thead", {}, h("tr", {}, ["Script", "Code de sortie", "Audit indépendant", "Échecs conservés"].map((x) => h("th", {scope: "col"}, x)))),
      h("tbody", {}, c.scripts.map((s) => h("tr", {}, h("td", {}, s.script), h("td", {}, String(s.code_sortie) + (s.code_sortie === 0 ? " (réussi)" : " (échec)")),
        h("td", {}, s.audit ? s.audit.missions + " missions, " + s.audit.appels_reels + " appels réels, " + s.audit.divergences.length + " divergence(s)" : "—"),
        h("td", {}, s.echecs.length || s.non_exerces.length ? h("ul", {class: "list"}, s.echecs.map((x) => h("li", {}, x)), s.non_exerces.map((x) => h("li", {}, "non exercé : " + x))) : "Aucun")))) ),
    h("p", {class: "note"}, c.remarque));
}

// ---- bibliothèque ----------------------------------------------------------------------------------------------------
async function bibliotheque(root) {
  const r = await api("/api/bibliotheque"); const comps = r.data.composants;
  const grid = h("div", {class: "grid c2", id: "grille"});
  const draw = (q) => grid.replaceChildren(...comps.filter((c) => (c.nom + " " + c.description).toLowerCase().includes(q.toLowerCase())).map((c) =>
    h("article", {class: "card"}, h("div", {class: "row between"}, h("h3", {}, c.nom), h("span", {class: "v neutre"}, c.type)), h("p", {}, c.description || "Règles communes de la méthode PDCA."),
      h("p", {class: "hash"}, "sha256 " + c.sha256.slice(0, 16) + "…"), h("button", {type: "button", on: {click: () => ouvrir(c)}}, "Lire la source"))));
  root.append(...intro("Bibliothèque", "Les rôles et le socle du moteur.", "Lecture seule : contenu exact des fichiers du dépôt utilisés par les missions."),
    h("label", {for: "recherche"}, "Rechercher"), h("input", {id: "recherche", type: "search", on: {input: (e) => draw(e.target.value)}}), h("div", {}, grid));
  draw("");
}
function ouvrir(c) {
  $("#detail-title").textContent = c.nom; $("#detail-desc").textContent = c.description; $("#detail-hash").textContent = c.chemin + " · sha256 " + c.sha256; $("#detail-text").textContent = c.texte;
  $("#detail").showModal();
}
$("#detail-close").addEventListener("click", () => $("#detail").close());
window.addEventListener("hashchange", route);
route();
