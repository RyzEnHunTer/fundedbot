import os
import sys

print("========================================")
print("  STARTING LIVE BOT CONNECTION TO MT5")
print("========================================\n")

try:
    # We just run the live_bot module
    import lk_system.live.live_bot
except KeyboardInterrupt:
    print("\nBot stopped by user.")
except Exception as e:
    print(f"\n[CRITICAL ERROR]: {e}")
finally:
    input("\nPress Enter to exit...")
