import os
import glob
import pandas as pd
import sys

sys.path.append('d:/FOREX/FOREX')
from lk_system.backtest.tick_engine import TickBacktestEngine

def run_portfolio(month_pattern="*jan to feb ticks*.csv", allowed_pairs=None):
    data_dir = r"D:\FOREX\FOREX\candle data"
    files = glob.glob(os.path.join(data_dir, month_pattern))
    
    if not files:
        print(f"No tick data found matching {month_pattern} in {data_dir}")
        return
        
    print(f"Found {len(files)} pairs for Portfolio Backtest.")
    
    portfolio_trades = []
    pair_stats = {}
    
    for file_path in files:
        filename = os.path.basename(file_path).upper()
        pair_name = filename.split('_')[0][:6] if '_' in filename else filename[:6]
        pair_name = pair_name.replace(' ', '')
        
        if allowed_pairs and pair_name not in allowed_pairs:
            continue
            
        # Pure Tuning: Determine nature of pair geographically
        # EUR/GBP/CHF are highly active in London/NY
        # AUD/NZD/JPY are highly active in Asia/London
        active_sessions = []
        if any(x in pair_name for x in ['EUR', 'GBP', 'CHF', 'CAD']):
            active_sessions.extend(['London', 'NY'])
        if any(x in pair_name for x in ['AUD', 'NZD', 'JPY']):
            active_sessions.extend(['Asia', 'London'])
            
        # Deduplicate and order
        target_sessions = list(dict.fromkeys(active_sessions))
                
        print(f"\n========================================================")
        print(f"Testing Pair: {pair_name}")
        print(f"Geographical Nature (Sessions): {target_sessions}")
        print(f"========================================================")
        
        engine = TickBacktestEngine(execution_mode='MARKET_CONFIRMATION', target_sessions=target_sessions)
        
        # Memory Management: Load one pair at a time, clear memory after
        try:
            df_m1, df_m15 = engine.load_and_resample(file_path)
            engine.run(df_m1, df_m15)
            
            # Store trades
            for t in engine.trades:
                t['pair'] = pair_name
                portfolio_trades.append(t)
                
            pair_stats[pair_name] = engine.stats
        except Exception as e:
            print(f"Failed to process {pair_name}: {e}")
            
    # Combine trades into a single portfolio curve
    if not portfolio_trades:
        print("No trades generated across any pair.")
        return
        
    print("\n========================================================")
    print("                PORTFOLIO PROFILING REPORT")
    print("========================================================")
    
    for pair, stats in pair_stats.items():
        print(f"{pair:<8} | Win Rate: {stats['Win Rate']:>6.2f}% | Trades: {stats['Total Trades']:>3} | Net Profit: {stats['Net Profit']:>6.2f}%")
        
    total_trades = len(portfolio_trades)
    wins = sum(1 for t in portfolio_trades if t['pnl'] > 0)
    overall_win_rate = (wins / total_trades) * 100
    
    # We started with 10k per pair conceptually, but if trading one single 10k funded account:
    # Net profit percentage is simply the sum of all individual trade risk percentages.
    # Since we risk 1% (0.01) per trade:
    initial_cap = 10000
    total_pnl = sum(t['pnl'] for t in portfolio_trades)
    total_pct = (total_pnl / initial_cap) * 100
    
    print("\n--- AGGREGATED PORTFOLIO EQUITY ---")
    print(f"Total Portfolio Trades : {total_trades}")
    print(f"Overall Win Rate       : {overall_win_rate:.2f}%")
    print(f"Total Account Growth   : {total_pct:.2f}%")
    print("========================================================")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "march":
            print("Running Phase 9: Forward Testing Gainers on March Data")
            gainers = ['AUDCAD', 'AUDNZD', 'EURUSD', 'USDJPY']
            run_portfolio(month_pattern="*march_ticks*.csv", allowed_pairs=gainers)
        elif sys.argv[1] == "new_pairs":
            print("Running Phase 10: Testing New Pairs (Jan-Feb)")
            new_pairs = ['USDCAD', 'USDCHF', 'NZDUSD', 'EURJPY']
            run_portfolio(month_pattern="*jan to feb ticks*.csv", allowed_pairs=new_pairs)
        elif sys.argv[1] == "new_pairs_march":
            print("Running Phase 10: Testing New Pairs (March)")
            new_pairs = ['USDCAD', 'USDCHF', 'NZDUSD', 'EURJPY']
            run_portfolio(month_pattern="*march_ticks*.csv", allowed_pairs=new_pairs)
    else:
        run_portfolio()
