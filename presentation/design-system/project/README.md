QuantForge is a research lab for systematic investing. Hypotheses are registered, tested, challenged and validated here. It is not a trading terminal. Every screen answers one question: **how much should we trust this claim, and why?** Charts are evidence attached to a claim. They are never the product.

The system has two themes, **Paper** (light, the default) and **Graphite** (dark). Components live in `components/bundle.js` as `window.QuantForge` and need React 18.

## Principles

1. **Every number says where it came from.** A metric without a partition is not shown. Use `PartitionTag` (`is`, `oos`, `holdout`) on every metric, chart band and table that mixes periods. In-sample figures sit in neutral `partition-is`, because they are the least trustworthy numbers on the page.
2. **The holdout is sealed.** Data after the freeze point is not drawn until the holdout is opened, and the chart shows a hatched `partition-holdout` band instead. The holdout opens once, through a deliberate ceremony (`HoldoutScreen`). Never add a "peek" or preview.
3. **Rejection is a result.** `status-rejected` is graphite, not red. A rejected hypothesis gets the same verdict banner, tear sheet and research-log entry as a confirmed one. Keep red (`danger`) for integrity alarms: look-ahead leaks, a holdout breach, a failed gate.
4. **Code computes, the UI formats.** Components receive numbers that `quantlab` has already computed. The UI never derives a financial metric. `QuantForge.format` only formats.
5. **Describe, never recommend.** Copy states what happened historically, under which costs, with which uncertainty. It never says buy, sell, increase, allocate, or "this strategy works".
6. **Quiet chrome, loud evidence.** The interface is paper, graphite and hairlines. Colour is reserved for meaning: partitions, statuses, P&L. `forge` appears once per view, on the primary action.

## Content fundamentals

**Voice.** Write like a careful colleague reviewing a paper: precise, plain and unhurried. Use short declarative sentences. Put the finding first and the qualification second. Write "we" in research-log conclusions and the imperative in UI actions ("Run fold 6", "Open holdout"). No exclamation marks, no emoji, no hype.

**Casing.** Use sentence case everywhere: buttons, titles, tabs ("Hypothesis registry", "Open holdout"). Eyebrows are sentence case in the source and uppercased by CSS (`qf-eyebrow`). Class and model names keep their code casing (`RealisticCostModel`, `mom_12w`).

**Say, don't say**

| Say | Don't say |
| --- | --- |
| "Sharpe 0.64 out-of-sample, net of costs" | "Great Sharpe!" |
| "Rejected: the edge does not survive costs" | "Failed", "Loser", "Bad strategy" |
| "Inconclusive: 23 trades cannot separate the effect from noise" | "Maybe works" |
| "Historical simulation" | "Performance", "Returns you can expect" |
| "Open holdout" | "Reveal results", "Unlock profits" |
| "Consistent with investor under-reaction" | "Proves that markets…" |

**Numbers.** Set every number in `font-mono` with tabular figures (`text-metric`). Use a real minus sign (U+2212 "−") and sign deltas explicitly ("+3.1 pp", "−0.48"). Precision:

- Sharpe, Sortino and Calmar: 2 dp.
- Returns and drawdowns: 1 dp with `%`.
- p-values: 3 dp.
- Costs: bps, 1 dp.
- Turnover: `×/yr`.

Show uncertainty whenever the engine provides it (`CI [0.21, 1.05]`). Show a missing value as "—", never 0.

**Dates.** In the UI, write `14 Aug 2026`. In ranges, parameters and anything copied into code, write ISO `2019-01-01 → 2023-12-31`. Commits are 7-character SHAs in `code`.

**Disclaimers.** Every tear sheet and registry ends with one line in `qf-disclaimer`: *"Historical simulation … nothing here is a recommendation to trade."* The app shell footer repeats it.

## Visual foundations

**Colour roles.** Each colour family has one job.

