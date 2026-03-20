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

        deriv_app_id = os.getenv("DERIV_APP_ID") or self.config_manager.get("deriv.app_id")
        deriv_token = os.getenv("DERIV_API_TOKEN") or self.config_manager.get("deriv.api_token")
        tele_token = os.getenv("TELEGRAM_BOT_TOKEN") or self.config_manager.get("telegram.bot_token")
        tele_chat = os.getenv("TELEGRAM_CHAT_ID") or self.config_manager.get("telegram.chat_id")

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
        self.target_profit = float(self.config_manager.get('trading.target_profit', 100.0))
        self.max_loss = -abs(float(self.config_manager.get('trading.max_loss', 1000.0)))

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
        if self.is_running: return
        self.is_running = True
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.last_report_time = time.time()
        self.trading_strategy.reset()
        await self.telegram_bot.send_status_message("✅ <b>Bot INICIADO.</b> Sessão Sniper ativa.")

    async def stop_trading(self):
        if not self.is_running: return
        self.is_running = False
        await self.telegram_bot.send_status_message("🛑 <b>Bot PARADO.</b>")

    async def set_target_profit(self, new_profit: float):
        self.target_profit = new_profit
        self.config_manager.set('trading.target_profit', new_profit)
        self.config_manager.save_config()
        await self.telegram_bot.send_status_message(f"🎯 Stop Win: ${new_profit:.2f}")

    async def set_max_loss(self, new_loss: float):
        self.max_loss = -abs(new_loss)
        self.config_manager.set('trading.max_loss', self.max_loss)
        self.config_manager.save_config()
        await self.telegram_bot.send_status_message(f"🛡️ Stop Loss: ${abs(self.max_loss):.2f}")

    async def set_stake_amount(self, new_stake: float):
        self.trading_strategy.set_stake(new_stake)
        await self.telegram_bot.send_status_message(f"💸 Stake: ${new_stake:.2f}")

    async def web_server(self):
        async def health_check(request): return web.Response(text="Bot Online")
        app = web.Application()
        app.router.add_get('/', health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        await web.TCPSite(runner, '0.0.0.0', port).start()

    async def start(self):
        try:
            if not await self.telegram_bot.test_connection(): raise Exception("Erro Telegram")
            if not self.deriv_api.connect(): raise Exception("Erro Deriv")
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())
            for s in ["R_100", "R_75", "R_50", "R_25", "R_10"]: self.deriv_api.subscribe_to_ticks(s)
            asyncio.create_task(self.web_server())
            asyncio.create_task(self.telegram_bot.run_polling())
            await self.telegram_bot.send_status_message("🤖 <b>Bot Conectado.</b>")
            while not self.shutdown_requested:
                if self.is_running and (time.time() - self.last_report_time) >= 300:
                    self.last_report_time = time.time()
                    await self.telegram_bot.send_periodic_report(self.total_profit, self.total_wins, self.total_losses)
                await asyncio.sleep(5)
        finally: self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress: return
        trade_signal = self.trading_strategy.analyze_tick(tick_data)
        if trade_signal:
            self.is_trade_in_progress = True
            await self.telegram_bot.send_trade_notification(trade_signal)
            self.deriv_api.buy_contract(**trade_signal)

    async def on_trade_result(self, result: str, details: dict):
        self.is_trade_in_progress = False # DESTRAVA IMEDIATA
        profit = float(details.get('profit', 0.0))
        self.total_profit += profit
        if result == "WIN": self.total_wins += 1
        else: self.total_losses += 1
        await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
        self.trading_strategy.on_trade_result(result)
        if self.total_profit >= self.target_profit or self.total_profit <= self.max_loss:
            self.is_running = False
            await self.telegram_bot.send_status_message("🏁 Meta Atingida. Bot Pausado.")

    def stop(self):
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__": asyncio.run(TradingBotMain().start())
