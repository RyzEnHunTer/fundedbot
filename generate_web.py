import os
import json
import pandas as pd

WEB_DIR = r"D:\FOREX\FOREX\web"
DATA_FILE = r"C:\Users\rafta\.gemini\antigravity-ide\brain\d61cef1c-09e3-423d-a794-751ac594c159\scratch\golden5_dynamic_results.json"

if not os.path.exists(WEB_DIR):
    os.makedirs(WEB_DIR)

def build_web():
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        
    trades = data['trades']
    summary = data['summary']
    monthly = data['monthly']
    
    # Pre-calculate equity curve points for chart
    equity = 5000.0
    labels = ["Start"]
    data_points = [5000.0]
    
    # Sort trades
    trades.sort(key=lambda x: pd.to_datetime(x['entry_time']))
    
    for i, t in enumerate(trades):
        equity += t['pnl']
        labels.append(f"Trade {i+1}")
        data_points.append(equity)

    # 1. CSS File
    css = """
    :root {
        --bg: #0f172a;
        --card-bg: rgba(30, 41, 59, 0.7);
        --text: #f8fafc;
        --accent: #3b82f6;
        --accent-hover: #60a5fa;
        --success: #10b981;
        --danger: #ef4444;
        --border: rgba(255, 255, 255, 0.1);
    }
    body {
        background-color: var(--bg);
        color: var(--text);
        font-family: 'Inter', sans-serif;
        margin: 0;
        padding: 0;
        background-image: radial-gradient(circle at top right, rgba(59,130,246,0.15), transparent 40%),
                          radial-gradient(circle at bottom left, rgba(16,185,129,0.1), transparent 40%);
        background-attachment: fixed;
        min-height: 100vh;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
    }
    header {
        text-align: center;
        margin-bottom: 3rem;
    }
    h1 {
        font-size: 2.5rem;
        background: -webkit-linear-gradient(45deg, #3b82f6, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
    }
    .tabs {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .tab-btn {
        background: var(--card-bg);
        border: 1px solid var(--border);
        color: var(--text);
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        font-size: 1rem;
        font-weight: 500;
    }
    .tab-btn:hover {
        background: rgba(59,130,246,0.2);
        border-color: var(--accent);
    }
    .tab-btn.active {
        background: var(--accent);
        border-color: var(--accent);
        box-shadow: 0 0 15px rgba(59,130,246,0.4);
    }
    .tab-content {
        display: none;
        animation: fadeIn 0.4s ease;
    }
    .tab-content.active {
        display: block;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Metrics Grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
    }
    .positive { color: var(--success); }
    .negative { color: var(--danger); }
    
    /* Charts */
    .chart-container {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 2rem;
        backdrop-filter: blur(12px);
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Table */
    .table-container {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 16px;
        backdrop-filter: blur(12px);
        overflow-x: auto;
        padding: 1rem;
    }
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th, td {
        padding: 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border);
    }
    th {
        color: #94a3b8;
        font-weight: 500;
        text-transform: uppercase;
        font-size: 0.85rem;
        letter-spacing: 1px;
    }
    tr:hover td {
        background: rgba(255,255,255,0.02);
    }
    """
    with open(os.path.join(WEB_DIR, 'styles.css'), 'w') as f:
        f.write(css)

    # 2. HTML Structure
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Golden 5 Prop Engine Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Golden 5 Prop Engine</h1>
            <div class="subtitle">Dynamic Session Backtest Report (Summer 2026)</div>
        </header>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="openTab('dashboard')">Global Dashboard</button>
            <button class="tab-btn" onclick="openTab('monthly')">Monthly Report</button>
            <button class="tab-btn" onclick="openTab('drawdown')">Drawdown Report</button>
            <button class="tab-btn" onclick="openTab('trades')">Trade Logs</button>
        </div>
        
        <!-- DASHBOARD TAB -->
        <div id="dashboard" class="tab-content active">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Trades</div>
                    <div class="metric-value">{summary['total_trades']}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Win Rate</div>
                    <div class="metric-value">{summary['win_rate']:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Net Profit</div>
                    <div class="metric-value positive">+${summary['pnl']:.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Total ROI</div>
                    <div class="metric-value positive">+{summary['roi']:.1f}%</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h2 style="margin-top:0; color:#94a3b8; font-size:1.2rem;">Global Equity Curve</h2>
                <canvas id="equityChart"></canvas>
            </div>
        </div>
        
        <!-- MONTHLY TAB -->
        <div id="monthly" class="tab-content">
            <div class="metrics-grid">"""
            
    for m in ['June', 'July', 'August']:
        if m in monthly:
            color_class = "positive" if monthly[m]['pnl'] >= 0 else "negative"
            prefix = "+" if monthly[m]['pnl'] >= 0 else ""
            html += f"""
                <div class="metric-card">
                    <div class="metric-title">{m} Performance</div>
                    <div class="metric-value {color_class}">{prefix}{monthly[m]['roi']:.1f}%</div>
                    <div style="color: #94a3b8; margin-top: 10px; font-size: 0.9rem;">
                        Win Rate: {monthly[m]['wr']:.1f}%<br>
                        Trades: {monthly[m]['trades']}<br>
                        Net PnL: ${monthly[m]['pnl']:.2f}
                    </div>
                </div>"""
                
    html += """
            </div>
        </div>
        
        <!-- DRAWDOWN TAB -->
        <div id="drawdown" class="tab-content">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Max Global Drawdown</div>
                    <div class="metric-value" style="color: #f59e0b;">{summary['max_dd']:.2f}%</div>
                </div>"""
                
    for m in ['June', 'July', 'August']:
        if m in monthly:
            html += f"""
                <div class="metric-card">
                    <div class="metric-title">{m} Max DD</div>
                    <div class="metric-value" style="color: #ef4444;">{monthly[m]['max_dd']:.2f}%</div>
                    <div style="color: #94a3b8; margin-top: 10px; font-size: 0.9rem;">Max Daily DD: {monthly[m]['max_daily_dd']:.2f}%</div>
                </div>"""
                
    html += """
            </div>
        </div>
        
        <!-- TRADES TAB -->
        <div id="trades" class="tab-content">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Pair</th>
                            <th>Type</th>
                            <th>Entry Time</th>
                            <th>Exit Time</th>
                            <th>Entry Price</th>
                            <th>Exit Price</th>
                            <th>PnL</th>
                        </tr>
                    </thead>
                    <tbody>"""
                    
    for t in trades:
        color_class = "positive" if t['pnl'] > 0 else "negative"
        pnl_str = f"+${t['pnl']:.2f}" if t['pnl'] > 0 else f"-${abs(t['pnl']):.2f}"
        html += f"""
                        <tr>
                            <td><strong>{t.get('pair', 'N/A')}</strong></td>
                            <td style="text-transform: uppercase;">{t['type']}</td>
                            <td>{str(t['entry_time'])[:16]}</td>
                            <td>{str(t['exit_time'])[:16]}</td>
                            <td>{t['entry_price']:.5f}</td>
                            <td>{t['exit_price']:.5f}</td>
                            <td class="{color_class}"><strong>{pnl_str}</strong></td>
                        </tr>"""
                        
    html += f"""
                    </tbody>
                </table>
            </div>
        </div>
        
    </div>

    <script>
        function openTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }}

        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(labels)},
                datasets: [{{
                    label: 'Account Equity ($)',
                    data: {json.dumps(data_points)},
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ display: false }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open(os.path.join(WEB_DIR, 'index.html'), 'w') as f:
        f.write(html)
        
    print(f"Generated successfully at {os.path.join(WEB_DIR, 'index.html')}")

if __name__ == "__main__":
    build_web()
