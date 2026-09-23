# Dialog

A modal for decisions that cannot be undone. `tone="holdout"` gives it the hatched header used for the holdout ceremony.

- Props: `title`, `subtitle` (the consequence), `icon`, `tone`, `footer` (actions, with the committing action last) and `scrim` (default `true`; set `false` to render inline).
- Restate exactly what will happen and require an explicit confirmation, such as typing the ID.
