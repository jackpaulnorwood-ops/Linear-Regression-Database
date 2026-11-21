# Trial analysis

- **Trial:** 5
- **Run:** C:\Users\Jack Attack\Repos\Linear-Regression-Database\runs\run_20261121_055137
- **Started:** 2026-11-21T06:05:54.583075+00:00
- **Symbol:** AAPL+RBLX
- **Seed:** 4
- **Episodes:** 20
- **Test period:** 2025-07-03 to 2026-11-19
- **Net return:** -2.705%
- **Buy-and-hold:** -42.151%
- **Random baseline:** -99.570%
- **Sharpe:** -1.815
- **Trades:** 32

## Analysis

The learned policy beat the seeded random flat/long baseline. The policy completed 32 round-trip trades with 0.2% market exposure. Learned net return -2.705% versus random -99.570% and buy-and-hold -42.151%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Interpretation notes

- **Epsilon:** No universal optimum: epsilon is the training-time random-action chance, not decision quality. This run linearly decays the configured start to end; compare schedules across multiple seeds using validation data. Backtest prediction is greedy (epsilon=0).
- **Sharpe:** Annualized mean daily net return divided by daily return standard deviation (252 sessions/year, 0% risk-free rate); not prediction accuracy and not itself a comparison against random.
