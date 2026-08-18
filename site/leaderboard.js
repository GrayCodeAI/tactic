/* Render the prover leaderboard from the repo's leaderboard.json.
 * Zero dependencies — a small fetch + table build. */
"use strict";

const TIERS = ["trivial", "easy", "medium", "hard"];

const LEADERBOARD_URLS = [
  "../leaderboard.json",    // local dev (serve from repo root)
  "leaderboard.json",       // deployed alongside a copied leaderboard.json
];

function el(tag, attrs = {}) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  return node;
}

async function loadBoard() {
  let lastError = null;
  for (const url of LEADERBOARD_URLS) {
    try {
      const resp = await fetch(url, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const board = await resp.json();
      if (!Array.isArray(board)) throw new Error("expected a JSON array");
      return board;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("failed to load leaderboard.json");
}

function tierBadges(entry) {
  return TIERS.map((tier) => {
    const t = (entry.tiers || {})[tier];
    const text = t && typeof t.total === "number" ? `${t.proved}/${t.total}` : "—";
    const badge = el("span", { class: `badge ${tier}`, text, title: `${tier}: ${text}` });
    return badge;
  });
}

function boardTable(board) {
  const sorted = [...board].sort(
    (a, b) => (b.score ?? 0) - (a.score ?? 0) || (b.date || "").localeCompare(a.date || "")
  );

  const columns = [
    ["#", "rank"], ["model", "model"], ["score", "score"],
    ["tiers", "tier"], ["steps", "steps"], ["date", "date"],
  ];
  const table = el("table");
  const headRow = el("tr");
  for (const [label, cls] of columns) {
    headRow.appendChild(el("th", { text: label, class: cls }));
  }
  const head = el("thead");
  head.appendChild(headRow);
  table.appendChild(head);

  const body = el("tbody");
  sorted.forEach((entry, i) => {
    const row = el("tr");
    row.appendChild(el("td", { text: String(i + 1), class: "rank" }));
    row.appendChild(el("td", { text: entry.name || "unknown", class: "model", title: entry.name || "" }));

    const scoreCell = el("td", { class: "score" });
    scoreCell.appendChild(el("span", { class: "score-badge", text: `${entry.score ?? 0}/${entry.total ?? 100}` }));
    const pct = entry.total ? Math.round(((entry.score ?? 0) / entry.total) * 100) : 0;
    const bar = el("span", { class: "bar", title: `${pct}%` });
    const fill = el("i");
    fill.style.width = `${pct}%`;
    bar.appendChild(fill);
    scoreCell.appendChild(bar);
    row.appendChild(scoreCell);

    const tierCell = el("td", { class: "tier" });
    for (const badge of tierBadges(entry)) tierCell.appendChild(badge);
    row.appendChild(tierCell);

    row.appendChild(el("td", { text: String(entry.max_steps ?? "—"), class: "steps" }));
    row.appendChild(el("td", { text: entry.date || "", class: "date" }));
    body.appendChild(row);
  });
  table.appendChild(body);
  return table;
}

async function main() {
  const loading = document.getElementById("loading");
  const errorBox = document.getElementById("error");
  const boardEl = document.getElementById("board");
  try {
    const board = await loadBoard();
    loading.hidden = true;
    if (!board.length) {
      errorBox.textContent = "The leaderboard is empty — run `prover leaderboard --run` and submit a PR.";
      errorBox.hidden = false;
      return;
    }
    boardEl.appendChild(boardTable(board));
  } catch (err) {
    loading.hidden = true;
    errorBox.textContent = `Could not load the leaderboard: ${err.message}`;
    errorBox.hidden = false;
  }
}

main();
