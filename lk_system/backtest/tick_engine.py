import pandas as pd
import numpy as np
import os
import sys
import joblib
import sys
sys.path.append('d:/FOREX/FOREX')
from lk_system.core.market_structure import MarketStructure
from lk_system.core.session_manager import SessionManager
from lk_system.core.imbalance import ImbalanceDetector
from lk_system.core.market_conditions import AdvancedConditionCalculator
from lk_system.core.session_analyzer import DynamicSessionAnalyzer
try:
    from lk_system.core.optimal_windows import OPTIMAL_WINDOWS
except ImportError:
    OPTIMAL_WINDOWS = {}

class TickBacktestEngine:
    def __init__(self, execution_mode='MARKET_CONFIRMATION', target_sessions=None, pair_name='EURUSD', use_ml_filter=False, use_amcc=True, partial_ratio=0.3):
        """
        execution_mode: 'LIMIT' or 'MARKET_CONFIRMATION'
        target_sessions: List of sessions to trade (e.g., ['London', 'NY'] or ['Asia', 'London'])
        """
        self.execution_mode = execution_mode
        self.target_sessions = target_sessions or ['Asia', 'London', 'NY']
        self.pair_name = pair_name
        self.use_ml_filter = use_ml_filter
        self.use_amcc = use_amcc
        self.allowed_days = None
        self.ml_model = None
        
        if self.use_ml_filter and self.pair_name:
            self.load_ml_model()
            
        self.capital = 5000.0
        self.initial_capital = 5000.0
        self.risk_per_trade = 0.0115
        
        self.rr_ratio = 6.0
        self.breakeven_rr = 3.0
        self.partial_ratio = partial_ratio
        
        self.awaiting_short_fvg = False
        self.awaiting_short_sl = 0.0
        self.awaiting_short_time = None
        self.awaiting_short_features = None
        
        self.awaiting_long_fvg = False
        self.awaiting_long_sl = 0.0
        self.awaiting_long_time = None
        self.awaiting_long_features = None
        
        self.trades = []
        self.last_traded_session = None
        
        self.market_structure = MarketStructure()
        self.session_manager = SessionManager()
        self.imbalance_detector = ImbalanceDetector()
        self.condition_calculator = AdvancedConditionCalculator()
        self.session_analyzer = DynamicSessionAnalyzer(drop_threshold=0.70)
        
    def load_ml_model(self):
        model_path = os.path.join(r"D:\FOREX\FOREX\qpe\ai\models", f"{self.pair_name}_rf_model.pkl")
        if os.path.exists(model_path):
            self.ml_model = joblib.load(model_path)
            print(f"Loaded ML Brain for {self.pair_name}")
        else:
            print(f"Warning: No ML Brain found for {self.pair_name} at {model_path}")
            self.use_ml_filter = False
            
    def load_and_resample(self, file_path):
        print(f"Loading tick data from {file_path} (reading all rows)...")
        df_ticks = pd.read_csv(file_path, sep='\t')
        
        df_ticks['Datetime'] = pd.to_datetime(df_ticks['<DATE>'] + ' ' + df_ticks['<TIME>'], format='%Y.%m.%d %H:%M:%S.%f')
        df_ticks.set_index('Datetime', inplace=True)
        df_ticks['Price'] = df_ticks['<BID>']
        
        print("Resampling to M1, M5, and M15...")
        df_m1 = df_ticks['Price'].resample('1min').ohlc().dropna()
        df_m5 = df_ticks['Price'].resample('5min').ohlc().dropna()
        df_m15 = df_ticks['Price'].resample('15min').ohlc().dropna()
        
        df_m1.columns = ['Open', 'High', 'Low', 'Close']
        df_m5.columns = ['Open', 'High', 'Low', 'Close']
        df_m15.columns = ['Open', 'High', 'Low', 'Close']
        
        df_m1.index = df_m1.index.tz_localize('UTC').tz_convert('US/Eastern')
        df_m5.index = df_m5.index.tz_localize('UTC').tz_convert('US/Eastern')
        df_m15.index = df_m15.index.tz_localize('UTC').tz_convert('US/Eastern')
        
        return df_m1, df_m5, df_m15

    def run(self, df_m1, df_m5, df_m15, risk_schedule=None):
        print(f"Running Pure Lewis Kelly Video Strategy (Mode: {self.execution_mode})...")
        print(f"Total M15 bars: {len(df_m15)} | Total M1 bars: {len(df_m1)} | Total M5 bars: {len(df_m5)}")
        
        df_m15 = self.session_manager.update(df_m15)
        df_m15 = self.market_structure.update(df_m15)
        
        if self.use_amcc:
            self.condition_calculator.initialize(df_m15)
            self.session_analyzer.initialize(df_m15)
        
        df_m1 = self.market_structure.update(df_m1)
        df_m1 = self.imbalance_detector.detect(df_m1)
        df_m5 = self.imbalance_detector.detect(df_m5)
        
        m15_records = df_m15.to_dict('index')
        m5_records = df_m5.to_dict('index')
        
        active_trade = None
        pending_setup = None
        pending_features = None
        
        for m1_dt, m1_bar in df_m1.iterrows():
            m15_dt = m1_dt.floor('15min')
            if m15_dt not in m15_records:
                continue
                
            m15_bar = m15_records[m15_dt]
            active_session = m15_bar['Active_Session']
            
            # 0. HTF Pair Screener Filter (Daily Trend)
            current_day = m1_dt.floor('1D')
            if self.allowed_days is not None and current_day not in self.allowed_days:
                continue
                
            current_risk = risk_schedule.get(current_day, self.risk_per_trade) if risk_schedule else self.risk_per_trade
            if current_risk <= 0.0:
                continue
            
            # 1. Manage Active Trade
            if active_trade:
                if active_trade['type'] == 'long':
                    current_rr = (m1_bar['High'] - active_trade['entry_price']) / (active_trade['entry_price'] - active_trade['original_sl'])
                    if current_rr >= self.breakeven_rr and active_trade['sl'] < active_trade['entry_price']:
                        active_trade['sl'] = active_trade['entry_price']
                        active_trade['partial_taken'] = True
                        
                    if m1_bar['Low'] <= active_trade['sl']:
                        active_trade['exit_price'] = active_trade['sl']
                        active_trade['exit_time'] = m1_dt
                        if active_trade['sl'] == active_trade['entry_price']:
                            active_trade['pnl'] = (self.capital * current_risk * self.partial_ratio * self.breakeven_rr) if active_trade.get('partial_taken') else 0.0
                        else:
                            active_trade['pnl'] = -self.capital * current_risk
                        self.capital += active_trade['pnl']
                        self.trades.append(active_trade)
                        active_trade = None
                    elif m1_bar['High'] >= active_trade['tp']:
                        active_trade['exit_price'] = active_trade['tp']
                        active_trade['exit_time'] = m1_dt
                        active_trade['pnl'] = self.capital * current_risk * (self.partial_ratio * self.breakeven_rr + (1 - self.partial_ratio) * self.rr_ratio)
                        self.capital += active_trade['pnl']
                        self.trades.append(active_trade)
                        active_trade = None
                        
                elif active_trade['type'] == 'short':
                    current_rr = (active_trade['entry_price'] - m1_bar['Low']) / (active_trade['original_sl'] - active_trade['entry_price'])
                    if current_rr >= self.breakeven_rr and active_trade['sl'] > active_trade['entry_price']:
                        active_trade['sl'] = active_trade['entry_price']
                        active_trade['partial_taken'] = True
                        
                    if m1_bar['High'] >= active_trade['sl']:
                        active_trade['exit_price'] = active_trade['sl']
                        active_trade['exit_time'] = m1_dt
                        if active_trade['sl'] == active_trade['entry_price']:
                            active_trade['pnl'] = (self.capital * current_risk * self.partial_ratio * self.breakeven_rr) if active_trade.get('partial_taken') else 0.0
                        else:
                            active_trade['pnl'] = -self.capital * current_risk
                        self.capital += active_trade['pnl']
                        self.trades.append(active_trade)
                        active_trade = None
                    elif m1_bar['Low'] <= active_trade['tp']:
                        active_trade['exit_price'] = active_trade['tp']
                        active_trade['exit_time'] = m1_dt
                        active_trade['pnl'] = self.capital * current_risk * (self.partial_ratio * self.breakeven_rr + (1 - self.partial_ratio) * self.rr_ratio)
                        self.capital += active_trade['pnl']
                        self.trades.append(active_trade)
                        active_trade = None
                continue
            
            # 2. Check Pending Setup Execution
            if pending_setup:
                if pending_setup == 'Short':
                    if m1_bar['High'] >= pending_ob_low:
                        use_limit = False
                        if self.execution_mode == 'LIMIT':
                            use_limit = True
                                
                        if use_limit:
                            entry = pending_ob_low
                            risk = abs(entry - pending_sl)
                            active_trade = {
                                'type': 'short', 'entry_time': m1_dt, 'entry_price': entry,
                                'original_sl': pending_sl, 'sl': pending_sl, 'tp': entry - (risk * self.rr_ratio),
                                'pnl': 0, 'features': pending_features
                            }
                            self.last_traded_session = m15_bar['Active_Session']
                            pending_setup = None
                        elif self.execution_mode == 'MARKET_CONFIRMATION':
                            if m1_bar['Close'] < m1_bar['Open']:
                                entry = m1_bar['Close']
                                risk = abs(entry - pending_sl)
                                if risk > 0.0001: 
                                    active_trade = {
                                        'type': 'short', 'entry_time': m1_dt, 'entry_price': entry,
                                        'original_sl': pending_sl, 'sl': pending_sl, 'tp': entry - (risk * self.rr_ratio),
                                        'pnl': 0, 'features': pending_features
                                    }
                                    self.last_traded_session = m15_bar['Active_Session']
                                    pending_setup = None
                                
                elif pending_setup == 'Long':
                    if m1_bar['Low'] <= pending_ob_high:
                        use_limit = False
                        if self.execution_mode == 'LIMIT':
                            use_limit = True
                                
                        if use_limit:
                            entry = pending_ob_high
                            risk = abs(entry - pending_sl)
                            active_trade = {
                                'type': 'long', 'entry_time': m1_dt, 'entry_price': entry,
                                'original_sl': pending_sl, 'sl': pending_sl, 'tp': entry + (risk * self.rr_ratio),
                                'pnl': 0, 'features': pending_features
                            }
                            self.last_traded_session = m15_bar['Active_Session']
                            pending_setup = None
                        elif self.execution_mode == 'MARKET_CONFIRMATION':
                            if m1_bar['Close'] > m1_bar['Open']:
                                entry = m1_bar['Close']
                                risk = abs(entry - pending_sl)
                                if risk > 0.0001:
                                    active_trade = {
                                        'type': 'long', 'entry_time': m1_dt, 'entry_price': entry,
                                        'original_sl': pending_sl, 'sl': pending_sl, 'tp': entry + (risk * self.rr_ratio),
                                        'pnl': 0, 'features': pending_features
                                    }
                                    self.last_traded_session = m15_bar['Active_Session']
                                    pending_setup = None
                                
                if pending_setup == 'Short' and m1_bar['High'] > pending_sl:
                    pending_setup = None
                elif pending_setup == 'Long' and m1_bar['Low'] < pending_sl:
                    pending_setup = None
                    
            # 3. Look for New Setups
            active_session = m15_bar['Active_Session']
            if not pending_setup and not active_trade:
                is_in_window = True
                # if self.pair_name in OPTIMAL_WINDOWS:
                #     w_start, w_end = OPTIMAL_WINDOWS[self.pair_name]
                #     h = m1_dt.hour
                #     if w_start <= w_end:
                #         is_in_window = (w_start <= h <= w_end)
                #     else:
                #         is_in_window = (h >= w_start) or (h <= w_end)
                        
                if active_session in self.target_sessions and is_in_window:
                    if self.use_amcc:
                        is_active, ratio, reason = self.session_analyzer.is_session_active(m1_dt, active_session)
                        if not is_active:
                            continue
                            
                    # STRICT GEOGRAPHICAL SWEEPS ONLY (No PDH/PDL bypasses)
                    swept_high = False
                    swept_low = False
                    
                    if active_session == 'London':
                        swept_high = m15_bar['Asia_Swept_High']
                        swept_low = m15_bar['Asia_Swept_Low']
                    elif active_session == 'NY':
                        swept_high = m15_bar['London_Swept_High']
                        swept_low = m15_bar['London_Swept_Low']
                    elif active_session == 'Asia':
                        swept_high = m15_bar['NY_Swept_High']
                        swept_low = m15_bar['NY_Swept_Low']
                                 
                    # 1. Check for Sweep + M1 CHoCH (aligned with M15 Trend)
                    if m15_bar['Trend'] == 'bearish' and swept_high and m1_bar['CHoCH']:
                        self.awaiting_short_fvg = True
                        self.awaiting_short_sl = m1_bar['Active_High']
                        self.awaiting_short_time = m1_dt
                        self.awaiting_short_features = {
                            'session': active_session,
                            'swept_high': swept_high,
                            'amcc_bearish_score': self.condition_calculator.bearish_score if hasattr(self.condition_calculator, 'bearish_score') else 0,
                            'hour_of_day': m1_dt.hour,
                            'day_of_week': m1_dt.dayofweek
                        }
                        
                    if m15_bar['Trend'] == 'bullish' and swept_low and m1_bar['CHoCH']:
                        self.awaiting_long_fvg = True
                        self.awaiting_long_sl = m1_bar['Active_Low']
                        self.awaiting_long_time = m1_dt
                        self.awaiting_long_features = {
                            'session': active_session,
                            'swept_low': swept_low,
                            'amcc_bullish_score': self.condition_calculator.bullish_score if hasattr(self.condition_calculator, 'bullish_score') else 0,
                            'hour_of_day': m1_dt.hour,
                            'day_of_week': m1_dt.dayofweek
                        }
                        
                    # 2. Check for M5 FVG Entry within 15 minutes
                    if self.awaiting_short_fvg:
                        if (m1_dt - self.awaiting_short_time).total_seconds() > 900:
                            self.awaiting_short_fvg = False
                        else:
                            m5_dt = m1_dt.floor('5min')
                            prev_m5_dt = m5_dt - pd.Timedelta(minutes=5)
                            prev2_m5_dt = m5_dt - pd.Timedelta(minutes=10)
                            
                            for check_dt in [prev_m5_dt, prev2_m5_dt]:
                                if check_dt in m5_records:
                                    m5_bar = m5_records[check_dt]
                                    if m5_bar.get('Bearish_FVG', False):
                                        pending_setup = 'Short'
                                        pending_ob_high = m5_bar['Bearish_OB_High']
                                        pending_ob_low = m5_bar['Bearish_OB_Low']
                                        pending_sl = self.awaiting_short_sl
                                        pending_features = self.awaiting_short_features
                                        pending_features['fvg_size'] = pending_ob_high - pending_ob_low
                                        self.awaiting_short_fvg = False
                                        
                                        if self.use_amcc:
                                            is_fav, reason, quality = self.condition_calculator.evaluate_condition(m1_dt, 'short', pending_features['fvg_size'])
                                            if not is_fav:
                                                pending_setup = None
                                                pending_features['amcc_reason'] = reason
                                            else:
                                                pending_features['amcc_quality'] = quality
                                        break
                                        
                            if pending_setup == 'Short' and self.use_ml_filter and self.ml_model:
                                session_map = {'Asia': 0, 'London': 1, 'NY': 2}
                                X = pd.DataFrame([{
                                    'session': session_map.get(active_session, 0),
                                    'day_of_week': m1_dt.dayofweek,
                                    'hour': m1_dt.hour,
                                    'setup_type': 0,
                                    'fvg_size': pending_ob_high - pending_ob_low
                                }])
                                probs = self.ml_model.predict_proba(X)[0]
                                if len(probs) > 1 and probs[1] >= 0.5:
                                    pass # Approved
                                else:
                                    pending_setup = None
                            
                    if self.awaiting_long_fvg:
                        if (m1_dt - self.awaiting_long_time).total_seconds() > 900:
                            self.awaiting_long_fvg = False
                        else:
                            m5_dt = m1_dt.floor('5min')
                            prev_m5_dt = m5_dt - pd.Timedelta(minutes=5)
                            prev2_m5_dt = m5_dt - pd.Timedelta(minutes=10)
                            
                            for check_dt in [prev_m5_dt, prev2_m5_dt]:
                                if check_dt in m5_records:
                                    m5_bar = m5_records[check_dt]
                                    if m5_bar.get('Bullish_FVG', False):
                                        pending_setup = 'Long'
                                        pending_ob_high = m5_bar['Bullish_OB_High']
                                        pending_ob_low = m5_bar['Bullish_OB_Low']
                                        pending_sl = self.awaiting_long_sl
                                        pending_features = self.awaiting_long_features
                                        pending_features['fvg_size'] = pending_ob_high - pending_ob_low
                                        self.awaiting_long_fvg = False
                                        
                                        if self.use_amcc:
                                            is_fav, reason, quality = self.condition_calculator.evaluate_condition(m1_dt, 'long', pending_features['fvg_size'])
                                            if not is_fav:
                                                pending_setup = None
                                                pending_features['amcc_reason'] = reason
                                            else:
                                                pending_features['amcc_quality'] = quality
                                        break
                                        
                            if pending_setup == 'Long' and self.use_ml_filter and self.ml_model:
                                session_map = {'Asia': 0, 'London': 1, 'NY': 2}
                                X = pd.DataFrame([{
                                    'session': session_map.get(active_session, 0),
                                    'day_of_week': m1_dt.dayofweek,
                                    'hour': m1_dt.hour,
                                    'setup_type': 1,
                                    'fvg_size': pending_ob_high - pending_ob_low
                                }])
                                probs = self.ml_model.predict_proba(X)[0]
                                if len(probs) > 1 and probs[1] >= 0.5:
                                    pass # Approved
                                else:
                                    pending_setup = None
                            
        self.stats = self._calculate_stats()
        self._print_report()
        
    def _calculate_stats(self):
        total_trades = len(self.trades)
        if total_trades == 0:
            return {'Total Trades': 0, 'Win Rate': 0.0, 'Net Profit': 0.0, 'trades': []}
            
        wins = sum(1 for t in self.trades if t['pnl'] > 0)
        win_rate = (wins / total_trades) * 100
        total_pnl = sum(t['pnl'] for t in self.trades)
        profit_pct = (total_pnl / self.initial_capital) * 100
        
        return {'Total Trades': total_trades, 'Win Rate': win_rate, 'Net Profit': profit_pct, 'trades': self.trades}
        
    def _print_report(self):
        print(f"\n--- Pure Lewis Kelly Engine ({self.execution_mode}) [{'-'.join(self.target_sessions)}] ---")
        total_trades = len(self.trades)
        if total_trades == 0:
            print("No trades executed.")
            return
            
        wins = sum(1 for t in self.trades if t['pnl'] > 0)
        win_rate = (wins / total_trades) * 100
        total_pnl = sum(t['pnl'] for t in self.trades)
        
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Starting Capital: ${self.initial_capital:.2f}")
        print(f"Ending Capital: ${self.capital:.2f}")
        print(f"Total Net Profit: ${total_pnl:.2f} ({total_pnl/self.initial_capital * 100:.2f}%)")
        print("----------------------------------------------------------------------")
