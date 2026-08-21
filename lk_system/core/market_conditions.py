import pandas as pd
import numpy as np

class AdvancedConditionCalculator:
    def __init__(self):
        # We need historical M15 and D1 data to calculate the context
        self.df_d1 = None
        self.df_m15 = None
        
    def initialize(self, df_m15):
        """
        Initialize the calculator with the full M15 dataframe.
        Calculates Daily ADR and M15 Average Ranges beforehand for fast lookup.
        """
        self.df_m15 = df_m15.copy()
        
        # Calculate Daily Data (ADR)
        self.df_d1 = df_m15.resample('1D').agg({
            'Open': 'first', 
            'High': 'max', 
            'Low': 'min', 
            'Close': 'last'
        }).dropna()
        
        self.df_d1['ADR_5'] = (self.df_d1['High'] - self.df_d1['Low']).rolling(5).mean()
        
        # Calculate Rolling M15 Range for FVG Conviction (Last 12 bars = 3 hours)
        self.df_m15['Range'] = self.df_m15['High'] - self.df_m15['Low']
        self.df_m15['Avg_Range_12'] = self.df_m15['Range'].rolling(12).mean()

    def evaluate_condition(self, current_time, trade_type, fvg_size_pips=None):
        """
        Evaluates the market condition at the specific current_time.
        Returns (is_favorable: bool, reason: str, quality: int)
        Quality: 1 (Normal), 2 (Perfect)
        """
        if self.df_d1 is None or self.df_m15 is None:
            return True, "NOT_INITIALIZED", 1
            
        m15_time = current_time.floor('15min')
        if m15_time not in self.df_m15.index:
            return True, "NO_M15_DATA", 1
            
        current_day = current_time.floor('1D')
        
        quality = 1
        perfect_fvg = False
        perfect_asian = False
        
        # 1. FVG Displacement Conviction (Most predictive metric)
        if fvg_size_pips is not None:
            avg_m15_range = self.df_m15.loc[m15_time, 'Avg_Range_12']
            if not pd.isna(avg_m15_range) and avg_m15_range > 0:
                fvg_ratio = fvg_size_pips / avg_m15_range
                # Our backtest showed < 0.55 ratio has an 18-23% win rate.
                # > 0.70 ratio is considered extremely strong.
                if fvg_ratio < 0.55:
                    return False, f"WEAK_DISPLACEMENT (Ratio: {fvg_ratio:.2f} < 0.55)", 1
                elif fvg_ratio > 0.70:
                    perfect_fvg = True

        # 2. Volatility State (Asian Range vs ADR)
        if current_day in self.df_d1.index:
            adr = self.df_d1.loc[current_day, 'ADR_5']
            if not pd.isna(adr) and adr > 0:
                # Calculate Asian Range (17:00 to 03:00 EST)
                prev_day_17 = current_day - pd.Timedelta(days=1) + pd.Timedelta(hours=17)
                current_day_03 = current_day + pd.Timedelta(hours=3)
                asian_session = self.df_m15.loc[prev_day_17:current_day_03]
                
                if not asian_session.empty:
                    asian_range = asian_session['High'].max() - asian_session['Low'].min()
                    asian_range_pct = asian_range / adr
                    
                    # Our backtest showed < 0.40 has a 22-25% win rate.
                    # > 0.63 is considered a perfectly expanding market.
                    if asian_range_pct < 0.40:
                        return False, f"DEAD_MARKET (Asian Range {asian_range_pct:.2f} < 0.40 ADR)", 1
                    elif asian_range_pct > 0.60:
                        perfect_asian = True
                        
        if perfect_fvg and perfect_asian:
            quality = 2

        reason_str = "FAVORABLE"
        if fvg_size_pips is not None and not pd.isna(avg_m15_range) and avg_m15_range > 0:
            reason_str += f" (Ratio: {fvg_size_pips / avg_m15_range:.2f})"
        
        if current_day in self.df_d1.index and not pd.isna(adr) and adr > 0 and not asian_session.empty:
            reason_str += f" (AsianVol: {asian_range / adr:.2f})"

        return True, reason_str, quality
