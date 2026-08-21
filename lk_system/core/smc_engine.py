import pandas as pd
from .market_structure import MarketStructure
from .session_manager import SessionManager
from .imbalance import ImbalanceDetector
import numpy as np

class SMCEngine:
    """
    The orchestrator that combines Market Structure, Session Killzones,
    and Imbalances (OB+FVG) to generate execution signals based on Lewis Kelly's models.
    """
    def __init__(self):
        self.market_structure = MarketStructure(atr_period=14, atr_multiplier=1.5)
        self.session_manager = SessionManager()
        self.imbalance_detector = ImbalanceDetector()
        
    def generate_signals(self, df_m15):
        """
        Generates buy/sell signals on M15 (approximating M1 CHoCH for backtesting).
        In a live environment, this would ingest M15 for Bias and M1 for Entry.
        """
        # 1. Update Subsystems
        df = self.session_manager.update(df_m15)
        df = self.market_structure.update(df)
        df = self.imbalance_detector.detect(df)
        
        df['Signal'] = 0  
        df['Setup'] = 'None'
        df['Limit_Entry_Price'] = np.nan
        df['Stop_Loss_Price'] = np.nan
        
        # State Machine Tracking
        pending_setup = None
        pending_ob_high = 0.0
        pending_ob_low = 0.0
        pending_sl = 0.0
        
        for i in range(1, len(df)):
            curr = df.iloc[i]
            
            # 1. Check if we have a Pending Setup waiting for mitigation (pullback)
            if pending_setup == 'Short':
                # Check if price pulls back UP into the Bearish Order Block
                if curr['High'] >= pending_ob_low:
                    df.loc[df.index[i], 'Signal'] = -1
                    df.loc[df.index[i], 'Setup'] = 'Mitigated_Short'
                    df.loc[df.index[i], 'Limit_Entry_Price'] = pending_ob_low
                    df.loc[df.index[i], 'Stop_Loss_Price'] = pending_sl
                    pending_setup = None # Reset after trigger
                    continue # Skip to next candle
            
            elif pending_setup == 'Long':
                # Check if price pulls back DOWN into the Bullish Order Block
                if curr['Low'] <= pending_ob_high:
                    df.loc[df.index[i], 'Signal'] = 1
                    df.loc[df.index[i], 'Setup'] = 'Mitigated_Long'
                    df.loc[df.index[i], 'Limit_Entry_Price'] = pending_ob_high
                    df.loc[df.index[i], 'Stop_Loss_Price'] = pending_sl
                    pending_setup = None # Reset after trigger
                    continue
            
            # 2. If no pending setup, look for new CHoCH + FVG combinations
            # STRATEGY 1 & 2 COMBINED LOGIC:
            if curr['Active_Session'] in ['London', 'NY']:
                
                # Was a previous session high swept? (Liquidity Grab)
                swept_high = (curr['Active_Session'] == 'London' and curr['Asia_Swept_High']) or \
                             (curr['Active_Session'] == 'NY' and curr['London_Swept_High'])
                             
                # Was a previous session low swept? (Liquidity Grab)
                swept_low = (curr['Active_Session'] == 'London' and curr['Asia_Swept_Low']) or \
                            (curr['Active_Session'] == 'NY' and curr['London_Swept_Low'])
                            
                # --- BEARISH SETUP (Short) ---
                if curr['Trend'] == 'bearish' and swept_high and curr['CHoCH']:
                    # We have a structural shift. Now we must have an FVG to confirm the OB
                    if curr['Bearish_FVG']:
                        pending_setup = 'Short'
                        pending_ob_high = curr['Bearish_OB_High']
                        pending_ob_low = curr['Bearish_OB_Low']
                        # SL goes above the swing high that swept liquidity
                        pending_sl = max(curr['Asia_High'], curr['London_High']) if curr['Active_Session'] == 'NY' else curr['Asia_High']
                        
                # --- BULLISH SETUP (Long) ---
                elif curr['Trend'] == 'bullish' and swept_low and curr['CHoCH']:
                    # We have a structural shift. Look for Bullish FVG
                    if curr['Bullish_FVG']:
                        pending_setup = 'Long'
                        pending_ob_high = curr['Bullish_OB_High']
                        pending_ob_low = curr['Bullish_OB_Low']
                        # SL goes below the swing low that swept liquidity
                        pending_sl = min(curr['Asia_Low'], curr['London_Low']) if curr['Active_Session'] == 'NY' else curr['Asia_Low']
                        
        return df
