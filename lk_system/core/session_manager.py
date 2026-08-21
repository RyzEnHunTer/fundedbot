import pandas as pd
import pytz
import numpy as np

class SessionManager:
    """
    Tracks Lewis Kelly's Session Killzones.
    Expects timestamps in US/Eastern timezone.
    
    Killzones (EST):
    - Asia: 20:00 - 00:00 (8 PM - Midnight)
    - London: 02:00 - 05:00 (2 AM - 5 AM)
    - New York: 07:00 - 10:00 (7 AM - 10 AM)
    """
    
    def __init__(self):
        # We store the high/low of each session for the current trading day
        self.daily_sessions = {
            'Asia': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False},
            'London': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False},
            'NY': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False}
        }
        self.previous_ny = {
            'high': 0.0, 'low': float('inf')
        }
        self.daily_high = 0.0
        self.daily_low = float('inf')
        self.pdh = 0.0
        self.pdl = float('inf')
        self.current_date = None

    def _is_asia(self, dt):
        return dt.hour >= 20 or dt.hour == 0

    def _is_london(self, dt):
        return 2 <= dt.hour < 5

    def _is_ny(self, dt):
        return 7 <= dt.hour < 10

    def update(self, df):
        """
        Processes a dataframe and returns a dataframe with Session info.
        Assumes df.index is localized to 'US/Eastern'.
        """
        df = df.copy()
        df['Active_Session'] = 'None'
        df['Asia_High'] = np.nan
        df['Asia_Low'] = np.nan
        df['London_High'] = np.nan
        df['London_Low'] = np.nan
        df['NY_High'] = np.nan
        df['NY_Low'] = np.nan
        df['PDH'] = np.nan
        df['PDL'] = np.nan
        df['PDH_Swept'] = False
        df['PDL_Swept'] = False
        
        for i in range(len(df)):
            dt = df.index[i]
            # Reset daily tracked sessions at 5 PM EST (New York close / Forex new day)
            # Actually, standard Forex day resets at 17:00 EST. 
            current_trade_day = dt.date() if dt.hour < 17 else (dt + pd.Timedelta(days=1)).date()
            
            if self.current_date != current_trade_day:
                self.current_date = current_trade_day
                self.previous_ny = {'high': self.daily_sessions['NY']['high'], 'low': self.daily_sessions['NY']['low']}
                self.pdh = self.daily_high
                self.pdl = self.daily_low
                self.daily_high = 0.0
                self.daily_low = float('inf')
                
                self.daily_sessions = {
                    'Asia': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False},
                    'London': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False},
                    'NY': {'high': 0.0, 'low': float('inf'), 'swept_high': False, 'swept_low': False}
                }

            curr_high = df['High'].iloc[i]
            curr_low = df['Low'].iloc[i]
            
            if curr_high > self.daily_high:
                self.daily_high = curr_high
            if curr_low < self.daily_low:
                self.daily_low = curr_low

            # 1. Update Asia Session
            if self._is_asia(dt):
                df.loc[dt, 'Active_Session'] = 'Asia'
                if curr_high > self.daily_sessions['Asia']['high']:
                    self.daily_sessions['Asia']['high'] = curr_high
                if curr_low < self.daily_sessions['Asia']['low']:
                    self.daily_sessions['Asia']['low'] = curr_low
                    
                # Check for Previous NY Sweeps during Asia
                if curr_high > self.previous_ny['high'] and self.previous_ny['high'] != 0:
                    self.daily_sessions['NY']['swept_high'] = True # Storing NY swept status
                if curr_low < self.previous_ny['low'] and self.previous_ny['low'] != float('inf'):
                    self.daily_sessions['NY']['swept_low'] = True
            
            # 2. Update London Session
            elif self._is_london(dt):
                df.loc[dt, 'Active_Session'] = 'London'
                if curr_high > self.daily_sessions['London']['high']:
                    self.daily_sessions['London']['high'] = curr_high
                if curr_low < self.daily_sessions['London']['low']:
                    self.daily_sessions['London']['low'] = curr_low
                    
                # Check for Asian Sweeps during London
                if curr_high > self.daily_sessions['Asia']['high'] and self.daily_sessions['Asia']['high'] != 0:
                    self.daily_sessions['Asia']['swept_high'] = True
                if curr_low < self.daily_sessions['Asia']['low'] and self.daily_sessions['Asia']['low'] != float('inf'):
                    self.daily_sessions['Asia']['swept_low'] = True

            # 3. Update NY Session
            elif self._is_ny(dt):
                df.loc[dt, 'Active_Session'] = 'NY'
                if curr_high > self.daily_sessions['NY']['high']:
                    self.daily_sessions['NY']['high'] = curr_high
                if curr_low < self.daily_sessions['NY']['low']:
                    self.daily_sessions['NY']['low'] = curr_low
                    
                # Check for London Sweeps during NY
                if curr_high > self.daily_sessions['London']['high'] and self.daily_sessions['London']['high'] != 0:
                    self.daily_sessions['London']['swept_high'] = True
                if curr_low < self.daily_sessions['London']['low'] and self.daily_sessions['London']['low'] != float('inf'):
                    self.daily_sessions['London']['swept_low'] = True

            # Write current session high/low to dataframe so the engine can read it easily
            df.loc[dt, 'Asia_High'] = self.daily_sessions['Asia']['high']
            df.loc[dt, 'Asia_Low'] = self.daily_sessions['Asia']['low']
            df.loc[dt, 'London_High'] = self.daily_sessions['London']['high']
            df.loc[dt, 'London_Low'] = self.daily_sessions['London']['low']
            df.loc[dt, 'NY_High'] = self.previous_ny['high'] if self._is_asia(dt) else self.daily_sessions['NY']['high']
            df.loc[dt, 'NY_Low'] = self.previous_ny['low'] if self._is_asia(dt) else self.daily_sessions['NY']['low']
            df.loc[dt, 'Asia_Swept_High'] = self.daily_sessions['Asia']['swept_high']
            df.loc[dt, 'Asia_Swept_Low'] = self.daily_sessions['Asia']['swept_low']
            df.loc[dt, 'London_Swept_High'] = self.daily_sessions['London']['swept_high']
            df.loc[dt, 'London_Swept_Low'] = self.daily_sessions['London']['swept_low']
            df.loc[dt, 'NY_Swept_High'] = self.daily_sessions['NY']['swept_high']
            df.loc[dt, 'NY_Swept_Low'] = self.daily_sessions['NY']['swept_low']
            
            # PDH/PDL tracking
            df.loc[dt, 'PDH'] = self.pdh
            df.loc[dt, 'PDL'] = self.pdl
            df.loc[dt, 'PDH_Swept'] = True if (curr_high > self.pdh and self.pdh != 0.0) else False
            df.loc[dt, 'PDL_Swept'] = True if (curr_low < self.pdl and self.pdl != float('inf')) else False

        return df
