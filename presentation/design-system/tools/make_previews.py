import os
import sys
from pathlib import Path

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "project", "components")

TPL = """<!-- @dsCard group="{group}" height={height}{extra} -->
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{name} — QuantForge</title>
<style>html,body{{margin:0}} #root{{padding:{pad}}}</style></head>
<body>
<div id="root" class="qf-root"></div>
<script>
var Q = window.QuantForge, h = React.createElement, F = React.Fragment, S = Q.sample, fmt = Q.format;
{data}
{body}
</script>
</body>
</html>
"""

# Shared illustrative data for screens and charts. Synthetic, seeded, not a real result.
DATA = r"""
var N = 520, OOS = 300, HOLD = 430;
var eq = S.series(7, N, 0.0011, 0.021, 100, [{from: OOS, to: HOLD, mu: 0.0004, sigma: 0.024}, {from: HOLD, to: N, mu: 0.0001, sigma: 0.026}]);
var bh = S.series(11, N, 0.0007, 0.032, 100);
var xt = [{i: 0, label: '2019'}, {i: 104, label: '2020'}, {i: 208, label: '2021'}, {i: 312, label: '2022'}, {i: 416, label: '2023'}, {i: 519, label: '2024'}];
var H1 = {
  id: 'H-001', title: 'Time-series momentum on crypto majors', status: 'testing',
  statement: 'Instruments whose trailing 12-week return is positive keep outperforming cash over the following week, after realistic trading costs.',
  rationale: 'Investors under-react to slow-moving information, so trends persist for weeks (Moskowitz, Ooi & Pedersen, 2012).',
  criteria: [
    {label: 'Walk-forward Sharpe, net of costs', threshold: '≥ 0.50', result: '0.64', pass: true},
    {label: 'Permutation test p-value', threshold: '< 0.05', result: '0.031', pass: true},
    {label: 'Max drawdown, walk-forward', threshold: '> −35%', result: '−28.9%', pass: true},
    {label: 'Holdout Sharpe, net of costs', threshold: '≥ 0.30', locked: true}
  ],
  frozen: {sha: '3f9a2c1', date: '14 Aug 2026'}, owner: 'T. Stokłosa', updated: 'Updated 2 h ago'
};
"""

P = {}
def add(name, group, height, body, extra="", pad="16px", data=False):
    P[name] = {"group": group, "height": height, "body": body, "extra": extra, "pad": pad, "data": data}

add("Logo", "Brand", 72, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-row', style: {gap: 32}},
  h(Q.Logo, {size: 28}), h(Q.Logo, {size: 22}), h(Q.Logo, {size: 28, wordmark: false})));
""")

add("Icon", "Brand", 150, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(92px, 1fr))', gap: '14px 8px'}},
  Q.Icon.names.map(function (n) { return h('div', {key: n, style: {display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--ink-muted)', fontFamily: 'var(--font-mono)'}}, h(Q.Icon, {name: n, size: 20, style: {color: 'var(--ink)'}}), n); })));
""")

add("Button", "Actions", 96, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 12}},
  h('div', {className: 'qf-row'},
    h(Q.Button, {variant: 'primary', icon: 'run'}, 'Run walk-forward'),
    h(Q.Button, {icon: 'plus'}, 'Register hypothesis'),
    h(Q.Button, {variant: 'ghost', icon: 'download'}, 'Export'),
    h(Q.Button, {variant: 'seal', icon: 'unlock'}, 'Open holdout…'),
    h(Q.Button, {variant: 'danger', icon: 'x'}, 'Reject hypothesis'),
    h(Q.Button, {variant: 'seal', icon: 'lock', disabled: true}, 'Open holdout')),
  h('div', {className: 'qf-row'},
    h(Q.Button, {variant: 'primary', size: 'sm'}, 'Run'), h(Q.Button, {size: 'sm', icon: 'filter'}, 'Filter'), h(Q.Button, {variant: 'ghost', size: 'sm', iconRight: 'arrow'}, 'Open tear sheet'))));
""")

add("StatusBadge", "Status", 84, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 12}},
  h('div', {className: 'qf-row'}, ['proposed', 'testing', 'confirmed', 'rejected', 'inconclusive'].map(function (s) { return h(Q.StatusBadge, {key: s, status: s}); })),
  h('div', {className: 'qf-row'}, ['confirmed', 'rejected', 'inconclusive'].map(function (s) { return h(Q.StatusBadge, {key: s, status: s, size: 'lg'}); }))));
""")

add("PartitionTag", "Status", 64, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-row'},
  h(Q.PartitionTag, {partition: 'is'}), h(Q.PartitionTag, {partition: 'oos'}), h(Q.PartitionTag, {partition: 'holdout'}), h(Q.PartitionTag, {partition: 'holdout', sealed: false}, 'Holdout · opened'),
  h('span', {style: {width: 16}}), h(Q.PartitionTag, {partition: 'is', short: true}), h(Q.PartitionTag, {partition: 'oos', short: true})));
""")

add("Panel", "Layout", 190, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.Panel, {title: 'Transaction costs', icon: 'costs', subtitle: 'RealisticCostModel · spread + 10 bps fee + vol-scaled slippage', actions: h(Q.Button, {size: 'sm', variant: 'ghost'}, 'Compare models'), footer: h('span', null, 'Computed by ', h('code', null, 'quantlab.costs'), ' at ', h('code', null, '3f9a2c1'))},
  h('p', {style: {margin: 0}}, 'Costs remove 0.48 of the 1.12 gross Sharpe. The edge survives, narrowly.')));
""")

