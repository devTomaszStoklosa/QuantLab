/* @ds-bundle: {"format":4,"namespace":"QuantForge","components":[{"name":"Logo"},{"name":"Icon"},{"name":"Button"},{"name":"StatusBadge"},{"name":"PartitionTag"},{"name":"Panel"},{"name":"Metric"},{"name":"MetricStrip"},{"name":"StageRail"},{"name":"StageMeter"},{"name":"HypothesisCard"},{"name":"HoldoutSeal"},{"name":"Verdict"},{"name":"Callout"},{"name":"ChecksList"},{"name":"Tabs"},{"name":"Field"},{"name":"TextInput"},{"name":"Select"},{"name":"Checkbox"},{"name":"DataTable"},{"name":"EquityChart"},{"name":"Sparkline"},{"name":"CostWaterfall"},{"name":"WalkForward"},{"name":"PermutationTest"},{"name":"RegimeTable"},{"name":"MonthlyHeatmap"},{"name":"LogEntry"},{"name":"Dialog"},{"name":"AppShell"}]} */
(function () {
  var R = window.React, h = R.createElement, F = R.Fragment;
  var MINUS = '−';
  var uid = 0;
  function nextId(p) { uid += 1; return p + uid; }
  function useStableId(p) { var r = R.useRef(null); if (r.current === null) r.current = nextId(p); return r.current; }
  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(' '); }

  /* ---------- number formatting: code computes, UI only formats ---------- */
  function num(v, d, sign) {
    if (v == null || isNaN(v)) return '—';
    var s = Math.abs(v).toFixed(d == null ? 2 : d);
    return (v < 0 && Number(s) !== 0 ? MINUS : (sign && v > 0 ? '+' : '')) + s;
  }
  function pct(v, d, sign) { return v == null || isNaN(v) ? '—' : num(v * 100, d == null ? 1 : d, sign) + '%'; }

  /* ---------- deterministic synthetic data for previews (illustrative only) ---------- */
  function rng(seed) { var a = seed >>> 0; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function gauss(r) { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function series(seed, n, mu, sigma, start, regimes) {
    var r = rng(seed), out = [start || 100], x = start || 100;
    for (var i = 1; i < n; i++) {
      var m = mu, s = sigma;
      if (regimes) regimes.forEach(function (g) { if (i >= g.from && i < g.to) { m = g.mu; s = g.sigma; } });
      x = x * (1 + m + s * gauss(r)); out.push(x);
    }
    return out;
  }
  function draws(seed, n, mu, sd) { var r = rng(seed), o = []; for (var i = 0; i < n; i++) o.push(mu + sd * gauss(r)); return o; }

  /* ---------- Icon ---------- */
  var ICONS = {
    check: ['M5 12.5l4.5 4.5L19 7.5'],
    x: ['M6.5 6.5l11 11M17.5 6.5l-11 11'],
    lock: ['M6 11h12v9H6z', 'M8.5 11V8a3.5 3.5 0 0 1 7 0v3'],
    unlock: ['M6 11h12v9H6z', 'M8.5 11V8a3.5 3.5 0 0 1 6.9-.9'],
    dash: ['M7 12h10'],
    alert: ['M12 4l9 16H3z', 'M12 10v4', 'M12 17h.01'],
    info: ['M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 1 0 0-17z', 'M12 11v5', 'M12 8h.01'],
    flask: ['M9.5 3.5h5', 'M10.5 3.5v5.5L5.2 18.2A1.8 1.8 0 0 0 6.8 21h10.4a1.8 1.8 0 0 0 1.6-2.8L13.5 9V3.5', 'M7.5 15h9'],
    commit: ['M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z', 'M3 12h6M15 12h6'],
    clock: ['M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 1 0 0-17z', 'M12 7.5V12l3 2'],
    arrow: ['M5 12h14', 'M13 6l6 6-6 6'],
    chevron: ['M9.5 6l6 6-6 6'],
    search: ['M11 5a6 6 0 1 0 0 12a6 6 0 1 0 0-12z', 'M20 20l-4.6-4.6'],
    plus: ['M12 5v14', 'M5 12h14'],
    registry: ['M5 4h14v16H5z', 'M9 8h6', 'M9 12h6', 'M9 16h3'],
    data: ['M4 6.5c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z', 'M4 6.5v11c0 1.7 3.6 3 8 3s8-1.3 8-3v-11', 'M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3'],
    signal: ['M3 12h3.5l2.5-6 4 12 2.5-6H21'],
    run: ['M4 19h16', 'M6 15l4-5 3 3 5-7'],
    costs: ['M12 4v16', 'M7 20h10', 'M5 8h14', 'M5 8l-2.5 5.5h5z', 'M19 8l-2.5 5.5h5z'],
    validate: ['M12 3.5l7.5 3v5.5c0 4.3-3.2 7.6-7.5 8.5-4.3-.9-7.5-4.2-7.5-8.5V6.5z', 'M8.5 12l2.5 2.5 4.5-5'],
    regime: ['M4 4h7v7H4z', 'M13 4h7v7h-7z', 'M4 13h7v7H4z', 'M13 13h7v7h-7z'],
    attribution: ['M4 20V10', 'M10 20V4', 'M16 20v-7', 'M21 20H3'],
    book: ['M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z', 'M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3'],
    report: ['M6 3h8l4 4v14H6z', 'M14 3v4h4', 'M9 12h6', 'M9 16h6'],
    shuffle: ['M4 7h3.5c4 0 5 10 9 10H20', 'M4 17h3.5c1.6 0 2.6-1.6 3.4-3.5', 'M13.1 9.5C14 8 15 7 16.5 7H20', 'M17.5 4.5L20 7l-2.5 2.5', 'M17.5 14.5L20 17l-2.5 2.5'],
    repeat: ['M4.5 11a7.5 7.5 0 0 1 13-4.5', 'M19.5 13a7.5 7.5 0 0 1-13 4.5', 'M17.5 3v3.5H14', 'M6.5 21v-3.5H10'],
    filter: ['M4 5h16l-6 7.5V19l-4-2v-4.5z'],
    settings: ['M4 7h10', 'M18 7h2', 'M4 17h4', 'M12 17h8', 'M14 5v4', 'M8 15v4'],
    eye: ['M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z', 'M12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5z'],
    download: ['M12 4v11', 'M7 10.5l5 5 5-5', 'M5 20h14']
  };
  function Icon(p) {
    var s = p.size || 16, d = ICONS[p.name];
    var kids = p.name === 'pending'
      ? [h('circle', { key: 'c', cx: 12, cy: 12, r: 7.5, strokeDasharray: '2.6 2.6' })]
      : (d || ICONS.dash).map(function (x, i) { return h('path', { key: i, d: x }); });
    return h('svg', { className: cx('qf-icon', p.className), width: s, height: s, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: p.strokeWidth || 1.75, strokeLinecap: 'round', strokeLinejoin: 'round', role: p.label ? 'img' : undefined, 'aria-label': p.label, 'aria-hidden': p.label ? undefined : true, style: p.style }, kids);
  }
  Icon.names = Object.keys(ICONS).concat(['pending']);

  /* ---------- Logo ---------- */
  function Logo(p) {
    var s = p.size || 22;
    return h('span', { className: cx('qf-logo', p.className) },
      h('svg', { width: s, height: s, viewBox: '0 0 24 24', 'aria-hidden': p.wordmark === false ? undefined : true, role: p.wordmark === false ? 'img' : undefined, 'aria-label': p.wordmark === false ? 'QuantForge' : undefined },
        h('rect', { className: 'qf-logo-ink', x: 0, y: 0, width: 24, height: 24, rx: 3 }),
        h('path', { className: 'qf-logo-line', d: 'M4.5 17.5L8 13.5l3 2 4-6', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }),
        h('path', { className: 'qf-logo-line', d: 'M16.5 4v16', strokeWidth: 1, strokeDasharray: '1.5 1.5', opacity: 0.7 }),
        h('rect', { className: 'qf-logo-spark', x: 17.8, y: 6, width: 3.4, height: 3.4, rx: 0.6 })),
      p.wordmark === false ? null : h('span', { className: 'qf-logo__word' }, 'Quant', h('i', null, 'Forge')));
  }

  /* ---------- Button ---------- */
  function Button(p) {
    var rest = Object.assign({}, p); ['variant', 'size', 'icon', 'iconRight', 'className', 'children'].forEach(function (k) { delete rest[k]; });
    return h('button', Object.assign({ type: 'button' }, rest, { className: cx('qf-btn', 'qf-btn--' + (p.variant || 'secondary'), p.size === 'sm' && 'qf-btn--sm', p.className) }),
      p.icon && h(Icon, { name: p.icon, size: p.size === 'sm' ? 13 : 15, strokeWidth: 2 }), p.children,
      p.iconRight && h(Icon, { name: p.iconRight, size: p.size === 'sm' ? 13 : 15, strokeWidth: 2 }));
  }

  /* ---------- StatusBadge ---------- */
  var STATUS = {
    proposed: { label: 'Proposed', icon: 'pending' },
    testing: { label: 'Testing', icon: 'flask' },
    confirmed: { label: 'Confirmed', icon: 'check' },
    rejected: { label: 'Rejected', icon: 'x' },
    inconclusive: { label: 'Inconclusive', icon: 'dash' }
  };
  function StatusBadge(p) {
    var k = STATUS[p.status] ? p.status : 'proposed', s = STATUS[k];
    return h('span', { className: cx('qf-status', 'qf-status--' + k, p.size === 'lg' && 'qf-status--lg', p.className) },
      h(Icon, { name: s.icon, size: p.size === 'lg' ? 14 : 12, strokeWidth: 2.4 }), p.children || s.label);
  }

  /* ---------- PartitionTag ---------- */
  var PART = { is: ['In-sample', 'IS'], oos: ['Out-of-sample', 'OOS'], holdout: ['Holdout', 'Holdout'] };
  function PartitionTag(p) {
    var k = PART[p.partition] ? p.partition : 'is', m = PART[k];
    return h('span', { className: cx('qf-part', 'qf-part--' + k, p.className), title: m[0] },
      k === 'holdout' ? h(Icon, { name: p.sealed === false ? 'unlock' : 'lock', size: 11, strokeWidth: 2.4 }) : h('span', { className: 'qf-part__swatch' }),
      p.children || (p.short ? m[1] : m[0]));
  }

  /* ---------- Panel ---------- */
  function Panel(p) {
    var head = p.title || p.actions;
    return h('section', { className: cx('qf-panel', p.flush && 'qf-panel--flush', p.className), style: p.style },
      head && h('header', { className: 'qf-panel__head' },
        p.icon && h(Icon, { name: p.icon, size: 16, style: { color: 'var(--ink-muted)' } }),
        h('div', { className: 'qf-panel__titles' }, h('h3', { className: 'qf-panel__title' }, p.title, p.tag), p.subtitle && h('div', { className: 'qf-panel__sub' }, p.subtitle)),
        p.actions && h('div', { className: 'qf-panel__actions' }, p.actions)),
      h('div', { className: 'qf-panel__body' }, p.children),
      p.footer && h('footer', { className: 'qf-panel__foot' }, p.footer));
  }

  /* ---------- Metric ---------- */
  function Metric(p) {
    return h('div', { className: cx('qf-metric', p.size === 'lg' && 'qf-metric--lg', p.struck && 'is-struck', p.className) },
      h('div', { className: 'qf-metric__label' }, p.label, p.partition && h(PartitionTag, { partition: p.partition, short: true, sealed: p.sealed })),
      h('div', { className: 'qf-metric__value' }, p.value, p.unit && h('span', { className: 'qf-metric__unit' }, p.unit)),
      (p.ci || p.delta != null || p.hint) && h('div', { className: 'qf-metric__foot' },
        p.ci && h('span', null, 'CI [' + p.ci[0] + ', ' + p.ci[1] + ']'),
        p.delta != null && h('span', { className: cx('qf-metric__delta', 'is-' + (p.deltaTone || 'neutral')) }, p.delta, p.deltaLabel && h('span', { className: 'qf-metric__dl' }, ' ' + p.deltaLabel)),
        p.hint && h('span', null, p.hint)));
  }
  function MetricStrip(p) {
    return h('div', { className: cx('qf-metrics', p.className), style: p.columns ? { gridTemplateColumns: 'repeat(' + p.columns + ', minmax(0, 1fr))' } : null },
      (p.items || []).map(function (m, i) { return h(Metric, Object.assign({ key: i }, m)); }), p.children);
  }

  /* ---------- StageRail / StageMeter ---------- */
  var STAGE_ICON = { passed: 'check', failed: 'x', active: 'flask', pending: 'pending', locked: 'lock', skipped: 'dash' };
  var STAGES = [
    ['hypothesis', 'Hypothesis'], ['data', 'Data & universe'], ['signal', 'Signal'], ['backtest', 'Backtest'], ['costs', 'Costs'],
    ['walkforward', 'Walk-forward'], ['holdout', 'Holdout'], ['regimes', 'Regimes'], ['attribution', 'Attribution'], ['conclusion', 'Conclusion']
  ];
  function StageRail(p) {
    return h('ol', { className: cx('qf-rail', p.className), 'aria-label': 'Research pipeline' },
      p.stages.map(function (s, i) {
        var st = s.state || 'pending';
        return h('li', { key: s.key || i, className: cx('qf-rail__step', 'is-' + st, p.current != null && p.current === (s.key || i) && 'is-current'), 'aria-current': p.current === s.key ? 'step' : undefined },
          h('span', { className: 'qf-rail__node' }, h(Icon, { name: STAGE_ICON[st], size: 14, strokeWidth: 2.4, label: st })),
          h('span', { className: 'qf-rail__text' }, h('span', { className: 'qf-rail__label' }, s.label), s.meta && h('span', { className: 'qf-rail__meta' }, s.meta)));
      }));
  }
  StageRail.STAGES = STAGES;
  function StageMeter(p) {
    var states = p.states || [], done = states.filter(function (s) { return s === 'passed'; }).length;
    return h('span', { className: 'qf-meter', title: done + ' of ' + states.length + ' stages passed' },
      states.map(function (s, i) { return h('span', { key: i, className: cx('qf-meter__cell', 'is-' + s), title: (STAGES[i] ? STAGES[i][1] : 'Stage ' + (i + 1)) + ': ' + s }); }),
      p.showCount !== false && h('span', { className: 'qf-meter__label' }, done + '/' + states.length));
  }

  /* ---------- HypothesisCard ---------- */
  function critState(c) { return c.locked ? 'locked' : (c.pass == null ? 'pending' : (c.pass ? 'passed' : 'failed')); }
  function HypothesisCard(p) {
    return h('article', { className: cx('qf-hyp', p.className) },
      h('header', { className: 'qf-hyp__head' }, h('span', { className: 'qf-hyp__id' }, p.id), h(StatusBadge, { status: p.status }), h('span', { className: 'qf-hyp__spacer' }), p.updated && h('span', { className: 'qf-hyp__meta' }, p.updated)),
      p.title && h('h3', { className: 'qf-hyp__title' }, p.title),
      h('blockquote', { className: 'qf-hyp__statement' }, p.statement),
      p.rationale && h('p', { className: 'qf-hyp__rationale' }, h('span', { className: 'qf-eyebrow' }, 'Why it might work'), p.rationale),
      p.criteria && h('div', { className: 'qf-hyp__criteria' },
        h('div', { className: 'qf-eyebrow' }, 'Pre-registered success criteria'),
        h('ul', null, p.criteria.map(function (c, i) {
          var st = critState(c);
          return h('li', { key: i, className: 'is-' + st },
            h(Icon, { name: STAGE_ICON[st], size: 14, strokeWidth: 2.4, label: st }),
            h('span', null, c.label), h('span', { className: 'qf-hyp__thr' }, c.threshold),
            h('span', { className: 'qf-hyp__res' }, c.result != null ? c.result : (st === 'locked' ? 'sealed' : 'not run')));
        }))),
      (p.frozen || p.owner) && h('footer', { className: 'qf-hyp__foot' },
        p.frozen ? h('span', { className: 'qf-hyp__frozen' }, h(Icon, { name: 'lock', size: 12, strokeWidth: 2.2 }), 'Frozen at ', h('code', null, p.frozen.sha), p.frozen.date ? ' · ' + p.frozen.date : null) : h('span'),
        p.owner && h('span', null, p.owner)));
  }

  /* ---------- HoldoutSeal ---------- */
  function KV(rows) {
    return h('dl', { className: 'qf-kv' }, rows.filter(function (r) { return r[1] != null; }).map(function (r, i) { return h(F, { key: i }, h('dt', null, r[0]), h('dd', null, r[1])); }));
  }
  function HoldoutSeal(p) {
    var sealed = p.state !== 'unsealed', allowed = p.looksAllowed || 1, used = p.looksUsed || (sealed ? 0 : 1);
    return h('section', { className: cx('qf-seal', sealed ? 'is-sealed' : 'is-unsealed', p.className) },
      h('div', { className: 'qf-seal__band', 'aria-hidden': true }),
      h('div', { className: 'qf-seal__body' },
        h('div', { className: 'qf-seal__head' }, h(Icon, { name: sealed ? 'lock' : 'unlock', size: 16, strokeWidth: 2 }),
          h('span', { className: 'qf-seal__title' }, sealed ? 'Holdout sealed' : 'Holdout opened'),
          h('span', { className: 'qf-seal__looks' }, (allowed - used) + ' of ' + allowed + ' look' + (allowed > 1 ? 's' : '') + ' left')),
        KV([['Window', p.range], ['Frozen at', p.sha && h('code', null, p.sha)], ['Frozen on', p.frozenAt], ['Pass if', p.criterion], ['Opened', sealed ? null : p.openedAt]]),
        p.children));
  }

  /* ---------- Verdict ---------- */
  var VERDICT_LEAD = { confirmed: 'Confirmed', rejected: 'Rejected', inconclusive: 'Inconclusive' };
  function Verdict(p) {
    var k = VERDICT_LEAD[p.verdict] ? p.verdict : 'inconclusive';
    return h('section', { className: cx('qf-verdict', 'qf-verdict--' + k, p.className) },
      h(StatusBadge, { status: k, size: 'lg' }),
      h('div', null, h('p', { className: 'qf-verdict__text' }, p.children), p.meta && h('div', { className: 'qf-verdict__meta' }, p.meta)),
      p.side && h('div', { className: 'qf-verdict__side' }, p.side));
  }

  /* ---------- Callout ---------- */
  var CALLOUT_ICON = { info: 'info', warning: 'alert', danger: 'alert', frozen: 'lock' };
  function Callout(p) {
    var t = CALLOUT_ICON[p.tone] ? p.tone : 'info';
    return h('div', { className: cx('qf-callout', 'qf-callout--' + t, p.className), role: t === 'danger' ? 'alert' : 'note' },
      h(Icon, { name: p.icon || CALLOUT_ICON[t], size: 16, strokeWidth: 2 }),
      h('div', { className: 'qf-callout__title' }, p.title),
      p.children && h('div', { className: 'qf-callout__body' }, p.children));
  }

  /* ---------- ChecksList ---------- */
  var CHECK_ICON = { pass: 'check', warn: 'alert', fail: 'x', na: 'dash' };
  function ChecksList(p) {
    return h('ul', { className: cx('qf-checks', p.className) }, (p.items || []).map(function (c, i) {
      var st = CHECK_ICON[c.state] ? c.state : 'na';
      return h('li', { key: i, className: 'is-' + st }, h(Icon, { name: CHECK_ICON[st], size: 15, strokeWidth: 2.2, label: st }),
        h('span', null, c.label, c.detail && h('span', { className: 'qf-checks__detail' }, c.detail)),
        h('span', { className: 'qf-checks__val' }, c.value));
    }));
  }

  /* ---------- Tabs ---------- */
  function Tabs(p) {
    var st = R.useState(p.defaultValue || (p.items[0] && p.items[0].value)), cur = p.value != null ? p.value : st[0];
    return h('div', { className: cx('qf-tabs', p.className), role: 'tablist' }, p.items.map(function (t) {
      return h('button', { key: t.value, role: 'tab', className: 'qf-tab', 'aria-selected': cur === t.value, onClick: function () { st[1](t.value); if (p.onChange) p.onChange(t.value); } },
        t.icon && h(Icon, { name: t.icon, size: 14 }), t.label, t.count != null && h('span', { className: 'qf-tab__count' }, t.count));
    }));
  }

  /* ---------- Form ---------- */
  function Field(p) {
    return h('label', { className: cx('qf-field', p.className) },
      h('span', { className: 'qf-field__label' }, p.label, p.frozen && h(PartitionTag, { partition: 'holdout' }, 'Frozen')),
      p.children,
      p.error ? h('span', { className: 'qf-field__error' }, p.error) : p.hint && h('span', { className: 'qf-field__hint' }, p.hint));
  }
  function TextInput(p) {
    var rest = Object.assign({}, p); delete rest.mono; delete rest.className;
    return h('input', Object.assign({ type: 'text' }, rest, { className: cx('qf-input', p.mono && 'qf-input--mono', p.className) }));
  }
  function Select(p) {
    var rest = Object.assign({}, p); delete rest.options; delete rest.className;
    return h('select', Object.assign({}, rest, { className: cx('qf-select', p.className) }), (p.options || []).map(function (o) {
      var v = typeof o === 'string' ? o : o.value; return h('option', { key: v, value: v }, typeof o === 'string' ? o : o.label);
    }));
  }
  function Checkbox(p) {
    var rest = Object.assign({}, p); delete rest.label; delete rest.className;
    return h('label', { className: cx('qf-check', p.className) }, h('input', Object.assign({ type: 'checkbox' }, rest)), h('span', null, p.label));
  }

  /* ---------- DataTable ---------- */
  function DataTable(p) {
    return h('div', { className: 'qf-table-wrap' }, h('table', { className: cx('qf-table', p.dense && 'qf-table--dense', p.className) },
      h('thead', null, h('tr', null, p.columns.map(function (c) { return h('th', { key: c.key, className: c.numeric ? 'is-num' : null, style: c.width ? { width: c.width } : null }, c.label); }))),
      h('tbody', null, p.rows.map(function (r, i) {
        return h('tr', { key: r.id || i, className: p.selected != null && p.selected === (r.id || i) ? 'is-selected' : null },
          p.columns.map(function (c) {
            var v = r[c.key], out = c.render ? c.render(v, r) : (c.format ? c.format(v, r) : v);
            var tone = c.tone ? c.tone(v, r) : null;
            return h('td', { key: c.key, className: cx(c.numeric && 'is-num', tone && 'is-' + tone) }, out);
          }));
      }))));
  }

  /* ---------- chart helpers ---------- */
  function niceTicks(lo, hi, k) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log(span / k) / Math.LN10)), err = span / k / step;
    if (err >= 5) step *= 5; else if (err >= 2) step *= 2;
    var out = []; for (var t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(10));
    return out;
  }
  function pathOf(pts) { return pts.length ? 'M' + pts.map(function (q) { return q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join('L') : ''; }
  function Hatch(p) {
    return h('pattern', { id: p.id, width: 7, height: 7, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' },
      h('line', { className: 'qf-hatch', x1: 0, y1: 0, x2: 0, y2: 7 }));
  }
  var BAND_LABEL = { is: 'IN-SAMPLE', oos: 'WALK-FORWARD OOS', holdout: 'HOLDOUT' };

  /* ---------- EquityChart ---------- */
  function EquityChart(p) {
    var hid = useStableId('qf-hatch-');
    var v = p.series, n = v.length, W = p.width || 880, H = p.height || 300;
    var showDD = p.showDrawdown !== false, ddH = showDD ? 64 : 0, gap = showDD ? 18 : 0;
    var pl = 48, pr = 14, pt = 24, pb = 22;
    var parts = p.partitions || [], sealedFrom = null;
    parts.forEach(function (q) { if (q.kind === 'holdout' && q.sealed) sealedFrom = q.from; });
    var visN = sealedFrom == null ? n : sealedFrom + 1;
    var vis = v.slice(0, visN), bm = p.benchmark ? p.benchmark.slice(0, visN) : null;
    var all = vis.concat(bm || []), lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.08 || 1;
    lo -= pad; hi += pad;
    var mainB = H - pb - ddH - gap, ddT = mainB + gap, ddB = H - pb;
    function X(i) { return pl + (W - pl - pr) * i / (n - 1); }
    function Y(y) { return pt + (mainB - pt) * (1 - (y - lo) / (hi - lo)); }
    var yt = niceTicks(lo, hi, 4);
    // Drawdowns computed by quantlab when given; the running-peak fallback is for previews only.
    var peak = -Infinity, dd = p.drawdown ? p.drawdown.slice(0, visN) : vis.map(function (x) { peak = Math.max(peak, x); return x / peak - 1; });
    var ddMin = Math.min.apply(null, dd.concat([-0.01])), ddAt = dd.indexOf(Math.min.apply(null, dd));
    function YD(d) { return ddT + (ddB - ddT) * (d / ddMin); }
    var kids = [h('defs', { key: 'd' }, h(Hatch, { id: hid }))];
    parts.forEach(function (q, i) {
      var x0 = X(q.from), x1 = X(Math.min(q.to, n - 1));
      kids.push(h('rect', { key: 'b' + i, className: 'qf-band-' + q.kind, x: x0, y: pt - 8, width: x1 - x0, height: ddB - pt + 8 }));
      if (q.kind === 'holdout') kids.push(h('rect', { key: 'bh' + i, x: x0, y: pt - 8, width: x1 - x0, height: ddB - pt + 8, fill: 'url(#' + hid + ')' }));
      if (q.kind !== 'is') kids.push(h('line', { key: 'be' + i, className: 'qf-band-edge is-' + q.kind, x1: x0, x2: x0, y1: pt - 18, y2: ddB }));
      kids.push(h('text', { key: 'bl' + i, className: 'qf-lbl-' + q.kind, x: x0 + (q.kind === 'is' ? 0 : 6), y: pt - 12 }, (q.label || BAND_LABEL[q.kind]) + (q.kind === 'holdout' ? (q.sealed ? ' · SEALED' : ' · OPENED') : '')));
      if (q.kind === 'holdout' && q.sealed) {
        var bw = x1 - x0, wide = bw >= 190, boxW = wide ? 172 : Math.max(60, bw - 16), cxm = (x0 + x1) / 2, cym = (pt + mainB) / 2;
        kids.push(h('rect', { key: 'sm' + i, x: cxm - boxW / 2, y: cym - 24, width: boxW, height: 46, rx: 4, style: { fill: 'var(--surface)', stroke: 'var(--partition-holdout)' } }));
        kids.push(h('text', { key: 'st' + i, className: 'qf-sealed-msg', x: cxm, y: cym - 4, textAnchor: 'middle' }, wide ? 'Not yet observed' : 'Sealed'));
        kids.push(h('text', { key: 'ss' + i, className: 'qf-sealed-sub', x: cxm, y: cym + 12, textAnchor: 'middle' }, q.note || (wide ? '1 look, after all gates pass' : '1 look left')));
      }
    });
    yt.forEach(function (t, i) {
      kids.push(h('line', { key: 'g' + i, className: 'qf-grid', x1: pl, x2: W - pr, y1: Y(t), y2: Y(t) }));
      kids.push(h('text', { key: 'gt' + i, x: pl - 8, y: Y(t) + 3.5, textAnchor: 'end' }, p.yFormat ? p.yFormat(t) : t));
    });
    (p.xTicks || []).forEach(function (t, i) { kids.push(h('text', { key: 'x' + i, x: X(t.i), y: H - 6, textAnchor: t.i === 0 ? 'start' : 'middle' }, t.label)); });
    if (bm) kids.push(h('path', { key: 'bm', className: 'qf-bench', d: pathOf(bm.map(function (y, i) { return [X(i), Y(y)]; })) }));
    kids.push(h('path', { key: 'eq', className: 'qf-line', d: pathOf(vis.map(function (y, i) { return [X(i), Y(y)]; })) }));
    kids.push(h('circle', { key: 'end', className: 'qf-dot', cx: X(visN - 1), cy: Y(vis[visN - 1]), r: 3.5 }));
    if (showDD) {
      kids.push(h('line', { key: 'dz', className: 'qf-zero', x1: pl, x2: W - pr, y1: ddT, y2: ddT }));
      var ddPts = dd.map(function (d, i) { return [X(i), YD(d)]; });
      kids.push(h('path', { key: 'dd', className: 'qf-dd', d: pathOf([[X(0), ddT]].concat(ddPts).concat([[X(visN - 1), ddT]])) + 'Z' }));
      kids.push(h('text', { key: 'ddl', x: pl - 8, y: ddT + 11, textAnchor: 'end' }, '0%'));
      kids.push(h('text', { key: 'ddm', x: pl - 8, y: ddB, textAnchor: 'end' }, pct(ddMin, 0)));
      var ddRight = X(ddAt) > W - 150; kids.push(h('text', { key: 'ddn', className: 'qf-ax-strong', x: X(ddAt) + (ddRight ? -6 : 6), y: YD(ddMin) - 4, textAnchor: ddRight ? 'end' : 'start' }, 'max DD ' + pct(ddMin, 1)));
    }
    return h('div', { className: p.className },
      p.legend !== false && h('div', { className: 'qf-legend', style: { marginBottom: 8 } },
        h('span', { className: 'qf-legend__item' }, h('span', { className: 'qf-legend__line' }), p.seriesLabel || 'Strategy, net of costs'),
        bm && h('span', { className: 'qf-legend__item' }, h('span', { className: 'qf-legend__line is-bench' }), p.benchmarkLabel || 'Buy & hold'),
        showDD && h('span', { className: 'qf-legend__item' }, h('span', { className: 'qf-legend__line is-dd' }), 'Drawdown')),
      h('svg', { className: 'qf-chart', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': p.ariaLabel || 'Equity curve with in-sample, out-of-sample and holdout partitions' }, kids));
  }

  /* ---------- Sparkline ---------- */
  function Sparkline(p) {
    var v = p.series, n = v.length, W = p.width || 96, H = p.height || 24;
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    function X(i) { return W * i / (n - 1); } function Y(y) { return 2 + (H - 4) * (1 - (y - lo) / ((hi - lo) || 1)); }
    var oos = p.oosFrom, hold = p.holdoutFrom, end = hold != null && p.sealed !== false ? hold + 1 : n;
    var kids = [];
    if (hold != null) kids.push(h('rect', { key: 'h', className: 'qf-spark-hold', x: X(hold), y: 0, width: W - X(hold), height: H }));
    kids.push(h('path', { key: 'a', className: 'qf-line', d: pathOf(v.slice(0, oos != null ? oos + 1 : end).map(function (y, i) { return [X(i), Y(y)]; })) }));
    if (oos != null) kids.push(h('path', { key: 'b', className: 'qf-spark-oos', d: pathOf(v.slice(oos, end).map(function (y, i) { return [X(i + oos), Y(y)]; })) }));
    return h('svg', { className: 'qf-spark', width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, 'aria-hidden': true }, kids);
  }

  /* ---------- CostWaterfall ---------- */
  function CostWaterfall(p) {
    var steps = p.steps, W = p.width || 560, rowH = 30, pl = 132, pr = 64, H = steps.length * rowH + 26;
    var run = 0, rows = steps.map(function (s) {
      if (s.kind === 'total') { var r = { s: s, a: 0, b: s.value != null ? s.value : run }; run = r.b; return r; }
      var r2 = { s: s, a: run, b: run + s.value }; run = r2.b; return r2;
    });
    var vals = [0]; rows.forEach(function (r) { vals.push(r.a, r.b); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var ticks = niceTicks(lo, hi, 4); lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]);
    function X(x) { return pl + (W - pl - pr) * (x - lo) / (hi - lo); }
    var kids = [];
    ticks.forEach(function (t, i) {
      kids.push(h('line', { key: 'g' + i, className: t === 0 ? 'qf-zero' : 'qf-grid', x1: X(t), x2: X(t), y1: 0, y2: H - 20 }));
      kids.push(h('text', { key: 't' + i, x: X(t), y: H - 6, textAnchor: 'middle' }, num(t, 1)));
    });
    rows.forEach(function (r, i) {
      var y = i * rowH + 6, x0 = X(Math.min(r.a, r.b)), x1 = X(Math.max(r.a, r.b)), total = r.s.kind === 'total';
      kids.push(h('text', { key: 'l' + i, className: total ? 'qf-ax-strong' : null, x: pl - 12, y: y + 13, textAnchor: 'end', style: { fontFamily: 'var(--font-sans)', fontSize: 12 } }, r.s.label));
      kids.push(h('rect', { key: 'r' + i, className: total ? (r.b < 0 ? 'qf-bar-net-neg' : 'qf-bar-total') : 'qf-bar-cost', x: x0, y: y, width: Math.max(1.5, x1 - x0), height: 18, rx: 2 }));
      if (i < rows.length - 1) kids.push(h('line', { key: 'c' + i, className: 'qf-connector', x1: X(r.b), x2: X(r.b), y1: y + 18, y2: y + rowH }));
      kids.push(h('text', { key: 'v' + i, className: total ? 'qf-ax-strong' : null, x: W - pr + 10, y: y + 13 }, total ? num(r.b, 2) : num(r.s.value, 2, true)));
    });
    return h('svg', { className: cx('qf-chart', p.className), viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Cost waterfall from gross to net ' + (p.unit || 'Sharpe') }, kids);
  }

  /* ---------- WalkForward ---------- */
  function WalkForward(p) {
    var hid = useStableId('qf-wf-');
    var folds = p.folds, W = p.width || 720, laneH = 22, pl = 64, pr = 70, top = 26, span = p.span;
    var H = top + folds.length * laneH + 30;
    function X(t) { return pl + (W - pl - pr) * (t - span[0]) / (span[1] - span[0]); }
    var kids = [h('defs', { key: 'd' }, h(Hatch, { id: hid }))];
    if (p.holdout) {
      var hx0 = X(p.holdout[0]), hx1 = X(p.holdout[1]);
      kids.push(h('rect', { key: 'hb', className: 'qf-band-holdout', x: hx0, y: top - 6, width: hx1 - hx0, height: folds.length * laneH + 6 }));
      kids.push(h('rect', { key: 'hh', x: hx0, y: top - 6, width: hx1 - hx0, height: folds.length * laneH + 6, fill: 'url(#' + hid + ')' }));
      kids.push(h('line', { key: 'he', className: 'qf-band-edge is-holdout', x1: hx0, x2: hx0, y1: top - 6, y2: top + folds.length * laneH }));
    }
    (p.ticks || []).forEach(function (t, i) {
      kids.push(h('line', { key: 'g' + i, className: 'qf-grid', x1: X(t.t), x2: X(t.t), y1: top - 6, y2: top + folds.length * laneH }));
      kids.push(h('text', { key: 'gt' + i, x: X(t.t), y: H - 12, textAnchor: 'middle' }, t.label));
    });
    folds.forEach(function (f, i) {
      var y = top + i * laneH + 4;
      kids.push(h('text', { key: 'n' + i, x: pl - 10, y: y + 10, textAnchor: 'end' }, 'Fold ' + (i + 1)));
      kids.push(h('rect', { key: 'tr' + i, className: 'qf-train', x: X(f.train[0]), y: y + 2, width: X(f.train[1]) - X(f.train[0]), height: 10, rx: 1.5 }));
      kids.push(h('rect', { key: 'te' + i, className: cx('qf-test', f.sharpe < 0 && 'is-neg'), x: X(f.test[0]) + 1, y: y, width: X(f.test[1]) - X(f.test[0]) - 1, height: 14, rx: 1.5 }));
      kids.push(h('text', { key: 's' + i, className: 'qf-ax-strong', x: W - pr + 12, y: y + 11 }, num(f.sharpe, 2)));
    });
    kids.push(h('text', { key: 'sh', x: W - pr + 12, y: 10 }, 'OOS SR'));
    return h('svg', { className: cx('qf-chart', p.className), viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Walk-forward folds: training windows and out-of-sample test windows' }, kids);
  }

  /* ---------- PermutationTest ---------- */
  function PermutationTest(p) {
    var nd = p.nullDist, W = p.width || 560, H = p.height || 180, pl = 12, pr = 12, pt = 26, pb = 24, bins = p.bins || 36;
    var lo = Math.min.apply(null, nd.concat([p.observed])), hi = Math.max.apply(null, nd.concat([p.observed]));
    var pad = (hi - lo) * 0.05; lo -= pad; hi += pad;
    var bw = (hi - lo) / bins, counts = []; for (var i = 0; i < bins; i++) counts.push(0);
    nd.forEach(function (x) { counts[Math.min(bins - 1, Math.floor((x - lo) / bw))]++; });
    var cmax = Math.max.apply(null, counts), exceed = nd.filter(function (x) { return x >= p.observed; }).length;
    var pval = p.pValue != null ? p.pValue : (exceed + 1) / (nd.length + 1);
    function X(x) { return pl + (W - pl - pr) * (x - lo) / (hi - lo); }
    var kids = [];
    counts.forEach(function (c, i) {
      var x0 = X(lo + i * bw), x1 = X(lo + (i + 1) * bw), bh = (H - pt - pb) * c / cmax;
      kids.push(h('rect', { key: i, className: cx('qf-hist', lo + i * bw >= p.observed - bw * 0.5 && 'is-tail'), x: x0 + 0.5, y: H - pb - bh, width: Math.max(0.5, x1 - x0 - 1), height: bh }));
    });
    kids.push(h('line', { key: 'z', className: 'qf-zero', x1: pl, x2: W - pr, y1: H - pb, y2: H - pb }));
    niceTicks(lo, hi, 5).forEach(function (t, i) { kids.push(h('text', { key: 't' + i, x: X(t), y: H - 6, textAnchor: 'middle' }, num(t, 1))); });
    var ox = X(p.observed);
    kids.push(h('line', { key: 'o', className: 'qf-observed', x1: ox, x2: ox, y1: pt - 10, y2: H - pb }));
    kids.push(h('text', { key: 'ol', className: 'qf-ax-strong', x: ox + (ox > W * 0.7 ? -6 : 6), y: pt - 2, textAnchor: ox > W * 0.7 ? 'end' : 'start' }, 'observed ' + num(p.observed, 2) + '  ·  p = ' + num(pval, 3)));
    return h('div', { className: p.className },
      h('svg', { className: 'qf-chart', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Permutation test null distribution with observed statistic' }, kids),
      h('div', { className: 'qf-legend', style: { marginTop: 6 } },
        h('span', { className: 'qf-legend__item' }, h('span', { className: 'qf-legend__sw', style: { background: 'var(--partition-is)', opacity: .55 } }), nd.length.toLocaleString('en-US') + ' shuffled-signal runs'),
        h('span', { className: 'qf-legend__item' }, h('span', { className: 'qf-legend__sw', style: { background: 'var(--forge)' } }), exceed + ' at or above observed')));
  }

  /* ---------- RegimeTable ---------- */
  var REGIME = { low: 'Low vol', mid: 'Mid vol', high: 'High vol' };
  function RegimeTable(p) {
    var maxAbs = Math.max.apply(null, p.rows.map(function (r) { return Math.abs(r.sharpe); }).concat([1]));
    return h(DataTable, { className: p.className, columns: [
      { key: 'regime', label: 'Regime', render: function (v, r) { return h('span', { style: { whiteSpace: 'nowrap' } }, h('span', { className: 'qf-regime-sw is-' + v }), r.label || REGIME[v]); } },
      { key: 'share', label: 'Days', numeric: true, format: function (v) { return pct(v, 0); } },
      { key: 'sharpe', label: 'Sharpe', numeric: true, render: function (v) {
        var w = 40 * Math.abs(v) / maxAbs;
        return h('span', { style: { display: 'inline-flex', gap: 10, alignItems: 'center' } },
          h('span', { className: 'qf-minibar' }, h('span', { className: 'qf-minibar__zero', style: { left: 40 } }), h('span', { className: cx('qf-minibar__fill', v < 0 && 'is-neg'), style: { left: v < 0 ? 40 - w : 40, width: w } })),
          h('span', { style: { minWidth: 40, display: 'inline-block' } }, num(v, 2)));
      } },
      { key: 'ret', label: 'Ann. return', numeric: true, format: function (v) { return pct(v, 1, true); }, tone: function (v) { return v < 0 ? 'loss' : null; } },
      { key: 'maxdd', label: 'Max DD', numeric: true, format: function (v) { return pct(v, 1); } },
      { key: 'hit', label: 'Hit rate', numeric: true, format: function (v) { return pct(v, 0); } }
    ], rows: p.rows });
  }

  /* ---------- MonthlyHeatmap ---------- */
  var MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  function MonthlyHeatmap(p) {
    var scale = p.scale || 0.08;
    function cell(v, key, hold) {
      if (v == null) return h('td', { key: key, className: 'is-empty' }, '·');
      var k = Math.min(1, Math.abs(v) / scale) * 55;
      return h('td', { key: key, className: hold ? 'is-holdout' : null, style: { background: 'color-mix(in srgb, var(' + (v < 0 ? '--loss' : '--gain') + ') ' + k.toFixed(0) + '%, var(--surface))' }, title: pct(v, 2, true) }, num(v * 100, 1));
    }
    return h('table', { className: cx('qf-heat', p.className) },
      h('thead', null, h('tr', null, h('th', { className: 'is-year' }), MONTHS.map(function (m, i) { return h('th', { key: i }, m); }), h('th', null, 'YEAR'))),
      h('tbody', null, p.years.map(function (y) {
        // The year total computed by quantlab when given; compounding is for previews only.
        var tot = 'total' in y ? y.total : y.months.reduce(function (a, b) { return b == null ? a : a * (1 + b); }, 1) - 1;
        return h('tr', { key: y.year }, h('th', { className: 'is-year' }, y.year),
          y.months.map(function (v, i) { return cell(v, i, y.holdoutFrom != null && i >= y.holdoutFrom); }),
          h('td', { className: 'is-total' }, tot == null ? '—' : num(tot * 100, 1)));
      })));
  }

  /* ---------- LogEntry ---------- */
  function LogEntry(p) {
    return h('article', { className: cx('qf-log', 'qf-log--' + p.verdict, p.className) },
      h('div', { className: 'qf-log__date' }, p.date),
      h('div', { className: 'qf-log__track' }, h('span', { className: 'qf-log__dot' })),
      h('div', { className: 'qf-log__body' },
        h('div', { className: 'qf-log__head' }, h('span', { className: 'qf-log__id' }, p.id), h('span', { className: 'qf-log__title' }, p.title), h(StatusBadge, { status: p.verdict })),
        h('p', { className: 'qf-log__conclusion' }, p.conclusion),
        p.facts && h('div', { className: 'qf-log__facts' }, p.facts.map(function (f, i) { return h('span', { key: i }, f[0] + ' ', h('b', null, f[1])); }))));
  }

  /* ---------- Dialog ---------- */
  function Dialog(p) {
    var box = h('div', { className: cx('qf-dialog', p.tone === 'holdout' && 'qf-dialog--holdout', p.className), role: 'dialog', 'aria-modal': true, 'aria-label': typeof p.title === 'string' ? p.title : undefined },
      h('div', { className: 'qf-dialog__head' },
        p.icon && h(Icon, { name: p.icon, size: 20, strokeWidth: 2, style: { color: p.tone === 'holdout' ? 'var(--partition-holdout)' : 'var(--ink)', marginTop: 2 } }),
        h('div', null, h('h2', { className: 'qf-dialog__title' }, p.title), p.subtitle && h('div', { className: 'qf-dialog__sub' }, p.subtitle))),
      h('div', { className: 'qf-dialog__body' }, p.children),
      p.footer && h('div', { className: 'qf-dialog__foot' }, p.footer));
    return p.scrim === false ? box : h('div', { className: 'qf-scrim' }, box);
  }

  /* ---------- AppShell ---------- */
  var NAV = [
    { group: 'Research' },
    { key: 'registry', label: 'Hypothesis registry', icon: 'registry' },
    { key: 'runs', label: 'Runs', icon: 'run' },
    { key: 'validation', label: 'Validation', icon: 'validate' },
    { key: 'log', label: 'Research log', icon: 'book' },
    { group: 'Inputs' },
    { key: 'data', label: 'Data & universes', icon: 'data' },
    { key: 'signals', label: 'Signals', icon: 'signal' },
    { key: 'costs', label: 'Cost models', icon: 'costs' },
    { group: 'Outputs' },
    { key: 'reports', label: 'Tear sheets', icon: 'report' }
  ];
  function AppShell(p) {
    var nav = p.nav || NAV;
    return h('div', { className: cx('qf-root qf-shell', p.className), style: p.style },
      h('aside', { className: 'qf-side' },
        h('div', { className: 'qf-side__brand' }, h(Logo, null)),
        h('div', { className: 'qf-side__ws' }, h('div', null, h('b', null, p.workspace || 'Crypto majors'), h('span', null, p.workspaceMeta || 'Binance daily · 7 instruments')), h(Icon, { name: 'chevron', size: 14, style: { transform: 'rotate(90deg)', color: 'var(--ink-muted)' } })),
        h('nav', { className: 'qf-nav' }, nav.map(function (n, i) {
          if (n.group) return h('div', { key: 'g' + i, className: 'qf-nav__group' }, n.group);
          return h('a', { key: n.key, href: n.href, className: cx('qf-nav__item', p.active === n.key && 'is-active'), 'aria-current': p.active === n.key ? 'page' : undefined },
            h(Icon, { name: n.icon, size: 16 }), n.label, (p.counts && p.counts[n.key] != null) && h('span', { className: 'qf-nav__count' }, p.counts[n.key]));
        })),
        h('div', { className: 'qf-side__foot' }, p.sideFoot || 'Historical simulations. Nothing here is investment advice.')),
      h('div', { className: 'qf-main' },
        h('div', { className: 'qf-top' },
          h('div', { className: 'qf-crumbs' }, (p.crumbs || []).map(function (c, i, a) { return h(F, { key: i }, i ? h(Icon, { name: 'chevron', size: 12 }) : null, i === a.length - 1 ? h('b', null, c) : h('span', null, c)); })),
          p.search !== false && h('div', { className: 'qf-search' }, h(Icon, { name: 'search', size: 14 }), 'Search hypotheses, runs, commits', h('kbd', null, '/')),
          p.topActions),
        h('main', { className: 'qf-content' }, p.children)),
      p.overlay);
  }

  var api = {
    Logo: Logo, Icon: Icon, Button: Button, StatusBadge: StatusBadge, PartitionTag: PartitionTag, Panel: Panel,
    Metric: Metric, MetricStrip: MetricStrip, StageRail: StageRail, StageMeter: StageMeter, HypothesisCard: HypothesisCard,
    HoldoutSeal: HoldoutSeal, Verdict: Verdict, Callout: Callout, ChecksList: ChecksList, Tabs: Tabs, Field: Field,
    TextInput: TextInput, Select: Select, Checkbox: Checkbox, DataTable: DataTable, EquityChart: EquityChart,
    Sparkline: Sparkline, CostWaterfall: CostWaterfall, WalkForward: WalkForward, PermutationTest: PermutationTest,
    RegimeTable: RegimeTable, MonthlyHeatmap: MonthlyHeatmap, LogEntry: LogEntry, Dialog: Dialog, AppShell: AppShell,
    format: { num: num, pct: pct },
    sample: { rng: rng, series: series, draws: draws }
  };
  window.QuantForge = Object.assign(window.QuantForge || {}, api);
})();
