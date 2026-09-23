# Button

An action button. `forge` fills the primary variant, and there is at most one primary per view.

- `variant`: `primary` (the next research step), `secondary` (default), `ghost` (low-emphasis toolbars), `danger` (reject or delete), `seal` (holdout actions only).
- `size` `sm` is for toolbars and tables. `icon` and `iconRight` take `Icon` names. Other props pass to `<button>`.
- A disabled button carries a `title` that says what unlocks it.
- Labels are imperative, sentence case, and describe research ("Run fold 6", "Open holdout"), never trading.
