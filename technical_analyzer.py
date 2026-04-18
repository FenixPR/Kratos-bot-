import math

class TechnicalAnalyzer:
    def calculate_indicators(self, prices):
        if len(prices) < 100:
            return None
        
        # RSI (14) - Mais robusto
        period_rsi = 14
        if len(prices) < period_rsi + 1: return None

        # Calcula as mudanças de preço
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # Calcula ganhos e perdas para o período RSI
        avg_gain = sum(c for c in changes[-period_rsi:] if c > 0) / period_rsi
        avg_loss = sum(abs(c) for c in changes[-period_rsi:] if c < 0) / period_rsi

        if avg_loss == 0: # Evita divisão por zero
            rsi = 100 if avg_gain > 0 else 50
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Bollinger (20, 2.5)
        period_bb = 20
        sma_bb = sum(prices[-period_bb:]) / period_bb
        std = math.sqrt(sum((x - sma_bb) ** 2 for x in prices[-period_bb:]) / period_bb)
        upper_bb = sma_bb + (2.5 * std)
        lower_bb = sma_bb - (2.5 * std)
        
        # EMAs
        ema9 = self._calculate_ema(prices, 9)
        ema21 = self._calculate_ema(prices, 21)
        ema50 = self._calculate_ema(prices, 50)
        ema200 = self._calculate_ema(prices, 100) # Reduzido para 100 para operar mais rápido
        
        # Verifica se todas as EMAs foram calculadas com sucesso
        if any(e is None for e in [ema9, ema21, ema50, ema200]): return None

        # MACD
        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        if ema12 is None or ema26 is None: return None
        macd_line = ema12 - ema26
        # A linha de sinal do MACD requer uma série de valores MACD, o que é complexo para este método.
        # Por simplicidade, usaremos apenas a linha MACD para a análise de confluência.
        # macd_signal = self._calculate_ema([macd_line], 9) # Removido para evitar complexidade e erro

        
        # Stochastic (14,3)
        stoch_k = self._stochastic_k(prices[-14:])
        
        last_price = prices[-1]
        
        return {
            "rsi": round(rsi, 2),
            "upper_bb": round(upper_bb, 5),
            "lower_bb": round(lower_bb, 5),
            "ema9": round(ema9, 5),
            "ema21": round(ema21, 5),
            "ema50": round(ema50, 5),
            "ema200": round(ema200, 5),
            "macd_line": round(macd_line, 5),
            "stoch_k": round(stoch_k, 2),
            "last_price": round(last_price, 5)
        }

    def _calculate_ema(self, prices, period):
        if not prices or len(prices) < period: return None
        
        ema = sum(prices[:period]) / period # SMA inicial para EMA
        for price in prices[period:]:
            ema = (price - ema) * (2 / (period + 1)) + ema
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

        # Confluência 1: Momentum forte (RSI) - Zonas de exaustão
        if ind["rsi"] > 70: # Sobrecomprado
            score += 1
            reasons.append("RSI sobrecomprado (PUT)")
        elif ind["rsi"] < 30: # Sobrevendido
            score += 1
            reasons.append("RSI sobrevendido (CALL)")

        # Confluência 2: Breakout Bollinger
        if last_p > ind["upper_bb"]:
            score += 1
            reasons.append("Breakout Upper BB")
        elif last_p < ind["lower_bb"]:
            score += 1
            reasons.append("Breakout Lower BB")

        # Confluência 3: Cruzamento de EMAs (Tendência)
        if ind["ema9"] > ind["ema21"] and ind["ema21"] > ind["ema50"]:
            score += 1
            reasons.append("EMAs alinhadas para alta")
        elif ind["ema9"] < ind["ema21"] and ind["ema21"] < ind["ema50"]:
            score += 1
            reasons.append("EMAs alinhadas para baixa")

        # Confluência 4: MACD (linha zero)
        if ind["macd_line"] > 0:
            score += 1
            reasons.append("MACD acima de zero (alta)")
        elif ind["macd_line"] < 0:
            score += 1
            reasons.append("MACD abaixo de zero (baixa)")

        # Confluência 5: Stochastic (zonas de exaustão)
        if ind["stoch_k"] > 80:
            score += 1
            reasons.append("Stoch sobrecomprado (PUT)")
        elif ind["stoch_k"] < 20:
            score += 1
            reasons.append("Stoch sobrevendido (CALL)")

        # Confluência 6: Preço vs EMA200 (Tendência de longo prazo)
        if last_p > ind["ema200"]:
            score += 1
            reasons.append("Preço acima EMA200 (alta)")
        elif last_p < ind["ema200"]:
            score += 1
            reasons.append("Preço abaixo EMA200 (baixa)")

        # Determina o status com base na confluência e direção das EMAs
        status = "WAIT"
        if score >= 3:
            if ind["ema9"] > ind["ema21"] and ind["ema21"] > ind["ema50"] and ind["rsi"] < 70 and ind["stoch_k"] < 80: # Filtro para evitar sobrecompra
                status = "CALL"
            elif ind["ema9"] < ind["ema21"] and ind["ema21"] < ind["ema50"] and ind["rsi"] > 30 and ind["stoch_k"] > 20: # Filtro para evitar sobrevenda
                status = "PUT"

        return {
            "status": status,
            "confluence_score": score,
            "indicators": ind,
            "reason": " + ".join(reasons[:4]) if reasons else "Sem confluência"
        }
