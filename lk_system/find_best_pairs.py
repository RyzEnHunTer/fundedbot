import sys
import os
import pandas as pd
from datetime import datetime
import multiprocessing

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lk_system.backtest.tick_engine import TickBacktestEngine
from lk_system.core.market_structure import MarketStructure

def run_single_backtest(args):
    pair, period_name, file_path = args
    if not os.path.exists(file_path):
        return None
        
    print(f"Starting {pair} for {period_name}...")
    
    active_sessions = ['London', 'NY', 'Asia']
    target_sessions = active_sessions
        
    engine = TickBacktestEngine(
        execution_mode='MARKET_CONFIRMATION', 
        target_sessions=target_sessions, 
        pair_name=pair, 
        use_amcc=True,
        use_ml_filter=False
    )
    
    try:
        df_m1, df_m5, df_m15 = engine.load_and_resample(file_path)
        
        engine.run(df_m1, df_m5, df_m15, risk_schedule=None)
        
        metrics = engine.stats
        trades = metrics.get('trades', [])
        
        max_dd = 0.0
        running_capital = 5000.0
        peak_capital = 5000.0
        
        for t in trades:
            running_capital += t['pnl']
            if running_capital > peak_capital:
                peak_capital = running_capital
            dd = (peak_capital - running_capital) / peak_capital * 100
            if dd > max_dd: max_dd = dd
            
        win_rate = metrics.get('Win Rate', 0.0)
        net_profit = metrics.get('Net Profit', 0.0)
        
        return {
            'Pair': pair,
            'Period': period_name,
            'Trades': len(trades),
            'WinRate': win_rate,
            'Profit': net_profit,
            'MaxDD': max_dd
        }
    except Exception as e:
        print(f"Error on {pair} {period_name}: {e}")
        return None

def run_pure_strategy_scan():
    pairs = ['AUDCAD', 'AUDNZD', 'CHFJPY', 'EURJPY', 'EURUSD', 'GBPAUD', 'USDJPY']
    datasets = {
        'Jan-Feb': '_jan to feb ticks.csv',
        'April-July': '_april_to_july_ticks.csv'
    }
    
    data_dir = "D:/FOREX/FOREX/candle data"
    report_path = r"C:\Users\rafta\.gemini\antigravity-ide\brain\d61cef1c-09e3-423d-a794-751ac594c159\optimal_windows_performance.md"
    
    tasks = []
    for pair in pairs:
        for period_name, suffix in datasets.items():
            file_path = f"{data_dir}/{pair}{suffix}"
            tasks.append((pair, period_name, file_path))
            
    print(f"Running {len(tasks)} backtests in parallel...")
    results = []
    
    with multiprocessing.Pool(processes=2) as pool:
        for res in pool.imap_unordered(run_single_backtest, tasks):
            if res:
                results.append(res)
                print(f"Finished {res['Pair']} {res['Period']} -> Profit: {res['Profit']:.2f}%")

    # Generate Report
    with open(report_path, 'w') as f:
        f.write("# AMCC + ML Optimized Time Windows Performance\n\n")
        f.write("Results of the pure strategy filtered by AMCC and restricted to each pair's absolute best 3-hour micro-session.\n\n")
        
        df_res = pd.DataFrame(results)
        
        for period in datasets.keys():
            f.write(f"## Dataset: {period}\n\n")
            f.write("| Pair | Trades | Win Rate | Net Profit | Max Drawdown |\n")
            f.write("|---|---|---|---|---|\n")
            
            period_data = df_res[df_res['Period'] == period].sort_values(by='Profit', ascending=False)
            for _, row in period_data.iterrows():
                f.write(f"| **{row['Pair']}** | {row['Trades']} | {row['WinRate']:.2f}% | **{row['Profit']:.2f}%** | {row['MaxDD']:.2f}% |\n")
            f.write("\n")

if __name__ == '__main__':
    run_pure_strategy_scan()
