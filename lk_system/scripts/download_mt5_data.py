import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import os
import time

def download_data():
    if not mt5.initialize():
        print("Failed to initialize MT5, make sure the terminal is running.")
        return False
        
    pairs = ['EURJPY', 'AUDNZD', 'EURUSD', 'USDJPY', 'GBPAUD', 'AUDCAD', 'CHFJPY']
    
    # Timezone aware datetime for UTC
    date_from = datetime(2026, 8, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 8, 7, tzinfo=timezone.utc)
    
    data_dir = r"D:\FOREX\FOREX\candle data"
    os.makedirs(data_dir, exist_ok=True)
    
    for pair in pairs:
        print(f"Downloading {pair}...")
        mt5.symbol_select(pair, True)
        time.sleep(0.5)
        
        ticks = mt5.copy_ticks_range(pair, date_from, date_to, mt5.COPY_TICKS_ALL)
        
        if ticks is None or len(ticks) == 0:
            print(f"Failed to get ticks for {pair}. Error: {mt5.last_error()}")
        else:
            df = pd.DataFrame(ticks)
            df['Datetime'] = pd.to_datetime(df['time_msc'], unit='ms')
            
            df['<DATE>'] = df['Datetime'].dt.strftime('%Y.%m.%d')
            df['<TIME>'] = df['Datetime'].dt.strftime('%H:%M:%S.%f').str[:-3]
            
            df['<BID>'] = df['bid']
            df['<ASK>'] = df['ask']
            df['<LAST>'] = df['last']
            df['<VOLUME>'] = df['volume']
            
            df_out = df[['<DATE>', '<TIME>', '<BID>', '<ASK>', '<LAST>', '<VOLUME>']]
            
            file_name = f"{pair}_august_ticks.csv"
            out_path = os.path.join(data_dir, file_name)
            df_out.to_csv(out_path, sep='\t', index=False)
            print(f"Saved {len(df_out)} ticks for {pair} to {out_path}")
            
    mt5.shutdown()
    return True

if __name__ == "__main__":
    download_data()
