import logging

class TechnicalAnalyzer:
    # Médias móveis estendidas para 14 e 50 ticks para confirmar tendências longas
    def __init__(self, rsi_period=14, sma_short=14, sma_long=50):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period
        self.sma_short = sma_short
        self.sma_long = sma_long

    def calculate_rsi(self, prices):
        if len(prices) < self.rsi_period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period

        if avg_loss == 0: return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_sma(self, prices, period):
        if len(prices) < period: return None
        return sum(prices[-period:]) / period

    def analyze_trend(self, prices):
        rsi = self.calculate_rsi(prices)
        sma_curta = self.calculate_sma(prices, self.sma_short)
        sma_longa = self.calculate_sma(prices, self.sma_long)
        preco_atual = prices[-1]

        if rsi is None or sma_curta is None or sma_longa is None:
            return {"status": "WAIT", "reason": "Coletando dados suficientes"}

        # --- CONFLUÊNCIA DE ALTA (SNIPER CALL) ---
        if preco_atual > sma_curta > sma_longa and rsi > 60:
            return {"status": "STRONG_UPTREND", "rsi": rsi}

        # --- CONFLUÊNCIA DE BAIXA (SNIPER PUT) ---
        elif preco_atual < sma_curta < sma_longa and rsi < 40:
            return {"status": "STRONG_DOWNTREND", "rsi": rsi}

        else:
            return {"status": "NEUTRAL", "rsi": rsi}