import pandas as pd
import numpy as np

class DynamicSessionAnalyzer:
    def __init__(self, short_term_days=5, long_term_days=30, drop_threshold=0.85):
        self.short_term_days = short_term_days
        self.long_term_days = long_term_days
        self.drop_threshold = drop_threshold
        self.session_stats = {}
        
    def initialize(self, df_m15):
        """
        Calculates the historical session ranges from the M15 dataframe.
        df_m15 must be localized to US/Eastern timezone.
        """
        df = df_m15.copy()
        
        # Tag each M15 bar with its session
        df['Session'] = 'None'
        df.loc[(df.index.hour >= 17) | (df.index.hour < 3), 'Session'] = 'Asia'
        df.loc[(df.index.hour >= 3) & (df.index.hour < 8), 'Session'] = 'London'
        df.loc[(df.index.hour >= 8) & (df.index.hour < 17), 'Session'] = 'NY'
        
        # To group by Forex Day (which starts at 17:00 EST), we add 7 hours so the day rolls over at 17:00
        df['Forex_Date'] = (df.index + pd.Timedelta(hours=7)).date
        
        # Calculate max high and min low per session per day
        session_ranges = df.groupby(['Forex_Date', 'Session']).agg({'High': 'max', 'Low': 'min'})
        session_ranges['Range'] = session_ranges['High'] - session_ranges['Low']
        
        session_ranges = session_ranges.reset_index()
        
        # Calculate Rolling Averages for each session
        self.session_stats = {}
        for session in ['Asia', 'London', 'NY']:
            sess_df = session_ranges[session_ranges['Session'] == session].copy()
            sess_df = sess_df.sort_values('Forex_Date')
            sess_df.set_index('Forex_Date', inplace=True)
            
            sess_df['SMA_30'] = sess_df['Range'].rolling(self.long_term_days).mean()
            sess_df['SMA_5'] = sess_df['Range'].rolling(self.short_term_days).mean()
            
            self.session_stats[session] = sess_df
            
    def is_session_active(self, current_time, active_session):
        """
        Evaluates if the active_session is healthy on the given day.
        Returns: (is_active: bool, ratio: float, reason: str)
        """
        if active_session not in self.session_stats:
            return True, 1.0, "UNKNOWN_SESSION"
            
        forex_date = (current_time + pd.Timedelta(hours=7)).date()
        
        stats = self.session_stats[active_session]
        
        # Use previous day's stats to prevent look-ahead bias
        past_stats = stats[stats.index < forex_date]
        
        if past_stats.empty:
            return True, 1.0, "NOT_ENOUGH_DATA"
            
        latest = past_stats.iloc[-1]
        
        sma_30 = latest['SMA_30']
        sma_5 = latest['SMA_5']
        
        if pd.isna(sma_30) or pd.isna(sma_5) or sma_30 == 0:
            return True, 1.0, "WARMUP"
            
        ratio = sma_5 / sma_30
        
        if ratio < self.drop_threshold:
            return False, ratio, f"DEAD_SESSION ({ratio:.2f} < {self.drop_threshold})"
            
        return True, ratio, "HEALTHY"
