import logging
import math

class TechnicalAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_indicators(self, prices):
        if len(prices) < 100: return None
        
        # 1. RSI (Força do Movimento)
        period = 14
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        rsi = 100 - (100 / (1 + (avg_gain/avg_loss))) if avg_loss > 0 else 100

        # 2. Médias Móveis (Direção da Tendência)
        sma_fast = sum(prices[-20:]) / 20
        sma_slow = sum(prices[-100:]) / 100

        # 3. Bandas de Bollinger (Volatilidade Extremada)
        mean = sum(prices[-20:]) / 20
        variance = sum((x - mean) ** 2 for x in prices[-20:]) / 20
        std_dev = math.sqrt(variance)
        upper_band = mean + (2.2 * std_dev) 
        lower_band = mean - (2.2 * std_dev)

        return {
            "rsi": rsi,
            "sma_fast": sma_fast,
            "sma_slow": sma_slow,
            "upper": upper_band,
            "lower": lower_band,
            "price": prices[-1]
        }

    def analyze_trend(self, prices):
        ind = self.calculate_indicators(prices)
        if not ind: return {"status": "WAIT"}

        p = ind["price"]
        
        # --- ESTRATÉGIA ULTRA SNIPER: SEGUIDOR DE TENDÊNCIA ---
        
        # Só entra em CALL se: 
        # Preço acima da média lenta + Preço rompendo a banda SUPERIOR + RSI Forte (>65)
        if p > ind["sma_slow"] and p > ind["upper"] and ind["rsi"] > 65:
            return {"status": "ULTRA_CALL", "rsi": ind["rsi"]}

        # Só entra em PUT se: 
        # Preço abaixo da média lenta + Preço rompendo a banda INFERIOR + RSI Fraco (<35)
        elif p < ind["sma_slow"] and p < ind["lower"] and ind["rsi"] < 35:
            return {"status": "ULTRA_PUT", "rsi": ind["rsi"]}

        return {"status": "NEUTRAL"}
