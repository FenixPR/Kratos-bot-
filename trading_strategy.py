import logging
import time
from typing import Optional, Dict, Any, List
from ai_analyzer import AIAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.ai_analyzer = AIAnalyzer()

        # Configurações de stake e martingale
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        # Variáveis de estado da estratégia
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        
        # Histórico por ativo (R_100, R_75, etc.)
        self.tick_histories: Dict[str, List[float]] = {}
        self.last_ai_analysis_times: Dict[str, float] = {}
        self.ai_cooldown = 15  # Segundos entre análises de IA para evitar sinais precipitados
        self.max_history = 100

        self.reset()

    def reset(self):
        """Reseta o estado da estratégia."""
        self.logger.info("A redefinir a estratégia para o estado inicial.")
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        """
        Analisa ticks e só permite entrada se a IA recomendar com alta confiança.
        """
        symbol = "Unknown"
        try:
            if not tick_data or 'quote' not in tick_data:
                return None
            
            symbol = tick_data.get('symbol', 'Unknown')
            quote = float(tick_data['quote'])
            
            # Gerencia o histórico de ticks do ativo
            if symbol not in self.tick_histories:
                self.tick_histories[symbol] = []
                self.last_ai_analysis_times[symbol] = 0
                
            self.tick_histories[symbol].append(quote)
            if len(self.tick_histories[symbol]) > self.max_history:
                self.tick_histories[symbol].pop(0)

            # Só envia para a IA se tivermos pelo menos 50 ticks (amostragem estatística)
            current_time = time.time()
            if len(self.tick_histories[symbol]) >= 50 and (current_time - self.last_ai_analysis_times[symbol]) > self.ai_cooldown:
                self.last_ai_analysis_times[symbol] = current_time
                
                # CHAMADA À IA PARA ANÁLISE PROFUNDA
                ai_rec = self.ai_analyzer.analyze_market(self.tick_histories[symbol], symbol)
                
                # SÓ OPERA SE A IA ESTIVER MUITO CONFIANTE (> 80%)
                if ai_rec:
                    confidence = float(ai_rec.get('confidence', 0))
                    if confidence >= 0.80:
                        rec = ai_rec.get('recommendation')
                        barrier = ai_rec.get('barrier')
                        
                        if rec == "UNDER":
                            self.logger.info(f"--- [ENTRADA IA] Ativo: {symbol} | Recomendação: UNDER | Barreira: {barrier} ---")
                            return self._create_trade_signal("DIGITUNDER", symbol, barrier)
                        elif rec == "OVER":
                            self.logger.info(f"--- [ENTRADA IA] Ativo: {symbol} | Recomendação: OVER | Barreira: {barrier} ---")
                            return self._create_trade_signal("DIGITOVER", symbol, barrier)
                    else:
                        self.logger.info(f"[{symbol}] Aguardando melhor oportunidade de IA (Confiança atual: {confidence*100:.1f}%).")
            
            # Log de progresso do histórico
            elif len(self.tick_histories[symbol]) < 50 and len(self.tick_histories[symbol]) % 10 == 0:
                self.logger.info(f"[{symbol}] Coletando histórico de ticks: {len(self.tick_histories[symbol])}/50")

        except Exception as e:
            self.logger.error(f"Erro ao analisar tick [{symbol}]: {e}")
        
        return None

    def on_trade_result(self, result: str):
        """Atualiza o estado da estratégia com base no resultado."""
        if result == "WIN":
            self.logger.info("--- [RESULTADO] VITÓRIA! ---")
            self.reset()
        else: # LOSS
            self.logger.info("--- [RESULTADO] LOSS. Aplicando Martingale para recuperação. ---")
            self.consecutive_losses += 1
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
                self.is_recovery_mode = True
            else:
                self.logger.warning(f"Limite Martingale atingido. Resetando para proteger saldo.")
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str, barrier: Any) -> Dict[str, Any]:
        """Cria o sinal de trade com os parâmetros definidos pela IA."""
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }
