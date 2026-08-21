import os
import json
import urllib.request
import datetime
import pandas as pd
import pytz

class NewsManager:
    def __init__(self, cache_dir=None, embargo_minutes=15):
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, "logs")
            
        self.cache_dir = cache_dir
        self.embargo_minutes = embargo_minutes
        self.eastern = pytz.timezone("US/Eastern")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.high_impact_events = []
        self._load_and_refresh()

    def _load_and_refresh(self):
        # We fetch the current week's news
        # To avoid spam, we cache it daily
        today_str = datetime.datetime.now(self.eastern).strftime("%Y%m%d")
        cache_file = os.path.join(self.cache_dir, f"news_cache_{today_str}.json")
        
        data = None
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                print(f"[NewsManager] Loaded weekly calendar from cache ({len(data)} events)")
            except:
                pass
                
        if data is None:
            print("[NewsManager] Fetching live Forex Factory calendar...")
            try:
                req = urllib.request.Request(
                    'https://nfs.faireconomy.media/ff_calendar_thisweek.json', 
                    headers={'User-Agent': 'Mozilla/5.0 LK_Bot'}
                )
                response = urllib.request.urlopen(req, timeout=10)
                data = json.loads(response.read().decode('utf-8'))
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
            except Exception as e:
                print(f"[NewsManager] Failed to fetch news: {e}")
                data = []

        self._parse_events(data)

    def _parse_events(self, data):
        self.high_impact_events = []
        for item in data:
            if item.get("impact") == "High":
                try:
                    # date string: "2026-08-16T18:30:00-04:00"
                    event_dt = pd.to_datetime(item["date"]).astimezone(self.eastern)
                    self.high_impact_events.append({
                        "title": item.get("title", "News"),
                        "currency": item.get("country", "").upper(),
                        "time": event_dt
                    })
                except Exception as e:
                    print(f"[NewsManager] Error parsing date {item.get('date')}: {e}")
                    
        print(f"[NewsManager] Active High-Impact Events this week: {len(self.high_impact_events)}")

    def is_news_embargo(self, pair, current_dt):
        """
        Returns (True, reason) if current_dt is within embargo_minutes of a high-impact event
        affecting the given pair.
        """
        # Pair is like 'EURUSD' -> base 'EUR', quote 'USD'
        if len(pair) != 6:
            return False, ""
            
        base_cur = pair[:3]
        quote_cur = pair[3:]
        
        # current_dt might be tz-naive in pandas if not careful, ensure tz-aware
        if current_dt.tzinfo is None:
            current_dt = self.eastern.localize(current_dt)
            
        for event in self.high_impact_events:
            if event["currency"] in [base_cur, quote_cur]:
                time_diff = abs((current_dt - event["time"]).total_seconds())
                if time_diff <= (self.embargo_minutes * 60):
                    reason = f"{event['currency']} {event['title']} at {event['time'].strftime('%H:%M')}"
                    return True, reason
                    
        return False, ""
