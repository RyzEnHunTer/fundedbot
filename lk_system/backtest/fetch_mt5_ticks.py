import MetaTrader5 as mt5
import pandas as pd
import datetime
import os
import pytz

def fetch_ticks(symbol, start_date, end_date, output_filename):
    print(f"Fetching ticks for {symbol} from {start_date} to {end_date}...")
    
    # We use UTC for MT5 query, then the tick_engine will handle timezones
    timezone = pytz.timezone("Etc/UTC")
    utc_from = datetime.datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone)
    utc_to = datetime.datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone)
    
    # Copy ticks
    ticks = mt5.copy_ticks_range(symbol, utc_from, utc_to, mt5.COPY_TICKS_ALL)
    
    if ticks is None or len(ticks) == 0:
        print(f"FAILED: No ticks found for {symbol}. Error: {mt5.last_error()}")
        return False
        
    print(f"Success! Fetched {len(ticks)} ticks. Converting to dataframe...")
    df = pd.DataFrame(ticks)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Format to match <DATE> \t <TIME> \t <BID>
    # Note: df['time'] is a datetime object. We need to split it into DATE and TIME columns matching format 'Y.m.d H:M:S.f'
    # Since MT5 'time' might just be seconds, 'time_msc' has the milliseconds.
    df['datetime'] = pd.to_datetime(df['time_msc'], unit='ms')
    df['<DATE>'] = df['datetime'].dt.strftime('%Y.%m.%d')
    df['<TIME>'] = df['datetime'].dt.strftime('%H:%M:%S.%f')
    df['<BID>'] = df['bid']
    
    final_df = df[['<DATE>', '<TIME>', '<BID>']]
    
    out_path = os.path.join(r"D:\FOREX\FOREX\candle data", output_filename)
    print(f"Saving to {out_path}...")
    final_df.to_csv(out_path, sep='\t', index=False)
    print("Done.\n")
    return True


if __name__ == "__main__":
    if not mt5.initialize():
        print("initialize() failed")
        quit()
        
    pairs = ['GBPAUD', 'AUDCAD', 'CHFJPY']
    
    train_start = datetime.date(2026, 4, 1)
    train_end = datetime.date(2026, 8, 1)
    
    for p in pairs:
        # Enable symbol in Market Watch to allow download
        mt5.symbol_select(p, True)
        
        fetch_ticks(p, train_start, train_end, f"{p}_april_to_july_ticks.csv")
        
    mt5.shutdown()
