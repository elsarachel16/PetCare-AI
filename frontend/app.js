"use strict";

/* PetCare AI front end: plain JavaScript, no build step. The FastAPI server serves this folder. */

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const CATS = { exercise: "Exercise", grooming: "Grooming", feeding: "Feeding", health: "Health" };
const SPECIES = ["dog", "cat", "rabbit", "bird", "hamster", "guinea pig", "other"];

const S = {
  view: "today", pets: [], petId: null, plan: null, reminders: [], reports: [],
  chats: {}, flow: [], flowState: "idle", health: null, editing: null, pending: null, busy: false,
};

/* ---------- helpers ---------- */
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = () => $("#view");

function store(key, value) {
  try { if (value === undefined) return JSON.parse(localStorage.getItem(key)); localStorage.setItem(key, JSON.stringify(value)); } catch { return null; }
}
async function api(path, opts = {}) {
  const res = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let msg = "Something went wrong. Try again.";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = "Check the details you entered: " + j.detail.map((d) => (d.loc || []).slice(-1)[0]).join(", ") + ".";
    } catch { /* keep default */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}
let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "show" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = ""), 3200);
}
const pad = (n) => String(n).padStart(2, "0");
const isoToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const todayName = () => DAYS[(new Date().getDay() + 6) % 7];
function fmtTime(t) {
  const [h, m] = t.split(":").map(Number);
  return `${((h + 11) % 12) + 1}:${pad(m)} ${h < 12 ? "am" : "pm"}`;
}
function fmtAge(a) {
  if (a == null) return "Unknown";
  return a < 1 ? `${Math.round(a * 12)} months` : `${+a.toFixed(1)} ${a === 1 ? "year" : "years"}`;
}
function fmtDue(iso) {
  const days = Math.round((new Date(iso + "T00:00:00") - new Date(isoToday() + "T00:00:00")) / 86400000);
  if (days < 0) return { text: `Overdue by ${-days} day${days === -1 ? "" : "s"}`, late: true };
  if (days === 0) return { text: "Due today", late: false };
  if (days === 1) return { text: "Due tomorrow", late: false };
  return { text: `Due in ${days} days (${iso})`, late: false };
}
const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
function md(text) {
  let html = "", list = false;
  for (const line of esc(text).split("\n")) {
    if (line.startsWith("- ")) {
      if (!list) { html += "<ul>"; list = true; }
      html += `<li>${inline(line.slice(2))}</li>`;
    } else {
      if (list) { html += "</ul>"; list = false; }
      if (line.trim()) html += `<p>${inline(line)}</p>`;
    }
  }
  return html + (list ? "</ul>" : "");
}
const curPet = () => S.pets.find((p) => p.id === S.petId) || null;
const petName = (id) => (S.pets.find((p) => p.id === id) || {}).name || "Unknown pet";
const doneKey = (id) => `petcare.done.${id}.${isoToday()}`;

/* ---------- data ---------- */
async function loadPets() {
  S.pets = await api("/pets");
  if (!S.pets.find((p) => p.id === S.petId)) S.petId = (store("petcare.pet") && S.pets.find((p) => p.id === store("petcare.pet")) ? store("petcare.pet") : (S.pets[0] || {}).id) || null;
}
async function loadPlan() { S.plan = S.petId ? await api(`/pets/${S.petId}/plan`) : null; }
async function loadReminders() { S.reminders = await api("/reminders"); }
async function refreshAll() { await loadPets(); await Promise.all([loadPlan(), loadReminders()]); }
async function setPet(id) { S.petId = id; store("petcare.pet", id); await loadPlan(); render(); }

