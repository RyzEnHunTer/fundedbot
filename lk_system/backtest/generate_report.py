import os
import glob
import pandas as pd
from tick_engine import TickBacktestEngine

def generate_report():
    pairs = ['EURUSD', 'USDJPY', 'CHFJPY', 'EURJPY']
    data_dir = "D:/FOREX/FOREX/candle data"
    
    all_trades = []
    
    for pair in pairs:
        file_path = f"{data_dir}/{pair}_jan to feb ticks.csv"
        
        if not os.path.exists(file_path):
            print(f"No file found for {pair}")
            continue
            
        print(f"Processing {pair}...")
        
        # Set target sessions dynamically just like portfolio engine
        if pair in ['EURJPY', 'GBPJPY', 'CHFJPY']:
            target_sessions = ['London', 'NY', 'Asia']
        elif pair in ['AUDNZD', 'AUDCAD', 'EURAUD', 'EURNZD']:
            target_sessions = ['Asia', 'London']
        else:
            target_sessions = ['London', 'NY']
        engine = TickBacktestEngine(execution_mode='MARKET_CONFIRMATION', target_sessions=target_sessions, pair_name=pair, use_ml_filter=True)
        
        print(f"Running Dual-Timeframe Backtest (Mode: {engine.execution_mode})...")
        df_m1, df_m15 = engine.load_and_resample(file_path)
        print(f"Running backtest for {pair}...")
        engine.run(df_m1, df_m15)
        
        metrics = engine.stats
        
        if 'trades' in metrics:
            for t in metrics['trades']:
                t['pair'] = pair
                all_trades.append(t)
                
    # Sort trades by entry time
    all_trades.sort(key=lambda x: x['entry_time'])
    
    # Generate Markdown Table
    md_lines = []
    md_lines.append("# Detailed Portfolio Trade Log (March 2026)")
    md_lines.append("")
    md_lines.append("This log represents the aggregated trades from the expanded portfolio over the 1-month March backtest.")
    md_lines.append("All trades strictly follow the 5-Candle Fractal Structure and Market Confirmation entry rule within their respective geographical killzones. **No curve-fitting.**")
    md_lines.append("")
    md_lines.append("| Trade # | Pair | Type | Entry Time (EST) | Entry Price | SL | TP | Exit Time (EST) | Exit Price | PnL ($) | ROI |")
    md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    running_capital = 5000.0
    
    for i, t in enumerate(all_trades, 1):
        pnl = t['pnl']
        running_capital += pnl
        roi = (running_capital - 5000.0) / 5000.0 * 100
        
        entry_time_str = t['entry_time'].strftime('%Y-%m-%d %H:%M')
        exit_time_str = t.get('exit_time', t['entry_time']).strftime('%Y-%m-%d %H:%M')
        
        entry_price = f"{t['entry_price']:.5f}"
        sl = f"{t['sl']:.5f}"
        tp = f"{t['tp']:.5f}"
        exit_price = f"{t['exit_price']:.5f}"
        
        pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "$0.00"
        roi_str = f"{roi:.2f}%"
        
        # Color code PNL
        if pnl > 0:
            pnl_str = f"**<span style='color:green'>{pnl_str}</span>**"
        elif pnl < 0:
            pnl_str = f"**<span style='color:red'>{pnl_str}</span>**"
        else:
            pnl_str = f"**<span style='color:gray'>{pnl_str} (BE)</span>**"
            
        line = f"| {i} | **{t['pair']}** | {t['type'].upper()} | {entry_time_str} | {entry_price} | {sl} | {tp} | {exit_time_str} | {exit_price} | {pnl_str} | **{roi_str}** |"
        md_lines.append(line)
        
    md_lines.append("")
    md_lines.append("### Summary")
    md_lines.append(f"- **Total Trades:** {len(all_trades)}")
    md_lines.append(f"- **Final Capital:** ${running_capital:.2f}")
    md_lines.append(f"- **Total Return:** {(running_capital - 5000.0) / 5000.0 * 100:.2f}%")
    
    out_path = r"C:\Users\rafta\.gemini\antigravity-ide\brain\d61cef1c-09e3-423d-a794-751ac594c159\portfolio_trades.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    print(f"Successfully wrote trade log to {out_path}")

if __name__ == "__main__":
    generate_report()
