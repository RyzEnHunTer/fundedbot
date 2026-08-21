import pandas as pd
import numpy as np

class ImbalanceDetector:
    """
    Detects Fair Value Gaps (FVG) and their associated Order Blocks (OB).
    Optimized for vector-like execution over huge dataframes.
    """
    def __init__(self):
        pass
        
    def detect(self, df):
        """
        Returns a dataframe with FVG and OB signals.
        """
        highs = df['High'].values
        lows = df['Low'].values
        opens = df['Open'].values
        closes = df['Close'].values
        
        n = len(df)
        bullish_fvg = np.zeros(n, dtype=bool)
        bearish_fvg = np.zeros(n, dtype=bool)
        bullish_ob_high = np.full(n, np.nan)
        bullish_ob_low = np.full(n, np.nan)
        bearish_ob_high = np.full(n, np.nan)
        bearish_ob_low = np.full(n, np.nan)
        
        for i in range(2, n):
            c1_h = highs[i-2]
            c1_l = lows[i-2]
            c3_h = highs[i]
            c3_l = lows[i]
            
            # --- Bullish FVG ---
            if c3_l > c1_h:
                bullish_fvg[i] = True
                
                # Find the Bullish Order Block (the last bearish candle before the push)
                found_ob = False
                for j in range(i-2, max(-1, i-11), -1):
                    if closes[j] < opens[j]:
                        bullish_ob_high[i] = highs[j]
                        bullish_ob_low[i] = lows[j]
                        found_ob = True
                        break
                        
                if not found_ob:
                    bullish_ob_high[i] = c1_h
                    bullish_ob_low[i] = c1_l
                    
            # --- Bearish FVG ---
            elif c3_h < c1_l:
                bearish_fvg[i] = True
                
                # Find the Bearish Order Block (the last bullish candle before the push)
                found_ob = False
                for j in range(i-2, max(-1, i-11), -1):
                    if closes[j] > opens[j]:
                        bearish_ob_high[i] = highs[j]
                        bearish_ob_low[i] = lows[j]
                        found_ob = True
                        break
                        
                if not found_ob:
                    bearish_ob_high[i] = c1_h
                    bearish_ob_low[i] = c1_l

        df['Bullish_FVG'] = bullish_fvg
        df['Bearish_FVG'] = bearish_fvg
        df['Bullish_OB_High'] = bullish_ob_high
        df['Bullish_OB_Low'] = bullish_ob_low
        df['Bearish_OB_High'] = bearish_ob_high
        df['Bearish_OB_Low'] = bearish_ob_low

        return df
