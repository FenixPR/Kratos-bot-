import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Inicializa o analisador gráfico estendido
        self.tech_analyzer = TechnicalAnalyzer()

        # Configurações para Rise/Fall
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 1.0))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 2.1))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        
        self.tick_histories: Dict[str, List[float]] = {}
        # Aumentamos a capacidade de memória para 500 ticks
        self.max_history = 500
        
        self.global_pause_until = 0

        self.reset()

    def reset(self):
        self.logger.info("Estratégia redefinida para o estado inicial.")
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0

    def set_stake(self, new_stake: float):
        self.initial_stake = new_stake
        self.current_stake = new_stake
        self.config_manager.set('trading.stake_amount', new_stake)
        self.config_manager.save_config()
        self.logger.info(f"Valor de entrada (Stake) atualizado para: {new_stake}")

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        
        if current_time < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        try:
            if not tick_data or 'quote' not in tick_data:
                return None
            
            quote = float(tick_data['quote'])
            
            if symbol not in self.tick_histories:
                self.tick_histories[symbol] = []
                
            self.tick_histories[symbol].append(quote)
            
            if len(self.tick_histories[symbol]) > self.max_history:
                self.tick_histories[symbol].pop(0)

            # AGUARDA 60 TICKS (1 minuto) ANTES DE ANALISAR
            if len(self.tick_histories[symbol]) >= 60:
                
                tech_analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
                rsi_status = tech_analysis.get("status")
                rsi_value = tech_analysis.get("rsi", 50)
                
                # --- LÓGICA SNIPER: ALTA PRECISÃO E MUITA PACIÊNCIA ---
                if rsi_status == "STRONG_UPTREND": 
                    self.logger.info(f"[{symbol}] ALINHAMENTO PERFEITO (Alta)! RSI: {rsi_value:.2f} + Médias Móveis -> Entrando CALL.")
                    return self._create_trade_signal("CALL", symbol)
                    
                elif rsi_status == "STRONG_DOWNTREND": 
                    self.logger.info(f"[{symbol}] ALINHAMENTO PERFEITO (Queda)! RSI: {rsi_value:.2f} + Médias Móveis -> Entrando PUT.")
                    return self._create_trade_signal("PUT", symbol)

            # Log de progresso da coleta rigorosa
            elif len(self.tick_histories[symbol]) < 60 and len(self.tick_histories[symbol]) % 15 == 0:
                self.logger.info(f"[{symbol}] Visão Sniper carregando: {len(self.tick_histories[symbol])}/60 ticks")

        except Exception as e:
            self.logger.error(f"Erro ao analisar tick [{symbol}]: {e}")
        
        return None

    def on_trade_result(self, result: str):
        current_time = time.time()
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [RESULTADO] VITÓRIA! Limpando histórico e iniciando nova análise rigorosa. ---")
            # Pode manter a pausa curta, pois ele já vai ser obrigado a esperar 60 segundos coletando dados
            self.global_pause_until = current_time + 10 
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
            
        else: # LOSS
            self.consecutive_losses += 1
            self.logger.info(f"--- [RESULTADO] LOSS ({self.consecutive_losses} seguidos). Cenário instável. Pausa de 60 segundos. ---")
            
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
                self.is_recovery_mode = True
            else:
                self.logger.warning(f"Limite Martingale atingido. Resetando stake e aguardando 2 minutos.")
                self.global_pause_until = current_time + 120 
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "duration": 5, 
            "duration_unit": "t",
            "symbol": symbol
        }