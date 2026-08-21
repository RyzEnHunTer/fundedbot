import pandas as pd
import numpy as np

class MarketStructure:
    """
    Identifies true Price Action structural swing points (Valid Pullbacks) and trend direction.
    Uses a standard SMC Fractal Pivot model to map swings purely via price geometry.
    
    A Swing High is confirmed when a candle has a higher high than the N candles before it and N candles after it.
    A Swing Low is confirmed when a candle has a lower low than the N candles before it and N candles after it.
    """
    def __init__(self, pivot_length=2):
        self.pivot_length = pivot_length
        
    def update(self, df):
        df = df.copy()
        
        n = len(df)
        highs = df['High'].values
        lows = df['Low'].values
        closes = df['Close'].values
        
        swing_high = np.zeros(n, dtype=bool)
        swing_low = np.zeros(n, dtype=bool)
        bos = np.zeros(n, dtype=bool)
        choch = np.zeros(n, dtype=bool)
        trend = np.full(n, 'none', dtype=object)
        last_break = np.full(n, 'None', dtype=object)
        
        active_highs_out = np.full(n, np.nan)
        active_lows_out = np.full(n, np.nan)
        
        # 1. Identify all valid Fractal Swings (Length 2)
        pl = self.pivot_length
        for i in range(pl, n - pl):
            # Check Pivot High
            is_high = True
            for j in range(1, pl + 1):
                if highs[i - j] >= highs[i] or highs[i + j] >= highs[i]:
                    is_high = False
                    break
            if is_high:
                swing_high[i] = True
                
            # Check Pivot Low
            is_low = True
            for j in range(1, pl + 1):
                if lows[i - j] <= lows[i] or lows[i + j] <= lows[i]:
                    is_low = False
                    break
            if is_low:
                swing_low[i] = True

        # 2. Map Trend & CHoCH / BoS based on those swings
        current_trend = 'none'
        
        # We will keep an array of active swing levels
        active_high = np.nan
        active_low = np.nan
        current_break = 'None'
        
        for i in range(pl, n):
            c = closes[i]
            
            # Did a swing get confirmed on this bar? (The pivot happened at i - pl)
            if swing_high[i - pl]:
                active_high = highs[i - pl]
            if swing_low[i - pl]:
                active_low = lows[i - pl]
                
            ch = False
            b = False
            
            if current_trend == 'none':
                if c > active_high and active_high != -1.0:
                    current_trend = 'bullish'
                    ch = True
                elif c < active_low and active_low != 999999.0:
                    current_trend = 'bearish'
                    ch = True
            
            elif current_trend == 'bullish':
                if c > active_high:
                    b = True # Break of Structure
                elif c < active_low:
                    current_trend = 'bearish'
                    ch = True # Change of Character
                    
            elif current_trend == 'bearish':
                if c < active_low:
                    b = True # Break of Structure
                elif c > active_high:
                    current_trend = 'bullish'
                    ch = True # Change of Character
                    
            if ch:
                current_break = 'CHoCH'
            elif b:
                current_break = 'BoS'
                
            trend[i] = current_trend
            bos[i] = b
            choch[i] = ch
            last_break[i] = current_break
            active_highs_out[i] = active_high
            active_lows_out[i] = active_low
            
        df['Swing_High'] = swing_high
        df['Swing_Low'] = swing_low
        df['BoS'] = bos
        df['CHoCH'] = choch
        df['Trend'] = trend
        df['Last_Break'] = last_break
        df['Active_High'] = active_highs_out
        df['Active_Low'] = active_lows_out
        
        return df
