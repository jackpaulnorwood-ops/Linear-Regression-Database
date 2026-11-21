# Training analyses

- **Symbol:** AAPL
- **Trials:** 1
- **Episodes per trial:** 1
- **Seed:** 0

## Trial 1: AAPL (seed 0)

- **Net return:** -35.823%
- **Sharpe:** -4.975
- **Trades:** 491
- **Details:** [`analysis.md`](trial_0001/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 491 round-trip trades with 31.0% market exposure. Learned net return -35.823% versus random -99.107% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Run comparison

- [`trial_comparison.png`](./trial_comparison.png)
