# EquityChart

The equity curve with partition bands, a benchmark and a drawdown pane. While the holdout is sealed, its data is not drawn.

- Props: `series` and `benchmark` (index levels), `drawdown` (drawdowns computed by quantlab, one per point; without it the chart derives them, for previews only), `partitions` (`[{kind: 'is'|'oos'|'holdout', from, to, sealed, label, note}]` as indices), `xTicks` (`[{i, label}]`), `height`, `width` (viewBox), `showDrawdown`, `yFormat`, `seriesLabel` and `benchmarkLabel`.
- With `sealed: true`, the curve stops at the freeze point and the band says "Not yet observed". Name the cost model in the surrounding `Panel` subtitle.
