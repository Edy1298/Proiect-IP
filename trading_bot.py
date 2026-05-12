import sqlite3
import config

def get_candles(symbol):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    query = """
        SELECT sp.date, sp.open, sp.high, sp.low, sp.close, sp.volume
        FROM stock_price sp
        JOIN stock s ON sp.stock_id = s.id
        WHERE s.symbol = ?
        ORDER BY sp.date DESC
        LIMIT 5
    """

    cursor.execute(query, (symbol,))
    rows = cursor.fetchall()

    candles = []
    for row in rows:
        candles.append({
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"]
        })

    connection.close()
    return candles


def predict_price_trend(symbol):

    candles = get_candles(symbol)
    closes = [candle["close"] for candle in candles]
    volumes = [candle["volume"] for candle in candles]

    trend = "Increasing" if closes[0] > closes[-1] else "Decreasing"

    patterns = []

    avg_close = sum(closes) / len(closes)
    if closes[0] > avg_close:
        patterns.append("Above average close price")
    else:
        patterns.append("Below average close price")

    if volumes[0] > sum(volumes) / len(volumes):
        patterns.append("High volume spike")

    open = candles[0]["open"]
    close = candles[0]["close"]
    previous_open = candles[1]["open"]
    previous_close = candles[1]["close"]

    # Bearish
    if (open > close and
            previous_open < previous_close and
            close < previous_open and
            open >= previous_close):
        patterns.append("Bearish pattern")

    # Bullish
    elif (open < close and
          previous_open > previous_close and
          close > previous_open and
          open <= previous_close):
        patterns.append("Bullish pattern")

    return {
        "trend": trend,
        "patterns": patterns
    }


def engulfing_signal(candles):

    last_candle = candles[0]
    prev_candle = candles[1]

    #Bullish Engulfing Signal
    if (last_candle["close"] > last_candle["open"] and
        prev_candle["close"] < prev_candle["open"] and
        last_candle["open"] < prev_candle["close"] and
        last_candle["close"] > prev_candle["open"] and
        last_candle["close"] > last_candle["low"] and
        last_candle["close"] < last_candle["high"]
    ):
        return 2  #Buy

    #Bearish Engulfing Signal
    elif (last_candle["close"] < last_candle["open"] and
          prev_candle["close"] > prev_candle["open"] and
          last_candle["open"] > prev_candle["close"] and
          last_candle["close"] < prev_candle["open"] and
          last_candle["close"] < last_candle["high"] and
          last_candle["close"] > last_candle["low"]
    ):
        return 1  #Sell

    return 0

def doji_signal(candles):

    last_candle = candles[0]
    prev_candle = candles[1]
    prev_prev_candle = candles[2]

    # Bullish Signal
    if (last_candle["close"] > last_candle["low"] and
        last_candle["close"] < last_candle["high"] + last_candle["low"] / 2 and
        last_candle["close"] > last_candle["open"] and
        prev_candle["close"] == prev_candle["open"] and
        prev_prev_candle["close"] < prev_prev_candle["open"]):
        return 2 #Buy

    # Bearish Signal
    elif (last_candle["close"] < last_candle["high"] and
          last_candle["close"] > last_candle["high"] + last_candle["low"] / 2 and
          last_candle["close"] < last_candle["open"] and
          prev_candle["close"] == prev_candle["open"] and
          prev_prev_candle["close"] > prev_prev_candle["open"]):
        return 1 #Sell

    # No Signal
    return 0


def signal_generator(candles):
    open = candles[0]["open"]
    close = candles[0]["close"]
    previous_open = candles[1]["open"]
    previous_close = candles[1]["close"]

    # Bearish
    if (open > close and
            previous_open < previous_close and
            close < previous_open and
            open >= previous_close):
        return 1 #sell

    # Bullish
    elif (open < close and
          previous_open > previous_close and
          close > previous_open and
          open <= previous_close):
        return 2 #buy
    else:
        return 0



def process_all_stocks():
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    query = "SELECT symbol FROM stock"
    cursor.execute(query)

    symbols = [row["symbol"] for row in cursor.fetchall()]

    for symbol in symbols:
        buy_or_sell(symbol)

    connection.close()

def buy_or_sell(symbol):
    candles = get_candles(symbol)
    if len(candles) >= 3:
        doji = doji_signal(candles)
        engulfing = engulfing_signal(candles)
        if doji == 1 or engulfing == 1:
            return "Sell!"
        if doji == 2 or engulfing == 2:
            return "Buy!"
        else:
            return "Unpredictable Market!"
