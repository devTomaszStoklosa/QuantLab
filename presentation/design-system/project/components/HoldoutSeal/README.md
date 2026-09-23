# HoldoutSeal

The frozen holdout window: its range, freeze commit, pass criterion and the number of looks left.

- Props: `state` (`sealed` or `unsealed`), `range`, `sha`, `frozenAt`, `criterion`, `openedAt`, `looksAllowed` (default 1), `looksUsed` and `children`.
- The hatched band and violet border are reserved for this component and the holdout partition.
- Once opened, the seal switches to a dashed border. It never returns to sealed.
