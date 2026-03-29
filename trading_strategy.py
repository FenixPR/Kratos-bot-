import time
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.tech_analyzer = TechnicalAnalyzer()
        self.initial_stake = 2.0
        self.current_stake = self.initial_stake
        self.tick_histories = {}
        self.last_trade_time = {}

    def reset(self):
        self.tick_histories.clear()
        self.current_stake = self.initial_stake

    def set_stake(self, val):
        self.initial_stake = float(val); self.current_stake = float(val)

    def analyze_tick(self, tick_data: dict):
        symbol = tick_data.get('symbol')
        quote = float(tick_data.get('quote'))
        if symbol not in self.tick_histories: self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > 600: self.tick_histories[symbol].pop(0)
        
        count = len(self.tick_histories[symbol])
        if count > 0 and count % 100 == 0 and count <= 500:
            return {"status": "PROGRESS", "symbol": symbol, "count": count}

        now = time.time()
        # Só opera se tiver 500 ticks e se o último trade no ativo foi há mais de 45s
        if count >= 500 and (now - self.last_trade_time.get(symbol, 0)) > 45:
            res = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            if res["status"] in ["ULTRA_CALL", "ULTRA_PUT"]:
                self.last_trade_time[symbol] = now
                return {
                    "status": "TRADE", "symbol": symbol, "amount": self.current_stake,
                    "contract_type": "CALL" if res["status"] == "ULTRA_CALL" else "PUT",
                    "duration": 15, "duration_unit": "t"
                }
        return None

    def on_trade_result(self, result):
        if result == "WIN": self.current_stake = self.initial_stake
        else: self.current_stake *= 2.1