add("Metric", "Data display", 132, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.MetricStrip, {items: [
  {label: 'Sharpe, net', partition: 'oos', value: '0.64', ci: ['0.21', '1.05'], size: 'lg'},
  {label: 'Sharpe, net', partition: 'is', value: '1.12', delta: '−0.48', deltaLabel: 'IS → OOS decay', size: 'lg'},
  {label: 'Max drawdown', value: '−28.9', unit: '%', hint: '41 days to recover'},
  {label: 'CAGR', value: '+14.2', unit: '%', delta: '+3.1 pp', deltaTone: 'gain', deltaLabel: 'vs buy & hold'},
  {label: 'Holdout Sharpe', partition: 'holdout', value: '—', hint: 'sealed'}
]}));
""")

add("StageRail", "Research flow", 96, r"""
var st = ['passed','passed','passed','passed','passed','active','locked','pending','pending','pending'];
var meta = ['frozen 14 Aug', '7 assets · daily', 'mom_12w', 'SR 1.12 IS', 'SR 0.64 net', 'fold 5 of 6', 'sealed', '', '', ''];
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.StageRail, {current: 'walkforward', stages: Q.StageRail.STAGES.map(function (s, i) { return {key: s[0], label: s[1], state: st[i], meta: meta[i]}; })}));
""", pad="16px 16px 8px")

add("StageMeter", "Research flow", 96, r"""
function row(id, states) { return h('div', {className: 'qf-row', style: {gap: 16}}, h('code', null, id), h(Q.StageMeter, {states: states})); }
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 10}},
  row('H-001', ['passed','passed','passed','passed','passed','active','locked','pending','pending','pending']),
  row('H-002', ['passed','passed','passed','passed','failed','pending','locked','pending','pending','passed']),
  row('H-004', ['passed','passed','passed','passed','passed','passed','passed','passed','passed','passed'])));
""")

add("HypothesisCard", "Research flow", 470, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 720}}, h(Q.HypothesisCard, H1)));
""", data=True)

add("HoldoutSeal", "Validation", 250, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16}},
  h(Q.HoldoutSeal, {range: '1 Mar 2023 → 31 Dec 2023', sha: '3f9a2c1', frozenAt: '14 Aug 2026, 09:12', criterion: 'Sharpe, net ≥ 0.30'}),
  h(Q.HoldoutSeal, {state: 'unsealed', range: '1 Mar 2023 → 31 Dec 2023', sha: '3f9a2c1', frozenAt: '14 Aug 2026, 09:12', criterion: 'Sharpe, net ≥ 0.30', openedAt: '22 Sep 2026 by T. Stokłosa'})));
""")

add("Verdict", "Validation", 300, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 12}},
  h(Q.Verdict, {verdict: 'rejected', meta: 'Decided 19 Sep 2026 · criteria frozen at 8be41d0', side: ['Gross SR 0.91', h('br', {key: 1}), 'Net SR −0.22']}, 'The one-day reversal is real before costs and gone after them: spread and slippage absorb the whole edge.'),
  h(Q.Verdict, {verdict: 'confirmed', meta: 'Decided 2 Sep 2026 · criteria frozen at a71c0e3', side: ['Holdout SR 0.58', h('br', {key: 1}), 'p = 0.012']}, 'Scaling exposure to 20-day volatility shortened drawdowns in every fold and in the holdout.'),
  h(Q.Verdict, {verdict: 'inconclusive', meta: 'Decided 28 Aug 2026 · criteria frozen at 51d9e20', side: ['Holdout SR 0.21', h('br', {key: 1}), 'p = 0.14']}, 'The spread mean-reverts, but 23 trades in the holdout cannot separate the effect from noise.')));
""")

add("Callout", "Feedback", 250, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 10}},
  h(Q.Callout, {tone: 'danger', title: 'Look-ahead detected in signal mom_12w_v2'}, 'The signal on 2021-03-04 reads the close of 2021-03-05. Runs using this signal are quarantined until it is fixed.'),
  h(Q.Callout, {tone: 'warning', title: 'Only 38 trades in fold 3'}, 'Fold Sharpe estimates below ~50 trades have wide confidence intervals. Read fold 3 with care.'),
  h(Q.Callout, {tone: 'frozen', title: 'Parameters frozen'}, 'lookback, rebalance and universe were committed at 3f9a2c1 before any walk-forward run. Editing them registers a new hypothesis.'),
  h(Q.Callout, {tone: 'info', title: 'This is a historical simulation'}, 'Results describe past behaviour under the stated costs. They are not a forecast or a recommendation.')));
""")

add("ChecksList", "Validation", 290, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 520}}, h(Q.ChecksList, {items: [
  {state: 'pass', label: 'No look-ahead', detail: 'Signals lagged one bar; verified by shift test', value: 'shift=1'},
  {state: 'pass', label: 'Costs applied', detail: 'RealisticCostModel on every fill', value: '24.6 bps avg'},
  {state: 'pass', label: 'Universe fixed before test', detail: 'Committed with the hypothesis', value: '7 assets'},
  {state: 'warn', label: 'Trials logged', detail: 'Six variants tried; deflated Sharpe applied', value: 'n=6 · DSR 0.41'},
  {state: 'na', label: 'Survivorship', detail: 'Static crypto universe, no delistings in window', value: 'n/a'},
  {state: 'fail', label: 'Minimum trade count', detail: 'Fold 3 below 50 trades', value: '38'}
]})));
""")

