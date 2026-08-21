import MetaTrader5 as mt5
import datetime
import pytz

class PortfolioRiskManager:
    def __init__(self, magic_number=999111, max_daily_losses=2, risk_percent_per_trade=1.0, circuit_breaker_percent=9.0):
        self.magic_number = magic_number
        self.max_daily_losses = max_daily_losses
        self.risk_percent_per_trade = risk_percent_per_trade
        self.circuit_breaker_percent = circuit_breaker_percent
        self.timezone = pytz.timezone("Etc/UTC")
        
    def _get_start_of_day(self):
        now = datetime.datetime.now(self.timezone)
        return datetime.datetime(now.year, now.month, now.day, tzinfo=self.timezone)
        
    def check_circuit_breaker(self):
        """
        Checks MT5 history for today to see if the global loss limit is hit,
        AND checks if the global max drawdown (9%) is breached.
        Returns True if trading is ALLOWED.
        Returns False if the CIRCUIT BREAKER is triggered.
        """
        # 1. Global Max Drawdown Check (9%)
        account_info = mt5.account_info()
        if account_info:
            current_equity = account_info.equity
            
            # Fetch all history to find the highest balance water mark
            all_deals = mt5.history_deals_get(datetime.datetime(2000, 1, 1, tzinfo=self.timezone), datetime.datetime.now(self.timezone))
            if all_deals:
                # Approximate peak balance (starting balance + cumulative profit of all deals)
                # Since MT5 doesn't easily expose daily historical balances without heavy tracking, 
                # we'll approximate the peak balance. A safer approach for prop firms is just checking 
                # if current equity is 9% below the initial deposit.
                # Assuming the first deal in history is the deposit:
                initial_deposit = all_deals[0].profit if all_deals[0].type == mt5.DEAL_TYPE_BALANCE else account_info.balance
                
                # Check absolute drawdown from initial deposit using dynamic circuit breaker limit
                max_loss_allowed = initial_deposit * (self.circuit_breaker_percent / 100.0)
                if current_equity <= (initial_deposit - max_loss_allowed):
                    print(f"[CIRCUIT BREAKER] Global {self.circuit_breaker_percent}% Max Drawdown breached! Equity: {current_equity}, Deposit: {initial_deposit}")
                    return False

        # 2. Daily Loss Limit Check (Max 2 losses per day)
        start_of_day = self._get_start_of_day()
        now = datetime.datetime.now(self.timezone)
        
        deals = mt5.history_deals_get(start_of_day, now, group="*")
        if deals is None:
            return True # Cannot verify, allow trading but ideally log this
            
        losses_today = 0
        for deal in deals:
            # Check if it belongs to our bot and is an exit deal
            if deal.magic == self.magic_number and deal.entry == mt5.DEAL_ENTRY_OUT:
                if deal.profit < 0:
                    losses_today += 1
                    
        if losses_today >= self.max_daily_losses:
            print(f"[CIRCUIT BREAKER] {losses_today} losses today. Trading suspended until rollover.")
            return False
            
        return True
