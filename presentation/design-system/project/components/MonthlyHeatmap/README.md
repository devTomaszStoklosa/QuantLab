# MonthlyHeatmap

Monthly net returns by year, on a blue (gain) to red (loss) diverging scale, with a compounded year total.

- Props: `years` (`[{year, months: [12 fractions or null], holdoutFrom}]`) and `scale` (the return at full intensity, default 0.08).
- Holdout months are outlined in `partition-holdout`.
