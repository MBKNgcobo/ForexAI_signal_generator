"""Server-rendered signals dashboard (SSE + 10s polling fallback)."""

PAGE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ForexAI — Signal Tracking</title>
<style>
body { font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 1100px; }
.badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 0.4rem;
  font-weight: 600; font-size: 0.85rem; }
.active { background: #e3f2fd; color: #0d47a1; }
.tp { background: #e8f5e9; color: #1b5e20; }
.sl { background: #ffebee; color: #b71c1c; }
.other { background: #f3e5f5; color: #4a148c; }
table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left;
  font-size: 0.9rem; }
#health { padding: 0.75rem; border: 1px solid #ccc; border-radius: 0.5rem; }
.stale { color: #b71c1c; font-weight: 700; }
.filters { margin: 1rem 0; display: flex; gap: 0.5rem; flex-wrap: wrap; }
</style>
</head>
<body>
<h1>Signal Tracking</h1>
<div id="health" role="status">Connecting…</div>
<div class="filters">
<label>Status <select id="f-status">
<option value="">All</option><option value="active">Active</option>
<option value="completed">Completed</option>
<option value="ACCEPTED">Accepted</option><option value="ACTIVE">Active</option>
<option value="TAKE_PROFIT_HIT">TP hit</option>
<option value="STOP_LOSS_HIT">SL hit</option>
<option value="CANCELLED">Cancelled</option><option value="EXPIRED">Expired</option>
<option value="OUTCOME_UNRESOLVED">Unresolved</option>
</select></label>
<label>Symbol <input id="f-symbol" placeholder="EURUSD" size="8"></label>
<label>Direction <select id="f-direction">
<option value="">All</option><option value="LONG">LONG</option>
<option value="SHORT">SHORT</option></select></label>
<label>Outcome <select id="f-outcome">
<option value="">All</option><option value="TAKE_PROFIT_HIT">TP</option>
<option value="STOP_LOSS_HIT">SL</option></select></label>
<button id="f-apply" type="button">Apply</button>
</div>
<div id="summary"></div>
<h2>Active signals</h2>
<div id="active"><p>Loading…</p></div>
<h2>History</h2>
<div id="history"><p>Loading…</p></div>
"""

PAGE_SCRIPT = """<script>
const $ = (id) => document.getElementById(id);
function badge(status) {
  let cls = "other";
  if (status === "ACTIVE" || status === "ACCEPTED") cls = "active";
  else if (status === "TAKE_PROFIT_HIT") cls = "tp";
  else if (status === "STOP_LOSS_HIT") cls = "sl";
  return '<span class="badge ' + cls + '">' + status + "</span>";
}
function row(s) {
  const move = s.unrealized_move == null ? "—" : Number(s.unrealized_move).toFixed(5);
  return "<tr><td>" + s.signal_id + "</td><td>" + s.symbol + "</td><td>" + s.direction +
    "</td><td>" + (s.timeframe || "") + "</td><td>" + s.entry_price + "</td><td>" +
    (s.current_price == null ? "—" : s.current_price) + "</td><td>" + s.stop_loss +
    "</td><td>" + s.take_profit + "</td><td>" + badge(s.status) + "</td><td>" + move +
    "</td><td>" + s.accepted_at + "</td><td>" + (s.last_price_at || "—") + "</td></tr>";
}
function table(signals) {
  if (!signals.length) return "<p>No signals.</p>";
  return "<table><thead><tr><th>ID</th><th>Symbol</th><th>Dir</th><th>TF</th>" +
    "<th>Entry</th><th>Current</th><th>SL</th><th>TP</th><th>Status</th>" +
    "<th>Move</th><th>Accepted</th><th>Last price</th></tr></thead>" +
    "<tbody>" + signals.map(row).join("") + "</tbody></table>";
}
async function load() {
  const qs = new URLSearchParams();
  const st = $("f-status").value, sy = $("f-symbol").value.trim().toUpperCase();
  const dr = $("f-direction").value, oc = $("f-outcome").value;
  if (st === "active") qs.set("active_only", "true");
  else if (st === "completed") qs.set("completed_only", "true");
  else if (st) qs.set("status", st);
  if (sy) qs.set("symbol", sy);
  if (dr) qs.set("direction", dr);
  if (oc) qs.set("outcome", oc);
  const q = qs.toString() ? ("?" + qs.toString()) : "";
  const h = await fetch("/signals/health").then((r) => r.json());
  const s = await fetch("/signals/summary").then((r) => r.json());
  const a = await fetch("/signals" + q).then((r) => r.json());
  $("health").innerHTML =
    "<strong>Market data:</strong> " + (h.provider_connected ? "connected" : "disconnected") +
    " (" + (h.provider || "unknown") + ") · <strong>Monitor:</strong> " +
    (h.monitoring_running ? "running" : "stopped") +
    " · <strong>Active:</strong> " + h.active_count +
    " · <strong>Last cycle:</strong> " + (h.last_cycle_at || "never") +
    (h.provider_connected ? "" : ' · <span class="stale">STALE — no hits fabricated</span>') +
    (h.note ? "<br>" + h.note : "");
  $("summary").innerHTML =
    "<p><strong>Total accepted:</strong> " + s.total_accepted + " · " +
    "<strong>Active:</strong> " + s.active + " · " +
    "<strong>TP hits:</strong> " + s.take_profit_hits + " · " +
    "<strong>SL hits:</strong> " + s.stop_loss_hits + " · " +
    "<strong>Cancelled/unresolved:</strong> " + s.cancelled_or_unresolved + " · " +
    "<strong>TP-hit rate:</strong> " +
    (s.outcome_rate == null ? "—" : (s.outcome_rate * 100).toFixed(1) + "%") +
    " <small>(TP/(TP+SL) only — not profitability)</small></p>";
  const act = a.signals.filter((x) => x.is_active);
  const done = a.signals.filter((x) => !x.is_active);
  $("active").innerHTML = act.length ? table(act) :
    "<p>Monitoring running but no active signals.</p>";
  $("history").innerHTML = table(done.length ? done : a.signals);
}
$("f-apply").addEventListener("click", load);
load();
setInterval(load, 10000);
try {
  const src = new EventSource("/signals/stream");
  src.onmessage = load;
  src.onerror = () => {};
} catch (e) {}
</script>
</body>
</html>
"""

PAGE = PAGE_HEAD + PAGE_SCRIPT
