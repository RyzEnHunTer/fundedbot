import subprocess
import sys
import os

def install():
    print("========================================")
    print("    LK SMC LIVE BOT - INSTALLER")
    print("========================================\n")
    print("Installing Python dependencies for the bot...\n")
    
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    if not os.path.exists(requirements_path):
        print(f"Error: {requirements_path} not found.")
        input("Press Enter to exit...")
        return

    # Upgrade pip
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install requirements
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
    
    print("\n========================================")
    print("Installation Complete!")
    print("Make sure MetaTrader 5 is installed and 'Algo Trading' is turned ON.")
    print("You can now run 'run_bot.py' to start the Live Bot.")
    print("========================================")
    input("Press Enter to exit...")

if __name__ == "__main__":
    install()