/* ---------- shared pieces ---------- */
function petChips() {
  if (S.pets.length < 2) return "";
  return `<div class="chips" role="group" aria-label="Choose a pet">${S.pets.map((p) =>
    `<button class="chip" data-pet="${esc(p.id)}" aria-pressed="${p.id === S.petId}">${esc(p.name)}</button>`).join("")}</div>`;
}
function tagCard(p, mini = false) {
  return `<section class="tag${mini ? " mini" : ""}" aria-label="${esc(p.name)}'s profile">
    <h2>${esc(p.name)}</h2>
    <p class="sub">${esc(p.breed || p.species)}${p.breed ? ` (${esc(p.species)})` : ""}</p>
    <dl>
      <div><dt>Age</dt><dd>${esc(fmtAge(p.age))}</dd></div>
      <div><dt>Weight</dt><dd>${esc(p.weight_kg)} kg</dd></div>
      <div><dt>Activity</dt><dd>${esc(p.activity_level)}</dd></div>
    </dl>
    ${mini
      ? `<div class="pet-actions"><button class="btn small" data-act="edit-pet" data-id="${esc(p.id)}">Edit</button>
         <button class="btn small danger" data-act="delete-pet" data-id="${esc(p.id)}">Delete</button></div>`
      : `<button class="btn small" data-go="pets">Edit profile</button>`}
  </section>`;
}
function noPets() {
  return `<div class="empty"><h2>Add your first pet</h2>
    <p>PetCare AI builds a weekly care plan from your pet's age, weight, and activity level.</p>
    <div class="form-actions">
      <button class="btn primary" data-act="new-pet">Add a pet</button>
      <button class="btn" data-act="sample-pet">Try with a sample dog (Bruno)</button>
    </div></div>`;
}

/* ---------- views ---------- */
function viewToday() {
  const pet = curPet();
  const h = new Date().getHours();
  const greet = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  if (!pet) return `<div class="page-head"><h1>${greet}</h1></div>${noPets()}`;

  const tasks = (S.plan && S.plan.week && S.plan.week[todayName()]) || [];
  const done = store(doneKey(pet.id)) || [];
  const count = tasks.filter((t) => done.includes(t.id)).length;
  const pct = tasks.length ? Math.round((count / tasks.length) * 100) : 0;
  const rems = S.reminders.filter((r) => r.pet_id === pet.id).slice(0, 5);

  const taskHtml = tasks.length
    ? `<div class="progress" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="Tasks done today"><span style="width:${pct}%"></span></div>
       <p class="hint">${count} of ${tasks.length} done</p>` +
      tasks.map((t) => `<label class="task cat-${esc(t.category)}${done.includes(t.id) ? " done" : ""}">
        <input type="checkbox" data-task="${esc(t.id)}" ${done.includes(t.id) ? "checked" : ""}>
        <span class="time">${fmtTime(t.time)}</span><span class="what">${esc(t.task)}</span></label>`).join("")
    : `<p>${S.plan ? "Nothing is scheduled for today." : `${esc(pet.name)} doesn't have a care plan yet.`}</p>
       <button class="btn primary" data-ask="Create a weekly care plan for ${esc(pet.name)}.">Create ${esc(pet.name)}'s care plan</button>`;

  const remHtml = rems.length
    ? rems.map((r) => { const d = fmtDue(r.due_date); return `<div class="rem-row"><div><strong>${esc(r.title)}</strong><div class="when${d.late ? " late" : ""}">${esc(d.text)}</div></div>
        <div class="rem-actions"><button class="btn small" data-act="done-reminder" data-id="${esc(r.id)}">Done</button></div></div>`; }).join("")
    : `<p class="hint">No reminders yet. Ask PetCare AI: "Next vet appointment 20 October".</p>`;

  return `<div class="page-head"><div><h1>${greet}</h1><p>${new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p></div>${petChips()}</div>
    <div class="today-grid">
      ${tagCard(pet)}
      <div>
        <section class="panel"><h2>Today for ${esc(pet.name)}</h2>${taskHtml}</section>
        <section class="panel"><h2>Coming up</h2>${remHtml}</section>
      </div>
    </div>
    <form class="ask-quick" id="quickAsk"><label class="sr" for="quickInput">Ask PetCare AI</label>
      <input id="quickInput" placeholder="Ask PetCare AI, e.g. Create a grooming schedule for ${esc(pet.name)}" maxlength="1000" required>
      <button class="btn primary">Ask</button></form>`;
}

