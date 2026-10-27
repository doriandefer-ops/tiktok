const $ = (s) => document.querySelector(s);
const pct = (p) => `${Math.round(p * 100)} %`;
const OUTCOME = { home: "Domicile", draw: "Nul", away: "Extérieur" };
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
    el.innerHTML = `<span class="badge">${me.plan}</span><span class="muted">${me.email}</span><button class="ghost" id="logout-btn">Déconnexion</button>`;
    $("#logout-btn").onclick = async () => { await api("/api/logout", { method: "POST" }); location.reload(); };
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

document.querySelectorAll("[data-plan]").forEach((b) => {
  b.onclick = async () => {
    if (!me.email) return openAuth(true);
    try { location.href = (await api(`/api/checkout/${b.dataset.plan}`, { method: "POST" })).url; }
    catch (err) { alert(err.message); }
  };
});

function matchCard(m) {
  const p = m.probs;
  let html = `<div class="card">
    <div class="meta"><span>${m.league_name}</span><span>${m.date.split("-").reverse().join("/")} ${m.time || ""}</span></div>
    <div class="teams"><span>${m.home}</span><span>${m.away}</span></div>
    <div class="bar"><div class="h" style="flex:${p.home}">${pct(p.home)}</div><div class="d" style="flex:${p.draw}">${pct(p.draw)}</div><div class="a" style="flex:${p.away}">${pct(p.away)}</div></div>
    <div class="legend"><span>Domicile</span><span>Nul</span><span>Extérieur</span></div>`;
  if (m.locked) {
    html += `<div class="locked">Buts, scores probables et écarts avec les cotes : <a href="#offres">offre Premium</a></div>`;
  } else {
    html += `<div class="extra">
      <div>+2,5 buts<b>${pct(m.over25)}</b></div>
      <div>Les deux marquent<b>${pct(m.btts)}</b></div>
      <div>Buts attendus<b>${m.xg[0]} – ${m.xg[1]}</b></div></div>
      <p class="muted">Scores les plus probables : ${m.scores.map((s) => `${s.score} (${pct(s.p)})`).join(", ")}</p>`;
    for (const v of m.value) html += `<div class="value">Écart favorable : ${OUTCOME[v.outcome]} à ${v.odds.toFixed(2)} (+${(v.edge * 100).toFixed(1)} % d'espérance estimée)</div>`;
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

function chart(byMonth) {
  const months = Object.keys(byMonth).sort();
  let cum = 0;
  const pts = months.map((m) => (cum += byMonth[m].profit));
  const W = 760, H = 220, pad = 40;
  const lo = Math.min(0, ...pts), hi = Math.max(0, ...pts);
  const x = (i) => pad + (i * (W - 2 * pad)) / Math.max(1, pts.length - 1);
  const y = (v) => H - pad - ((v - lo) / (hi - lo || 1)) * (H - 2 * pad);
  const path = pts.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("");
  const labels = months.map((m, i) => `<text x="${x(i)}" y="${H - 14}" fill="#8b949e" font-size="11" text-anchor="middle">${m.slice(5)}/${m.slice(2, 4)}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gains cumulés en unités">
    <text x="${pad}" y="22" fill="#e6edf3" font-size="13">Gains cumulés (mise de 1 unité par pari)</text>
    <line x1="${pad}" x2="${W - pad}" y1="${y(0)}" y2="${y(0)}" stroke="#2a313c"/>
    <path d="${path}" fill="none" stroke="${cum < 0 ? "#f85149" : "#3fb950"}" stroke-width="2"/>
    <text x="${x(pts.length - 1)}" y="${y(cum) - 8}" fill="#e6edf3" font-size="12" text-anchor="end">${cum.toFixed(1)} u</text>
    ${labels}</svg>`;
}

async function loadTrackRecord() {
  const { summary: s, picks } = await api("/api/track-record");
  if (!s.matches) return;
  const cls = (v) => (v < 0 ? "neg" : "pos");
  $("#stats").innerHTML = `
    <div class="stat"><span>Matchs analysés</span><b>${s.matches.toLocaleString("fr-FR")}</b></div>
    <div class="stat"><span>Value bets signalés</span><b>${s.bets}</b></div>
    <div class="stat"><span>Taux de réussite</span><b>${pct(s.hit_rate)}</b></div>
    <div class="stat"><span>ROI (mise fixe)</span><b class="${cls(s.roi)}">${(s.roi * 100).toFixed(1)} %</b></div>
    <div class="stat"><span>CLV moyen</span><b class="${cls(s.clv)}">${(s.clv * 100).toFixed(1)} %</b></div>`;
  $("#chart").innerHTML = chart(s.by_month);
  $("#picks tbody").innerHTML = picks.map((h) => `<tr>
    <td>${h.date.split("-").reverse().join("/")}</td><td>${h.home} – ${h.away}</td>
    <td>${OUTCOME[h.pick.outcome]}</td><td>${h.pick.odds.toFixed(2)}</td><td>${pct(h.pick.p)}</td>
    <td>${h.score}</td><td class="${h.pick.won ? "pos" : "neg"}">${h.pick.won ? "Gagné" : "Perdu"}</td></tr>`).join("");
}

(async () => {
  me = await api("/api/me");
  renderAccount();
  await Promise.all([loadMatches(), loadTrackRecord()]);
})();
