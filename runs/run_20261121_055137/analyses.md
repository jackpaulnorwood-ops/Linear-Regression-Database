# Training analyses

- **Symbol:** AAPL
- **Trials:** 5
- **Episodes per trial:** 20
- **Seed:** 0

## Trial 1: AAPL+RBLX (seed 0)

- **Net return:** -0.445%
- **Sharpe:** -1.241
- **Trades:** 3
- **Details:** [`analysis.md`](trial_0001/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 3 round-trip trades with 0.0% market exposure. Learned net return -0.445% versus random -99.554% and buy-and-hold -42.151%. This is one seed on one held-out period, not conclusive evidence of future performance.