add("Tabs", "Navigation", 64, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.Tabs, {items: [
  {value: 'all', label: 'All', count: 12}, {value: 'testing', label: 'Testing', count: 3}, {value: 'confirmed', label: 'Confirmed', count: 2},
  {value: 'rejected', label: 'Rejected', count: 5}, {value: 'inconclusive', label: 'Inconclusive', count: 2}]}));
""")

add("Field", "Forms", 250, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 640}},
  h(Q.Field, {label: 'Lookback window', hint: 'Weeks of trailing return used for the signal.', frozen: true}, h(Q.TextInput, {mono: true, value: '12', readOnly: true})),
  h(Q.Field, {label: 'Cost model'}, h(Q.Select, {options: ['RealisticCostModel', 'NaiveCostModel (10 bps)'], defaultValue: 'RealisticCostModel'})),
  h(Q.Field, {label: 'Holdout window', error: 'Holdout overlaps the walk-forward window by 14 days.'}, h(Q.TextInput, {mono: true, defaultValue: '2023-02-15 → 2023-12-31', 'aria-invalid': true})),
  h(Q.Field, {label: 'Random seed', hint: 'Stored with the run for reproducibility.'}, h(Q.TextInput, {mono: true, placeholder: '42'}))));
""")

add("TextInput", "Forms", 64, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, maxWidth: 560}},
  h(Q.TextInput, {placeholder: 'Name the hypothesis in one line'}), h(Q.TextInput, {mono: true, defaultValue: 'lookback=12w, rebalance=W-FRI'})));
""")

add("Select", "Forms", 64, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 280}}, h(Q.Select, {options: ['Walk-forward (expanding)', 'Walk-forward (rolling)', 'Permutation test']})));
""")

add("Checkbox", "Forms", 96, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-stack', style: {gap: 10}},
  h(Q.Checkbox, {defaultChecked: true, label: 'Parameters are unchanged since the freeze at 3f9a2c1'}),
  h(Q.Checkbox, {label: 'I will record the result in the research log whatever it is'})));
""")

add("DataTable", "Data display", 250, r"""
var rows = [
  {id: 't1', entry: '2022-11-04', asset: 'ETH-USDT', side: 'Long', days: 21, gross: 0.084, cost: -0.0031, regime: 'mid'},
  {id: 't2', entry: '2022-11-25', asset: 'SOL-USDT', side: 'Long', days: 7, gross: -0.061, cost: -0.0042, regime: 'high'},
  {id: 't3', entry: '2022-12-09', asset: 'BTC-USDT', side: 'Flat', days: 14, gross: 0, cost: 0, regime: 'low'},
  {id: 't4', entry: '2023-01-13', asset: 'BTC-USDT', side: 'Long', days: 35, gross: 0.212, cost: -0.0024, regime: 'mid'},
  {id: 't5', entry: '2023-02-17', asset: 'ADA-USDT', side: 'Long', days: 7, gross: -0.023, cost: -0.0051, regime: 'high'}];
function tone(v) { return v > 0 ? 'gain' : (v < 0 ? 'loss' : 'dim'); }
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.Panel, {flush: true, title: 'Trade ledger', subtitle: '412 trades · walk-forward window'}, h(Q.DataTable, {dense: true, selected: 't4', rows: rows, columns: [
  {key: 'entry', label: 'Entry', render: function (v) { return h('span', {className: 'qf-num'}, v); }},
  {key: 'asset', label: 'Instrument'}, {key: 'side', label: 'Side'},
  {key: 'regime', label: 'Regime at entry', render: function (v) { return h('span', null, h('span', {className: 'qf-regime-sw is-' + v}), v); }},
  {key: 'days', label: 'Held', numeric: true, format: function (v) { return v + 'd'; }},
  {key: 'gross', label: 'Gross', numeric: true, format: function (v) { return fmt.pct(v, 2, true); }, tone: tone},
  {key: 'cost', label: 'Costs', numeric: true, format: function (v) { return fmt.pct(v, 2, true); }, tone: function (v) { return v ? 'dim' : 'dim'; }},
  {key: 'net', label: 'Net', numeric: true, render: function (v, r) { return fmt.pct(r.gross + r.cost, 2, true); }, tone: function (v, r) { return tone(r.gross + r.cost); }}]})));
""")

add("EquityChart", "Charts", 420, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.Panel, {title: 'Equity, net of costs', subtitle: 'Weekly rebalance · index = 100', tag: h(Q.PartitionTag, {partition: 'holdout'})},
  h(Q.EquityChart, {series: eq, benchmark: bh, xTicks: xt, partitions: [{kind: 'is', from: 0, to: OOS}, {kind: 'oos', from: OOS, to: HOLD}, {kind: 'holdout', from: HOLD, to: N - 1, sealed: true}]})));
""", data=True)

add("Sparkline", "Charts", 72, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {className: 'qf-row', style: {gap: 28}},
  h(Q.Sparkline, {series: eq, oosFrom: OOS, holdoutFrom: HOLD, width: 120, height: 28}),
  h(Q.Sparkline, {series: eq, oosFrom: OOS, holdoutFrom: HOLD, sealed: false, width: 120, height: 28}),
  h(Q.Sparkline, {series: bh, width: 120, height: 28})));
