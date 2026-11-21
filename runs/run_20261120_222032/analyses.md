# Training analyses

- **Symbol:** AAPL
- **Trials:** 1
- **Episodes per trial:** 20
- **Seed:** 0

## Trial 1: AAPL (seed 0)

- **Net return:** 0.000%
- **Sharpe:** 0.000
- **Trades:** 0
- **Details:** [`analysis.md`](trial_0001/analysis.md)

The learned policy beat the seeded random flat/long baseline. The learned policy made no trades and stayed flat; its return and Sharpe should not be interpreted as evidence of skill. Learned net return 0.000% versus random -99.107% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

