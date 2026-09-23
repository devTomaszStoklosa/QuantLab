# PartitionTag

Labels which slice of history a number or band comes from: in-sample, out-of-sample (walk-forward) or holdout.

- Props: `partition` (`is`, `oos` or `holdout`), `short` (IS/OOS) and `sealed` (holdout only; `false` shows the open lock).
- Put one next to every metric or series that mixes periods. The holdout tag is hatched, so the partition reads without colour.
