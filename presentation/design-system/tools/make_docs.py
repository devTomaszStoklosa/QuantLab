import os
from pathlib import Path

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "project", "components")
D = {
"Logo": """The QuantForge mark and wordmark: an ink square holding an equity line that stops at a dashed seal, with the forge spark beyond it.

- Props: `size` (px, default 22) and `wordmark` (default `true`; set `false` for the mark alone, which is then labelled for screen readers).
- The mark takes `ink`, `ground` and `forge` from the theme, so it inverts correctly in Graphite.
- Use it once per screen, in the `AppShell` sidebar. Don't recolour it, add taglines inside it or place it on `forge`.""",
"Icon": """A 24px line icon with a 1.75 stroke, drawn in `currentColor` to sit beside IBM Plex at 13–16px.

- Props: `name` (see `Icon.names`), `size`, `strokeWidth` and `label` (set it when the icon carries meaning alone; otherwise it is `aria-hidden`).
- Some glyphs have fixed meanings: `check` = passed, `x` = failed or rejected, `dash` = inconclusive or n/a, `pending` = not run, `lock` = sealed or frozen, `flask` = in progress. Never reuse them for anything else.
- No emoji and no filled icons.""",
"Button": """An action button. `forge` fills the primary variant, and there is at most one primary per view.

- `variant`: `primary` (the next research step), `secondary` (default), `ghost` (low-emphasis toolbars), `danger` (reject or delete), `seal` (holdout actions only).
- `size` `sm` is for toolbars and tables. `icon` and `iconRight` take `Icon` names. Other props pass to `<button>`.
- A disabled button carries a `title` that says what unlocks it.
- Labels are imperative, sentence case, and describe research ("Run fold 6", "Open holdout"), never trading.""",
"StatusBadge": """The lifecycle status of a hypothesis: proposed, testing, confirmed, rejected or inconclusive, always shown with its glyph and word.

- Props: `status` and `size` (`lg` for verdict banners).
- Rejected is graphite, not red. It is a finished result, not an error.
- Confirmed requires walk-forward AND an opened holdout. The UI must never show `confirmed` for a hypothesis whose holdout is still sealed.""",
"PartitionTag": """Labels which slice of history a number or band comes from: in-sample, out-of-sample (walk-forward) or holdout.

- Props: `partition` (`is`, `oos` or `holdout`), `short` (IS/OOS) and `sealed` (holdout only; `false` shows the open lock).
- Put one next to every metric or series that mixes periods. The holdout tag is hatched, so the partition reads without colour.""",
"Panel": """The standard container for a chart, table or block of evidence, bordered by a hairline.

- Props: `title`, `subtitle` (state the method or cost model here), `icon`, `tag`, `actions`, `footer` (provenance: module and commit), and `flush` (removes body padding for tables).
- One idea per panel. Title it with the question it answers where you can ("Where the edge went", "Is it luck?").""",
"Metric": """A single number with its label, partition and uncertainty, in tabular mono.

- Props: `label`, `value` (a pre-formatted string; compute nothing in the UI), `unit`, `partition`, `ci` ([lo, hi] strings), `delta`, `deltaTone` (`gain`, `loss` or `neutral`; default neutral, because "up" is not always good), `deltaLabel`, `hint`, `size` (`lg`) and `struck` (for a figure superseded by a stricter one, e.g. gross beside net).
- Show a sealed or missing value as "—" with a hint, never 0.""",
"MetricStrip": """A row of `Metric` tiles sharing one border, used for headline figures under a page header.

- Props: `items` (Metric props) and `columns` (fixed column count; otherwise auto-fit from 150px).
- Order the tiles from most to least trustworthy partition: OOS, then IS for comparison, then holdout.""",
"StageRail": """The research pipeline for one hypothesis, from registration to conclusion, with each stage's state and key figure.

- Props: `stages` (`[{key, label, state, meta}]`, where state is `passed`, `failed`, `active`, `pending`, `locked` or `skipped`) and `current` (the key being viewed, underlined in forge).
- `StageRail.STAGES` holds the ten canonical stages in order. Don't reorder, rename or skip them.
- `meta` is one short mono fact ("SR 0.64 net", "fold 6 of 6").""",
"StageMeter": """A compact ten-cell version of `StageRail` for table rows, with a passed-count.

- Props: `states` (array of stage states) and `showCount` (default `true`).
- Each cell has a tooltip naming its stage. The holdout cell is hatched while it is locked.""",
"HypothesisCard": """The hypothesis as registered: ID, status, a one-sentence serif statement, the economic rationale and the pre-registered success criteria.

- Props: `id`, `title`, `status`, `statement`, `rationale`, `criteria` (`[{label, threshold, result, pass, locked}]`), `frozen` (`{sha, date}`), `owner` and `updated`.
- The statement is a falsifiable claim in one sentence. The rationale is economic, not statistical.
- Criteria are read-only once frozen, and results fill in as stages pass.""",
"HoldoutSeal": """The frozen holdout window: its range, freeze commit, pass criterion and the number of looks left.

- Props: `state` (`sealed` or `unsealed`), `range`, `sha`, `frozenAt`, `criterion`, `openedAt`, `looksAllowed` (default 1), `looksUsed` and `children`.
- The hatched band and violet border are reserved for this component and the holdout partition.
- Once opened, the seal switches to a dashed border. It never returns to sealed.""",
"Verdict": """The conclusion banner at the top of a tear sheet or finished workspace: a status, a serif sentence of what was learned, and the key figures.

- Props: `verdict` (`confirmed`, `rejected` or `inconclusive`), `children` (one or two sentences, finding first), `meta` (decision date and freeze commit) and `side` (key figures).
- Give all three verdicts equal visual weight and equal care in wording.""",
"Callout": """An inline message about the integrity or reading of the evidence.

- `tone`: `danger` (look-ahead, holdout breach: blocks conclusions), `warning` (thin evidence that does not block), `frozen` (explains a locked parameter) or `info` (context, disclaimers).
- Props: `title` (the fact) and `children` (what it means and what happens next). Never use danger for a rejected hypothesis.""",
"ChecksList": """A list of methodology checks, each with a state, label, optional detail and a mono value.

- Each item is `{state, label, detail, value}`, where state is `pass`, `warn`, `fail` or `na`.
- Use it for integrity checks (look-ahead, costs, survivorship, trial count), gate summaries and "what we know" lists. Every state carries its glyph.""",
"Tabs": """Underlined tabs for switching views of the same object, with optional counts.

- Props: `items` (`[{value, label, count, icon}]`), `value` or `defaultValue`, and `onChange`.
- Keep the counts honest: registry tabs count rejected and inconclusive results alongside confirmed ones.""",
"Field": """A form field wrapper with a label, hint or error, and an optional frozen marker.

- Props: `label`, `hint`, `error` and `frozen` (adds a hatched "Frozen" tag; pair it with a read-only input).
- Say in the hint what the value does to the research ("Stored with the run for reproducibility").""",
"TextInput": """A single-line text input. Set `mono` for parameters, dates, seeds and IDs.

- Other props pass to `<input>`. Set `aria-invalid` with a `Field` error. Frozen values are `readOnly` and render sunken.""",
"Select": """A native select styled to match the inputs.

- Props: `options` (strings or `{value, label}`). Other props pass to `<select>`.""",
"Checkbox": """A checkbox with its label, used for explicit acknowledgements such as the holdout ceremony.

- Props: `label`. Other props pass to `<input type="checkbox">`. Write the label as a first-person commitment.""",
"DataTable": """A dense data table with uppercase sunken headers, right-aligned mono numerics, row tones and an optional selected row.

- Props: `columns` (`[{key, label, numeric, width, format(v, row), render(v, row), tone(v, row) → 'gain'|'loss'|'dim'}]`), `rows`, `dense` and `selected` (row `id`).
- Format values in `format`; never compute metrics there.""",
"EquityChart": """The equity curve with partition bands, a benchmark and a drawdown pane. While the holdout is sealed, its data is not drawn.

- Props: `series` and `benchmark` (index levels), `drawdown` (drawdowns computed by quantlab, one per point; without it the chart derives them, for previews only), `partitions` (`[{kind: 'is'|'oos'|'holdout', from, to, sealed, label, note}]` as indices), `xTicks` (`[{i, label}]`), `height`, `width` (viewBox), `showDrawdown`, `yFormat`, `seriesLabel` and `benchmarkLabel`.
- With `sealed: true`, the curve stops at the freeze point and the band says "Not yet observed". Name the cost model in the surrounding `Panel` subtitle.""",
"Sparkline": """A tiny equity line for table rows. The out-of-sample stretch is drawn in `partition-oos`, and a sealed holdout is left blank.

- Props: `series`, `oosFrom`, `holdoutFrom`, `sealed` (default `true`), `width` and `height`.""",
"CostWaterfall": """A horizontal waterfall from gross to net: how much of the edge each cost component takes.

- Props: `steps` (`[{label, value, kind: 'total'}]`; a total without a value closes the running sum) and `unit`.
- Put the two totals first and last. Costs are drawn in `loss` and totals in `ink`; a negative net is drawn in `loss`.""",
"WalkForward": """Walk-forward folds as lanes: a training window (outlined IS) and a test window (OOS, or `loss` when negative), with each fold's Sharpe. The sealed holdout is hatched at the end.

- Props: `folds` (`[{train: [a, b], test: [a, b], sharpe}]`), `span`, `holdout` ([a, b]) and `ticks`.""",
"PermutationTest": """Answers "Is it luck?": a histogram of the statistic under shuffled signals, the observed value as a line and the p-value. The tail at or above the observed value is drawn in forge.

- Props: `nullDist`, `observed`, `pValue` (computed from the distribution if omitted) and `bins`.""",
"RegimeTable": """Performance conditional on volatility regime (terciles of realized vol), with a diverging Sharpe bar per row.

- Each row is `{regime: 'low'|'mid'|'high', label, share, sharpe, ret, maxdd, hit}`, with fractions for the percentages.
- Use it to show whether an average hides a regime where the strategy fails when it hurts most.""",
"MonthlyHeatmap": """Monthly net returns by year, on a blue (gain) to red (loss) diverging scale, with a compounded year total.

- Props: `years` (`[{year, months: [12 fractions or null], total, holdoutFrom}]`; `total` is the year's return computed by quantlab, and only previews leave it out to have it compounded) and `scale` (the return at full intensity, default 0.08).
- Holdout months are outlined in `partition-holdout`.""",
"LogEntry": """One research-log entry on a timeline: date, ID, title, verdict, a serif conclusion and key facts.

- Props: `date`, `id`, `title`, `verdict`, `conclusion` (the lesson, in one or two sentences) and `facts` (`[[label, value]]`).
- Write rejected and inconclusive entries with the same care as confirmed ones, and say what would justify a retest.""",
"Dialog": """A modal for decisions that cannot be undone. `tone="holdout"` gives it the hatched header used for the holdout ceremony.

- Props: `title`, `subtitle` (the consequence), `icon`, `tone`, `footer` (actions, with the committing action last) and `scrim` (default `true`; set `false` to render inline).
- Restate exactly what will happen and require an explicit confirmation, such as typing the ID.""",
"AppShell": """The application frame: a sidebar with the logo, workspace (data universe) switcher, grouped research navigation and a standing disclaimer, plus a top bar with breadcrumbs and search.

- Props: `active` (nav key), `crumbs`, `counts`, `workspace`, `workspaceMeta`, `nav` (items may carry an `href`), `topActions`, `overlay` (for a `Dialog`), `sideFoot`, `search` (`false` hides the search box of an app without search) and `children` (page content).
- Nav keys: `registry`, `runs`, `validation`, `log`, `data`, `signals`, `costs` and `reports`.""",
}
for k, v in D.items():
    d = os.path.join(ROOT, k); os.makedirs(d, exist_ok=True)
    Path(d, "README.md").write_text("# " + k + "\n\n" + v + "\n")

SCREENS = {
"RegistryScreen": "The home screen: every registered hypothesis, its pipeline position, verdict and holdout state. Confirmed, rejected and inconclusive results are counted with equal weight.",
"WorkspaceScreen": "The working view of one hypothesis. It shows the stage rail, metrics split by partition, a partitioned equity chart with the holdout sealed and the walk-forward folds, with the hypothesis as registered, the seal and the integrity checks in the right rail.",
"HoldoutScreen": "The one-time ceremony that opens a frozen holdout. It restates the freeze, lists the gates passed and requires the hypothesis ID to be typed before the result can be seen.",
"TearSheetScreen": "The final report on a hypothesis, shown here for a rejected one. It leads with the verdict, then shows the evidence in the order a reviewer asks for it: net vs gross, equity, cost attribution, regimes, luck, and the monthly pattern.",
"ResearchLogScreen": "The institutional memory: a chronological timeline of verdicts with conclusions and key facts, plus a summary of what is now known.",
}
for k, v in SCREENS.items():
    Path(ROOT, k, "README.md").write_text("# " + k + "\n\n" + v + "\n")
print("ok")
