import os
import pandas as pd
import quantstats as qs
import re
import warnings
warnings.filterwarnings('ignore')

OUT_DIR = os.path.dirname(__file__)

def parse_trades():
    # Read the markdown reports to extract trades
    trades = []
    
    # 1. Parse June and July from monthly_performance_report.md
    report_path = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity-ide", "brain", "d61cef1c-09e3-423d-a794-751ac594c159", "monthly_performance_report.md")
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            if "|" in line and ("WIN" in line or "LOSS" in line):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 5:
                    date_str = "2026-" + parts[2]
                    pnl_str = parts[4].replace("$", "").replace(",", "")
                    try:
                        pnl = float(pnl_str)
                        dt = pd.to_datetime(date_str, format="%Y-%m-%d %H:%M")
                        trades.append({'exit_time': dt, 'pnl': pnl})
                    except Exception:
                        pass
                        
    # 2. Parse August from august_midmonth_report.md
    aug_path = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity-ide", "brain", "d61cef1c-09e3-423d-a794-751ac594c159", "august_midmonth_report.md")
    if os.path.exists(aug_path):
        with open(aug_path, 'r') as f:
            for line in f.readlines():
                if "|" in line and ("WIN" in line or "LOSS" in line):
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 5:
                        date_str = "2026-" + parts[2]
                        pnl_str = parts[4].replace("$", "").replace(",", "")
                        try:
                            pnl = float(pnl_str)
                            dt = pd.to_datetime(date_str, format="%Y-%m-%d %H:%M")
                            trades.append({'exit_time': dt, 'pnl': pnl})
                        except Exception:
                            pass

    return pd.DataFrame(trades)

def generate_quantstats_report():
    df = parse_trades()
    if df.empty:
        print("No trades found.")
        return
        
    df = df.sort_values('exit_time').reset_index(drop=True)
    df['Date'] = df['exit_time'].dt.normalize()
    
    # Calculate daily absolute PnL
    daily_pnl = df.groupby('Date')['pnl'].sum()
    
    # Reindex to include all calendar days (so we have 0% return on non-trading days)
    idx = pd.date_range(start=daily_pnl.index.min(), end=daily_pnl.index.max(), freq='D')
    daily_pnl = daily_pnl.reindex(idx, fill_value=0.0)
    
    # Convert absolute PnL to percentage returns based on compounding equity
    initial_capital = 5000.0
    equity = initial_capital
    returns = []
    
    for pnl in daily_pnl:
        if pnl == 0:
            returns.append(0.0)
        else:
            pct_return = pnl / equity
            returns.append(pct_return)
            equity += pnl
            
    # Create the pandas Series required by quantstats
    returns_series = pd.Series(returns, index=daily_pnl.index)
    returns_series.index.name = 'Date'
    
    # Ensure standard index timezone for quantstats
    returns_series.index = pd.to_datetime(returns_series.index)
    
    html_out = os.path.join(OUT_DIR, "Advanced_Institutional_Tear_Sheet.html")
    
    # QuantStats generated HTML report
    qs.reports.html(returns_series, title="Lewis Kelly - Advanced Quantitative Performance Report", output=html_out)
    
    print(f"Generated institutional HTML report at: {html_out}")

if __name__ == "__main__":
    generate_quantstats_report()