""", data=True)

add("CostWaterfall", "Charts", 240, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 620}}, h(Q.CostWaterfall, {steps: [
  {label: 'Gross Sharpe', value: 1.12, kind: 'total'}, {label: 'Bid–ask spread', value: -0.21}, {label: 'Exchange fees', value: -0.12},
  {label: 'Slippage', value: -0.15}, {label: 'Net Sharpe', kind: 'total'}]})));
""")

add("WalkForward", "Charts", 240, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.WalkForward, {span: [0, 60], holdout: [50, 60],
  ticks: [{t: 0, label: '2019'}, {t: 12, label: '2020'}, {t: 24, label: '2021'}, {t: 36, label: '2022'}, {t: 48, label: '2023'}, {t: 60, label: '2024'}],
  folds: [{train: [0, 24], test: [24, 28], sharpe: 1.21}, {train: [0, 28], test: [28, 32], sharpe: 0.44}, {train: [0, 32], test: [32, 36], sharpe: -0.37},
          {train: [0, 36], test: [36, 41], sharpe: 0.92}, {train: [0, 41], test: [41, 46], sharpe: 0.58}, {train: [0, 46], test: [46, 50], sharpe: 0.71}]}));
""")

add("PermutationTest", "Charts", 250, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 620}}, h(Q.PermutationTest, {nullDist: S.draws(3, 1000, 0, 0.33), observed: 0.64, pValue: 0.031})));
""")

add("RegimeTable", "Charts", 200, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.Panel, {flush: true}, h(Q.RegimeTable, {rows: [
  {regime: 'low', share: 0.33, sharpe: 0.94, ret: 0.121, maxdd: -0.112, hit: 0.54},
  {regime: 'mid', share: 0.34, sharpe: 0.71, ret: 0.162, maxdd: -0.187, hit: 0.52},
  {regime: 'high', share: 0.33, sharpe: -0.18, ret: -0.061, maxdd: -0.289, hit: 0.46}]})));
""")

add("MonthlyHeatmap", "Charts", 200, r"""
var r = S.rng(5); function yr(y, k, hf) { var m = []; for (var i = 0; i < 12; i++) m.push(i < k ? (r() - 0.44) * 0.16 : null); return {year: y, months: m, holdoutFrom: hf}; }
ReactDOM.createRoot(document.getElementById('root')).render(h(Q.MonthlyHeatmap, {years: [yr(2020, 12), yr(2021, 12), yr(2022, 12), yr(2023, 12, 2)]}));
""")

add("LogEntry", "Research flow", 330, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {maxWidth: 760}},
  h(Q.LogEntry, {date: '19 Sep 2026', id: 'H-002', title: 'One-day reversal', verdict: 'rejected', conclusion: 'Real before costs, gone after them. Spread and slippage absorb the whole edge; retesting needs a cheaper venue, not a better signal.', facts: [['gross SR', '0.91'], ['net SR', '−0.22'], ['p', '0.40'], ['trades', '2,184']]}),
  h(Q.LogEntry, {date: '2 Sep 2026', id: 'H-004', title: 'Volatility targeting', verdict: 'confirmed', conclusion: 'Scaling exposure to 20-day volatility shortened drawdowns in every fold and in the holdout.', facts: [['holdout SR', '0.58'], ['p', '0.012'], ['max DD', '−14.1%']]}),
  h(Q.LogEntry, {date: '28 Aug 2026', id: 'H-003', title: 'ETH/BTC spread reversion', verdict: 'inconclusive', conclusion: '23 trades in the holdout cannot separate the effect from noise. Revisit with hourly data.', facts: [['holdout SR', '0.21'], ['p', '0.14']]})));
""")

UNSEAL = r"""
h(Q.Dialog, {tone: 'holdout', icon: 'lock', title: 'Open the holdout for H-001?', subtitle: 'You get one look. The result is final and goes to the research log whatever it is.',
  footer: h(F, null, h(Q.Button, {variant: 'ghost'}, 'Not yet'), h(Q.Button, {variant: 'seal', icon: 'unlock'}, 'Open holdout and evaluate'))},
  h(Q.HoldoutSeal, {range: '1 Mar 2023 → 31 Dec 2023 (218 days)', sha: '3f9a2c1', frozenAt: '14 Aug 2026, 09:12', criterion: 'Sharpe, net ≥ 0.30'}),
  h(Q.ChecksList, {items: [
    {state: 'pass', label: 'Walk-forward passed', value: 'SR 0.64'}, {state: 'pass', label: 'Permutation test passed', value: 'p 0.031'},
    {state: 'pass', label: 'No parameter edits since the freeze', value: '0 diffs'}]}),
  h(Q.Field, {label: 'Type H-001 to confirm'}, h(Q.TextInput, {mono: true, defaultValue: 'H-001'})))
"""

add("Dialog", "Overlays", 600, "ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {position: 'relative', height: 568}}, " + UNSEAL + "));", pad="0")

add("AppShell", "Layout", 360, r"""
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 360}}, h(Q.AppShell, {active: 'registry', crumbs: ['Crypto majors', 'Hypothesis registry'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}},
  h('div', {className: 'qf-panel', style: {height: 160, display: 'grid', placeItems: 'center', color: 'var(--ink-muted)'}}, 'Page content'))));
""", pad="0")

# ------------------------------------------------------------- screens (pages)
REG = r"""
var hyps = [
  {id: 'H-001', title: 'Time-series momentum, 12-week', fam: 'Momentum', st: 'testing', meter: ['passed','passed','passed','passed','passed','active','locked','pending','pending','pending'], sr: 0.64, hold: 'sealed', upd: '2 h ago', seed: 7},
  {id: 'H-002', title: 'One-day reversal', fam: 'Mean reversion', st: 'rejected', meter: ['passed','passed','passed','passed','failed','pending','locked','pending','pending','passed'], sr: -0.22, hold: 'never opened', upd: '19 Sep', seed: 21},
  {id: 'H-003', title: 'ETH/BTC spread reversion', fam: 'Stat-arb', st: 'inconclusive', meter: ['passed','passed','passed','passed','passed','passed','passed','passed','passed','passed'], sr: 0.47, hold: 'opened', upd: '28 Aug', seed: 5},
  {id: 'H-004', title: 'Volatility targeting', fam: 'Risk', st: 'confirmed', meter: ['passed','passed','passed','passed','passed','passed','passed','passed','passed','passed'], sr: 0.81, hold: 'opened', upd: '2 Sep', seed: 3},
  {id: 'H-005', title: 'Weekend effect', fam: 'Calendar', st: 'rejected', meter: ['passed','passed','passed','passed','passed','failed','locked','pending','pending','passed'], sr: 0.05, hold: 'never opened', upd: '11 Aug', seed: 9},
  {id: 'H-006', title: 'Funding-rate carry', fam: 'Carry', st: 'proposed', meter: ['passed','pending','pending','pending','pending','pending','locked','pending','pending','pending'], sr: null, hold: 'sealed', upd: 'today', seed: 13},
  {id: 'H-007', title: 'Breakout after vol compression', fam: 'Momentum', st: 'testing', meter: ['passed','passed','passed','active','pending','pending','locked','pending','pending','pending'], sr: null, hold: 'sealed', upd: '5 h ago', seed: 17}
];
var body = h(F, null,
  h('div', {className: 'qf-pagehead'},
    h('div', {className: 'qf-pagehead__titles'}, h('div', {className: 'qf-eyebrow'}, 'Crypto majors · Binance daily · 7 instruments'), h('h1', {className: 'qf-pagehead__title', style: {fontSize: 32, lineHeight: '38px', letterSpacing: '-0.02em'}}, 'Hypothesis registry'),
      h('div', {className: 'qf-pagehead__sub'}, 'Every idea is registered before it touches data. Rejected and inconclusive results count as findings too.')),
    h(Q.Button, {icon: 'filter'}, 'Filter'), h(Q.Button, {variant: 'primary', icon: 'plus'}, 'Register hypothesis')),
  h(Q.MetricStrip, {columns: 5, items: [
    {label: 'Registered', value: '12', hint: '3 this month'}, {label: 'Confirmed', value: '2', hint: 'passed holdout'},
    {label: 'Rejected', value: '5', hint: 'all documented'}, {label: 'Inconclusive', value: '2', hint: '1 queued for retest'},
    {label: 'Median time to verdict', value: '19', unit: 'days'}]}),
  h(Q.Panel, {flush: true},
    h('div', {style: {padding: '0 16px'}}, h(Q.Tabs, {items: [{value: 'all', label: 'All', count: 12}, {value: 'testing', label: 'Testing', count: 3}, {value: 'confirmed', label: 'Confirmed', count: 2}, {value: 'rejected', label: 'Rejected', count: 5}, {value: 'inconclusive', label: 'Inconclusive', count: 2}]})),
    h(Q.DataTable, {selected: 'H-001', rows: hyps, columns: [
      {key: 'id', label: 'ID', width: 72, render: function (v) { return h('span', {className: 'qf-num', style: {fontWeight: 600}}, v); }},
      {key: 'title', label: 'Hypothesis', render: function (v, r) { return h('div', null, h('div', {style: {fontWeight: 600}}, v), h('div', {className: 'qf-muted', style: {fontSize: 12}}, r.fam)); }},
      {key: 'meter', label: 'Pipeline', render: function (v) { return h(Q.StageMeter, {states: v}); }},
      {key: 'st', label: 'Status', render: function (v) { return h(Q.StatusBadge, {status: v}); }},
      {key: 'spark', label: 'Equity (OOS in blue)', render: function (v, r) { return r.sr == null ? h('span', {className: 'qf-muted', style: {fontSize: 12}}, 'no runs yet') : h(Q.Sparkline, {series: S.series(r.seed, 120, r.sr > 0 ? 0.002 : -0.0004, 0.02), oosFrom: 70, holdoutFrom: 100, sealed: r.hold === 'sealed' || r.hold === 'never opened', width: 104, height: 22}); }},
      {key: 'sr', label: 'OOS Sharpe', numeric: true, format: function (v) { return fmt.num(v, 2); }, tone: function (v) { return v == null ? 'dim' : (v < 0 ? 'loss' : null); }},
      {key: 'hold', label: 'Holdout', render: function (v) { return v === 'opened' ? h(Q.PartitionTag, {partition: 'holdout', sealed: false}, 'Opened') : (v === 'sealed' ? h(Q.PartitionTag, {partition: 'holdout'}, 'Sealed') : h('span', {className: 'qf-muted', style: {fontSize: 12}}, 'Never opened')); }},
      {key: 'upd', label: 'Updated', numeric: true, tone: function () { return 'dim'; }}]})),
  h('div', {className: 'qf-disclaimer'}, 'All figures are historical simulations net of the stated cost model. QuantForge describes past behaviour; it does not recommend trades.'));
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 900}}, h(Q.AppShell, {active: 'registry', crumbs: ['Crypto majors', 'Hypothesis registry'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}}, body)));
"""
add("RegistryScreen", "Screens", 900, REG, extra=' width=1360 page subtitle="Hypothesis registry: every idea, its pipeline position and its verdict"', pad="0", data=True)

