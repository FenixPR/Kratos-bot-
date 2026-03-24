import logging
import os
import sys
import signal
import time
import asyncio
from dotenv import load_dotenv
from aiohttp import web

from deriv_api import DerivAPI
from telegram_bot import TelegramTradingBot
from trading_strategy import TradingStrategy
from config_manager import ConfigManager

class TradingBotMain:
    def __init__(self):
        load_dotenv()
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "bot_config.json")
        self.config_manager = ConfigManager(config_path)

        deriv_app_id = os.getenv("DERIV_APP_ID")
        deriv_token = os.getenv("DERIV_API_TOKEN")
        tele_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tele_chat = os.getenv("TELEGRAM_CHAT_ID")

        self.deriv_api = DerivAPI(app_id=str(deriv_app_id), api_token=str(deriv_token))
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        self.telegram_bot = TelegramTradingBot(
            bot_token=str(tele_token),
            chat_id=str(tele_chat),
            start_callback=self.start_trading,
            stop_callback=self.stop_trading,
            profit_callback=self.set_target_profit,
            loss_callback=self.set_max_loss,
            stake_callback=self.set_stake_amount
        )
        
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.last_report_time = time.time()
        self.trade_sent_time = 0
        
        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    def signal_handler(self, signum, frame):
        self.stop()

    async def start_trading(self):
        self.is_running = True
        self.is_trade_in_progress = False
        self.trading_strategy.reset()
        await self.telegram_bot.send_status_message("🚀 <b>Sniper Ativado!</b> Coletando 500 ticks...")

    async def stop_trading(self):
        self.is_running = False
        await self.telegram_bot.send_status_message("🛑 <b>Bot Parado.</b>")

    async def set_target_profit(self, val): self.config_manager.set('trading.target_profit', val)
    async def set_max_loss(self, val): self.config_manager.set('trading.max_loss', -abs(val))
    async def set_stake_amount(self, val): self.trading_strategy.set_stake(val)

    async def web_server(self):
        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot Online"))
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

    async def start(self):
        try:
            self.deriv_api.connect()
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())
            
            for s in ["R_100", "R_75"]: 
                self.deriv_api.subscribe_to_ticks(s)

            asyncio.create_task(self.web_server())
            asyncio.create_task(self.telegram_bot.run_polling())
            
            while not self.shutdown_requested:
                now = time.time()
                # Auto-destrava se a Deriv sumir por 60s
                if self.is_trade_in_progress and (now - self.trade_sent_time) > 60:
                    self.is_trade_in_progress = False

                # Relatório a cada 1 hora (3600s)
                if self.is_running and (now - self.last_report_time) >= 3600:
                    self.last_report_time = now
                    await self.telegram_bot.send_periodic_report(self.total_profit, self.total_wins, self.total_losses)
                
                await asyncio.sleep(2)
        finally: self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress: return
        
        trade_signal = self.trading_strategy.analyze_tick(tick_data)
        if trade_signal:
            self.is_trade_in_progress = True
            self.trade_sent_time = time.time()
            
            # --- VERIFICAÇÃO REAL DE COMPRA ---
            response = self.deriv_api.buy_contract(**trade_signal)
            
            # Se a resposta contiver 'contract_id' ou for um objeto de sucesso
            if response and not isinstance(response, bool):
                await self.telegram_bot.send_trade_notification(trade_signal)
            else:
                self.is_trade_in_progress = False
                self.logger.error("Compra falhou na Deriv. Verifique Token/Saldo.")

    async def on_trade_result(self, result: str, details: dict):
        self.is_trade_in_progress = False 
        profit = float(details.get('profit', 0.0))
        self.total_profit += profit
        if result == "WIN": self.total_wins += 1
        else: self.total_losses += 1
        await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
        self.trading_strategy.on_trade_result(result)

    def stop(self):
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__": asyncio.run(TradingBotMain().start())
