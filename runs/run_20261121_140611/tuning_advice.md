# Tuning recommendations

These are rule-based hypotheses from this run, not guaranteed improvements.
Compare them on held-out validation periods and never tune repeatedly against a final test set.

- **Trials compared:** 5
- **Average net return:** -3.209%
- **Best net return:** -0.372%
- **Worst net return:** -7.133%
- **Average trades:** 30.4

## epsilon_end — decrease
- Current: 0.05
- Suggested: 0.030000000000000002
- Reason: The best trial was not profitable; reducing final exploration can stabilize greedy behavior, but this remains an empirical result.
- Confidence: low
