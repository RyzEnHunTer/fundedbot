import sys
import os
import pandas as pd
from datetime import datetime
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lk_system.backtest.tick_engine import TickBacktestEngine

def run_comparison():
    pairs = ['EURUSD', 'USDJPY', 'CHFJPY', 'EURJPY']
    datasets = {
        'Jan-Feb (Trending according to User)': '_jan to feb ticks.csv',
        'April-July (Choppy according to User)': '_april_to_july_ticks.csv'
    }
    
    strategies = {
        'RAW TRENDING (M1 FVG, Loose Sweeps, No Filters)': 'TREND',
        'RAW CHOPPY (M5 FVG, Asian Range Filter)': 'CHOP'
    }
    
    data_dir = "D:/FOREX/FOREX/candle data"
    
    report_path = r"C:\Users\rafta\.gemini\antigravity-ide\brain\d61cef1c-09e3-423d-a794-751ac594c159\detailed_comparison_report.md"
    
    with open(report_path, 'w') as f:
        f.write("# Detailed Head-to-Head Strategy Comparison\n\n")
        f.write("This report details every trade taken by the RAW Trending strategy vs the RAW Choppy strategy across both datasets.\n\n")
    
    for period_name, suffix in datasets.items():
        with open(report_path, 'a') as f:
            f.write(f"## Dataset: {period_name}\n\n")
            
        for pair in pairs:
            file_path = f"{data_dir}/{pair}{suffix}"
            if not os.path.exists(file_path):
                continue
                
            for strat_name, strat_mode in strategies.items():
                print(f"Running {pair} on {period_name} with {strat_name}...")
                
                active_sessions = []
                if any(x in pair for x in ['EUR', 'GBP', 'CHF', 'CAD']):
                    active_sessions.extend(['London', 'NY'])
                if any(x in pair for x in ['AUD', 'NZD', 'JPY']):
                    active_sessions.extend(['Asia', 'London'])
                target_sessions = list(dict.fromkeys(active_sessions))
                        
                engine = TickBacktestEngine(
                    execution_mode='MARKET_CONFIRMATION', 
                    target_sessions=target_sessions, 
                    pair_name=pair, 
                    use_ml_filter=False, 
                    strategy_mode=strat_mode
                )
                
                df_m1, df_m5, df_m15 = engine.load_and_resample(file_path)
                engine.run(df_m1, df_m5, df_m15)
                
                metrics = engine.stats
                trades = metrics.get('trades', [])
                
                max_dd = 0.0
                running_capital = 5000.0
                peak_capital = 5000.0
                
                trade_lines = []
                for idx, t in enumerate(trades):
                    running_capital += t['pnl']
                    if running_capital > peak_capital:
                        peak_capital = running_capital
                    dd = (peak_capital - running_capital) / peak_capital * 100
                    if dd > max_dd: max_dd = dd
                    
                    status = "WIN" if t['pnl'] > 0 else "LOSS"
                    trade_lines.append(f"| {idx+1} | {t['entry_time']} | {t['type']} | {t['entry_price']:.5f} | {t['sl']:.5f} | {t['tp']:.5f} | {status} | ${t['pnl']:.2f} |")
                
                win_rate = metrics.get('Win Rate', 0.0)
                net_profit = metrics.get('Net Profit', 0.0)
                
                with open(report_path, 'a') as f:
                    f.write(f"### {pair} - {strat_name}\n")
                    f.write(f"**Trades:** {len(trades)} | **Win Rate:** {win_rate:.2f}% | **Net Profit:** {net_profit:.2f}% | **Max Drawdown:** {max_dd:.2f}%\n\n")
                    
                    if len(trades) > 0:
                        f.write("<details>\n<summary>View Detailed Trade List</summary>\n\n")
                        f.write("| # | Entry Time | Type | Entry | SL | TP | Result | PnL |\n")
                        f.write("|---|---|---|---|---|---|---|---|\n")
                        for line in trade_lines:
                            f.write(f"{line}\n")
                        f.write("\n</details>\n\n")
                    else:
                        f.write("*No trades taken.*\n\n")
                    f.write("---\n\n")
                    
if __name__ == '__main__':
    run_comparison()
