import MetaTrader5 as mt5

if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# Get all symbols
symbols = mt5.symbols_get()
print(f"Total symbols found: {len(symbols)}")

# Look for indices (US30, NAS100, SPX500, GER40) and metals (XAUUSD, XAGUSD)
targets = ['US30', 'US100', 'NAS', 'SPX', 'GER', 'DAX', 'XAU', 'XAG', 'GOLD', 'SILVER', 'USDCAD', 'NZDUSD', 'EURJPY', 'USDCHF', 'CADJPY']

found_symbols = []
for s in symbols:
    name = s.name.upper()
    for t in targets:
        if t in name:
            found_symbols.append(s.name)
            break

print("\nMatching Symbols found on your broker:")
for fs in sorted(found_symbols):
    print(fs)

mt5.shutdown()
