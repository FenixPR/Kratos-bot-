import logging
import os
import sys
import signal
import time
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv

from deriv_api import DerivAPI
from telegram_bot import TelegramTradingBot
from trading_strategy import TradingStrategy
from config_manager import ConfigManager

class TradingBotMain:
    def __init__(self):
        load_dotenv()
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Obter o caminho absoluto para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "bot_config.json")
        
        self.config_manager = ConfigManager(config_path)
        
        # Prioridade para variáveis de ambiente diretamente (melhor para o Render)
        deriv_app_id = os.getenv("DERIV_APP_ID") or self.config_manager.get("deriv.app_id")
        deriv_token = os.getenv("DERIV_API_TOKEN") or self.config_manager.get("deriv.api_token")

        self.deriv_api = DerivAPI(
            app_id=str(deriv_app_id) if deriv_app_id else None,
            api_token=str(deriv_token) if deriv_token else None
        )
        
        self.telegram_bot = TelegramTradingBot(
            bot_token=self.config_manager.get("telegram.bot_token"),
            chat_id=self.config_manager.get("telegram.chat_id"),
            start_callback=self.start_trading,
            stop_callback=self.stop_trading,
            profit_callback=self.set_target_profit,
            loss_callback=self.set_max_loss
        )
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.last_report_time = time.time()
        self.statistics_interval = self.config_manager.get("notifications.statistics_interval", 3600)
        
        self.target_profit = float(self.config_manager.get('trading.target_profit', 100.0))
        self.max_loss = -abs(float(self.config_manager.get('trading.max_loss', 1000.0)))

        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False


        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logging(self):
        # Configuração simplificada para evitar erro de disco cheio no Windows
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    def run_health_server(self):
        """Servidor HTTP para manter o Render acordado e responder ao health check."""
        app = Flask(__name__)
        @app.route('/')
        def health(): return "Bot is Running", 200
        
        port = int(os.getenv("PORT", 8080))
        self.logger.info(f"Iniciando servidor de Health Check na porta {port}")
        app.run(host='0.0.0.0', port=port)

    def signal_handler(self, signum, frame):
        self.logger.info("Sinal de encerramento recebido.")
        self.stop()

    async def start_trading(self):
        if self.is_running: return
        self.is_running = True
        await self.telegram_bot.send_status_message("✅ Bot iniciado e a monitorar múltiplos ativos.")

    async def stop_trading(self):
        if not self.is_running: return
        self.is_running = False
        await self.telegram_bot.send_status_message("🛑 Bot parado.")

    async def set_target_profit(self, new_profit: float):
        self.target_profit = new_profit
        await self.telegram_bot.send_status_message(f"✅ Meta de lucro: ${new_profit:.2f}")

    async def set_max_loss(self, new_loss: float):
        self.max_loss = -abs(new_loss)
        await self.telegram_bot.send_status_message(f"✅ Stop Loss: ${new_loss:.2f}")
    
    async def start(self):
        try:
            # Inicia servidor de health check em thread separada
            threading.Thread(target=self.run_health_server, daemon=True).start()

            if not await self.telegram_bot.test_connection(): raise Exception("Falha Telegram")
            if not self.deriv_api.connect(): raise Exception("Falha Deriv")
            
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            symbols = ["R_100", "R_75", "R_50", "R_25", "R_10"]
            for s in symbols: self.deriv_api.subscribe_to_ticks(s)
            
            telegram_task = asyncio.create_task(self.telegram_bot.run_polling())
            await self.telegram_bot.send_status_message("🤖 <b>Bot Conectado e Online!</b>\n\n✅ Iniciando operações automaticamente...")
            self.is_running = True
            
            while not self.shutdown_requested:
                if self.is_running and time.time() >= self.trading_strategy.pause_until:
                    self.trading_strategy.reset()
                    self.is_trade_in_progress = False

                # Lógica para enviar relatório horário
                if self.config_manager.get("notifications.send_statistics", False) and \
                   (time.time() - self.last_report_time) >= self.statistics_interval:
                    await self.telegram_bot.send_hourly_report(self.total_profit, self.total_wins, self.total_losses)
                    self.last_report_time = time.time()
                await asyncio.sleep(5)
            telegram_task.cancel()
        except Exception as e:
            self.logger.error(f"Erro: {e}")
        finally: self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress: return
        try:
            trade_signal = self.trading_strategy.analyze_tick(tick_data)
            if trade_signal:
                self.is_trade_in_progress = True
                await self.telegram_bot.send_trade_notification(trade_signal)
                # Extrai os parâmetros necessários para buy_contract
                contract_params = {
                    "contract_type": trade_signal["contract_type"],
                    "amount": trade_signal["amount"],
                    "barrier": trade_signal["barrier"], # Agora incluído
                    "duration": trade_signal["duration"],
                    "duration_unit": trade_signal["duration_unit"],
                    "symbol": trade_signal["symbol"]
                }
                self.deriv_api.buy_contract(**contract_params)
        except Exception as e:
            self.logger.error(f"Erro tick: {e}")
            self.is_trade_in_progress = False

    async def on_trade_result(self, result: str, details: dict):
        try:
            profit = float(details.get('profit', 0.0))
            self.total_profit += profit
            if result == "WIN": self.total_wins += 1
            else: self.total_losses += 1

            await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
            self.trading_strategy.on_trade_result(result)

            # LIBERA SEMPRE A OPERAÇÃO APÓS O RESULTADO
            self.is_trade_in_progress = False

            if self.trading_strategy.consecutive_losses >= 2:
                # A pausa agora é gerenciada exclusivamente pela TradingStrategy
                self.is_trade_in_progress = True # Mantém travado durante a pausa
                await self.telegram_bot.send_status_message("⚠️ Pausa de 5 min (2 perdas).")
            elif self.total_profit >= self.target_profit or self.total_profit <= self.max_loss:
                self.is_running = False
                await self.telegram_bot.send_status_message(f"🏁 Meta/Stop atingido. Lucro: {self.total_profit:.2f}")
        except Exception as e:
            self.logger.error(f"Erro resultado: {e}")
            self.is_trade_in_progress = False

    def stop(self):
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__":
    bot = TradingBotMain()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        bot.stop()
