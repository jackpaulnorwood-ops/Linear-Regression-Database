# Training analyses

- **Symbol:** AAPL
- **Trials:** 5
- **Episodes per trial:** 200
- **Seed:** 0

## Trial 1: AAPL (seed 0)

- **Net return:** -4.776%
- **Sharpe:** -5.242
- **Trades:** 56
- **Details:** [`analysis.md`](trial_0001/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 56 round-trip trades with 0.3% market exposure. Learned net return -4.776% versus random -99.107% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Trial 2: AAPL (seed 1)

- **Net return:** -0.372%
- **Sharpe:** -1.608
- **Trades:** 3
- **Details:** [`analysis.md`](trial_0002/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 3 round-trip trades with 0.0% market exposure. Learned net return -0.372% versus random -99.144% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

## Trial 3: AAPL (seed 2)

- **Net return:** -7.133%
- **Sharpe:** -5.372
- **Trades:** 58
- **Details:** [`analysis.md`](trial_0003/analysis.md)

The learned policy beat the seeded random flat/long baseline. The policy completed 58 round-trip trades with 0.3% market exposure. Learned net return -7.133% versus random -99.174% and buy-and-hold -31.406%. This is one seed on one held-out period, not conclusive evidence of future performance.

