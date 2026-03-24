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
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 2.1))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))
        
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        
        # Memória de 1000 para suportar análise de 500 sem gargalos
        self.max_history = 1000 
        self.global_pause_until = 0
        
        self.reset()

    def reset(self):
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()
        self.logger.info("🎯 Memória limpa. Iniciando coleta de 500 ticks para análise Sniper.")

    def set_stake(self, new_stake: float):
        self.initial_stake = new_stake
        self.current_stake = new_stake
        self.config_manager.set('trading.stake_amount', new_stake)
        self.config_manager.save_config()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        if current_time < self.global_pause_until: 
            return None
        
        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories: 
            self.tick_histories[symbol] = []
        
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > self.max_history: 
            self.tick_histories[symbol].pop(0)

        # --- REQUISITO DE 500 TICKS PARA ENTRADA ---
        if len(self.tick_histories[symbol]) >= 500:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            status = analysis.get("status")
            
            if status == "ULTRA_CALL": 
                self.logger.info(f"🎯 [SNIPER-PRO] CALL Confirmado em {symbol} (Análise 500t)")
                return self._create_trade_signal("CALL", symbol)
                
            elif status == "ULTRA_PUT": 
                self.logger.info(f"🎯 [SNIPER-PRO] PUT Confirmado em {symbol} (Análise 500t)")
                return self._create_trade_signal("PUT", symbol)
        
        # Log de progresso a cada 100 ticks
        elif len(self.tick_histories[symbol]) % 100 == 0:
            self.logger.info(f"🔍 {symbol}: Analisando histórico... ({len(self.tick_histories[symbol])}/500 ticks)")
            
        return None

    def on_trade_result(self, result: str):
        current_time = time.time()
        
        # Limpa o histórico após cada operação para garantir que o 
        # próximo sinal seja baseado em um mercado "novo"
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [RESULTADO] ✅ VITÓRIA! ---")
            self.global_pause_until = current_time + 60 
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.logger.info(f"--- [RESULTADO] ❌ LOSS ({self.consecutive_losses}). ---")
            
            # Pausa de 3 minutos no loss para evitar o "ruído" do ciclo ruim
            self.global_pause_until = current_time + 180 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
            else:
                self.logger.warning("Limite de Martingale atingido. Protegendo banca (Pausa 10 min).")
                self.global_pause_until = current_time + 600 
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str) -> Dict[str, Any]:
        """Contrato de longa duração (15 ticks) para maior taxa de acerto."""
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "duration": 15, # Duração estendida para segurança
            "duration_unit": "t",
            "symbol": symbol
        }
