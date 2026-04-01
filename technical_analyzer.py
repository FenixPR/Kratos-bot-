import math

class TechnicalAnalyzer:
    def calculate_indicators(self, prices):
        if len(prices) < 200:
            return None
        
        # RSI (14)
        period = 14
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_g = sum(gains) / period if sum(gains) > 0 else 0.0001
        avg_l = sum(losses) / period if sum(losses) > 0 else 0.0001
        rsi = 100 - (100 / (1 + (avg_g / avg_l)))
        
        # Bollinger (20, 2.5)
        period_bb = 20
        sma_bb = sum(prices[-period_bb:]) / period_bb
        std = math.sqrt(sum((x - sma_bb) ** 2 for x in prices[-period_bb:]) / period_bb)
        upper_bb = sma_bb + (2.5 * std)
        lower_bb = sma_bb - (2.5 * std)
        
        # EMA 21
        ema = self._calculate_ema(prices, 21)
        
        # MACD simples
        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        macd = ema12 - ema26
        signal = self._calculate_ema([ema12 - ema26 for _ in range(9)], 9)  # aproximado
        
        # Stochastic (14,3)
        stoch_k = self._stochastic_k(prices[-14:])
        
        last_price = prices[-1]
        
        return {
            "rsi": round(rsi, 2),
            "upper_bb": round(upper_bb, 5),
            "lower_bb": round(lower_bb, 5),
            "ema21": round(ema, 5),
            "macd": round(macd, 5),
            "stoch_k": round(stoch_k, 2),
            "last_price": round(last_price, 5)
        }

    def _calculate_ema(self, prices, period):
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def _stochastic_k(self, prices):
        if len(prices) < 14:
            return 50
        low = min(prices)
        high = max(prices)
        return ((prices[-1] - low) / (high - low)) * 100 if high != low else 50

    def analyze_trend(self, prices):
        ind = self.calculate_indicators(prices)
        if not ind:
            return {"status": "WAIT", "confluence_score": 0, "indicators": {}, "reason": "Dados insuficientes"}

        score = 0
        reasons = []

        last_p = ind["last_price"]

        # Confluência 1: Momentum forte (RSI)
        if last_p > ind["ema21"] and ind["rsi"] > 55:
            score += 1
            reasons.append("RSI bullish")
        elif last_p < ind["ema21"] and ind["rsi"] < 45:
            score += 1
            reasons.append("RSI bearish")

        # Confluência 2: Breakout Bollinger
        if last_p > ind["upper_bb"]:
            score += 1
            reasons.append("Breakout Upper BB")
        elif last_p < ind["lower_bb"]:
            score += 1
            reasons.append("Breakout Lower BB")

        # Confluência 3: EMA
        if last_p > ind["ema21"]:
            score += 1
            reasons.append("Acima EMA21")
        elif last_p < ind["ema21"]:
            score += 1
            reasons.append("Abaixo EMA21")

        # Confluência 4: MACD
        if ind["macd"] > 0:
            score += 1
            reasons.append("MACD positivo")
        elif ind["macd"] < 0:
            score += 1
            reasons.append("MACD negativo")

        # Confluência 5: Stochastic
        if ind["stoch_k"] > 80:
            score += 1
            reasons.append("Stoch overbought (CALL)")
        elif ind["stoch_k"] < 20:
            score += 1
            reasons.append("Stoch oversold (PUT)")

        # Confluência 6: Preço vs SMA recente
        sma200 = sum(prices[-200:]) / 200
        if (last_p > sma200 and last_p > ind["ema21"]) or (last_p < sma200 and last_p < ind["ema21"]):
            score += 1
            reasons.append("Alinhamento tendência")

        status = "CALL" if score >= 4 and last_p > ind["ema21"] else \
                 "PUT" if score >= 4 and last_p < ind["ema21"] else "WAIT"

        return {
            "status": status,
            "confluence_score": score,
            "indicators": ind,
            "reason": " + ".join(reasons[:4]) if reasons else "Sem confluência"
        }
