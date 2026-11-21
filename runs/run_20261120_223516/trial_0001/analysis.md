# Trial analysis

- **Trial:** 1
- **Run:** C:\Users\Jack Attack\Desktop\llama\llama_alpaca\intraday\tuner_runs\run_20261120_223516
- **Started:** 2026-11-21T04:35:17.674788+00:00
- **Symbol:** RBLX
- **Seed:** 0
- **Episodes:** 20
- **Test period:** 2025-09-29 to 2026-02-06
- **Net return:** -17.023%
- **Buy-and-hold:** -10.906%
- **Random baseline:** -33.960%
- **Sharpe:** -5.692
- **Trades:** 176

## Analysis

The learned policy beat the seeded random flat/long baseline. The policy completed 176 round-trip trades with 18.6% market exposure. Learned net return -17.023% versus random -33.960% and buy-and-hold -10.906%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Interpretation notes

- **Epsilon:** No universal optimum: epsilon is the training-time random-action chance, not decision quality. This run linearly decays the configured start to end; compare schedules across multiple seeds using validation data. Backtest prediction is greedy (epsilon=0).
- **Sharpe:** Annualized mean daily net return divided by daily return standard deviation (252 sessions/year, 0% risk-free rate); not prediction accuracy and not itself a comparison against random.
