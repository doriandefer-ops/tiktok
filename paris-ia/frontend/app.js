const $ = (s) => document.querySelector(s);
const pct = (p) => `${Math.round(p * 100)} %`;
const de = (n) => (/^[aeiouyéèêàâî]/i.test(n) ? `d'${n}` : `de ${n}`);
const outcomeLabel = (m, o) => (o === "draw" ? "un match nul" : `une victoire ${de(o === "home" ? m.home : m.away)}`);
const fmtPct = (p) => `${(p * 100).toFixed(1).replace(".", ",")} %`;
let me = { plan: "free" };
let signupMode = true;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || "Erreur");
  return body;
}

function renderAccount() {
  const el = $("#account");
  if (!me.email) {
    el.innerHTML = `<button class="ghost" id="login-btn">Connexion</button><button id="signup-btn">Créer un compte</button>`;
    $("#login-btn").onclick = () => openAuth(false);
    $("#signup-btn").onclick = () => openAuth(true);
  } else {
    el.innerHTML = `<span class="badge">${me.plan}</span><span class="muted">${me.email}</span>`
      + (me.plan !== "free" ? `<button class="ghost" id="manage-btn">Gérer ou résilier mon abonnement</button>` : "")
      + `<button class="ghost" id="logout-btn">Déconnexion</button>`;
    $("#logout-btn").onclick = async () => { await api("/api/logout", { method: "POST" }); location.reload(); };
    if ($("#manage-btn")) $("#manage-btn").onclick = async () => {
      if (!me.stripe && !confirm("Résilier ton abonnement maintenant ?")) return;
      location.href = (await api("/api/billing/portal", { method: "POST" })).url;
    };
  }
}

function openAuth(signup) {
  signupMode = signup;
  $("#auth-title").textContent = signup ? "Créer un compte" : "Connexion";
  $("#auth-switch").textContent = signup ? "J'ai déjà un compte" : "Créer un compte";
  $("#adult-row").style.display = signup ? "" : "none";
  $("#auth-error").textContent = "";
  $("#auth").showModal();
}

$("#auth-switch").onclick = () => openAuth(!signupMode);
$("#auth-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api(signupMode ? "/api/signup" : "/api/login", {
      method: "POST",
      body: JSON.stringify({ email: f.get("email"), password: f.get("password"), adult: f.get("adult") === "on" }),
    });
    location.reload();
  } catch (err) { $("#auth-error").textContent = err.message; }
};

let chosenPlan = null;
document.querySelectorAll("[data-plan]").forEach((b) => {
  b.onclick = () => {
    if (!me.email) return openAuth(true);
    chosenPlan = b.dataset.plan;
    $("#subscribe-title").textContent = `Abonnement ${chosenPlan === "pro" ? "Pro, 39,99 €" : "Premium, 19,99 €"} par mois`;
    $("#subscribe-error").textContent = "";
    $("#subscribe").showModal();
  };
});
$("#subscribe-cancel").onclick = () => $("#subscribe").close();
$("#subscribe-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const r = await api(`/api/checkout/${chosenPlan}`, {
      method: "POST", body: JSON.stringify({ cgv: f.get("cgv") === "on", immediate: f.get("immediate") === "on" }),
    });
    location.href = r.url;
  } catch (err) { $("#subscribe-error").textContent = err.message; }
};

