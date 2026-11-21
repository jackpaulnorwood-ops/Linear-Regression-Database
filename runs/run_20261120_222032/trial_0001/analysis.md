# Trial analysis

- **Trial:** 1
- **Run:** C:\Users\Jack Attack\Desktop\llama\llama_alpaca\intraday\tuner_runs\run_20261120_222032
- **Started:** 2026-11-21T04:20:35.683936+00:00
- **Symbol:** AAPL
- **Seed:** 0
- **Episodes:** 20
- **Test period:** 2025-07-03 to 2026-11-19
- **Net return:** 0.000%
- **Buy-and-hold:** -31.406%
- **Random baseline:** -99.107%
- **Sharpe:** 0.000
- **Trades:** 0

## Analysis

The learned policy beat the seeded random flat/long baseline. The learned policy made no trades and stayed flat; its return and Sharpe should not be interpreted as evidence of skill. Learned net return 0.000% versus random -99.107% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Interpretation notes

- **Epsilon:** No universal optimum: epsilon is the training-time random-action chance, not decision quality. This run linearly decays the configured start to end; compare schedules across multiple seeds using validation data. Backtest prediction is greedy (epsilon=0).
- **Sharpe:** Annualized mean daily net return divided by daily return standard deviation (252 sessions/year, 0% risk-free rate); not prediction accuracy and not itself a comparison against random.
