import json
import urllib.request
import urllib.error
import threading

class TradeNotifier:
    def __init__(self, config_path="config.json"):
        self.discord_url = ""
        self.tg_token = ""
        self.tg_chat_id = ""
        
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                notif = data.get("notifications", {})
                self.discord_url = notif.get("discord_webhook_url", "").strip()
                self.tg_token = notif.get("telegram_bot_token", "").strip()
                self.tg_chat_id = notif.get("telegram_chat_id", "").strip()
        except Exception as e:
            print(f"[Notifier] Failed to load config: {e}")
            
    def _send_discord(self, message):
        if not self.discord_url: return
        
        data = {"content": message}
        req = urllib.request.Request(
            self.discord_url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'LK_Bot'}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[Notifier] Discord Error: {e}")

    def _send_telegram(self, message):
        if not self.tg_token or not self.tg_chat_id: return
        
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        data = {
            "chat_id": self.tg_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[Notifier] Telegram Error: {e}")

    def send_message(self, message):
        """Sends a message to all configured platforms asynchronously."""
        # Use threading so slow HTTP requests don't block the M1 tick loop
        t1 = threading.Thread(target=self._send_discord, args=(message,))
        t2 = threading.Thread(target=self._send_telegram, args=(message,))
        t1.start()
        t2.start()

    def send_test(self):
        active = []
        if self.discord_url: active.append("Discord")
        if self.tg_token: active.append("Telegram")
        
        if active:
            msg = f"🟢 <b>LK SMC Bot Started!</b>\nNotifications enabled for: {', '.join(active)}"
            self.send_message(msg)
            return True
        return False
