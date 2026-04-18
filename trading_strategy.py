import time
from technical_analyzer import TechnicalAnalyzer
from ai_analyzer import AIAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.tech_analyzer = TechnicalAnalyzer()
        self.ai_analyzer = AIAnalyzer(config_manager)
        self.config_manager = config_manager
        
        self.initial_stake = 2.0
        self.current_stake = self.initial_stake
        self.tick_histories = {}
        self.consecutive_losses = 0
        self.pause_until = 0
        self.min_confluence = config_manager.get("ai.min_confluence_score", 3)
        self.ai_conf_threshold = config_manager.get("ai.ai_confidence_threshold", 0.65)

    def reset(self):
        self.tick_histories.clear()
        self.current_stake = self.initial_stake

    def set_stake(self, val):
        self.initial_stake = float(val)
        self.current_stake = float(val)

    def analyze_tick(self, tick_data: dict):
        if time.time() < self.pause_until:
            return None
        
        symbol = tick_data.get('symbol')
        quote = float(tick_data.get('quote'))
        
        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > 1000:  # mais histórico para segurança
            self.tick_histories[symbol].pop(0)
        
        count = len(self.tick_histories[symbol])
        if count < 100: # Reduzido para 100 para operar mais rápido após iniciar
            return None

        # Análise técnica robusta
        tech_result = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
        
        if tech_result["status"] == "WAIT" or tech_result["confluence_score"] < self.min_confluence:
            return None

        # Filtros adicionais de tendência e volatilidade
        indicators = tech_result["indicators"]
        last_p = indicators["last_price"]

        # Filtro de tendência principal (EMA200) - Desativado temporariamente para aumentar frequência
        # if tech_result["status"] == "CALL" and last_p < indicators["ema200"]:
        #     return None 
        # if tech_result["status"] == "PUT" and last_p > indicators["ema200"]:
        #     return None

        # Filtro de volatilidade (Bandas de Bollinger)
        # Evitar trades quando as bandas estão muito apertadas (baixa volatilidade)
        if (indicators["upper_bb"] - indicators["lower_bb"]) < (last_p * 0.0005):
            return None # Bandas muito apertadas, indica baixa volatilidade

        # Filtro de RSI para evitar reversões imediatas em zonas extremas
        if tech_result["status"] == "CALL" and indicators["rsi"] > 80:
            return None # Evita CALL se RSI estiver muito sobrecomprado
        if tech_result["status"] == "PUT" and indicators["rsi"] < 20:
            return None # Evita PUT se RSI estiver muito sobrevendido


        # Só chega aqui se o filtro pesado passou → agora IA Gemini (se habilitada)
        if self.ai_analyzer.model and self.config_manager.get("ai.enable_ai_confirmation", True):
            ai_result = self.ai_analyzer.analyze_market(
                self.tick_histories[symbol],
                symbol,
                tech_result["indicators"]
            )
            if ai_result and ai_result.get("recommendation") in ["CALL", "PUT"] and ai_result.get("confidence", 0) >= self.ai_conf_threshold:
                contract_type = ai_result["recommendation"]
            else:
                return None  # IA rejeitou ou baixa confiança
        else:
            # Sem IA → usa o sinal técnico
            if tech_result["status"] not in ["CALL", "PUT"]:
                return None
            contract_type = tech_result["status"]

        # Sinal aprovado
        return {
            "status": "TRADE",
            "symbol": symbol,
            "amount": self.current_stake,
            "contract_type": contract_type,
            "duration": 15,
            "duration_unit": "t",
            "barrier": None # Removido barreira fixa para CALL/PUT padrão
        }

    def on_trade_result(self, result):
        self.tick_histories.clear()
        if result == "WIN":
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
            self.pause_until = time.time() + 60  # Pausa menor após vitória
        else:
            self.consecutive_losses += 1
            # Implementação de Martingale mais robusta
            martingale_multiplier = self.config_manager.get("trading.martingale_multiplier", 2.1)
            max_consecutive_losses = self.config_manager.get("trading.martingale_max_consecutive_losses", 5)

            if self.consecutive_losses < max_consecutive_losses:
                self.current_stake *= martingale_multiplier
            else:
                # Se exceder o limite de perdas consecutivas, reinicia o stake
                self.current_stake = self.initial_stake
                self.consecutive_losses = 0
                # Adicionar notificação ao usuário sobre o reset do martingale

            self.pause_until = time.time() + 180  # Pausa maior após perda para recuperação

        # Notificar o usuário sobre o reset do martingale e a pausa prolongada
        # Isso seria feito via TelegramBot, mas aqui estamos na estratégia
        # A lógica de notificação será tratada na main.py ou telegram_bot.py

