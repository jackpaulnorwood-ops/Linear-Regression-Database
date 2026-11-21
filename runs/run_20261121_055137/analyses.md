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

## Trial 2: AAPL+RBLX (seed 1)

- **Net return:** -1.255%
- **Sharpe:** -1.180
- **Trades:** 8
- **Details:** [`analysis.md`](trial_0002/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 8 round-trip trades with 0.1% market exposure. Learned net return -1.255% versus random -99.486% and buy-and-hold -42.151%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Trial 3: AAPL+RBLX (seed 2)

- **Net return:** -0.630%
- **Sharpe:** -1.114
- **Trades:** 3
- **Details:** [`analysis.md`](trial_0003/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 3 round-trip trades with 0.0% market exposure. Learned net return -0.630% versus random -99.606% and buy-and-hold -42.151%. This is one seed on one held-out period, not conclusive evidence of future performance.