- **Neutrals:** `ground`, `surface` and `surface-sunken` for the working surfaces. `ink` and `ink-muted` for text. `line` for hairlines and `line-strong` for control borders.
- **Brand:** `forge` is the ember. It fills the primary button (text in `on-forge`) and the logo spark, and marks the active nav item (`forge-soft` fill with `forge-ink` text). One forge element per view.
- **Partitions:** `partition-is` (graphite), `partition-oos` (steel blue) and `partition-holdout` (violet). Each has a `-soft` fill. Holdout is always paired with the 45° hatch, so colour is never the only cue.
- **Statuses:** `status-proposed`, `-testing`, `-confirmed` (teal), `-rejected` (graphite) and `-inconclusive` (ochre), each with a `-soft` fill. A status always carries its glyph and its word.
- **P&L:** `gain` is blue and `loss` is red, so the pair survives red–green colour blindness and differs in lightness. Drawdown areas use `drawdown`.
- **Regimes:** `regime-low`, `regime-mid` and `regime-high` form a sequential ramp. High volatility always has the most contrast.
- **Alarms:** `danger` and `warning` appear only in callouts, checks and failed gates.

**Contrast.** Every text token meets 4.5:1 on the grounds named in its usage note, in both themes. `line-strong`, `focus` and the partition hues meet 3:1 as marks. `ink-faint` is for disabled text and placeholders only.

**Type.** Three families, each with a job:

- `font-sans` (IBM Plex Sans) for the interface: `text-display`, `text-h1`, `text-h2`, `text-body`, `text-small` and `text-eyebrow`.
- `font-serif` (Source Serif 4) for the scientific claim: `text-statement` for hypothesis statements and log conclusions, and `text-note` (italic) for rationale. Serif marks the words a researcher wrote, and it only appears there.
- `font-mono` (IBM Plex Mono) for numbers, SHAs and parameters: `text-metric-xl`, `text-metric` and `text-code`.

**Space and shape.** Spacing follows a 4px grid (`space-1` to `space-7`). Panels have `space-4` padding, and gaps between panels are `space-5`. Radii are small and technical: `radius-xs` for bars and cells, `radius-sm` for controls, `radius-md` for panels and dialogs. `radius-pill` is only for stage-rail nodes.

**Borders over shadows.** Panels are defined by a 1px `line`. `shadow-panel` is barely there, and `shadow-pop` is reserved for dialogs and menus.

**Focus.** Keyboard focus is a solid 2px `focus` ring at a 2px offset, on every interactive element, in both themes.

**Motion.** Keep it minimal. Colour and background transitions take 120 ms. Charts never animate in and numbers never count up, because evidence should not perform.

**Density.** Tables are the main surface. Use 9px/12px cells, or 6px with `dense`. Headers are uppercase `text-eyebrow` on `surface-sunken`. Numeric columns are right-aligned mono.

## Iconography

Icons come from `Icon`, a custom set of 24px line icons with a 1.75 stroke, round caps and `currentColor`, drawn to sit beside Plex at 13–16px. The glyphs have fixed meanings:

- `check`: passed / confirmed.
- `x`: failed / rejected.
- `dash`: inconclusive / not applicable.
- dashed circle `pending`: not run.
- `lock`: sealed / frozen.
- `flask`: in progress.

Do not substitute emoji or filled icons. The logo mark is part of this set: an ink square holding an equity line that stops at a dashed seal, with the forge spark beyond it. Use the `Logo` component in React, or `assets/Logos` elsewhere.

## Charts

Charts follow the partition rules. Bands run in the order IS (no fill) → OOS (`partition-oos-soft`, dotted edge) → Holdout (hatched, solid edge). The strategy line is `ink`, 1.6px. The benchmark is a dashed `chart-benchmark` line behind it. Drawdown gets its own pane under the equity line, never on a second axis. Gridlines are horizontal only. Axis labels are mono in `ink-muted`. Every chart names its cost model in the panel subtitle. The **Screens** cards show how the pieces compose.