function matchCard(m) {
  const p = m.probs;
  const fav = ["home", "draw", "away"].reduce((a, b) => (p[b] > p[a] ? b : a));
  let html = `<div class="card">
    <div class="meta"><span>${m.league_name}</span><span>${m.date.split("-").reverse().join("/")} ${m.time || ""}</span></div>
    <a class="teams" href="/match/${m.slug}"><span>${m.home}</span><span>${m.away}</span></a>
    <div class="bar"><div class="h" style="flex:${p.home}">${pct(p.home)}</div><div class="d" style="flex:${p.draw}">${pct(p.draw)}</div><div class="a" style="flex:${p.away}">${pct(p.away)}</div></div>
    <div class="legend"><span>Victoire ${m.home}</span><span>Nul</span><span>Victoire ${m.away}</span></div>
    <p class="estimate">Le modèle estime à <b>${pct(p[fav])}</b> les chances d'${outcomeLabel(m, fav)}.</p>`;
  if (m.locked) {
    html += `<div class="locked">Probabilités de buts, scores probables et comparaison avec les cotes : <a href="#offres">offre Premium</a></div>`;
  } else {
    html += `<div class="extra">
      <div>+2,5 buts<b>${pct(m.over25)}</b></div>
      <div>Les deux marquent<b>${pct(m.btts)}</b></div>
      <div>Buts attendus<b>${m.xg[0]} – ${m.xg[1]}</b></div></div>
      <p class="muted">Scores les plus probables : ${m.scores.map((s) => `${s.score} (${pct(s.p)})`).join(", ")}</p>`;
    const av = m.availability;
    if (av) {
      const list = (ab) => ab.length ? ab.map((a) => `${a.name}${a.weight < 1 ? " (incertain)" : ""}`).join(", ") : "aucun";
      html += `<div class="absences"><b>${av.lineups ? "Compositions officielles publiées" : "Absents connus"}</b>
        <div>${m.home} : ${list(av.absent_home)}</div><div>${m.away} : ${list(av.absent_away)}</div>
        ${av.weighted && (av.lam_mult !== 1 || av.mu_mult !== 1) ? `<div class="muted">Probabilités ajustées : buts attendus ×${av.lam_mult.toFixed(2).replace(".", ",")} pour ${m.home}, ×${av.mu_mult.toFixed(2).replace(".", ",")} pour ${m.away}.</div>` : ""}</div>`;
    }
    const fair = (o) => m.fair_odds[o].toFixed(2).replace(".", ",");
    html += `<div class="fair">Cotes justes, sans marge : ${m.home} <b>${fair("home")}</b> · Nul <b>${fair("draw")}</b> · ${m.away} <b>${fair("away")}</b></div>`;
    if (m.margin != null) html += `<p class="muted">Marge moyenne prélevée par les bookmakers sur ce match : ${fmtPct(m.margin)}.</p>`;
  }
  return html + "</div>";
}

async function loadMatches() {
  const d = await api("/api/matches");
  const leagues = [...new Set(d.matches.map((m) => m.league_name))];
  $("#league-filter").innerHTML = `<option value="">Tous les championnats</option>` + leagues.map((l) => `<option>${l}</option>`).join("");
  const render = () => {
    const f = $("#league-filter").value;
    const list = d.matches.filter((m) => !f || m.league_name === f);
    $("#matches").innerHTML = list.length ? list.map(matchCard).join("") : `<p class="muted">Aucun match programmé pour l'instant.</p>`;
  };
  $("#league-filter").onchange = render;
  $("#generated").textContent = d.generated ? `Mis à jour le ${new Date(d.generated).toLocaleString("fr-FR")}` : "";
  render();
}

async function loadTrackRecord() {
  const { summary: s } = await api("/api/track-record");
  if (!s.matches) return;
  const ll = (v) => v.toFixed(3).replace(".", ",");
  $("#stats").innerHTML = `
    <div class="stat"><span>Matchs testés</span><b>${s.matches.toLocaleString("fr-FR")}</b></div>
    <div class="stat"><span>Erreur du modèle seul</span><b>${ll(s.logloss.p_model)}</b></div>
    <div class="stat"><span>Erreur des probabilités publiées</span><b>${ll(s.logloss.p_pub)}</b></div>
    <div class="stat"><span>Erreur du marché à la clôture</span><b>${ll(s.logloss.p_close)}</b></div>`;
}

$("#newsletter-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/newsletter", { method: "POST", body: JSON.stringify({ email: f.get("email"), consent: f.get("consent") === "on" }) });
    $("#newsletter-msg").textContent = "C'est noté : tu recevras la première newsletter dès son lancement.";
    e.target.reset();
  } catch (err) { $("#newsletter-msg").textContent = err.message; }
};

(async () => {
  me = await api("/api/me");
  if (!me.stripe) $("#demo-banner").hidden = false;
  renderAccount();
  await Promise.all([loadMatches(), loadTrackRecord()]);
})();
