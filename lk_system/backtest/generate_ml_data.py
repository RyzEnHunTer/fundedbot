import os
from tick_engine import TickBacktestEngine
import pandas as pd

def generate_ml_training_data():
    pairs = ['EURJPY', 'AUDNZD', 'EURUSD', 'USDJPY', 'GBPAUD', 'AUDCAD', 'CHFJPY']
    data_dir = r"D:\FOREX\FOREX\candle data"
    
    print("--- GENERATING ML TRAINING DATA (April - July) ---")
    
    for pair in pairs:
        print(f"\nProcessing {pair}...")
        
        # Load the newly fetched training data
        tick_file = os.path.join(data_dir, f"{pair}_april_to_july_ticks.csv")
        
        if not os.path.exists(tick_file):
            print(f"Skipping {pair} - Training data not found at {tick_file}")
            continue
            
        print(f"Loading data from {tick_file}...")
        df_ticks = pd.read_csv(tick_file, sep='\t')
        
        # Convert MT5 tick format to standard format
        if '<DATE>' in df_ticks.columns and '<TIME>' in df_ticks.columns:
            df_ticks['datetime'] = pd.to_datetime(df_ticks['<DATE>'] + ' ' + df_ticks['<TIME>'], format='%Y.%m.%d %H:%M:%S.%f')
            df_ticks.set_index('datetime', inplace=True)
            if '<BID>' in df_ticks.columns:
                df_ticks['price'] = df_ticks['<BID>']
            else:
                df_ticks['price'] = df_ticks['bid']
        
        print("Resampling to M1 and M15...")
        df_m1 = df_ticks['price'].resample('1min').ohlc().dropna()
        df_m15 = df_ticks['price'].resample('15min').ohlc().dropna()
        
        df_m1.columns = ['Open', 'High', 'Low', 'Close']
        df_m15.columns = ['Open', 'High', 'Low', 'Close']
        
        engine = TickBacktestEngine(execution_mode='MARKET_CONFIRMATION', target_sessions=['London', 'NY', 'Asia'])
        
        print(f"Running backtest to extract features for {pair}...")
        engine.run(df_m1, df_m15)
        
        # Dump the features to a CSV
        engine.export_ml_training_data(pair)
        
    print("\n--- ALL TRAINING DATA EXTRACTED ---")

if __name__ == "__main__":
    generate_ml_training_data()
