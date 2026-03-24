import logging
import math

class TechnicalAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_indicators(self, prices):
        # Exige pelo menos 200 dados para começar a calcular médias longas
        if len(prices) < 200: return None
        
        # 1. RSI de 21 períodos (Filtra falsos rompimentos)
        period = 21
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        rsi = 100 - (100 / (1 + (avg_gain/avg_loss))) if avg_loss > 0 else 100

        # 2. Médias Móveis de Tendência Pesada (50 e 200)
        sma_fast = sum(prices[-50:]) / 50
        sma_slow = sum(prices[-200:]) / 200

        # 3. Bandas de Bollinger Rígidas (Desvio 2.5 para evitar lateralização)
        mean = sum(prices[-20:]) / 20
        variance = sum((x - mean) ** 2 for x in prices[-20:]) / 20
        std_dev = math.sqrt(variance)
        upper_band = mean + (2.5 * std_dev) 
        lower_band = mean - (2.5 * std_dev)

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
        
        # --- ESTRATÉGIA ULTRA SNIPER 500: SEGUIDOR DE FLUXO ---
        
        # COMPRA (CALL): Preço > Média 200 + Rompe Banda Superior + RSI > 65
        if p > ind["sma_slow"] and p > ind["upper"] and ind["rsi"] > 65:
            return {"status": "ULTRA_CALL", "rsi": ind["rsi"]}

        # VENDA (PUT): Preço < Média 200 + Rompe Banda Inferior + RSI < 35
        elif p < ind["sma_slow"] and p < ind["lower"] and ind["rsi"] < 35:
            return {"status": "ULTRA_PUT", "rsi": ind["rsi"]}

        return {"status": "NEUTRAL"}
