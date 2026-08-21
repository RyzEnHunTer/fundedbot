import re
from datetime import datetime
import pandas as pd

def calculate_drawdowns():
    md_file = r"C:\Users\rafta\.gemini\antigravity-ide\brain\d61cef1c-09e3-423d-a794-751ac594c159\portfolio_trades.md"
    
    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    trades = []
    
    # Parse markdown table
    for line in lines:
        if line.startswith('|') and not line.startswith('| Trade #') and not line.startswith('| :---'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) > 10:
                exit_time_str = parts[8]
                pnl_html = parts[10]
                
                pnl_match = re.search(r'([+-]?\$\d+\.\d+)', pnl_html)
                if pnl_match:
                    pnl_str = pnl_match.group(1).replace('$', '')
                    pnl = float(pnl_str)
                else:
                    pnl = 0.0
                    
                exit_time = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M')
                trades.append({
                    'exit_time': exit_time,
                    'pnl': pnl
                })
                
    if not trades:
        print("No trades found to calculate drawdown.")
        return
        
    df = pd.DataFrame(trades)
    df.sort_values('exit_time', inplace=True)
    
    # 1. Max Drawdown (Peak to Trough)
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['equity'] = 10000.0 + df['cumulative_pnl']
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = df['equity'] - df['peak']
    df['drawdown_pct'] = (df['drawdown'] / df['peak']) * 100
    
    max_dd_pct = df['drawdown_pct'].min()
    max_dd_usd = df['drawdown'].min()
    
    # 2. Max Daily Drawdown
    df['date'] = df['exit_time'].dt.date
    daily_pnl = df.groupby('date')['pnl'].sum().reset_index()
    
    daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
    daily_pnl['end_equity'] = 10000.0 + daily_pnl['cumulative_pnl']
    daily_pnl['start_equity'] = daily_pnl['end_equity'].shift(1).fillna(10000.0)
    
    # Only negative PnL counts towards drawdown
    daily_pnl['daily_dd_pct'] = daily_pnl.apply(lambda r: (r['pnl'] / r['start_equity']) * 100 if r['pnl'] < 0 else 0, axis=1)
    
    max_daily_dd_pct = daily_pnl['daily_dd_pct'].min()
    max_daily_dd_usd = daily_pnl['pnl'].min()
    
    streak = 0
    max_streak = 0
    for p in df['pnl']:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
            
    print(f"Total Trades: {len(df)}")
    print(f"Max Consecutive Losses: {max_streak}")
    print(f"---")
    print(f"Max Total Drawdown: {abs(max_dd_pct):.2f}% (${abs(max_dd_usd):.2f})")
    print(f"Max Daily Drawdown: {abs(max_daily_dd_pct):.2f}% (${abs(max_daily_dd_usd):.2f})")
    
    print(f"---")
    print("Worst 3 Days (by PnL):")
    worst_days = daily_pnl.sort_values('pnl').head(3)
    for _, row in worst_days.iterrows():
        print(f"{row['date']}: {row['daily_dd_pct']:.2f}% (${row['pnl']:.2f})")

if __name__ == "__main__":
    calculate_drawdowns()
