# HypothesisCard

The hypothesis as registered: ID, status, a one-sentence serif statement, the economic rationale and the pre-registered success criteria.

- Props: `id`, `title`, `status`, `statement`, `rationale`, `criteria` (`[{label, threshold, result, pass, locked}]`), `frozen` (`{sha, date}`), `owner` and `updated`.
- The statement is a falsifiable claim in one sentence. The rationale is economic, not statistical.
- Criteria are read-only once frozen, and results fill in as stages pass.
