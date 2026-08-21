"""
Live Bot V2 - Production Ready
==========================
This script replicates the EXACT logic from tick_engine.py for live trading.
"""
import sys
import os
import json
import time
import datetime
import pytz
import MetaTrader5 as mt5

# --- Dynamic Project Resolution ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

CONFIG_PATH = os.path.join(CURRENT_DIR, "config.json")
LOG_DIR = os.path.join(CURRENT_DIR, "logs")

class TeeLogger(object):
    def __init__(self, filename="bot_log"):
        self.terminal = sys.stdout
        os.makedirs(LOG_DIR, exist_ok=True)
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        log_path = os.path.join(LOG_DIR, f"{filename}_{today_str}.txt")
        self.log = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        # Ignore the spinner text so the log file stays clean
        if '\r' not in message and "Waiting for next minute" not in message:
            self.log.write(message)
            self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = TeeLogger()

from lk_system.live.mt5_bridge import MT5Bridge
from lk_system.live.risk_manager import PortfolioRiskManager
from lk_system.live.notifier import TradeNotifier
from lk_system.live.news_manager import NewsManager
from lk_system.core.session_manager import SessionManager
from lk_system.core.market_structure import MarketStructure
from lk_system.core.imbalance import ImbalanceDetector
from lk_system.core.market_conditions import AdvancedConditionCalculator
from lk_system.core.session_analyzer import DynamicSessionAnalyzer

# ─── Configuration ───────────────────────────────────────────────────────
PAIRS = ['AUDCAD', 'CHFJPY', 'EURJPY', 'EURUSD', 'USTEC']
MAGIC_NUMBER = 999111
RR_RATIO = 6.0
BREAKEVEN_RR = 3.0
PARTIAL_RATIO = 0.15

