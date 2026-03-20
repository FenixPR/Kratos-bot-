import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Inicializa o analisador técnico ultra-analítico
        self.tech_analyzer = TechnicalAnalyzer()

        # Configurações de stake e gestão de risco (Rise/Fall)
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 1.0))
        # Multiplicador Martingale mais conservador para Rise/Fall (~95% payout)
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 2.1))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        # Variáveis de estado da estratégia
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        
        # Histórico por ativo - Aumentado para 500 para análise de longo prazo
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 500
        
        # Controlo de pausas
        self.global_pause_until = 0

        self.reset()

    def reset(self):
        """Reseta o estado da estratégia para o padrão inicial."""
        self.logger.info("Estratégia redefinida. Voltando ao modo de observação Sniper.")
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0

    def set_stake(self, new_stake: float):
        """Atualiza a stake inicial e salva nas configurações."""
        self.initial_stake = new_stake
        self.current_stake = new_stake
        self.config_manager.set('trading.stake_amount', new_stake)
        self.config_manager.save_config()
        self.logger.info(f"Stake Sniper atualizada para: ${new_stake:.2f}")

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        """
        Analisa cada tick com rigor extremo. 
        Só entra se houver confluência total de indicadores.
        """
        current_time = time.time()
        
        # Verifica se o bot está em pausa obrigatória
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
            
            # Mantém o histórico limpo dentro do limite
            if len(self.tick_histories[symbol]) > self.max_history:
                self.tick_histories[symbol].pop(0)

            # --- GATILHO SNIPER: EXIGE NO MÍNIMO 100 TICKS DE HISTÓRICO ---
            if len(self.tick_histories[symbol]) >= 100:
                
                analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
                status = analysis.get("status")
                rsi_val = analysis.get("rsi", 0)
                
                # ENTRADA DE ALTA PRECISÃO - COMPRA (CALL)
                if status == "ULTRA_CALL": 
                    self.logger.info(f"🎯 [SNIPER] ALVOS ALINHADOS! Ativo: {symbol} | RSI: {rsi_val:.2f} | Sinal: CALL")
                    return self._create_trade_signal("CALL", symbol)
                    
                # ENTRADA DE ALTA PRECISÃO - VENDA (PUT)
                elif status == "ULTRA_PUT": 
                    self.logger.info(f"🎯 [SNIPER] ALVOS ALINHADOS! Ativo: {symbol} | RSI: {rsi_val:.2f} | Sinal: PUT")
                    return self._create_trade_signal("PUT", symbol)
            
            # Feedback de progresso de coleta (Logs a cada 20 ticks)
            elif len(self.tick_histories[symbol]) % 20 == 0:
                self.logger.info(f"🔍 {symbol}: Analisando cenário... ({len(self.tick_histories[symbol])}/100 ticks coletados)")

        except Exception as e:
            self.logger.error(f"Erro na análise de tick do ativo {symbol}: {e}")
        
        return None

    def on_trade_result(self, result: str):
        """Processa o resultado e aplica a gestão de pausa após cada operação."""
        current_time = time.time()
        
        # Limpa o histórico após qualquer operação para forçar nova análise do zero
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [RESULTADO] VITÓRIA! Reiniciando ciclo de observação (Pausa de 30s). ---")
            self.global_pause_until = current_time + 30 
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
            
        else: # LOSS
            self.consecutive_losses += 1
            self.logger.info(f"--- [RESULTADO] LOSS ({self.consecutive_losses}). Mercado instável. Pausa de 60s. ---")
            
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
                self.is_recovery_mode = True
            else:
                self.logger.warning(f"Limite de Martingale atingido. Resetando para proteger a banca.")
                self.global_pause_until = current_time + 300 # Pausa longa de 5 minutos se falhar o Martingale
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str) -> Dict[str, Any]:
        """Gera o pacote de dados para execução da ordem na Deriv."""
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "duration": 5, # Mantido 5 ticks para confirmação da tendência
            "duration_unit": "t",
            "symbol": symbol
        }
