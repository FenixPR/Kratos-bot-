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
        self.min_confluence = config_manager.get("ai.min_confluence_score", 4)
        self.ai_conf_threshold = config_manager.get("ai.ai_confidence_threshold", 0.75)

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
        if count < 500:
            return None

        # Análise técnica pesada
        tech_result = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
        
        if tech_result["status"] == "WAIT" or tech_result["confluence_score"] < self.min_confluence:
            return None

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
            "barrier": "5" # Adicionado um valor de barreira padrão para contratos de dígito
        }

    def on_trade_result(self, result):
        self.tick_histories.clear()
        if result == "WIN":
            self.current_stake = self.initial_stake
            self.consecutive_losses = 0
            self.pause_until = time.time() + 60
        else:
            self.current_stake *= 2.1
            self.consecutive_losses += 1
            self.pause_until = time.time() + 120
