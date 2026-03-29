import json
import os
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file: Optional[str] = None):
        if config_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_file = os.path.join(script_dir, "bot_config.json")
        else:
            self.config_file = config_file
            
        self.logger = logging.getLogger(__name__)
        
        # Configuração padrão (nunca coloque chaves reais aqui)
        self.default_config = {
            "trading": { ... },      # (mantém tudo igual ao que eu te passei antes)
            "strategy": { ... },
            "notifications": { ... },
            "advanced": { ... },
            "telegram": { ... },
            "deriv": { ... },
            "ai": {
                "gemini_api_key": "",           # ← fica vazio
                "model": "gemini-1.5-flash",
                "enable_ai_confirmation": True,
                "min_confluence_score": 4,
                "ai_confidence_threshold": 0.75
            }
        }
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                merged = self._merge_configs(self.default_config, config)
            else:
                merged = self.default_config.copy()
            
            # === SOBRESCREVE COM ENVIRONMENT VARIABLES (prioridade máxima) ===
            if os.getenv("GEMINI_API_KEY"):
                merged.setdefault("ai", {})["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
                self.logger.info("✅ GEMINI_API_KEY carregada do Environment Variable do Render")
            
            # (opcional: você pode adicionar mais chaves aqui no futuro)
            # if os.getenv("TELEGRAM_BOT_TOKEN"):
            #     merged["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
            
            return merged
        except Exception as e:
            self.logger.error(f"Erro ao carregar config: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Optional[Dict[str, Any]] = None):
        # Nunca salva chaves de env no JSON
        config_to_save = config or self.config
        # Remove chave real antes de salvar (segurança extra)
        if "ai" in config_to_save and "gemini_api_key" in config_to_save["ai"]:
            if len(config_to_save["ai"]["gemini_api_key"]) > 20:  # parece chave real
                config_to_save["ai"]["gemini_api_key"] = ""  
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar config: {e}")
    
    # (mantenha os métodos _merge_configs e get/set iguais aos que eu te passei antes)
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def get(self, key_path: str, default: Any = None) -> Any:
        try:
            keys = key_path.split('.')
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        # ... (mantém igual)
        pass
