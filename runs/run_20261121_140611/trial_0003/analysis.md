# Trial analysis

- **Trial:** 3
- **Run:** C:\Users\Jack Attack\Repos\Linear-Regression-Database\runs\run_20261121_140611
- **Started:** 2026-11-21T15:12:00.632523+00:00
- **Symbol:** AAPL
- **Seed:** 2
- **Episodes:** 200
- **Test period:** 2025-07-03 to 2026-11-19
- **Net return:** -7.133%
- **Buy-and-hold:** -31.406%
- **Random baseline:** -99.174%
- **Sharpe:** -5.372
- **Trades:** 58

## Analysis

The learned policy beat the seeded random flat/long baseline. The policy completed 58 round-trip trades with 0.3% market exposure. Learned net return -7.133% versus random -99.174% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Interpretation notes

- **Epsilon:** No universal optimum: epsilon is the training-time random-action chance, not decision quality. This run linearly decays the configured start to end; compare schedules across multiple seeds using validation data. Backtest prediction is greedy (epsilon=0).
- **Sharpe:** Annualized mean daily net return divided by daily return standard deviation (252 sessions/year, 0% risk-free rate); not prediction accuracy and not itself a comparison against random.
