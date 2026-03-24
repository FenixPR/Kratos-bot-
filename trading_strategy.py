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
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 2.1))
        self.max_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))
        
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 1000 
        self.global_pause_until = 0

    def reset(self):
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()
        self.logger.info("🎯 Reset completo. Iniciando nova contagem de 500 ticks.")

    def set_stake(self, new_stake: float):
        self.initial_stake = new_stake
        self.current_stake = new_stake

    def get_progress(self):
        return {s: len(t) for s, t in self.tick_histories.items()}

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        if current_time < self.global_pause_until: return None
        
        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories: self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > self.max_history: 
            self.tick_histories[symbol].pop(0)

        # RIGOR DOS 500 TICKS
        if len(self.tick_histories[symbol]) >= 500:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            status = analysis.get("status")
            
            if status == "ULTRA_CALL": 
                return self._create_trade_signal("CALL", symbol)
            elif status == "ULTRA_PUT": 
                return self._create_trade_signal("PUT", symbol)
        
        return None

    def on_trade_result(self, result: str):
        current_time = time.time()
        self.tick_histories.clear() # Limpa para nova análise pura

        if result == "WIN":
            self.global_pause_until = current_time + 60 
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.global_pause_until = current_time + 120 
            if self.consecutive_losses <= self.max_losses:
                self.current_stake *= self.martingale_multiplier
            else:
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "duration": 15,
            "duration_unit": "t",
            "symbol": symbol
        }