# ─── Live Bot V2 ─────────────────────────────────────────────────────────
class LiveBotV2:
    def __init__(self, daily_losses, circuit_breaker_percent, risk_percent, mt5_path):
        self.bridge = MT5Bridge(magic_number=MAGIC_NUMBER, warmup_days=7, mt5_path=mt5_path)
        self.risk_percent = risk_percent
        self.risk_manager = PortfolioRiskManager(
            magic_number=MAGIC_NUMBER, 
            max_daily_losses=daily_losses, 
            risk_percent_per_trade=self.risk_percent,
            circuit_breaker_percent=circuit_breaker_percent
        )
        self.eastern = pytz.timezone("US/Eastern")
        self.notifier = TradeNotifier(config_path=CONFIG_PATH)
        self.news_manager = NewsManager(cache_dir=LOG_DIR, embargo_minutes=15)
        self.tracked_positions = {}  # ticket -> {pair, entry, sl, tp, bias}
        self.current_global_session = None
        
        # Core SMC components — one per pair (same as backtest)
        self.session_managers = {p: SessionManager() for p in PAIRS}
        self.structure_analyzers_m15 = {p: MarketStructure() for p in PAIRS}
        self.structure_analyzers_m1 = {p: MarketStructure() for p in PAIRS}
        self.imbalance_detectors_m1 = {p: ImbalanceDetector() for p in PAIRS}
        self.imbalance_detectors_m5 = {p: ImbalanceDetector() for p in PAIRS}
        self.condition_calculators = {p: AdvancedConditionCalculator() for p in PAIRS}
        self.session_analyzers = {p: DynamicSessionAnalyzer(drop_threshold=0.70) for p in PAIRS}
        
        # State tracking per pair — exactly mirrors tick_engine.py
        self.state = {}
        for p in PAIRS:
            self.state[p] = {
                'awaiting_short_fvg': False,
                'awaiting_short_sl': 0.0,
                'awaiting_short_time': None,
                'awaiting_short_features': None,
                'awaiting_long_fvg': False,
                'awaiting_long_sl': 0.0,
                'awaiting_long_time': None,
                'awaiting_long_features': None,
                'pending_setup': None,
                'pending_ob_high': 0.0,
                'pending_ob_low': 0.0,
                'pending_sl': 0.0,
                'pending_features': None,
                'news_blocked': False
            }
        
        self.last_run_minute = -1
        self.initialized = False
        
    def startup(self):
        """Connect to MT5 and warm up the tick cache."""
        if not self.bridge.connect():
            return False
            
        self.bridge.warm_up(PAIRS)
        
        print("[INIT] Initializing core analyzers with full history...")
        startup_msg = "🟢 <b>LK SMC LIVE BOT V2 - STARTED</b>\n\n<b>Analyzers Initialized:</b>\n"
        
        for pair in PAIRS:
            df_m15 = self.bridge.get_rates(pair, 'M15', 2000)
            if df_m15 is None:
                print(f"  WARNING: No M15 data for {pair}")
                continue
                
            df_m15 = self.session_managers[pair].update(df_m15)
            df_m15 = self.structure_analyzers_m15[pair].update(df_m15)
            
            self.condition_calculators[pair].initialize(df_m15)
            self.session_analyzers[pair].initialize(df_m15)
            
            print(f"  {pair}: {len(df_m15)} M15 bars loaded")
            startup_msg += f"• {pair}: {len(df_m15)} bars\n"
            
        self.initialized = True
        print("[INIT] All analyzers initialized.\n")
        
        startup_msg += f"\n<b>Rules Active:</b>\n• Daily Loss Limit: {self.risk_manager.max_daily_losses}\n• Risk Per Trade: {self.risk_percent}%\n• Circuit Breaker: {self.risk_manager.circuit_breaker_percent}%"
        self.notifier.send_message(startup_msg)
        return True
        
    def run(self):
        """Main loop — runs every minute on candle close."""
        if not self.startup():
            return
            
        print("=" * 60)
        print("    LK SMC LIVE BOT V2 - PRODUCTION")
        print(f"    Monitoring: {PAIRS}")
        print("=" * 60)
        
        try:
            spinner = ['|', '/', '-', '\\']
            spin_idx = 0
            
            while True:
                now = datetime.datetime.now(self.eastern)
                current_minute = now.minute
                
                if current_minute != self.last_run_minute:
                    self.last_run_minute = current_minute
                    sys.stdout.write('\r' + ' ' * 80 + '\r')
                    sys.stdout.flush()
                    print(f"\n[{now.strftime('%H:%M:%S')}] -- M1 Candle Close --")
                    self.on_minute_close()
                else:
                    sys.stdout.write(f'\rWaiting for next minute... {spinner[spin_idx]}')
                    sys.stdout.flush()
                    spin_idx = (spin_idx + 1) % len(spinner)
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            self.bridge.shutdown()
            
    def on_minute_close(self):
        """Process all pairs on each M1 candle close."""
        if not self.risk_manager.check_circuit_breaker():
            return # Circuit breaker triggered
            
        # ─── Global Session Notification Tracker ───
        df_sess = self.bridge.get_rates('EURUSD', 'M15', 50)
        if df_sess is not None:
            df_sess = self.session_managers['EURUSD'].update(df_sess)
            active_session = df_sess.iloc[-1].get('Active_Session', 'None')
            if active_session != self.current_global_session:
                if self.current_global_session is not None:
                    if active_session == 'None':
                        current_h = now.hour
                        if 5 <= current_h < 7:
                            msg = "☕ <b>London Lunch / Pre-NY Gap</b> (05:00 - 07:00 ET)"
                        elif 10 <= current_h < 20:
                            msg = "🌙 <b>Post-NY / Asian Pre-Market</b> (10:00 - 20:00 ET)"
                        else:
                            msg = "💤 <b>Outside Killzones</b>"
                    else:
                        msg = f"🌍 <b>Session Open: {active_session}</b>\nTransitioned from {self.current_global_session}"
                    self.notifier.send_message(msg)
                    print(f"\n[NOTIFY] Session Shift: {self.current_global_session} -> {active_session}")
                self.current_global_session = active_session
        # ───────────────────────────────────────────
            
        open_positions = self.bridge.get_open_positions()
        
        # ─── Tracker Logic for Closed Positions (TP/SL) ───
        open_tickets = {p['ticket'] for p in open_positions}
        closed_tickets = []
        for ticket, data in self.tracked_positions.items():
            if ticket not in open_tickets:
                # Trade closed!
                closed_tickets.append(ticket)
                # Fetch history to see how it closed
                hist = mt5.history_deals_get(position=ticket)
                if hist:
                    close_deal = hist[-1]
                    profit = close_deal.profit
                    pnl_str = f"🟢 WIN (+${profit:.2f})" if profit > 0 else f"🔴 LOSS (${profit:.2f})"
                    msg = f"<b>{data['pair']}</b> Trade Closed!\n{pnl_str}\nBias: {data['bias']}"
                    self.notifier.send_message(msg)
                    print(f"\n[NOTIFY] Trade {ticket} Closed: {profit:.2f}")
                else:
                    self.notifier.send_message(f"<b>{data['pair']}</b> Trade {ticket} Closed!")
                    
        for t in closed_tickets:
            del self.tracked_positions[t]
        # ──────────────────────────────────────────────────
        
        for pair in PAIRS:
            self.bridge.update_cache(pair)
            
            pair_positions = [p for p in open_positions if p['symbol'] == pair]
            if len(pair_positions) > 0:
                self.manage_positions(pair, pair_positions)
                continue
            
            df_m15 = self.bridge.get_rates(pair, 'M15', 500)
            df_m5 = self.bridge.get_rates(pair, 'M5', 500)
            df_m1 = self.bridge.get_rates(pair, 'M1', 1000)
            
            if df_m15 is None or df_m5 is None or df_m1 is None:
                continue
                
            df_m15 = self.session_managers[pair].update(df_m15)
            df_m15 = self.structure_analyzers_m15[pair].update(df_m15)
            
            self.condition_calculators[pair].initialize(df_m15)
            self.session_analyzers[pair].initialize(df_m15)
            
            df_m1 = self.structure_analyzers_m1[pair].update(df_m1)
            df_m1 = self.imbalance_detectors_m1[pair].detect(df_m1)
            df_m5 = self.imbalance_detectors_m5[pair].detect(df_m5)
            
            m15_bar = df_m15.iloc[-1]
            m1_bar = df_m1.iloc[-1]
            m1_dt = df_m1.index[-1]
            
            # --- Detailed Logging ---
            active_session = m15_bar.get('Active_Session', 'None')
            bias = m15_bar.get('Trend', 'none')
            choch_status = "YES" if m1_bar.get('CHoCH', False) else "NO"
            print(f"  [{pair}] Trend: {bias.upper():<7} | Active: {active_session:<6} | M1 CHoCH: {choch_status}")
            # ------------------------
            
            if active_session not in ['Asia', 'London', 'NY']:
                continue
            
            is_active, ratio, reason = self.session_analyzers[pair].is_session_active(m1_dt, active_session)
            if not is_active:
                print(f"  [{pair}] {active_session} DEAD ({reason})")
                continue
            
            
            st = self.state[pair]
            
            # --- News Check ---
            is_embargo, news_reason = self.news_manager.is_news_embargo(pair, m1_dt)
            if is_embargo:
                if not st['news_blocked']:
                    msg = f"🚫 <b>NEWS BLOCK: {pair}</b>\n{news_reason}\nTrading paused (15m before/after)."
                    self.notifier.send_message(msg)
                    print(f"  [{pair}] [NEWS BLOCK] {news_reason}")
                    st['news_blocked'] = True
                    st['pending_setup'] = None
                    st['awaiting_short_fvg'] = False
                    st['awaiting_long_fvg'] = False
                continue
            else:
                if st['news_blocked']:
                    print(f"  [{pair}] News embargo lifted. Resuming normal operations.")
                    st['news_blocked'] = False
            # ------------------
            
            if st['pending_setup']:
                self._check_pending_execution(pair, m1_bar, m1_dt, m15_bar, df_m5)
                continue
            
            if bias == 'none':
                continue
                
            swept_high = False
            swept_low = False
            
            if active_session == 'London':
                swept_high = m15_bar.get('Asia_Swept_High', False)
                swept_low = m15_bar.get('Asia_Swept_Low', False)
            elif active_session == 'NY':
                swept_high = m15_bar.get('London_Swept_High', False)
                swept_low = m15_bar.get('London_Swept_Low', False)
            elif active_session == 'Asia':
                swept_high = m15_bar.get('NY_Swept_High', False)
                swept_low = m15_bar.get('NY_Swept_Low', False)
            
            if bias == 'bearish' and swept_high and m1_bar.get('CHoCH', False):
                st['awaiting_short_fvg'] = True
                st['awaiting_short_sl'] = m1_bar.get('Active_High', 0)
                st['awaiting_short_time'] = m1_dt
                st['awaiting_short_features'] = {
                    'session': active_session,
                    'swept_high': swept_high,
                    'hour_of_day': m1_dt.hour,
                    'day_of_week': m1_dt.dayofweek
                }
                print(f"  [{pair}] >> BEARISH CHoCH detected in {active_session}! Awaiting M5 FVG...")
                
            if bias == 'bullish' and swept_low and m1_bar.get('CHoCH', False):
                st['awaiting_long_fvg'] = True
                st['awaiting_long_sl'] = m1_bar.get('Active_Low', 0)
                st['awaiting_long_time'] = m1_dt
                st['awaiting_long_features'] = {
                    'session': active_session,
                    'swept_low': swept_low,
                    'hour_of_day': m1_dt.hour,
                    'day_of_week': m1_dt.dayofweek
                }
                print(f"  [{pair}] >> BULLISH CHoCH detected in {active_session}! Awaiting M5 FVG...")
            
            import pandas as pd
            m5_records = df_m5.to_dict('index')
            
            if st['awaiting_short_fvg']:
                if (m1_dt - st['awaiting_short_time']).total_seconds() > 900:
                    st['awaiting_short_fvg'] = False
                    print(f"  [{pair}] Bearish CHoCH expired (>15 min)")
                else:
                    m5_dt = m1_dt.floor('5min')
                    prev_m5 = m5_dt - pd.Timedelta(minutes=5)
                    prev2_m5 = m5_dt - pd.Timedelta(minutes=10)
                    
                    for check_dt in [prev_m5, prev2_m5]:
                        if check_dt in m5_records:
                            m5_bar = m5_records[check_dt]
                            if m5_bar.get('Bearish_FVG', False):
                                st['pending_setup'] = 'Short'
                                st['pending_ob_high'] = m5_bar['Bearish_OB_High']
                                st['pending_ob_low'] = m5_bar['Bearish_OB_Low']
                                st['pending_sl'] = st['awaiting_short_sl']
                                st['pending_features'] = st['awaiting_short_features']
                                st['pending_features']['fvg_size'] = st['pending_ob_high'] - st['pending_ob_low']
                                st['awaiting_short_fvg'] = False
                                
                                is_fav, amcc_reason, quality = self.condition_calculators[pair].evaluate_condition(
                                    m1_dt, 'short', st['pending_features']['fvg_size']
                                )
                                if not is_fav:
                                    msg = f"[{pair}] [X] AMCC blocked SHORT: {amcc_reason}"
                                    print(f"  {msg}")
                                    self.notifier.send_message(msg)
                                    st['pending_setup'] = None
                                else:
                                    st['pending_features']['amcc_quality'] = quality
                                    msg = f"[{pair}] [OK] SHORT pending! {amcc_reason} | OB: {st['pending_ob_low']:.5f}-{st['pending_ob_high']:.5f}, SL: {st['pending_sl']:.5f}"
                                    print(f"  {msg}")
                                    self.notifier.send_message(msg)
                                break
                                
            if st['awaiting_long_fvg']:
                if (m1_dt - st['awaiting_long_time']).total_seconds() > 900:
                    st['awaiting_long_fvg'] = False
                    print(f"  [{pair}] Bullish CHoCH expired (>15 min)")
                else:
                    m5_dt = m1_dt.floor('5min')
                    prev_m5 = m5_dt - pd.Timedelta(minutes=5)
                    prev2_m5 = m5_dt - pd.Timedelta(minutes=10)
                    
                    for check_dt in [prev_m5, prev2_m5]:
                        if check_dt in m5_records:
                            m5_bar = m5_records[check_dt]
                            if m5_bar.get('Bullish_FVG', False):
                                st['pending_setup'] = 'Long'
                                st['pending_ob_high'] = m5_bar['Bullish_OB_High']
                                st['pending_ob_low'] = m5_bar['Bullish_OB_Low']
                                st['pending_sl'] = st['awaiting_long_sl']
                                st['pending_features'] = st['awaiting_long_features']
                                st['pending_features']['fvg_size'] = st['pending_ob_high'] - st['pending_ob_low']
                                st['awaiting_long_fvg'] = False
                                
                                is_fav, amcc_reason, quality = self.condition_calculators[pair].evaluate_condition(
                                    m1_dt, 'long', st['pending_features']['fvg_size']
                                )
                                if not is_fav:
                                    msg = f"[{pair}] [X] AMCC blocked LONG: {amcc_reason}"
                                    print(f"  {msg}")
                                    self.notifier.send_message(msg)
                                    st['pending_setup'] = None
                                else:
                                    st['pending_features']['amcc_quality'] = quality
                                    msg = f"[{pair}] [OK] LONG pending! {amcc_reason} | OB: {st['pending_ob_low']:.5f}-{st['pending_ob_high']:.5f}, SL: {st['pending_sl']:.5f}"
                                    print(f"  {msg}")
                                    self.notifier.send_message(msg)
                                break
    
    def _check_pending_execution(self, pair, m1_bar, m1_dt, m15_bar, df_m5):
        st = self.state[pair]
        
        if st['pending_setup'] == 'Short':
            if m1_bar['High'] >= st['pending_ob_low']:
                if m1_bar['Close'] < m1_bar['Open']:
                    entry = m1_bar['Close']
                    risk = abs(entry - st['pending_sl'])
                    if risk > 0.0001:
                        tp = entry - (risk * RR_RATIO)
                        msg = f"<b>{pair}</b> >>> EXECUTING SHORT @ {entry:.5f}\nSL: {st['pending_sl']:.5f} | TP: {tp:.5f}\nRisk: {risk:.5f}"
                        print(f"  {msg.replace('<b>', '').replace('</b>', '')}")
                        self.notifier.send_message(msg)
                        
                        lot = self.bridge.calculate_lot_size(pair, self.risk_percent, st['pending_sl'])
                        res = self.bridge.send_market_order(pair, mt5.ORDER_TYPE_SELL, lot, st['pending_sl'], tp)
                        if res:
                            self.tracked_positions[res.order] = {'pair': pair, 'bias': 'SHORT'}
                            
                        st['pending_setup'] = None
                        return
                        
            if m1_bar['High'] > st['pending_sl']:
                msg = f"[{pair}] [X] SHORT invalidated (price hit SL before entry)"
                print(f"  {msg}")
                self.notifier.send_message(msg)
                st['pending_setup'] = None
                return
                
        elif st['pending_setup'] == 'Long':
            if m1_bar['Low'] <= st['pending_ob_high']:
                if m1_bar['Close'] > m1_bar['Open']:
                    entry = m1_bar['Close']
                    risk = abs(entry - st['pending_sl'])
                    if risk > 0.0001:
                        tp = entry + (risk * RR_RATIO)
                        msg = f"<b>{pair}</b> >>> EXECUTING LONG @ {entry:.5f}\nSL: {st['pending_sl']:.5f} | TP: {tp:.5f}\nRisk: {risk:.5f}"
                        print(f"  {msg.replace('<b>', '').replace('</b>', '')}")
                        self.notifier.send_message(msg)
                        
                        lot = self.bridge.calculate_lot_size(pair, self.risk_percent, st['pending_sl'])
                        res = self.bridge.send_market_order(pair, mt5.ORDER_TYPE_BUY, lot, st['pending_sl'], tp)
                        if res:
                            self.tracked_positions[res.order] = {'pair': pair, 'bias': 'LONG'}
                            
                        st['pending_setup'] = None
                        return
                        
            if m1_bar['Low'] < st['pending_sl']:
                msg = f"[{pair}] [X] LONG invalidated (price hit SL before entry)"
                print(f"  {msg}")
                self.notifier.send_message(msg)
                st['pending_setup'] = None
                return
    
    def manage_positions(self, pair, positions):
        for pos in positions:
            entry_price = pos['price_open']
            current_sl = pos['sl']
            current_tp = pos['tp']
            ticket = pos['ticket']
            volume = pos['volume']
            
            bid, ask = self.bridge.get_live_price(pair)
            if bid is None:
                continue
            
            if pos['type'] == 0:  # BUY position
                current_price = bid
                risk = entry_price - current_sl if current_sl > 0 else 0
                if risk <= 0:
                    continue
                    
                current_rr = (current_price - entry_price) / risk
                
                if current_rr >= BREAKEVEN_RR and current_sl < entry_price:
                    msg = f"<b>{pair}</b> LONG at {current_rr:.1f}R -- Moving SL to breakeven + taking {PARTIAL_RATIO*100:.0f}% partial"
                    print(f"  {msg.replace('<b>', '').replace('</b>', '')}")
                    self.notifier.send_message(msg)
                    
                    self.bridge.modify_sl(ticket, entry_price)
                    partial_vol = round(volume * PARTIAL_RATIO, 2)
                    if partial_vol >= 0.01:
                        self.bridge.close_position(ticket, partial_vol)
                            
            elif pos['type'] == 1:  # SELL position
                current_price = ask
                risk = current_sl - entry_price if current_sl > 0 else 0
                if risk <= 0:
                    continue
                    
                current_rr = (entry_price - current_price) / risk
                
                if current_rr >= BREAKEVEN_RR and current_sl > entry_price:
                    msg = f"<b>{pair}</b> SHORT at {current_rr:.1f}R -- Moving SL to breakeven + taking {PARTIAL_RATIO*100:.0f}% partial"
                    print(f"  {msg.replace('<b>', '').replace('</b>', '')}")
                    self.notifier.send_message(msg)
                    
                    self.bridge.modify_sl(ticket, entry_price)
                    partial_vol = round(volume * PARTIAL_RATIO, 2)
                    if partial_vol >= 0.01:
                        self.bridge.close_position(ticket, partial_vol)


