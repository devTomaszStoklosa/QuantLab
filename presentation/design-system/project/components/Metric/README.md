# Metric

A single number with its label, partition and uncertainty, in tabular mono.

- Props: `label`, `value` (a pre-formatted string; compute nothing in the UI), `unit`, `partition`, `ci` ([lo, hi] strings), `delta`, `deltaTone` (`gain`, `loss` or `neutral`; default neutral, because "up" is not always good), `deltaLabel`, `hint`, `size` (`lg`) and `struck` (for a figure superseded by a stricter one, e.g. gross beside net).
- Show a sealed or missing value as "—" with a hint, never 0.
