# Tuning recommendations

These are rule-based hypotheses from this run, not guaranteed improvements.
Compare them on held-out validation periods and never tune repeatedly against a final test set.

- **Trials compared:** 5
- **Average net return:** -1.315%
- **Best net return:** -0.445%
- **Worst net return:** -2.705%
- **Average trades:** 10.8

## epsilon_end — decrease
- Current: 0.05
- Suggested: 0.030000000000000002
- Reason: The best trial was not profitable; reducing final exploration can stabilize greedy behavior, but this remains an empirical result.
- Confidence: low
