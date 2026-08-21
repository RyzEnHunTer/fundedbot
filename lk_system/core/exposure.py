import pandas as pd
import numpy as np

class DynamicExposure:
    """
    Calculates dynamic risk exposure based on market conditions (Volatility/ADR).
    """
    def __init__(self, short_window=5, long_window=20, max_risk=0.01, min_risk=0.0):
        self.short_window = short_window
        self.long_window = long_window
        self.max_risk = max_risk
        self.min_risk = min_risk
        
    def calculate_daily_risk(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a daily OHLC dataframe and returns it with a 'Risk_Percent' column.
        """
        df = df_daily.copy()
        
        # Calculate Daily Range (Volatility)
        df['Range'] = df['High'] - df['Low']
        
        # Calculate short-term and long-term ADR (Average Daily Range)
        df['ADR_Short'] = df['Range'].rolling(window=self.short_window).mean()
        df['ADR_Long'] = df['Range'].rolling(window=self.long_window).mean()
        
        # If short-term volatility > long-term volatility, we are in an expansion phase.
        # This provides enough juice for our 1:3 targets to be hit.
        df['Is_Expanding'] = df['ADR_Short'] >= df['ADR_Long']
        
        # Assign risk
        df['Risk_Percent'] = np.where(df['Is_Expanding'], self.max_risk, self.min_risk)
        
        # Shift risk by 1 day to prevent lookahead bias (we trade today based on yesterday's close)
        df['Risk_Percent'] = df['Risk_Percent'].shift(1).fillna(self.min_risk)
        
        return df