function taskLi(t) {
  return `<li class="wt cat-${esc(t.category)}"><span class="t">${fmtTime(t.time)}</span> ${esc(t.task)}<span class="k">${CATS[t.category] || ""}</span></li>`;
}
function viewPlan() {
  const pet = curPet();
  if (!pet) return `<div class="page-head"><h1>Care plan</h1></div>${noPets()}`;
  const p = S.plan;
  const head = `<div class="page-head"><div><h1>${esc(pet.name)}'s weekly care plan</h1>
    <p>${p ? `Revision ${p.revision}, updated ${esc(new Date(p.generated_at).toLocaleString())}` : "No plan yet."}</p></div>
    <div class="form-actions" style="margin:0">${petChips()}
    <button class="btn primary" data-ask="Create a weekly care plan for ${esc(pet.name)}.">${p ? "Regenerate plan" : "Create care plan"}</button></div></div>`;
  if (!p) return head + `<div class="empty"><h2>No plan yet</h2><p>The exercise, grooming, feeding, and appointment agents will each add their part.</p></div>`;

  const legend = `<div class="legend">${Object.entries(CATS).map(([k, v]) => `<span class="cat-${k}"><i></i>${v}</span>`).join("")}</div>`;
  const week = `<div class="week">${DAYS.map((d) => `<section class="day${d === todayName() ? " today" : ""}"><h3>${d}</h3>
    <ul>${((p.week || {})[d] || []).map(taskLi).join("") || `<li class="hint" style="padding:6px">Nothing scheduled</li>`}</ul></section>`).join("")}</div>`;

  const ex = p.exercise, gr = p.grooming, fe = p.feeding;
  const tip = (x) => (x && x.ai_tip ? `<div class="tip">${esc(x.ai_tip)}</div>` : "");
  const list = (a) => `<ul>${(a || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`;
  const details = `<div class="detail-grid">
    ${ex ? `<section class="panel"><h2>Exercise</h2><p><strong>About ${ex.daily_minutes} minutes a day</strong>${(ex.unavailable_days || []).length ? `, away on ${esc(ex.unavailable_days.join(", "))}` : ""}.</p>${list(ex.notes)}${tip(ex)}</section>` : ""}
    ${gr ? `<section class="panel"><h2>Grooming</h2><p><strong>Brushing ${gr.brushing.per_week}x a week</strong> (${esc(gr.brushing.days.join(", ") || "as needed")}).</p>
      <p>Baths: ${esc(gr.bath.text)}</p>${gr.professional_interval_weeks ? `<p>Professional grooming every ${gr.professional_interval_weeks} weeks.</p>` : ""}${list(gr.notes)}${tip(gr)}</section>` : ""}
    ${fe ? `<section class="panel"><h2>Feeding</h2><p><strong>${fe.meals_per_day} meals a day</strong> at ${esc(fe.times.map(fmtTime).join(", "))}.</p>${list(fe.notes)}${tip(fe)}</section>` : ""}
    ${(p.appointments || []).length ? `<section class="panel"><h2>Appointments</h2>${list(p.appointments.map((a) => `${a.title}: ${a.date}`))}</section>` : ""}
  </div>`;
  const attention = ((p.assessment || {}).attention_points || []);
  return head + legend + week + details +
    (attention.length ? `<section class="panel" style="margin-top:18px"><h2>Keep in mind</h2>${list(attention)}</section>` : "") +
    `<p class="fine">${esc(p.disclaimer)}</p>`;
}

