import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer()
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 1.0))
        self.current_stake = self.initial_stake
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 1000 
        self.reset()

    def reset(self):
        self.tick_histories.clear()
        self.current_stake = self.initial_stake

    def get_progress(self) -> Dict[str, int]:
        """Retorna quantos ticks cada ativo já coletou."""
        return {symbol: len(ticks) for symbol, ticks in self.tick_histories.items()}

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        symbol = tick_data.get('symbol')
        quote = float(tick_data.get('quote'))
        
        if symbol not in self.tick_histories: self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > self.max_history:
            self.tick_histories[symbol].pop(0)

        # Só analisa se tiver os 500 ticks
        if len(self.tick_histories[symbol]) >= 500:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            if analysis["status"] == "ULTRA_CALL":
                return self._create_signal("CALL", symbol)
            elif analysis["status"] == "ULTRA_PUT":
                return self._create_signal("PUT", symbol)
        return None

    def _create_signal(self, type, symbol):
        return {
            "contract_type": type,
            "amount": self.current_stake,
            "duration": 15,
            "duration_unit": "t",
            "symbol": symbol
        }

    def on_trade_result(self, result):
        if result == "WIN": self.current_stake = self.initial_stake
        else: self.current_stake *= 2.1
        self.tick_histories.clear() # Reinicia análise após trade
