# CostWaterfall

A horizontal waterfall from gross to net: how much of the edge each cost component takes.

- Props: `steps` (`[{label, value, kind: 'total'}]`; a total without a value closes the running sum) and `unit`.
- Put the two totals first and last. Costs are drawn in `loss` and totals in `ink`; a negative net is drawn in `loss`.
