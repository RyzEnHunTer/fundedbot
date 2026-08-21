import pandas as pd
import numpy as np

def compute_fractal_structure(df, left_len=2, right_len=2):
    highs = df['High'].values
    lows = df['Low'].values
    
    n = len(df)
    swing_highs = np.zeros(n, dtype=bool)
    swing_lows = np.zeros(n, dtype=bool)
    
    for i in range(left_len, n - right_len):
        # Check Pivot High
        is_high = True
        for j in range(1, left_len + 1):
            if highs[i - j] >= highs[i]:
                is_high = False
                break
        if is_high:
            for j in range(1, right_len + 1):
                if highs[i + j] >= highs[i]:
                    is_high = False
                    break
        if is_high:
            swing_highs[i] = True
            
        # Check Pivot Low
        is_low = True
        for j in range(1, left_len + 1):
            if lows[i - j] <= lows[i]:
                is_low = False
                break
        if is_low:
            for j in range(1, right_len + 1):
                if lows[i + j] <= lows[i]:
                    is_low = False
                    break
        if is_low:
            swing_lows[i] = True
            
    df['Swing_High'] = swing_highs
    df['Swing_Low'] = swing_lows
    return df

if __name__ == "__main__":
    # Test on a sample chunk of EURUSD
    df = pd.read_csv(r"D:\FOREX\FOREX\candle data\EURUSD_jan to feb ticks.csv", nrows=50000)
    df.columns = ['Time', 'Ask', 'Bid', 'Volume']
    df['Mid'] = (df['Ask'] + df['Bid']) / 2
    df['Time'] = pd.to_datetime(df['Time'], format="%d.%m.%Y %H:%M:%S.%f")
    df.set_index('Time', inplace=True)
    m1 = df['Mid'].resample('1min').ohlc()
    m1.dropna(inplace=True)
    
    # 5-candle fractal (length 2)
    m1_frac2 = compute_fractal_structure(m1.copy(), 2, 2)
    print(f"Total M1 candles: {len(m1_frac2)}")
    print(f"Swing Highs (Length 2): {m1_frac2['Swing_High'].sum()}")
    print(f"Swing Lows (Length 2): {m1_frac2['Swing_Low'].sum()}")
    
    # 3-candle fractal (length 1)
    m1_frac1 = compute_fractal_structure(m1.copy(), 1, 1)
    print(f"Swing Highs (Length 1): {m1_frac1['Swing_High'].sum()}")
    print(f"Swing Lows (Length 1): {m1_frac1['Swing_Low'].sum()}")
    
    # ATR filter for comparison
    def calculate_atr(df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()
    m1['atr'] = calculate_atr(m1)
    print(f"Average M1 ATR: {m1['atr'].mean()}")
