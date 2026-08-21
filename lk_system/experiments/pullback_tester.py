import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Create directory if doesn't exist
os.makedirs('d:/FOREX/FOREX/lk_system/experiments', exist_ok=True)

# 1. Fetch Data
print("Fetching EURUSD data...")
df = yf.download("EURUSD=X", period="30d", interval="15m")
if df.empty:
    print("Failed to download data.")
    exit()

# If MultiIndex columns (yfinance sometimes does this), flatten them
if isinstance(df.columns, pd.MultiIndex):
    df.columns = [c[0] for c in df.columns]

# Ensure we have High, Low, Open, Close
df = df[['Open', 'High', 'Low', 'Close']].copy()

# 2. Logic A: Fractal Rule
def detect_fractals(df, window=2):
    df = df.copy()
    df['Fractal_High'] = np.nan
    df['Fractal_Low'] = np.nan
    
    for i in range(window, len(df) - window):
        is_high = True
        is_low = True
        for j in range(1, window + 1):
            if df['High'].iloc[i] <= df['High'].iloc[i-j] or df['High'].iloc[i] <= df['High'].iloc[i+j]:
                is_high = False
            if df['Low'].iloc[i] >= df['Low'].iloc[i-j] or df['Low'].iloc[i] >= df['Low'].iloc[i+j]:
                is_low = False
                
        if is_high:
            df.loc[df.index[i], 'Fractal_High'] = df['High'].iloc[i]
        if is_low:
            df.loc[df.index[i], 'Fractal_Low'] = df['Low'].iloc[i]
            
    return df

# 3. Logic B: Opposing Candle Rule
def detect_opposing_candles(df):
    df = df.copy()
    df['Opposing_High'] = np.nan
    df['Opposing_Low'] = np.nan
    
    state = 'neutral' # 'bullish', 'bearish'
    highest_high = 0
    highest_idx = None
    lowest_low = float('inf')
    lowest_idx = None
    
    for i in range(1, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        is_bullish_candle = curr['Close'] > curr['Open']
        is_bearish_candle = curr['Close'] < curr['Open']
        
        if state == 'neutral':
            if curr['High'] > prev['High']:
                state = 'bullish'
                highest_high = curr['High']
                highest_idx = df.index[i]
            elif curr['Low'] < prev['Low']:
                state = 'bearish'
                lowest_low = curr['Low']
                lowest_idx = df.index[i]
                
        elif state == 'bullish':
            if curr['High'] > highest_high:
                highest_high = curr['High']
                highest_idx = df.index[i]
            
            # Check for reversal (opposing candle breaking previous low)
            if is_bearish_candle and curr['Close'] < prev['Low']:
                df.loc[highest_idx, 'Opposing_High'] = highest_high
                state = 'bearish'
                lowest_low = curr['Low']
                lowest_idx = df.index[i]
                
        elif state == 'bearish':
            if curr['Low'] < lowest_low:
                lowest_low = curr['Low']
                lowest_idx = df.index[i]
                
            # Check for reversal (opposing candle breaking previous high)
            if is_bullish_candle and curr['Close'] > prev['High']:
                df.loc[lowest_idx, 'Opposing_Low'] = lowest_low
                state = 'bullish'
                highest_high = curr['High']
                highest_idx = df.index[i]
                
    return df

# 4. Logic C: ATR-Based Rule
def detect_atr_swings(df, period=14, multiplier=1.5):
    df = df.copy()
    df['ATR_High'] = np.nan
    df['ATR_Low'] = np.nan
    
    # Calculate ATR manually
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(period).mean()
    
    state = 'neutral'
    peak = 0
    peak_idx = None
    trough = float('inf')
    trough_idx = None
    
    for i in range(period, len(df)):
        curr = df.iloc[i]
        atr = curr['ATR']
        if pd.isna(atr): continue
        
        if state == 'neutral':
            state = 'bullish'
            peak = curr['High']
            peak_idx = df.index[i]
            
        elif state == 'bullish':
            if curr['High'] > peak:
                peak = curr['High']
                peak_idx = df.index[i]
            elif peak - curr['Low'] > (atr * multiplier):
                df.loc[peak_idx, 'ATR_High'] = peak
                state = 'bearish'
                trough = curr['Low']
                trough_idx = df.index[i]
                
        elif state == 'bearish':
            if curr['Low'] < trough:
                trough = curr['Low']
                trough_idx = df.index[i]
            elif curr['High'] - trough > (atr * multiplier):
                df.loc[trough_idx, 'ATR_Low'] = trough
                state = 'bullish'
                peak = curr['High']
                peak_idx = df.index[i]
                
    return df

# Apply all three logics
print("Applying algorithms...")
df_frac = detect_fractals(df)
df_opp = detect_opposing_candles(df)
df_atr = detect_atr_swings(df)

# Plotting
print("Generating charts...")
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                    subplot_titles=('Fractal Logic (2-Bar)', 'Opposing Candle Logic', 'ATR Logic (1.5x)'),
                    vertical_spacing=0.05)

# Limit to last 500 candles for better visibility in the browser
plot_idx = df.index[-500:]

for row, df_plot in enumerate([df_frac, df_opp, df_atr], 1):
    sub_df = df_plot.loc[plot_idx]
    
    fig.add_trace(go.Candlestick(x=sub_df.index,
                open=sub_df['Open'], high=sub_df['High'],
                low=sub_df['Low'], close=sub_df['Close'],
                name='EURUSD'), row=row, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=row, col=1)

# Add Fractal markers
sub_frac = df_frac.loc[plot_idx]
fig.add_trace(go.Scatter(x=sub_frac.index, y=sub_frac['Fractal_High'], mode='markers', 
                         marker=dict(symbol='triangle-down', size=12, color='red'), name='Fractal High'), row=1, col=1)
fig.add_trace(go.Scatter(x=sub_frac.index, y=sub_frac['Fractal_Low'], mode='markers', 
                         marker=dict(symbol='triangle-up', size=12, color='blue'), name='Fractal Low'), row=1, col=1)

# Add Opposing markers
sub_opp = df_opp.loc[plot_idx]
fig.add_trace(go.Scatter(x=sub_opp.index, y=sub_opp['Opposing_High'], mode='markers', 
                         marker=dict(symbol='triangle-down', size=12, color='red'), name='Opp High'), row=2, col=1)
fig.add_trace(go.Scatter(x=sub_opp.index, y=sub_opp['Opposing_Low'], mode='markers', 
                         marker=dict(symbol='triangle-up', size=12, color='blue'), name='Opp Low'), row=2, col=1)

# Add ATR markers
sub_atr = df_atr.loc[plot_idx]
fig.add_trace(go.Scatter(x=sub_atr.index, y=sub_atr['ATR_High'], mode='markers', 
                         marker=dict(symbol='triangle-down', size=12, color='red'), name='ATR High'), row=3, col=1)
fig.add_trace(go.Scatter(x=sub_atr.index, y=sub_atr['ATR_Low'], mode='markers', 
                         marker=dict(symbol='triangle-up', size=12, color='blue'), name='ATR Low'), row=3, col=1)

fig.update_layout(height=1200, title_text="Market Structure Mapping Comparison: EURUSD M15",
                  plot_bgcolor='#1e1e1e', paper_bgcolor='#1e1e1e', font=dict(color='white'))

out_path = 'd:/FOREX/FOREX/lk_system/experiments/structure_visualization.html'
fig.write_html(out_path)
print(f"Chart saved to {out_path}")
