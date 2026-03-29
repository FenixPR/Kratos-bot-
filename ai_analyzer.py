import logging
import json
import google.generativeai as genai
from typing import List, Optional, Dict

class AIAnalyzer:
    def __init__(self, config_manager):
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        
        self.api_key = self.config_manager.get("ai.gemini_api_key")
        self.model_name = self.config_manager.get("ai.model", "gemini-1.5-flash")
        self.enable_ai = self.config_manager.get("ai.enable_ai_confirmation", True)
        
        self.model = None
        if self.api_key and self.enable_ai:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.logger.info(f"✅ Gemini IA carregada com modelo {self.model_name}")
            except Exception as e:
                self.logger.error(f"Erro ao configurar Gemini: {e}")
        else:
            self.logger.warning("⚠️ IA Gemini desativada (chave não encontrada ou enable_ai=False)")

    def analyze_market(self, ticks: List[float], symbol: str, technical_indicators: Dict = None) -> Optional[Dict]:
        if not self.model or len(ticks) < 500:
            return None

        # Resumo para não estourar tokens
        last_50 = ticks[-50:]
        prompt = f"""
        Você é um trader profissional especializado em índices sintéticos da Deriv (R_75, R_100, etc.).
        Ativo: {symbol}
        Total de ticks analisados: {len(ticks)}

        Últimos 50 preços: {last_50}

        Indicadores técnicos (já passou filtro pesado de confluências):
        {json.dumps(technical_indicators, indent=2)}

        Missão: Confirmar ou rejeitar o sinal para contrato de 15 ticks (CALL = alta, PUT = baixa).
        Seja EXTREMAMENTE conservador. Só confirme se a probabilidade de acerto for muito alta.
        Se houver qualquer dúvida, reversão ou baixa convicção → responda WAIT.

        Responda **APENAS** com JSON válido:
        {{
            "recommendation": "CALL" | "PUT" | "WAIT",
            "confidence": 0.0-1.0,
            "reasoning": "explicação curta em português"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Limpeza de possível markdown
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(text)
            
            self.logger.info(f"🤖 Gemini [{symbol}] → {result.get('recommendation')} | Confiança: {result.get('confidence',0)*100:.1f}%")
            return result
        except Exception as e:
            self.logger.error(f"Erro Gemini: {e}")
            return None
