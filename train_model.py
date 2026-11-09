
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Reuse the working read-only database connection from explore_stocks.py
from explore_stocks import DB_PATH, DB_URI

TRAINING_STOCK = "AAPL"
HORIZON_BARS = 3
FEATURES = [
    "close",
    "recent_return_pct",
    "high_low_range",
    "volume"
]

def main():

    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Cannot see database: {DB_PATH}")

    # Connect to the database without allowing modifications.
    with sqlite3.connect(DB_URI, uri=True) as conn:

        conn.execute("PRAGMA query_only = ON")

        # 1. Retrieve all available historical data for AAPL.
        df = pd.read_sql_query("""
            SELECT symbol, ts_utc, high, low, close, volume
            FROM bars_5m
            WHERE symbol = ?
            ORDER BY ts_utc ASC
        """, conn, params=(TRAINING_STOCK,))

    # Convert timestamps to datetime
    df["timestamp"] = pd.to_datetime(
        df["ts_utc"], utc=True, errors="coerce"
    )

    df = df.dropna(
        subset=["timestamp", "high", "low", "close", "volume"]
    )

    # Convert UTC timestamps to New York time
    df["market_timestamp"] = df["timestamp"].dt.tz_convert(
        "America/New_York"
    )

    # Calculate the time of each record in minutes after midnight
    market_minutes = (
        df["market_timestamp"].dt.hour * 60
        + df["market_timestamp"].dt.minute
    )

    # Keep only regular market hours: 9:30 AM to 4:00 PM
    df = df[
        (market_minutes >= 9 * 60 + 30)
        & (market_minutes < 16 * 60)
    ].copy()

    # Group records by their actual market date
    df["session_date"] = df["market_timestamp"].dt.date

    print("Records during regular market hours:", len(df))

    print(f"Stock: {TRAINING_STOCK}")
    print(f"Raw historical records: {len(df)}")
    print(f"First date: {df['session_date'].min()}")
    print(f"Last date: {df['session_date'].max()}")

    # 2. Construct labeled examples.
    # Each example uses current information to predict
    # the percentage return three bars into the future.

    all_sessions = []
    five_minutes = pd.Timedelta(minutes=5)

    for session_date, day in df.groupby("session_date", sort=True):

        day = day.sort_values("timestamp").reset_index(drop=True)

        timestamps = day["timestamp"]
        close = day["close"]

        # Input 1: Current closing price (stored).
        # Input 2: Percentage return over previous 3 bars.
        day["recent_return_pct"] = (
            (close / close.shift(3)) - 1
        ) * 100

        # Input 3: Current high-low range.
        day["high_low_range"] = day["high"] - day["low"]

        # Input 4: Current trading volume (stored).

        # Target: Percentage return 3 bars into the future.
        future_close = close.shift(-HORIZON_BARS)

        day["target_return_pct"] = (
            (future_close / close) - 1
        ) * 100

        # Make sure the previous 3 intervals are consecutive.
        gaps = timestamps.diff()

        previous_valid = (
            gaps.eq(five_minutes)
            & gaps.shift(1).eq(five_minutes)
            & gaps.shift(2).eq(five_minutes)
        )

        # Make sure the next 3 intervals are consecutive.
        next_1 = timestamps.shift(-1) - timestamps
        next_2 = timestamps.shift(-2) - timestamps.shift(-1)
        next_3 = timestamps.shift(-3) - timestamps.shift(-2)

        future_valid = (
            next_1.eq(five_minutes)
            & next_2.eq(five_minutes)
            & next_3.eq(five_minutes)
        )

        day["valid_window"] = previous_valid & future_valid

        all_sessions.append(day)

    samples = pd.concat(all_sessions, ignore_index=True)

    # Remove incomplete examples.
    samples = samples[
        samples["valid_window"]
    ].dropna(subset=FEATURES + ["target_return_pct"])

    print("\n=== Labeled examples ===")
    print(f"Total valid examples: {len(samples)}")

    print("\nSample labeled examples:")
    print(
        samples[
            ["timestamp"] + FEATURES + ["target_return_pct"]
        ].head(10).to_string(index=False)
    )

    # 3. Chronological 80/20 train/test split.
    # Split by complete trading dates, not randomly.

    available_dates = sorted(samples["session_date"].unique())

    if len(available_dates) < 2:
        raise ValueError("Not enough trading dates for a train/test split.")

    split_index = int(len(available_dates) * 0.80)

    training_dates = set(available_dates[:split_index])

    train = samples[
        samples["session_date"].isin(training_dates)
    ]

    test = samples[
        ~samples["session_date"].isin(training_dates)
    ]

    X_train = train[FEATURES]
    y_train = train["target_return_pct"]

    X_test = test[FEATURES]
    y_test = test["target_return_pct"]

    print("\n=== Chronological train/test split ===")
    print(f"Training examples: {len(train)}")
    print(f"Testing examples: {len(test)}")
    print(f"Training period: {train['session_date'].min()} to "
          f"{train['session_date'].max()}")
    print(f"Testing period: {test['session_date'].min()} to "
          f"{test['session_date'].max()}")

    # 4. Train the linear regression model.

    model = LinearRegression()
    model.fit(X_train, y_train)

    print("\n=== Linear regression model ===")
    print(f"Intercept: {model.intercept_:.6f}")

    for feature, coefficient in zip(FEATURES, model.coef_):
        print(f"{feature}: {coefficient:.6f}")

    # 5. Evaluate predictions using the unseen test data.

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5
    r2 = r2_score(y_test, predictions)

    # Compare against a simple prediction of zero return.
    zero_predictions = [0.0] * len(y_test)
    baseline_mae = mean_absolute_error(y_test, zero_predictions)

    print("\n=== Model evaluation ===")
    print(f"Mean Absolute Error: {mae:.6f}%")
    print(f"Root Mean Squared Error: {rmse:.6f}%")
    print(f"R-squared: {r2:.6f}")
    print(f"Zero-return baseline MAE: {baseline_mae:.6f}%")

    # 6. Compare actual and predicted returns.

    results = pd.DataFrame({
        "date": test["session_date"].astype(str).values,
        "actual_return_pct": y_test.values,
        "predicted_return_pct": predictions
    })

    print("\n=== Actual vs predicted returns (first 10) ===")
    print(results.head(10).to_string(index=False))
    
    # === VISUAL REPRESENTATION ===

    # Create a figure with two graphs
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    # Graph 1: Actual vs. predicted returns over time
    plot_data = test.copy().reset_index(drop=True)
    plot_data["predicted_return_pct"] = predictions

    # Use the first 500 testing examples
    plot_data = plot_data.head(500).copy()

    # Use sequential positions instead of calendar timestamps
    x = range(len(plot_data))

    actual = plot_data["target_return_pct"].to_numpy().copy()
    predicted = plot_data["predicted_return_pct"].to_numpy().copy()

    # Break the lines wherever consecutive records are not 5 minutes apart
    time_differences = plot_data["timestamp"].diff()

    missing_intervals = time_differences.ne(pd.Timedelta(minutes=5))
    missing_intervals.iloc[0] = False

    actual[missing_intervals.to_numpy()] = float("nan")
    predicted[missing_intervals.to_numpy()] = float("nan")

    axes[0].plot(
        x,
        actual,
        label="Actual Return",
        linewidth=1
    )

    axes[0].plot(
        x,
        predicted,
        label="Predicted Return",
        linewidth=1
    )

    axes[0].axhline(y=0, linestyle="--", linewidth=0.8)

    axes[0].set_title("AAPL: Actual vs. Predicted Returns")
    axes[0].set_xlabel("Trading Records (Sequential)")
    axes[0].set_ylabel("15-Minute Return (%)")
    axes[0].legend()
    axes[0].grid(True)

    # Graph 2: Actual returns vs. predicted returns
    axes[1].scatter(
        y_test,
        predictions,
        alpha=0.3
    )

    # Add a diagonal reference line
    minimum = min(y_test.min(), predictions.min())
    maximum = max(y_test.max(), predictions.max())

    axes[1].plot(
        [minimum, maximum],
        [minimum, maximum],
        linestyle="--",
        label="Perfect Predictions"
    )

    axes[1].set_title("Actual vs. Predicted Returns")
    axes[1].set_xlabel("Actual Return (%)")
    axes[1].set_ylabel("Predicted Return (%)")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()

    # Save the graph as an image
    plt.savefig("aapl_model_visualization.png", dpi=300)

    # Display the graph
    plt.show()

    print("\nGraph saved as aapl_model_visualization.png")


if __name__ == "__main__":
    main()
