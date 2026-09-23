# Experience and flows

QuantForge follows the life of a hypothesis, not a portfolio. The navigation, screens and gates all mirror one research pipeline:

**Hypothesis → Data & universe → Signal → Backtest → Costs → Walk-forward → Holdout → Regimes → Attribution → Conclusion**

`StageRail` draws this pipeline in full, and `StageMeter` draws it in a table row. The order is fixed. A stage cannot pass before the stages to its left.

## Information architecture

The app is grouped by the object you are working on:

- **Research**
  - *Hypothesis registry*: the home screen.
  - *Runs*: every engine execution with its `git_sha`, seed and parameters.
  - *Validation*: walk-forward, permutation and holdout runs.
  - *Research log*: finished verdicts in chronological order.
- **Inputs**
  - *Data & universes*: providers, point-in-time universes.
  - *Signals*: signal definitions, tested in isolation.
  - *Cost models*: `NaiveCostModel` and `RealisticCostModel`, compared side by side.
- **Outputs**
  - *Tear sheets*.

Every screen sits inside `AppShell`. The workspace switcher at the top of the sidebar scopes everything to one data universe ("Crypto majors · Binance daily · 7 instruments"), so a number is never read without knowing what it was computed on.

## Key screens

1. **Hypothesis registry** (`RegistryScreen`). This is the portfolio of ideas. Summary tiles count confirmed, rejected and inconclusive outcomes with equal weight. The table shows each hypothesis's pipeline position, status, an OOS-highlighted sparkline and whether its holdout is sealed. Tabs filter by status. "Register hypothesis" is the forge action.
2. **Hypothesis workspace** (`WorkspaceScreen`). This is where the work happens. From top to bottom:
   - the header, with ID, status and seal state;
   - the `StageRail`;
   - metrics split by partition, so the IS→OOS decay is visible at a glance;
   - the partitioned equity chart, with the holdout sealed;
   - the walk-forward folds.

   The right rail holds the hypothesis as registered (serif statement, frozen criteria), the `HoldoutSeal` and the integrity checks. "Open holdout" stays disabled until every gate to its left has passed.
3. **Opening the holdout** (`HoldoutScreen`). This is a one-time ceremony in a `Dialog` with the holdout tone. It restates the frozen window, SHA and pass criterion, and lists the gates already passed. The user must type the hypothesis ID to continue. The copy says plainly that the result is final and will be logged whatever it is.
4. **Tear sheet** (`TearSheetScreen`). The page leads with the `Verdict`, then shows the evidence in the order a reviewer asks for it:
   1. headline metrics (gross struck through beside net);
   2. equity;
   3. where the edge went (`CostWaterfall`);
   4. regimes (`RegimeTable`);
   5. luck (`PermutationTest`);
   6. the monthly pattern (`MonthlyHeatmap`);
   7. the disclaimer.

   The example is a *rejected* hypothesis, on purpose.
5. **Research log** (`ResearchLogScreen`). A timeline of `LogEntry` items, with a "what we know so far" summary. It is the institutional memory that stops the same idea from being tested twice.

## Interaction rules

- **Register before you look.** A new hypothesis needs a statement, an economic rationale and pre-registered success criteria before any data stage unlocks.
- **Frozen means frozen.** Fields frozen at registration (`Field` with `frozen`) are read-only. Editing one creates a *new* hypothesis ID that links back to the original. It never overwrites.
- **Gates are visible, not hidden.** A disabled action carries a `title` that says what unlocks it ("Unlocks when walk-forward completes").
- **Trials are counted.** Every variant run against the same hypothesis increments the trial count shown in the integrity checks. The deflated Sharpe uses it.
- **One look.** After the holdout opens, the seal switches to `unsealed` (dashed border, "0 of 1 look left"). The holdout band on every chart becomes readable and stays marked. The hypothesis cannot return to `testing`.
- **Every ending is logged.** Confirmed, rejected and inconclusive verdicts all end in a research-log entry, drafted automatically from the tear sheet and edited by the researcher.

## Empty and edge states

- No runs yet: "no runs yet" in `ink-muted`, with no zero-filled chart.
- Sealed metric: "—" with the hint "sealed until gates pass".
- Thin evidence (under 50 trades in a fold): a `warning` callout, not a hidden number.
- Integrity breach (look-ahead detected): a `danger` callout. The affected runs are quarantined and marked in every table where they appear.
