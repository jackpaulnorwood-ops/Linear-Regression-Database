# Tuning recommendations

These are rule-based hypotheses from this run, not guaranteed improvements.
Compare them on held-out validation periods and never tune repeatedly against a final test set.

- **Trials compared:** 1
- **Average net return:** -35.823%
- **Best net return:** -35.823%
- **Worst net return:** -35.823%
- **Average trades:** 491.0

## cost_bps — increase
- Current: 5.0
- Suggested: 10.0
- Reason: Average trial trade count was high; a larger cost can discourage churn, but it should be compared on validation data.
- Confidence: low

## epsilon_end — decrease
- Current: 0.05
- Suggested: 0.030000000000000002
- Reason: The best trial was not profitable; reducing final exploration can stabilize greedy behavior, but this remains an empirical result.
- Confidence: low
