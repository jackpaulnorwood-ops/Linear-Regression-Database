"""Make one Q-learning decision using Alpaca's paper-trading account."""

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from q_learning import QLearningAgent, prepare_bars


def fetch_recent_bars(symbol: str, key: str, secret: str) -> pd.DataFrame:
    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    except ImportError as exc:
        raise RuntimeError(
            "Alpaca support is not installed. Install the project requirements first."
        ) from exc

    client = StockHistoricalDataClient(key, secret)
    now = datetime.now(timezone.utc)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        feed=DataFeed.IEX,
        start=now - timedelta(days=7),
        end=now,
        limit=1000,
    )
    response = client.get_stock_bars(request).df
    if response.empty:
        raise RuntimeError(f"Alpaca returned no recent bars for {symbol}.")
    if isinstance(response.index, pd.MultiIndex):
        response = response.xs(symbol, level="symbol")
    data = response.reset_index()
    if "timestamp" not in data and "index" in data:
        data = data.rename(columns={"index": "timestamp"})
    data["ts_utc"] = data["timestamp"]

    # Exclude the current, potentially incomplete five-minute bar.
    completed_before = pd.Timestamp.now(tz="UTC").floor("5min")
    data = data.loc[pd.to_datetime(data["ts_utc"], utc=True) < completed_before]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("q_learning_model.json"))
    parser.add_argument("--notional", type=float, default=100.0,
                        help="Maximum dollar amount for a new long position (default: 100)")
    parser.add_argument(
        "--manage-existing-position",
        action="store_true",
        help="Allow the model to close an existing long position in this symbol",
    )
    parser.add_argument(
        "--submit-paper-order",
        action="store_true",
        help="Submit the required market order to Alpaca paper trading; otherwise dry-run",
    )
    args = parser.parse_args()
    if args.notional <= 0:
        parser.error("--notional must be positive")

    agent, model = QLearningAgent.load(args.model)
    symbol = model["symbol"].upper()
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError(
            "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment."
        )

    bars = fetch_recent_bars(symbol, key, secret)
    samples = prepare_bars(bars, require_next=False)
    latest = samples.iloc[-1]
    if pd.Timestamp.now(tz="UTC") - latest["timestamp"] > pd.Timedelta(minutes=15):
        raise RuntimeError("The most recent completed bar is stale; no decision was made.")

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, OrderType, QueryOrderStatus, TimeInForce
        from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest
    except ImportError as exc:
        raise RuntimeError(
            "Alpaca support is not installed. Install the project requirements first."
        ) from exc

    # paper=True is deliberate; this script has no live-trading mode.
    client = TradingClient(key, secret, paper=True)
    positions = {position.symbol: position for position in client.get_all_positions()}
    position = positions.get(symbol)
    current_quantity = float(position.qty) if position else 0.0
    if current_quantity < 0:
        raise RuntimeError(f"Unexpected short position in {symbol}; refusing to trade.")
    current_state = int(current_quantity > 0)
    desired_state = agent.predict(latest, current_state)

    open_orders = client.get_orders(
        filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    )
    if open_orders:
        raise RuntimeError(f"An open Alpaca order already exists for {symbol}; refusing to add one.")

    print(f"Account mode: Alpaca paper trading")
    print(f"Symbol: {symbol}; completed bar: {latest['timestamp']}")
    print(f"Current position: {current_quantity:g} shares")
    print(f"Q-learning target: {'long' if desired_state else 'flat'}")
    if desired_state == current_state:
        print("No order needed.")
        return
    if not args.submit_paper_order:
        print("Dry run only. Re-run with --submit-paper-order to submit the paper order.")
        return
    if current_quantity and not desired_state and not args.manage_existing_position:
        raise RuntimeError(
            "The model wants to close an existing position. Confirm it is managed "
            "by this bot and re-run with --manage-existing-position."
        )

    if desired_state:
        order = MarketOrderRequest(
            symbol=symbol,
            notional=args.notional,
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
    else:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=current_quantity,
            side=OrderSide.SELL,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
    submitted = client.submit_order(order)
    print(f"Paper order submitted: id={submitted.id}, status={submitted.status}")


if __name__ == "__main__":
    main()
