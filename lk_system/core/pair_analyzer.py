import pandas as pd
import numpy as np
from scipy.stats import linregress
from scipy.signal import argrelextrema

class DynamicPairAnalyzer:
    def __init__(self, top_n=4):
        """
        Advanced Dynamic Pair Analyzer.
        Mathematically scores pairs based on Trend Cleanliness (R-squared) and Structure.
        """
        self.top_n = top_n
        self.lookback = 20 # 20 days of data for regression
        self.min_adr = 0.003 # Absolute minimum % move per day required

    def calculate_atr(self, df, window=14):
        """Calculates Average True Range (ATR)"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=window).mean()

    def analyze_structure(self, df):
        """
        Analyzes the Daily structure for cleanly alternating highs and lows.
        Returns a Structure Score multiplier.
        """
        close_prices = df['Close'].values
        # Find local maxima and minima over a small window
        highs = argrelextrema(close_prices, np.greater, order=2)[0]
        lows = argrelextrema(close_prices, np.less, order=2)[0]
        
        if len(highs) < 2 or len(lows) < 2:
            return 1.0 # Not enough structure to penalize
            
        # Extract the price of the last 2 highs and lows
        h1, h2 = close_prices[highs[-2]], close_prices[highs[-1]]
        l1, l2 = close_prices[lows[-2]], close_prices[lows[-1]]
        
        # Trend check
        uptrend = (h2 > h1) and (l2 > l1)
        downtrend = (h2 < h1) and (l2 < l1)
        
        # Choppy/Ranging (Expanding cone or sweeping both sides)
        expanding = (h2 > h1) and (l2 < l1)
        contracting = (h2 < h1) and (l2 > l1)
        
        if uptrend or downtrend:
            return 1.2 # Bonus for clean consecutive structure
        elif expanding or contracting:
            return 0.5 # Massive penalty for sweeping both sides / ranging
        else:
            return 0.8 # Slight penalty for mixed structure

    def rank_pairs(self, pair_data_dict):
        """
        Ranks pairs based on R-Squared Trend Cleanliness and Minimum Volatility.
        """
        scores = {}
        
        for pair, df in pair_data_dict.items():
            if len(df) < self.lookback:
                continue
                
            recent_df = df.iloc[-self.lookback:]
            closes = recent_df['Close'].values
            
            # 1. Trend Cleanliness (R-Squared)
            x = np.arange(len(closes))
            slope, intercept, r_value, p_value, std_err = linregress(x, closes)
            r_squared = r_value ** 2
            
            # 2. Volatility Floor (Is the pair completely dead?)
            atr = self.calculate_atr(df, 14).iloc[-1]
            current_price = df['Close'].iloc[-1]
            relative_adr = (atr / current_price)
            
            if relative_adr < self.min_adr:
                # Pair is mathematically dead (e.g. August flatline). Disqualify it.
                r_squared = 0 
                
            # 3. Structure Consistency
            structure_multiplier = self.analyze_structure(recent_df)
            
            # 4. Total Score
            # R-squared is the primary metric. Multiply by structure bonus/penalty.
            # Add a tiny fraction of slope magnitude to break ties
            slope_magnitude = abs(slope) / current_price * 100
            
            total_score = (r_squared * structure_multiplier * 100) + (slope_magnitude * 0.1)
            
            scores[pair] = {
                'total_score': total_score,
                'r_squared': r_squared,
                'structure_mult': structure_multiplier,
                'relative_adr': relative_adr * 100
            }
            
        ranked_pairs = sorted(scores.items(), key=lambda x: x[1]['total_score'], reverse=True)
        top_pairs = [p[0] for p in ranked_pairs[:self.top_n]]
        
        return top_pairs, scores
