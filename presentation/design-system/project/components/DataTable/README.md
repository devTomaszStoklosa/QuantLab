# DataTable

A dense data table with uppercase sunken headers, right-aligned mono numerics, row tones and an optional selected row.

- Props: `columns` (`[{key, label, numeric, width, format(v, row), render(v, row), tone(v, row) → 'gain'|'loss'|'dim'}]`), `rows`, `dense` and `selected` (row `id`).
- Format values in `format`; never compute metrics there.
