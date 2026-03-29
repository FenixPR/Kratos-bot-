import math

class TechnicalAnalyzer:
    def calculate_indicators(self, prices):
        if len(prices) < 200: return None
        period = 21
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_g = sum(gains) / period
        avg_l = sum(losses) / period
        rsi = 100 - (100 / (1 + (avg_g/avg_l))) if avg_l > 0 else 100
        sma_200 = sum(prices[-200:]) / 200
        mean_20 = sum(prices[-20:]) / 20
        std = math.sqrt(sum((x - mean_20)**2 for x in prices[-20:]) / 20)
        return {"rsi": rsi, "sma": sma_200, "up": mean_20 + (2.5 * std), "low": mean_20 - (2.5 * std), "p": prices[-1]}

    def analyze_trend(self, prices):
        ind = self.calculate_indicators(prices)
        if not ind: return {"status": "WAIT"}
        if ind["p"] > ind["sma"] and ind["p"] > ind["up"] and ind["rsi"] > 65: return {"status": "ULTRA_CALL"}
        if ind["p"] < ind["sma"] and ind["p"] < ind["low"] and ind["rsi"] < 35: return {"status": "ULTRA_PUT"}
        return {"status": "NEUTRAL"}