function chatOf() { const k = S.petId || "none"; return (S.chats[k] = S.chats[k] || []); }
function viewAsk() {
  const pet = curPet();
  const n = pet ? pet.name : "your pet";
  const chips = pet ? [
    `Create a weekly care plan for ${n}.`, `Create a grooming schedule for ${n}.`, `Help me organize ${n}'s feeding schedule.`,
    `I won't be home on Wednesday. Change ${n}'s exercise plan.`, "What should I prepare before the vet appointment?",
  ] : [];
  const llm = S.health && S.health.llm;
  const mode = llm && llm.reachable && llm.model_ready
    ? `AI mode: ${esc(llm.model)} is running through Ollama.`
    : `Rules mode: Ollama or ${esc((llm && llm.model) || "qwen2.5:3b")} wasn't found, so plans use built-in care rules without AI-written tips.`;
  return `<div class="page-head"><div><h1>Ask PetCare AI</h1><p>${pet ? `Talking about ${esc(pet.name)}.` : "Add a pet first so the agents know who to plan for."}</p></div>${petChips()}</div>
    <div class="ask">
      <section class="panel chat"><div class="log" id="chatLog" aria-live="polite"></div>
        <div class="chips" id="chips">${chips.map((c) => `<button class="chip" data-ask="${esc(c)}">${esc(c)}</button>`).join("")}</div>
        <form id="chatForm"><label class="sr" for="chatInput">Your message</label>
          <input id="chatInput" placeholder="Ask about exercise, grooming, feeding, or appointments" maxlength="1000" autocomplete="off" required>
          <button class="btn primary" id="sendBtn">Send</button></form></section>
      <aside class="panel flow" aria-label="Agent workflow"><h2>Agent workflow</h2><ol id="flow"></ol><p class="hint" id="mode">${mode}</p></aside>
    </div>`;
}
function renderChat() {
  const log = $("#chatLog"); if (!log) return;
  const msgs = chatOf();
  log.innerHTML = msgs.length
    ? msgs.map((m) => `<div class="msg ${m.role}${m.error ? " error" : ""}">${m.role === "ai" ? md(m.text) : `<p>${esc(m.text)}</p>`}
        ${m.plan ? `<button class="btn small" data-go="plan">View care plan</button>` : ""}</div>`).join("")
    : `<p class="hint">Ask in your own words. Each request is passed through routing, profile, assessment, supervisor, and specialist agents.</p>`;
  log.lastElementChild && log.lastElementChild.scrollIntoView({ block: "nearest" });
}
function renderFlow() {
  const ol = $("#flow"); if (!ol) return;
  if (S.flowState === "idle" && !S.flow.length) { ol.innerHTML = `<li class="on"><b>Waiting for a request</b><span>Steps appear here as the agents work.</span></li>`; return; }
  if (S.flowState === "working") { ol.innerHTML = `<li class="wait"><b>Agents are working</b><span>Routing your request. This can take a little longer in AI mode.</span></li>`; return; }
  ol.innerHTML = S.flow.map((t, i) => `<li data-i="${i}"><b>${esc(t.agent)}</b><span>${esc(t.summary)}</span><em>${t.ms} ms</em></li>`).join("");
}
function animateFlow() {
  renderFlow();
  const items = [...document.querySelectorAll("#flow li")];
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  items.forEach((li, i) => (reduce ? li.classList.add("on") : setTimeout(() => li.classList.add("on"), i * 160)));
}
async function send(text) {
  text = text.trim(); if (!text || S.busy) return;
  const pet = curPet(), log = chatOf();
  log.push({ role: "user", text }); renderChat();
  S.busy = true; S.flowState = "working"; renderFlow();
  const btn = $("#sendBtn"); if (btn) { btn.disabled = true; btn.textContent = "Working"; }
  try {
    const res = await api("/chat", { method: "POST", body: JSON.stringify({ message: text, pet_id: pet ? pet.id : null }) });
    log.push({ role: "ai", text: res.reply, plan: !!res.care_plan });
    if (res.care_plan) S.plan = res.care_plan;
    S.health = { ...(S.health || {}), llm: res.llm };
    S.flow = res.trace; S.flowState = "done";
    await Promise.all([loadPets(), loadReminders()]);
    if (res.reminders_created) toast(`Saved ${res.reminders_created} reminder${res.reminders_created > 1 ? "s" : ""}.`);
    renderChat(); animateFlow();
  } catch (e) {
    log.push({ role: "ai", text: e.message, error: true });
    S.flowState = "idle"; S.flow = []; renderChat(); renderFlow(); toast(e.message, true);
  } finally {
    S.busy = false;
    const b = $("#sendBtn"); if (b) { b.disabled = false; b.textContent = "Send"; }
  }
}