WS = r"""
var st = ['passed','passed','passed','passed','passed','active','locked','pending','pending','pending'];
var meta = ['frozen 14 Aug', '7 assets · 1D', 'mom_12w', 'SR 1.12 IS', 'SR 0.64 net', 'fold 6 of 6', 'sealed', '', '', ''];
var body = h(F, null,
  h('div', {className: 'qf-pagehead'},
    h('div', {className: 'qf-pagehead__titles'},
      h('div', {className: 'qf-row'}, h('span', {className: 'qf-num', style: {fontWeight: 600, color: 'var(--ink-muted)'}}, 'H-001'), h(Q.StatusBadge, {status: 'testing'}), h(Q.PartitionTag, {partition: 'holdout'}, 'Holdout sealed')),
      h('h1', {className: 'qf-pagehead__title'}, 'Time-series momentum on crypto majors'),
      h('div', {className: 'qf-pagehead__sub'}, h('span', null, 'Owner T. Stokłosa'), h('span', null, 'Registered 14 Aug 2026'), h('span', null, 'Frozen at ', h('code', null, '3f9a2c1')), h('span', null, '6 variants tried'))),
    h(Q.Button, {icon: 'report'}, 'Draft tear sheet'), h(Q.Button, {variant: 'seal', icon: 'lock', disabled: true, title: 'Unlocks when walk-forward completes'}, 'Open holdout'), h(Q.Button, {variant: 'primary', icon: 'repeat'}, 'Run fold 6')),
  h(Q.Panel, null, h(Q.StageRail, {current: 'walkforward', stages: Q.StageRail.STAGES.map(function (s, i) { return {key: s[0], label: s[1], state: st[i], meta: meta[i]}; })})),
  h('div', {style: {display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 24, alignItems: 'start'}},
    h('div', {className: 'qf-stack'},
      h(Q.MetricStrip, {columns: 4, items: [
        {label: 'Sharpe, net', partition: 'is', value: '1.12', hint: 'fitted here'},
        {label: 'Sharpe, net', partition: 'oos', value: '0.64', ci: ['0.21', '1.05'], delta: '−43%', deltaLabel: 'decay'},
        {label: 'Max drawdown', partition: 'oos', value: '−28.9', unit: '%'},
        {label: 'Sharpe, net', partition: 'holdout', value: '—', hint: 'sealed until gates pass'}]}),
      h(Q.Panel, {title: 'Equity, net of costs', subtitle: 'Weekly rebalance · RealisticCostModel · index = 100', actions: h(Q.Tabs, {items: [{value: 'net', label: 'Net'}, {value: 'gross', label: 'Gross'}, {value: 'both', label: 'Both'}]})},
        h(Q.EquityChart, {series: eq, benchmark: bh, xTicks: xt, height: 300, partitions: [{kind: 'is', from: 0, to: OOS}, {kind: 'oos', from: OOS, to: HOLD}, {kind: 'holdout', from: HOLD, to: N - 1, sealed: true}]})),
      h(Q.Panel, {title: 'Walk-forward folds', icon: 'repeat', subtitle: 'Expanding train window · 4-month test windows · no refit inside a test window'},
        h(Q.WalkForward, {span: [0, 60], holdout: [50, 60], ticks: [{t: 0, label: '2019'}, {t: 12, label: '2020'}, {t: 24, label: '2021'}, {t: 36, label: '2022'}, {t: 48, label: '2023'}, {t: 60, label: '2024'}],
          folds: [{train: [0, 24], test: [24, 28], sharpe: 1.21}, {train: [0, 28], test: [28, 32], sharpe: 0.44}, {train: [0, 32], test: [32, 36], sharpe: -0.37}, {train: [0, 36], test: [36, 41], sharpe: 0.92}, {train: [0, 41], test: [41, 46], sharpe: 0.58}, {train: [0, 46], test: [46, 50], sharpe: 0.71}]}))),
    h('div', {className: 'qf-stack'},
      h(Q.HypothesisCard, Object.assign({}, H1, {title: null, owner: null, updated: null})),
      h(Q.HoldoutSeal, {range: '1 Mar 2023 → 31 Dec 2023', sha: '3f9a2c1', frozenAt: '14 Aug 2026, 09:12', criterion: 'Sharpe, net ≥ 0.30'}),
      h(Q.Panel, {title: 'Integrity checks', icon: 'validate'}, h(Q.ChecksList, {items: [
        {state: 'pass', label: 'No look-ahead', value: 'shift=1'}, {state: 'pass', label: 'Costs on every fill', value: '24.6 bps'},
        {state: 'warn', label: 'Six variants tried', detail: 'Deflated Sharpe applied', value: 'DSR 0.41'}, {state: 'fail', label: 'Fold 3 trade count', detail: 'Below the 50-trade floor', value: '38'}]})))));
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 1400}}, h(Q.AppShell, {active: 'registry', crumbs: ['Crypto majors', 'Hypothesis registry', 'H-001'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}}, body)));
"""
add("WorkspaceScreen", "Screens", 1400, WS, extra=' width=1440 page subtitle="Hypothesis workspace: pipeline rail, partitioned evidence, the sealed holdout"', pad="0", data=True)

