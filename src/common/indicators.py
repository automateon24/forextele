import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).abs())
    adx = dx.rolling(window=period).mean()
    return adx

def calculate_ema(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates the Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Calculates Bollinger Bands (upper, middle, lower)"""
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Average True Range"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price using typical price for the given dataframe (assumed to be a single session or day)"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    # If tick_volume doesn't exist, we fallback to 1 to just be a simple moving average of typical price, but MT5 has tick_volume.
    volume = df['tick_volume'] if 'tick_volume' in df.columns else pd.Series(1, index=df.index)
    
    cumulative_vp = (typical_price * volume).cumsum()
    cumulative_volume = volume.cumsum()
    return cumulative_vp / cumulative_volume

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Calculates Supertrend. Returns DataFrame with 'supertrend' and 'direction' (1 for up, -1 for down)."""
    atr = calculate_atr(df['high'], df['low'], df['close'], period)
    hl2 = (df['high'] + df['low']) / 2
    
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    
    direction = pd.Series(1, index=df.index) # 1 = up, -1 = down
    supertrend = pd.Series(0.0, index=df.index)
    
    for i in range(1, len(df)):
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or df['close'].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
            
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or df['close'].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
            
        if supertrend.iloc[i-1] == final_upper.iloc[i-1] and df['close'].iloc[i] < final_upper.iloc[i]:
            direction.iloc[i] = -1
        elif supertrend.iloc[i-1] == final_upper.iloc[i-1] and df['close'].iloc[i] > final_upper.iloc[i]:
            direction.iloc[i] = 1
        elif supertrend.iloc[i-1] == final_lower.iloc[i-1] and df['close'].iloc[i] > final_lower.iloc[i]:
            direction.iloc[i] = 1
        elif supertrend.iloc[i-1] == final_lower.iloc[i-1] and df['close'].iloc[i] < final_lower.iloc[i]:
            direction.iloc[i] = -1
            
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = final_lower.iloc[i]
        else:
            supertrend.iloc[i] = final_upper.iloc[i]
            
    return pd.DataFrame({'supertrend': supertrend, 'direction': direction}, index=df.index)
