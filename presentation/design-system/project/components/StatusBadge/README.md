# StatusBadge

The lifecycle status of a hypothesis: proposed, testing, confirmed, rejected or inconclusive, always shown with its glyph and word.

- Props: `status` and `size` (`lg` for verdict banners).
- Rejected is graphite, not red. It is a finished result, not an error.
- Confirmed requires walk-forward AND an opened holdout. The UI must never show `confirmed` for a hypothesis whose holdout is still sealed.
