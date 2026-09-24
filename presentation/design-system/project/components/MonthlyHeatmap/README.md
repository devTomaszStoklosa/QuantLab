# MonthlyHeatmap

Monthly net returns by year, on a blue (gain) to red (loss) diverging scale, with a compounded year total.

- Props: `years` (`[{year, months: [12 fractions or null], total, holdoutFrom}]`; `total` is the year's return computed by quantlab, and only previews leave it out to have it compounded) and `scale` (the return at full intensity, default 0.08).
- Holdout months are outlined in `partition-holdout`.
