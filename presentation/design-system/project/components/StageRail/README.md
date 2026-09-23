# StageRail

The research pipeline for one hypothesis, from registration to conclusion, with each stage's state and key figure.

- Props: `stages` (`[{key, label, state, meta}]`, where state is `passed`, `failed`, `active`, `pending`, `locked` or `skipped`) and `current` (the key being viewed, underlined in forge).
- `StageRail.STAGES` holds the ten canonical stages in order. Don't reorder, rename or skip them.
- `meta` is one short mono fact ("SR 0.64 net", "fold 6 of 6").
