import logging
import math

class TechnicalAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_indicators(self, prices):
        if len(prices) < 200: return None
        
        # RSI de 21 períodos
        period = 21
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        rsi = 100 - (100 / (1 + (avg_gain/avg_loss))) if avg_loss > 0 else 100

        # SMA 200 e Bandas de Bollinger (Desvio 2.5)
        sma_200 = sum(prices[-200:]) / 200
        mean_20 = sum(prices[-20:]) / 20
        variance = sum((x - mean_20) ** 2 for x in prices[-20:]) / 20
        std_dev = math.sqrt(variance)
        upper = mean_20 + (2.5 * std_dev)
        lower = mean_20 - (2.5 * std_dev)

        return {"rsi": rsi, "sma": sma_200, "upper": upper, "lower": lower, "price": prices[-1]}

    def analyze_trend(self, prices):
        ind = self.calculate_indicators(prices)
        if not ind: return {"status": "WAIT"}
        p = ind["price"]
        
        if p > ind["sma"] and p > ind["upper"] and ind["rsi"] > 65:
            return {"status": "ULTRA_CALL"}
        elif p < ind["sma"] and p < ind["lower"] and ind["rsi"] < 35:
            return {"status": "ULTRA_PUT"}
        return {"status": "NEUTRAL"}