function petForm() {
  const p = S.editing || {};
  const opt = (v, cur) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(v)}</option>`;
  return `<section class="panel"><h2>${p.id ? `Edit ${esc(p.name)}` : "Add a pet"}</h2>
    <form id="petForm" data-id="${esc(p.id || "")}"><div class="form-grid">
      <div><label for="f-name">Name</label><input id="f-name" name="name" value="${esc(p.name || "")}" maxlength="40" required></div>
      <div><label for="f-species">Species</label><select id="f-species" name="species">${SPECIES.map((s) => opt(s, p.species || "dog")).join("")}</select></div>
      <div><label for="f-breed">Breed (optional)</label><input id="f-breed" name="breed" value="${esc(p.breed || "")}" maxlength="60"></div>
      <div><label for="f-age">Age in years</label><input id="f-age" name="age" type="number" min="0" max="40" step="0.1" value="${esc(p.age ?? 1)}" required></div>
      <div><label for="f-weight">Weight in kg</label><input id="f-weight" name="weight_kg" type="number" min="0.1" max="200" step="0.1" value="${esc(p.weight_kg ?? 10)}" required></div>
      <div><label for="f-act">Activity level</label><select id="f-act" name="activity_level">${["low", "moderate", "high"].map((s) => opt(s, p.activity_level || "moderate")).join("")}</select></div>
      <div class="wide"><label for="f-notes">Notes (optional)</label><textarea id="f-notes" name="notes" maxlength="500">${esc(p.notes || "")}</textarea></div>
    </div><div class="form-actions"><button class="btn primary">Save pet</button><button type="button" class="btn" data-act="cancel-edit">Cancel</button></div></form></section>`;
}
function viewPets() {
  if (S.editing) return `<div class="page-head"><h1>My pets</h1></div>${petForm()}`;
  return `<div class="page-head"><div><h1>My pets</h1><p>Profiles drive every plan the agents build.</p></div>
    <button class="btn primary" data-act="new-pet">Add a pet</button></div>
    ${S.pets.length ? `<div class="pet-list">${S.pets.map((p) => tagCard(p, true)).join("")}</div>` : noPets()}`;
}

function viewReminders() {
  if (!S.pets.length) return `<div class="page-head"><h1>Reminders</h1></div>${noPets()}`;
  const rows = S.reminders.length
    ? S.reminders.map((r) => { const d = fmtDue(r.due_date); return `<div class="rem-row"><div><strong>${esc(r.title)}</strong>
        <div class="when${d.late ? " late" : ""}">${esc(petName(r.pet_id))}. ${esc(d.text)}${r.repeat_weeks ? `. Repeats every ${r.repeat_weeks} week${r.repeat_weeks > 1 ? "s" : ""}` : ""}</div></div>
        <div class="rem-actions"><button class="btn small" data-act="done-reminder" data-id="${esc(r.id)}">Done</button>
        <button class="btn small danger" data-act="del-reminder" data-id="${esc(r.id)}">Delete</button></div></div>`; }).join("")
    : `<p class="hint">Nothing due. Add a reminder below, or tell PetCare AI about an appointment.</p>`;
  return `<div class="page-head"><h1>Reminders</h1></div>
    <section class="panel"><h2>Upcoming</h2>${rows}</section>
    <section class="panel"><h2>Add a reminder</h2><form id="remForm"><div class="form-grid">
      <div><label for="r-pet">Pet</label><select id="r-pet" name="pet_id">${S.pets.map((p) => `<option value="${esc(p.id)}"${p.id === S.petId ? " selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>
      <div><label for="r-title">What is it for?</label><input id="r-title" name="title" maxlength="120" placeholder="Flea treatment" required></div>
      <div><label for="r-date">Date</label><input id="r-date" name="due_date" type="date" value="${isoToday()}" required></div>
      <div><label for="r-rep">Repeat</label><select id="r-rep" name="repeat_weeks"><option value="">Does not repeat</option>${[1, 2, 4, 8, 12].map((n) => `<option value="${n}">Every ${n} week${n > 1 ? "s" : ""}</option>`).join("")}</select></div>
      <div><label for="r-cat">Type</label><select id="r-cat" name="category">${["general", "health", "grooming", "exercise", "feeding"].map((c) => `<option>${c}</option>`).join("")}</select></div>
    </div><div class="form-actions"><button class="btn primary">Save reminder</button></div></form></section>`;
}

function viewReports() {
  const rows = S.reports.map((r) => `<tr><td>${esc(new Date(r.created_at).toLocaleString())}</td><td>${esc(r.pet_name)}</td>
    <td>${esc(r.request)}</td><td>${esc((r.intent || "").replace(/_/g, " "))}</td>
    <td><a class="btn small" href="/api/reports/${encodeURIComponent(r.id)}/download">Download JSON</a></td></tr>`).join("");
  return `<div class="page-head"><div><h1>Reports</h1><p>Every request saves a JSON report with the pet profile, plan, and full agent trace.</p></div></div>
    <section class="panel">${S.reports.length ? `<div class="table-wrap"><table><thead><tr><th>When</th><th>Pet</th><th>Request</th><th>Intent</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<p class="hint">No reports yet. Ask PetCare AI something and the report appears here.</p>`}</section>`;
}

/* ---------- routing & rendering ---------- */
const VIEWS = { today: viewToday, plan: viewPlan, ask: viewAsk, pets: viewPets, reminders: viewReminders, reports: viewReports };

async function go(name) {
  S.view = name; S.editing = null;
  if (name === "reports") { try { S.reports = await api("/reports"); } catch (e) { toast(e.message, true); } }
  if (name === "reminders" || name === "today") { try { await loadReminders(); } catch { /* keep cached */ } }
  render();
}
function render() {
  document.querySelectorAll("#nav button").forEach((b) => (b.dataset.view === S.view ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  view().innerHTML = VIEWS[S.view]();
  if (S.view === "ask") {
    renderChat(); S.flow.length ? animateFlow() : renderFlow();
    if (S.pending) { const t = S.pending; S.pending = null; send(t); }
  }
}
function askAI(text) { S.pending = text; S.view = "ask"; render(); }

/* ---------- actions ---------- */
async function act(name, d) {
  try {
    if (name === "new-pet") { S.editing = {}; S.view = "pets"; render(); }
    else if (name === "edit-pet") { S.editing = S.pets.find((p) => p.id === d.id); render(); }
    else if (name === "cancel-edit") { S.editing = null; render(); }
    else if (name === "sample-pet") {
      const p = await api("/pets", { method: "POST", body: JSON.stringify({ name: "Bruno", species: "dog", breed: "Labrador", age: 3, weight_kg: 24, activity_level: "moderate" }) });
      S.petId = p.id; store("petcare.pet", p.id); await refreshAll(); toast("Added Bruno."); render();
    }
    else if (name === "delete-pet") {
      const p = S.pets.find((x) => x.id === d.id);
      if (!confirm(`Delete ${p.name}? Their care plan and reminders will be deleted too.`)) return;
      await api(`/pets/${d.id}`, { method: "DELETE" });
      if (S.petId === d.id) S.petId = null;
      await refreshAll(); toast(`Deleted ${p.name}.`); render();
    }
    else if (name === "done-reminder") { await api(`/reminders/${d.id}/done`, { method: "POST" }); await loadReminders(); toast("Marked done."); render(); }
    else if (name === "del-reminder") { await api(`/reminders/${d.id}`, { method: "DELETE" }); await loadReminders(); toast("Reminder deleted."); render(); }
  } catch (e) { toast(e.message, true); }
}

document.addEventListener("click", async (e) => {
  const nav = e.target.closest("#nav button");
  if (nav) return go(nav.dataset.view);
  const el = e.target.closest("[data-go],[data-pet],[data-ask],[data-act]");
  if (!el) return;
  if (el.dataset.go) go(el.dataset.go);
  else if (el.dataset.pet) setPet(el.dataset.pet);
  else if (el.dataset.ask) askAI(el.dataset.ask);
  else if (el.dataset.act) act(el.dataset.act, el.dataset);
});
document.addEventListener("change", (e) => {
  if (!e.target.matches("input[data-task]")) return;
  const pet = curPet(); if (!pet) return;
  let done = store(doneKey(pet.id)) || [];
  done = e.target.checked ? [...new Set([...done, e.target.dataset.task])] : done.filter((x) => x !== e.target.dataset.task);
  store(doneKey(pet.id), done); render();
});
document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, data = Object.fromEntries(new FormData(f));
  try {
    if (f.id === "chatForm") { const i = $("#chatInput"); const t = i.value; i.value = ""; send(t); }
    else if (f.id === "quickAsk") askAI($("#quickInput").value);
    else if (f.id === "petForm") {
      const body = { ...data, age: Number(data.age), weight_kg: Number(data.weight_kg) };
      const saved = f.dataset.id ? await api(`/pets/${f.dataset.id}`, { method: "PUT", body: JSON.stringify(body) }) : await api("/pets", { method: "POST", body: JSON.stringify(body) });
      if (!f.dataset.id) { S.petId = saved.id; store("petcare.pet", saved.id); }
      S.editing = null; await refreshAll(); toast(`Saved ${saved.name}.`); render();
    }
    else if (f.id === "remForm") {
      const body = { ...data, repeat_weeks: data.repeat_weeks ? Number(data.repeat_weeks) : null };
      await api("/reminders", { method: "POST", body: JSON.stringify(body) });
      await loadReminders(); toast("Reminder saved."); render();
    }
  } catch (err) { toast(err.message, true); }
});

(async function boot() {
  try { S.health = await api("/health"); } catch { /* server health is optional */ }
  try { await refreshAll(); } catch (e) { toast("Can't reach the PetCare AI server. Start it and reload.", true); }
  render();
})();
