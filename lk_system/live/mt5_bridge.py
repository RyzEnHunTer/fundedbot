"""
MT5 Bridge V2 - Tick Resampling Bridge
=======================================
Replaces broker-provided OHLC candles with pure Bid-tick resampled candles.
Uses a local cache so that only new ticks are fetched each minute.

This file is a TEST version. Once verified, it will replace mt5_bridge.py.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import pytz
import datetime
import time
import sys
import os

class MT5Bridge:
    """
    A bridge that fetches raw ticks from MT5 and resamples them into
    M1/M5/M15 candles using pure Bid prices — exactly matching the backtest engine.
    
    On first call, it fetches N days of tick history (cold start).
    On subsequent calls, it only fetches new ticks since the last fetch (hot path).
    """
    
    def __init__(self, magic_number=999111, warmup_days=7, mt5_path=None):
        self.magic_number = magic_number
        self.warmup_days = warmup_days
        self.mt5_path = mt5_path
        self.utc = pytz.timezone("Etc/UTC")
        self.eastern = pytz.timezone("US/Eastern")
        
        # Cache: symbol -> { 'last_fetch_time': datetime, 'ticks_df': DataFrame }
        self._tick_cache = {}
        
        # Candle cache: symbol -> { 'M1': df, 'M5': df, 'M15': df }
        self._candle_cache = {}
        
    @staticmethod
    def auto_detect_nasdaq(mt5_path=None):
        """Auto-detect the broker's specific Nasdaq symbol name."""
        init_args = {}
        if mt5_path and os.path.exists(mt5_path):
            init_args['path'] = mt5_path
            
        if not mt5.initialize(**init_args):
            return None
            
        aliases = ['USTEC', 'NAS100', 'US100', 'NDX', 'USTech100', 'US100.cash', 'NAS100.cash', 'NDX100', 'US100_m', 'US100.c']
        found = None
        for alias in aliases:
            info = mt5.symbol_info(alias)
            if info is not None:
                found = alias
                break
                
        mt5.shutdown()
        return found
        
    def connect(self):
        print("[TickCacheBridge] Connecting to MetaTrader 5...")
        init_args = {}
        if self.mt5_path and os.path.exists(self.mt5_path):
            init_args['path'] = self.mt5_path
            
        if not mt5.initialize(**init_args):
            print("  [ERROR] initialize() failed, error code =", mt5.last_error())
            if not self.mt5_path:
                print("  -> TIP: If MT5 isn't opening automatically, configure the MT5 Terminal Path in the Main Menu [2].")
            return False
            
        term_info = mt5.terminal_info()
        if term_info is None:
            print("  [ERROR] Could not retrieve terminal info.")
            return False
            
        if not term_info.trade_allowed:
            print("\n" + "!"*50)
            print("  🚨 MT5 AUTO-TRADING IS DISABLED! 🚨")
            print("  Please click the 'Algo Trading' button at the top")
            print("  of your MT5 terminal (it should turn green/play).")
            print("!"*50 + "\n")
            
            while not mt5.terminal_info().trade_allowed:
                sys.stdout.write('\r  Waiting for Algo Trading to be enabled...')
                sys.stdout.flush()
                time.sleep(1)
            print("\n  [TickCacheBridge] Auto-Trading Enabled!")
            
        print("  [TickCacheBridge] MT5 Connected.")
        return True
        
    def shutdown(self):
        mt5.shutdown()
        
    def get_account_info(self):
        info = mt5.account_info()
        if info is None:
            return None
        return info._asdict()
    
    def _ensure_symbol_selected(self, symbol):
        """Make sure the symbol is visible in MarketWatch."""
        si = mt5.symbol_info(symbol)
        if si is None:
            mt5.symbol_select(symbol, True)
            time.sleep(0.1)
        elif not si.visible:
            mt5.symbol_select(symbol, True)
            time.sleep(0.1)
    
    def _fetch_ticks(self, symbol, start_dt, end_dt):
        """Fetch raw ticks from MT5 between two UTC datetimes."""
        self._ensure_symbol_selected(symbol)
        ticks = mt5.copy_ticks_range(symbol, start_dt, end_dt, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return None
        df = pd.DataFrame(ticks)
        df['datetime'] = pd.to_datetime(df['time_msc'], unit='ms', utc=True)
        df.set_index('datetime', inplace=True)
        return df[['bid', 'ask']]
    
    def _resample_ticks(self, tick_df, freq):
        """Resample tick DataFrame into OHLC candles using pure Bid price."""
        ohlc = tick_df['bid'].resample(freq).ohlc().dropna()
        volume = tick_df['bid'].resample(freq).count().dropna()
        ohlc['Volume'] = volume
        ohlc.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        # Convert to Eastern Time
        ohlc.index = ohlc.index.tz_convert(self.eastern)
        return ohlc
    
    def warm_up(self, symbols):
        """
        Cold start: fetch warmup_days of tick history for all symbols.
        Call this once at bot startup.
        """
        print(f"[TickCacheBridge] Warming up {len(symbols)} symbols ({self.warmup_days} days of ticks)...")
        end_dt = datetime.datetime.now(self.utc)
        start_dt = end_dt - datetime.timedelta(days=self.warmup_days)
        
        for symbol in symbols:
            t0 = time.time()
            print(f"  Fetching ticks for {symbol}...", end=" ", flush=True)
            
            tick_df = self._fetch_ticks(symbol, start_dt, end_dt)
            if tick_df is None or tick_df.empty:
                print(f"FAILED (no ticks). Error: {mt5.last_error()}")
                continue
                
            self._tick_cache[symbol] = {
                'last_fetch_time': end_dt,
                'ticks_df': tick_df
            }
            
            # Pre-build candle caches
            self._candle_cache[symbol] = {
                'M1': self._resample_ticks(tick_df, '1min'),
                'M5': self._resample_ticks(tick_df, '5min'),
                'M15': self._resample_ticks(tick_df, '15min'),
            }
            
            elapsed = time.time() - t0
            n_ticks = len(tick_df)
            print(f"OK ({n_ticks:,} ticks, {elapsed:.1f}s)")
            
        print("[TickCacheBridge] Warm-up complete.\n")
    
    def update_cache(self, symbol):
        """
        Hot path: fetch only new ticks since the last fetch and append to cache.
        Call this every minute for each symbol.
        """
        if symbol not in self._tick_cache:
            # Cold start this symbol
            self.warm_up([symbol])
            return
            
        last_time = self._tick_cache[symbol]['last_fetch_time']
        now = datetime.datetime.now(self.utc)
        
        new_ticks = self._fetch_ticks(symbol, last_time, now)
        if new_ticks is not None and not new_ticks.empty:
            # Append new ticks, drop duplicates
            old_df = self._tick_cache[symbol]['ticks_df']
            combined = pd.concat([old_df, new_ticks])
            combined = combined[~combined.index.duplicated(keep='last')]
            
            # Trim old data (keep only warmup_days worth)
            cutoff = now - datetime.timedelta(days=self.warmup_days)
            combined = combined[combined.index >= cutoff]
            
            self._tick_cache[symbol]['ticks_df'] = combined
            self._tick_cache[symbol]['last_fetch_time'] = now
            
            # Rebuild candles
            self._candle_cache[symbol] = {
                'M1': self._resample_ticks(combined, '1min'),
                'M5': self._resample_ticks(combined, '5min'),
                'M15': self._resample_ticks(combined, '15min'),
            }
    
    def get_rates(self, symbol, timeframe, num_bars):
        """
        Drop-in replacement for the old MT5Bridge.get_rates().
        Returns the last `num_bars` of candles for the given timeframe,
        constructed from pure Bid ticks.
        """
        if symbol not in self._candle_cache:
            self.update_cache(symbol)
            
        if symbol not in self._candle_cache:
            return None
            
        df = self._candle_cache[symbol].get(timeframe)
        if df is None or df.empty:
            return None
            
        return df.tail(num_bars)
    
    def get_live_price(self, symbol):
        """Get the current live bid and ask prices."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None, None
        return tick.bid, tick.ask
    
    def calculate_lot_size(self, symbol, risk_percent, stop_loss_price):
        """
        Calculates lot size based on account balance, risk percentage, and SL distance.
        """
        account_info = self.get_account_info()
        if not account_info:
            return 0.01
            
        balance = account_info['balance']
        risk_amount = balance * (risk_percent / 100.0)
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.01
            
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        bid, ask = self.get_live_price(symbol)
        current_price = ask if ask else bid  # Fallback
        distance = abs(current_price - stop_loss_price)
        
        if distance == 0:
            return 0.01
            
        ticks_in_distance = distance / tick_size
        lot_size = risk_amount / (ticks_in_distance * tick_value)
        
        # Clamp to min/max/step
        min_vol = symbol_info.volume_min
        max_vol = symbol_info.volume_max
        step_vol = symbol_info.volume_step
        
        lot_size = round(lot_size / step_vol) * step_vol
        return max(min_vol, min(lot_size, max_vol))

    def send_market_order(self, symbol, order_type, lot_size, sl=None, tp=None, comment="LK_V2"):
        """
        order_type: mt5.ORDER_TYPE_BUY or mt5.ORDER_TYPE_SELL
        Uses live Ask for BUY, live Bid for SELL.
        """
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl: request["sl"] = float(sl)
        if tp: request["tp"] = float(tp)
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order failed for {symbol}: retcode={result.retcode}")
            return None
            
        return result
        
    def get_open_positions(self):
        positions = mt5.positions_get(magic=self.magic_number)
        if positions is None:
            return []
        return [p._asdict() for p in positions]
        
    def modify_sl(self, ticket, new_sl):
        position = mt5.positions_get(ticket=ticket)
        if not position: return False
        
        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": float(pos.tp)
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket, lot_size=None):
        position = mt5.positions_get(ticket=ticket)
        if not position: return False
        pos = position[0]
        
        tick = mt5.symbol_info_tick(pos.symbol)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        
        vol = lot_size if lot_size else pos.volume
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": float(vol),
            "type": close_type,
            "price": price,
            "magic": self.magic_number,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE
