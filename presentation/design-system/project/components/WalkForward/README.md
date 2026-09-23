# WalkForward

Walk-forward folds as lanes: a training window (outlined IS) and a test window (OOS, or `loss` when negative), with each fold's Sharpe. The sealed holdout is hatched at the end.

- Props: `folds` (`[{train: [a, b], test: [a, b], sharpe}]`), `span`, `holdout` ([a, b]) and `ticks`.
