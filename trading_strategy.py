import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer()
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 2.0))
        self.current_stake = self.initial_stake
        self.tick_histories: Dict[str, List[float]] = {}
        self.global_pause_until = 0

    def reset(self):
        self.tick_histories.clear()
        self.current_stake = self.initial_stake

    def set_stake(self, val):
        self.initial_stake = val
        self.current_stake = val

    def analyze_tick(self, tick_data: dict):
        if time.time() < self.global_pause_until: return None
        
        symbol = tick_data.get('symbol')
        quote = float(tick_data.get('quote'))
        
        if symbol not in self.tick_histories: self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > 600: self.tick_histories[symbol].pop(0)
        
        count = len(self.tick_histories[symbol])
        
        # Manda sinal de progresso a cada 100 ticks
        if count > 0 and count % 100 == 0 and count <= 500:
            return {"status": "PROGRESS", "symbol": symbol, "count": count}

        if count >= 500:
            res = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            if res["status"] in ["ULTRA_CALL", "ULTRA_PUT"]:
                return {
                    "status": "TRADE",
                    "contract_type": "CALL" if res["status"] == "ULTRA_CALL" else "PUT",
                    "amount": round(self.current_stake, 2),
                    "duration": 15, "duration_unit": "t", "symbol": symbol
                }
        return None

    def on_trade_result(self, result):
        self.tick_histories.clear()
        if result == "WIN":
            self.current_stake = self.initial_stake
            self.global_pause_until = time.time() + 60
        else:
            self.current_stake *= 2.1
            self.global_pause_until = time.time() + 120