# --- Configuration Loading ---

def load_config():
    default_config = {
        "trading_rules": {
            "mt5_terminal_path": "",
            "max_drawdown_percent": 10.0,
            "max_daily_losses": 2,
            "risk_percent": 1.3
        },
        "notifications": {
            "discord_webhook_url": "",
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
    }
    if not os.path.exists(CONFIG_PATH):
        save_config(default_config)
        return default_config
        
    try:
        with open(CONFIG_PATH, 'r') as f:
            data = json.load(f)
            # Merge with defaults in case of missing keys
            for cat in default_config:
                if cat not in data:
                    data[cat] = default_config[cat]
                else:
                    for key in default_config[cat]:
                        if key not in data[cat]:
                            data[cat][key] = default_config[cat][key]
            return data
    except Exception as e:
        print(f"Error loading config: {e}. Using defaults.")
        return default_config

def save_config(config_data):
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def main_menu():
    while True:
        config = load_config()
        print("\n" + "="*40)
        print("    LK SMC LIVE BOT - MAIN MENU")
        print("="*40)
        print(" [1] Start Live Bot")
        print(" [2] Configure Trading Rules")
        print(" [3] Configure Notifications")
        print(" [4] Exit")
        print("="*40)
        
        choice = input("Select an option (1-4): ").strip()
        
        if choice == '1':
            rules = config.get("trading_rules", {})
            mt5_path = rules.get("mt5_terminal_path", "")
            max_dd = rules.get("max_drawdown_percent", 10.0)
            daily_losses = rules.get("max_daily_losses", 2)
            risk_percent = rules.get("risk_percent", 1.3)
            circuit_breaker = max_dd - 1.0
            
            print(f"\n[STARTING ENGINE]")
            print(f"-> Max Daily Losses: {daily_losses}")
            print(f"-> Risk Per Trade: {risk_percent}%")
            print(f"-> Global Circuit Breaker: {circuit_breaker}%")
            if mt5_path: print(f"-> MT5 Path Override: {mt5_path}")
            print("========================================\n")
            
            bot = LiveBotV2(
                daily_losses=daily_losses, 
                circuit_breaker_percent=circuit_breaker,
                risk_percent=risk_percent,
                mt5_path=mt5_path
            )
            bot.run()
            break  # Exit menu after bot stops
            
        elif choice == '2':
            print("\n--- Configure Trading Rules ---")
            rules = config.get("trading_rules", {})
            try:
                mt5_in = input(f"MT5 terminal64.exe Path (Leave blank to keep current):\n> ")
                if mt5_in.strip(): rules['mt5_terminal_path'] = mt5_in.strip()
                
                max_dd_in = input(f"Account Max Drawdown % [{rules.get('max_drawdown_percent')}]: ")
                if max_dd_in.strip(): rules['max_drawdown_percent'] = float(max_dd_in)
                
                loss_in = input(f"Max Daily Losses [{rules.get('max_daily_losses')}]: ")
                if loss_in.strip(): rules['max_daily_losses'] = int(loss_in)
                
                risk_in = input(f"Risk Percent Per Trade [{rules.get('risk_percent')}]: ")
                if risk_in.strip(): rules['risk_percent'] = float(risk_in)
                
                config['trading_rules'] = rules
                save_config(config)
                print("Trading rules saved!")
            except ValueError:
                print("Invalid input. Please enter numbers only.")
                
        elif choice == '3':
            while True:
                print("\n--- Configure Notifications ---")
                notif = config.get("notifications", {})
                
                d_status = "ON" if notif.get('discord_webhook_url') else "OFF"
                t_status = "ON" if notif.get('telegram_bot_token') and notif.get('telegram_chat_id') else "OFF"
                
                print(f" [1] Setup Discord (Current: {d_status})")
                print(f" [2] Setup Telegram (Current: {t_status})")
                print(f" [3] Clear all Notifications (Turn OFF)")
                print(f" [4] Back to Main Menu")
                
                n_choice = input("Select an option (1-4): ").strip()
                if n_choice == '1':
                    d_url = input(f"Enter new Discord Webhook URL (Leave blank to cancel):\n> ")
                    if d_url.strip(): 
                        notif['discord_webhook_url'] = d_url.strip()
                        config['notifications'] = notif
                        save_config(config)
                        print("Discord Webhook saved!")
                elif n_choice == '2':
                    t_token = input(f"Enter Telegram Bot Token (Leave blank to cancel):\n> ")
                    t_chat = input(f"Enter Telegram Chat ID (Leave blank to cancel):\n> ")
                    if t_token.strip() or t_chat.strip(): 
                        if t_token.strip(): notif['telegram_bot_token'] = t_token.strip()
                        if t_chat.strip(): notif['telegram_chat_id'] = t_chat.strip()
                        config['notifications'] = notif
                        save_config(config)
                        print("Telegram settings saved!")
                elif n_choice == '3':
                    notif['discord_webhook_url'] = ""
                    notif['telegram_bot_token'] = ""
                    notif['telegram_chat_id'] = ""
                    config['notifications'] = notif
                    save_config(config)
                    print("All notifications cleared and disabled!")
                elif n_choice == '4':
                    break
                else:
                    print("Invalid option.")
            
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main_menu()
