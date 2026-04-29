const $ = (id) => document.getElementById(id);
const money = (v) => v == null ? "-" : "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
const num = (v) => v == null ? "-" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
const pct = (v) => v == null ? "-" : Number(v).toFixed(1) + "%";

function params() {
  const fd = new FormData($("filters"));
  const p = new URLSearchParams();
  for (const [k, v] of fd.entries()) {
    if (v !== "") p.set(k, v);
  }
  if (!$("filters").elements.plausible.checked) p.set("plausible", "false");
  if ($("filters").elements.cap_proxy.checked) p.set("cap_proxy", "true");
  return p;
}

async function getJson(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || "Request failed");
  return data;
}

function showError(err) {
  $("error").textContent = err.message || String(err);
  $("error").style.display = "block";
}

function clearError() {
  $("error").style.display = "none";
  $("error").textContent = "";
}

function fillSelect(id, values, allLabel) {
  const el = $(id);
  el.innerHTML = "";
  if (allLabel !== null) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = allLabel;
    el.appendChild(opt);
  }
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  });
}

function renderSummary(s) {
  $("public_wage_rows").textContent = num(s.public_wage_rows);
  $("lca_filings").textContent = num(s.lca_filings);
  $("jobs_requested").textContent = num(s.jobs_requested);
  $("lottery_weight_points").textContent = num(s.lottery_weight_points);
  $("median_offer").textContent = money(s.median_offer);
  $("avg_offer_vs_required").textContent = pct(s.avg_offer_vs_required);
  $("estimated_picked").textContent = num(s.estimated_picked);
  $("estimated_pick_rate").textContent = pct(s.estimated_pick_rate);
}

function renderTable(id, columns, rows) {
  const table = $(id);
  if (!rows.length) {
    table.innerHTML = "<tbody><tr><td>No matches.</td></tr></tbody>";
    return;
  }
  const head = "<thead><tr>" + columns.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("") + "</tr></thead>";
  const body = "<tbody>" + rows.map((row) => "<tr>" + columns.map((c) => {
    let v = row[c.key];
    if (c.format === "money") v = money(v);
    else if (c.format === "num") v = num(v);
    else if (c.format === "pct") v = pct(v);
    else if (c.format === "bool") v = v ? '<span class="pill yes">Yes</span>' : '<span class="pill">No</span>';
    else if (v == null || v === "") v = "-";
    return `<td class="${c.num ? "num" : ""}">${v}</td>`;
  }).join("") + "</tr>").join("") + "</tbody>";
  table.innerHTML = head + body;
}

async function loadOptions() {
  const data = await getJson("/api/options");
  fillSelect("state", data.states, "All states");
  fillSelect("wage_level", data.wage_levels, "All levels");
  fillSelect("case_status", data.statuses, null);
  $("case_status").value = "Certified";
  fillSelect("salary_band", data.salary_bands, "All bands");
  $("selected_total").value = data.default_selected_registrations;
  $("selected_source_count").textContent = num(data.default_selected_registrations);
  $("selection_source").href = data.selection_source_url;

  const dim = $("dimension");
  dim.innerHTML = data.group_dimensions
    .map((d) => `<option value="${d.value}">${d.label}</option>`)
    .join("");
}

async function search() {
  clearError();
  const p = params();
  const [searchData, groupData] = await Promise.all([
    getJson("/api/search?" + p.toString()),
    getJson(
      "/api/group?" +
        p.toString() +
        "&dimension=" +
        encodeURIComponent($("dimension").value) +
        "&limit=" +
        encodeURIComponent($("group_limit").value),
    ),
  ]);

  renderSummary(searchData.summary);
  renderTable("group_table", [
    { key: "group_label", label: groupData.dimension_label },
    { key: "jobs_requested", label: "Filed Jobs", format: "num", num: true },
    { key: "estimated_picked", label: "Est. Picked", format: "num", num: true },
    { key: "estimated_pick_rate", label: "Est. Pick Rate", format: "pct", num: true },
    { key: "lottery_weight_points", label: "Weight Points", format: "num", num: true },
    { key: "lca_filings", label: "Filings", format: "num", num: true },
    { key: "median_offer", label: "Median Offer", format: "money", num: true },
    { key: "avg_offer_vs_required", label: "Offer Above Required", format: "pct", num: true },
    { key: "cap_proxy_jobs", label: "Cap Proxy Jobs", format: "num", num: true },
  ], groupData.rows);

  renderTable("results_table", [
    { key: "case_number", label: "Case" },
    { key: "employer_name", label: "Company" },
    { key: "soc_title", label: "Job" },
    { key: "soc_code", label: "Code" },
    { key: "worksite_city", label: "City" },
    { key: "worksite_state", label: "State" },
    { key: "wage_level", label: "Level" },
    { key: "worker_positions", label: "Jobs", format: "num", num: true },
    { key: "weighted_entries", label: "Weight", format: "num", num: true },
    { key: "annual_wage_from", label: "Offer From", format: "money", num: true },
    { key: "annual_wage_to", label: "Offer To", format: "money", num: true },
    { key: "annual_prevailing_wage", label: "Required Wage", format: "money", num: true },
    { key: "wage_premium_pct", label: "Above Required", format: "pct", num: true },
    { key: "salary_band", label: "Band" },
    { key: "begin_date", label: "Start" },
    { key: "cap_season_proxy_flag", label: "Cap Proxy", format: "bool" },
    { key: "h1b_dependent", label: "H-1B Dep.", format: "bool" },
    { key: "secondary_entity_business_name", label: "Client / Secondary Site" },
  ], searchData.rows);
}

function hardReset() {
  const form = $("filters");
  [...form.elements].forEach((el) => {
    if (!el.name) return;
    if (el.type === "checkbox") el.checked = el.name === "plausible";
    else if (el.tagName === "SELECT") el.selectedIndex = 0;
    else el.value = "";
  });
  $("case_status").value = "Certified";
  $("selected_total").value = $("selected_source_count").textContent.replaceAll(",", "");
  search().catch(showError);
}

$("filters").addEventListener("submit", (event) => {
  event.preventDefault();
  search().catch(showError);
});

$("dimension").addEventListener("change", () => search().catch(showError));
$("group_limit").addEventListener("change", () => search().catch(showError));
$("reset").addEventListener("click", hardReset);

loadOptions().then(search).catch(showError);