TS = r"""
var eq2 = S.series(31, N, 0.0012, 0.018, 100, [{from: OOS, to: N, mu: -0.0003, sigma: 0.018}]);
var r = S.rng(8); function yr(y, k, hf) { var m = []; for (var i = 0; i < 12; i++) m.push(i < k ? (r() - (y > 2022 ? 0.56 : 0.45)) * 0.12 : null); return {year: y, months: m, holdoutFrom: hf}; }
var body = h(F, null,
  h('div', {className: 'qf-pagehead'},
    h('div', {className: 'qf-pagehead__titles'},
      h('div', {className: 'qf-eyebrow'}, 'Tear sheet · H-002 · run 8be41d0-r14'),
      h('h1', {className: 'qf-pagehead__title', style: {fontSize: 32, lineHeight: '38px', letterSpacing: '-0.02em'}}, 'One-day reversal'),
      h('div', {className: 'qf-pagehead__sub'}, h('span', null, 'BTC, ETH, SOL, BNB, XRP, ADA, DOGE vs USDT'), h('span', null, 'Daily · 2019-01-01 → 2023-12-31'), h('span', null, 'RealisticCostModel'))),
    h(Q.Button, {icon: 'download'}, 'Export PDF'), h(Q.Button, {icon: 'book'}, 'Open log entry')),
  h(Q.Verdict, {verdict: 'rejected', meta: 'Decided 19 Sep 2026 against criteria frozen at 8be41d0 · holdout never opened: the hypothesis failed the cost gate first', side: ['Gross SR  0.91', h('br', {key: 1}), 'Net SR  −0.22', h('br', {key: 2}), 'p  0.40']},
    'Yesterday’s losers do bounce the next day, but the bounce is smaller than the cost of trading it. The effect is real before costs and gone after them.'),
  h(Q.MetricStrip, {columns: 6, items: [
    {label: 'Sharpe, gross', value: '0.91', struck: true, hint: 'before costs'}, {label: 'Sharpe, net', value: '−0.22', hint: 'after costs'},
    {label: 'CAGR, net', value: '−4.8', unit: '%'}, {label: 'Max drawdown', value: '−57.1', unit: '%'},
    {label: 'Turnover', value: '184', unit: '×/yr'}, {label: 'Avg cost / trade', value: '27.3', unit: 'bps'}]}),
  h('div', {style: {display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)', gap: 24}},
    h(Q.Panel, {title: 'Equity, net of costs', subtitle: 'Gross equity rose; net equity decayed from the first OOS month'},
      h(Q.EquityChart, {series: eq2, benchmark: bh, xTicks: xt, height: 280, partitions: [{kind: 'is', from: 0, to: OOS}, {kind: 'oos', from: OOS, to: N - 1}]})),
    h(Q.Panel, {title: 'Where the edge went', icon: 'costs', subtitle: 'Sharpe, walk-forward window'},
      h(Q.CostWaterfall, {width: 460, steps: [{label: 'Gross Sharpe', value: 0.91, kind: 'total'}, {label: 'Spread', value: -0.47}, {label: 'Fees', value: -0.29}, {label: 'Slippage', value: -0.37}, {label: 'Net Sharpe', kind: 'total'}]}),
      h('p', {className: 'qf-muted', style: {margin: '12px 0 0', fontSize: 12.5}}, 'Spread alone removes half the edge. A cheaper venue, not a better signal, is the only route to retest.'))),
  h('div', {style: {display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 24}},
    h(Q.Panel, {title: 'Conditional on volatility regime', icon: 'regime', subtitle: 'Terciles of 20-day realized volatility', flush: true},
      h(Q.RegimeTable, {rows: [{regime: 'low', share: 0.33, sharpe: -0.61, ret: -0.094, maxdd: -0.214, hit: 0.47}, {regime: 'mid', share: 0.34, sharpe: -0.28, ret: -0.052, maxdd: -0.198, hit: 0.49}, {regime: 'high', share: 0.33, sharpe: 0.19, ret: 0.041, maxdd: -0.412, hit: 0.51}]})),
    h(Q.Panel, {title: 'Is it luck?', icon: 'shuffle', subtitle: 'Net Sharpe vs 1,000 runs with the signal shuffled in time'},
      h(Q.PermutationTest, {nullDist: S.draws(4, 1000, -0.29, 0.3), observed: -0.22, height: 150}))),
  h(Q.Panel, {title: 'Monthly net returns, %', subtitle: 'Blue gains, red losses; intensity scales to ±8%'}, h(Q.MonthlyHeatmap, {years: [yr(2019, 12), yr(2020, 12), yr(2021, 12), yr(2022, 12), yr(2023, 12)]})),
  h('div', {className: 'qf-disclaimer'}, 'Historical simulation on Binance daily data, net of RealisticCostModel. Metrics computed by quantlab.reporting at 8be41d0. Past behaviour does not predict future results; nothing here is a recommendation to trade.'));
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 1540}}, h(Q.AppShell, {active: 'reports', crumbs: ['Crypto majors', 'Tear sheets', 'H-002'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}}, body)));
"""
add("TearSheetScreen", "Screens", 1540, TS, extra=' width=1440 page subtitle="Tear sheet of a rejected hypothesis: the verdict first, then the evidence"', pad="0", data=True)

