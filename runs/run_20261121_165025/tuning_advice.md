# Tuning recommendations

These are rule-based hypotheses from this run, not guaranteed improvements.
Compare them on held-out validation periods and never tune repeatedly against a final test set.

- **Trials compared:** 5
- **Average net return:** 0.000%
- **Best net return:** 0.000%
- **Worst net return:** 0.000%
- **Average trades:** 0.0

## entry_bonus_bps — increase
- Current: 5.0
- Suggested: 6.0
- Reason: No completed trades occurred; a small training-only entry bonus may encourage exploration of long positions.
- Confidence: low

## epsilon_end — decrease
- Current: 0.05
- Suggested: 0.030000000000000002
- Reason: The best trial was not profitable; reducing final exploration can stabilize greedy behavior, but this remains an empirical result.
- Confidence: low
