import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Analisador gráfico de alta precisão
        self.tech_analyzer = TechnicalAnalyzer()
        
        # Configurações de Gestão (Banca e Martingale)
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 1.0))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 2.1))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))
        
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        
        # Aumentamos a memória para 600 ticks para garantir fluidez na análise de 300
        self.max_history = 600 
        self.global_pause_until = 0
        
        self.reset()

    def reset(self):
        """Reseta o estado do robô para uma nova sessão limpa."""
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()
        self.logger.info("🎯 Sniper Resetado. Iniciando nova fase de observação profunda.")

    def set_stake(self, new_stake: float):
        """Atualiza o valor da entrada inicial."""
        self.initial_stake = new_stake
        self.current_stake = new_stake
        self.config_manager.set('trading.stake_amount', new_stake)
        self.config_manager.save_config()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        """Analisa o gráfico com rigor extremo antes de qualquer disparo."""
        current_time = time.time()
        
        # Respeita pausas de segurança (pós-win ou pós-loss)
        if current_time < self.global_pause_until: 
            return None
        
        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories: 
            self.tick_histories[symbol] = []
        
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > self.max_history: 
            self.tick_histories[symbol].pop(0)

        # --- RIGOR SNIPER: EXIGÊNCIA DE 300 TICKS (APROX. 7-10 MINUTOS) ---
        if len(self.tick_histories[symbol]) >= 300:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            status = analysis.get("status")
            rsi_val = analysis.get("rsi", 0)
            
            if status == "ULTRA_CALL": 
                self.logger.info(f"🎯 [SNIPER-10T] ALVOS ALINHADOS EM {symbol}! RSI: {rsi_val:.2f} | Disparando CALL.")
                return self._create_trade_signal("CALL", symbol)
                
            elif status == "ULTRA_PUT": 
                self.logger.info(f"🎯 [SNIPER-10T] ALVOS ALINHADOS EM {symbol}! RSI: {rsi_val:.2f} | Disparando PUT.")
                return self._create_trade_signal("PUT", symbol)
        
        # Feedback de progresso nos logs a cada 50 ticks coletados
        elif len(self.tick_histories[symbol]) % 50 == 0:
            self.logger.info(f"🔍 {symbol}: Carregando análise profunda... ({len(self.tick_histories[symbol])}/300 ticks)")
            
        return None

    def on_trade_result(self, result: str):
        """Gerencia o resultado e limpa a visão para evitar entradas viciadas."""
        current_time = time.time()
        
        # Limpamos o histórico para forçar uma análise totalmente nova do próximo ciclo
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [RESULTADO] ✅ VITÓRIA! ---")
            # Pausa de 1 minuto para o gráfico respirar após o Win
            self.global_pause_until = current_time + 60 
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.logger.info(f"--- [RESULTADO] ❌ LOSS ({self.consecutive_losses}). Mercado perigoso. ---")
            
            # Pausa de 3 minutos após Loss para esperar a mudança de ciclo do mercado
            self.global_pause_until = current_time + 180 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
                self.logger.info(f"🚀 Próxima entrada Martingale: ${self.current_stake:.2f}")
            else:
                self.logger.warning("🚨 Limite de Martingale atingido. Pausa longa de 10 min para proteção.")
                self.global_pause_until = current_time + 600 
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str) -> Dict[str, Any]:
        """Configura o contrato com a duração de 10 Ticks para segurança."""
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "duration": 10, # Aumentado de 5 para 10 para evitar o 'ruído' de empate
            "duration_unit": "t",
            "symbol": symbol
        }