UN = r"""
var body = h(F, null,
  h('div', {className: 'qf-pagehead'}, h('div', {className: 'qf-pagehead__titles'}, h('div', {className: 'qf-row'}, h('span', {className: 'qf-num', style: {fontWeight: 600, color: 'var(--ink-muted)'}}, 'H-001'), h(Q.StatusBadge, {status: 'testing'})), h('h1', {className: 'qf-pagehead__title'}, 'Time-series momentum on crypto majors'))),
  h(Q.Panel, {title: 'Equity, net of costs'}, h(Q.EquityChart, {series: eq, benchmark: bh, xTicks: xt, height: 300, partitions: [{kind: 'is', from: 0, to: OOS}, {kind: 'oos', from: OOS, to: HOLD}, {kind: 'holdout', from: HOLD, to: N - 1, sealed: true}]})));
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 820}}, h(Q.AppShell, {active: 'validation', crumbs: ['Crypto majors', 'Validation', 'H-001'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}, overlay: """ + UNSEAL + r"""}, body)));
"""
add("HoldoutScreen", "Screens", 820, UN, extra=' width=1360 page subtitle="Opening the holdout: a deliberate, one-time ceremony"', pad="0", data=True)

LOG = r"""
var body = h(F, null,
  h('div', {className: 'qf-pagehead'},
    h('div', {className: 'qf-pagehead__titles'}, h('div', {className: 'qf-eyebrow'}, 'Institutional memory'), h('h1', {className: 'qf-pagehead__title', style: {fontSize: 32, lineHeight: '38px', letterSpacing: '-0.02em'}}, 'Research log'),
      h('div', {className: 'qf-pagehead__sub'}, 'One entry per finished hypothesis, written the day it is decided. What failed and why is the part that saves next year’s time.')),
    h(Q.Button, {icon: 'download'}, 'Export Markdown')),
  h('div', {style: {display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: 32, alignItems: 'start'}},
    h('div', {style: {maxWidth: 820}},
      h(Q.LogEntry, {date: '19 Sep 2026', id: 'H-002', title: 'One-day reversal', verdict: 'rejected', conclusion: 'Real before costs, gone after them. Spread and slippage absorb the whole edge; retesting needs a cheaper venue, not a better signal.', facts: [['gross SR', '0.91'], ['net SR', '−0.22'], ['p', '0.40'], ['trades', '2,184']]}),
      h(Q.LogEntry, {date: '2 Sep 2026', id: 'H-004', title: 'Volatility targeting', verdict: 'confirmed', conclusion: 'Scaling exposure to 20-day volatility shortened drawdowns in every walk-forward fold and in the one-look holdout.', facts: [['holdout SR', '0.58'], ['p', '0.012'], ['max DD', '−14.1%']]}),
      h(Q.LogEntry, {date: '28 Aug 2026', id: 'H-003', title: 'ETH/BTC spread reversion', verdict: 'inconclusive', conclusion: 'The spread mean-reverts, but 23 trades in the holdout cannot separate the effect from noise. Revisit with hourly data.', facts: [['holdout SR', '0.21'], ['p', '0.14'], ['trades', '23']]}),
      h(Q.LogEntry, {date: '11 Aug 2026', id: 'H-005', title: 'Weekend effect', verdict: 'rejected', conclusion: 'Weekend returns are no different from weekday returns once the 2020–21 bull run is split into its own regime.', facts: [['OOS SR', '0.05'], ['p', '0.62']]})),
    h('div', {className: 'qf-stack'},
      h(Q.Panel, {title: 'What we know so far'}, h(Q.ChecksList, {items: [
        {state: 'pass', label: 'Volatility scaling helps', value: 'H-004'}, {state: 'fail', label: 'Short-horizon reversal is too costly', value: 'H-002'},
        {state: 'fail', label: 'No calendar effect at weekly scale', value: 'H-005'}, {state: 'warn', label: 'Pairs need more data', value: 'H-003'}]})),
      h(Q.Callout, {tone: 'info', title: 'Why log rejections?'}, 'An undocumented failure gets tested again next year, at the same cost. A documented one is a finding.'))));
ReactDOM.createRoot(document.getElementById('root')).render(h('div', {style: {height: 860}}, h(Q.AppShell, {active: 'log', crumbs: ['Crypto majors', 'Research log'], counts: {registry: 12, runs: 148, log: 9}, style: {height: '100%'}}, body)));
"""
add("ResearchLogScreen", "Screens", 860, LOG, extra=' width=1360 page subtitle="Research log: rejected results recorded as carefully as confirmed ones"', pad="0")

for name, c in P.items():
    d = os.path.join(ROOT, name); os.makedirs(d, exist_ok=True)
    body = c["body"]
    if "</script" in body.lower() or "<!--" in body: sys.exit("bad body " + name)
    Path(d, "preview.html").write_text(TPL.format(group=c["group"], height=c["height"], extra=c["extra"], name=name, pad=c["pad"], data=DATA if c["data"] else "", body=body.strip()))
print(len(P), "previews")
