import logging, os, time, asyncio
from dotenv import load_dotenv
from deriv_api import DerivAPI
from telegram_bot import TelegramTradingBot
from trading_strategy import TradingStrategy
from config_manager import ConfigManager

class TradingBotMain:
    def __init__(self):
        load_dotenv()
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.config_manager = ConfigManager("bot_config.json")
        self.deriv_api = DerivAPI(os.getenv("DERIV_APP_ID"), os.getenv("DERIV_API_TOKEN"))
        self.trading_strategy = TradingStrategy(self.config_manager)
        self.telegram_bot = TelegramTradingBot(
            os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID"),
            self.start_trading, self.stop_trading, self.set_profit, self.set_loss, self.set_stake
        )
        self.is_running = False
        self.is_trade_in_progress = False
        self.trade_sent_time = 0
        self.total_profit, self.total_wins, self.total_losses = 0.0, 0, 0

    async def start_trading(self):
        self.is_running = True
        self.is_trade_in_progress = False
        self.trading_strategy.reset()
        await self.telegram_bot.send_status_message("🚀 <b>Sniper Ativado!</b> Iniciando leitura de 500 ticks...")

    async def stop_trading(self): self.is_running = False

    async def set_profit(self, v): self.config_manager.set('trading.target_profit', v)
    async def set_loss(self, v): self.config_manager.set('trading.max_loss', -abs(v))
    async def set_stake(self, v): self.trading_strategy.set_stake(v)

    async def start(self):
        if self.deriv_api.connect():
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())
            for s in ["R_100", "R_75"]: self.deriv_api.subscribe_to_ticks(s)
            
            asyncio.create_task(self.telegram_bot.run_polling())
            while True:
                if self.is_trade_in_progress and (time.time() - self.trade_sent_time) > 60:
                    self.is_trade_in_progress = False
                await asyncio.sleep(5)
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress: return
        res = self.trading_strategy.analyze_tick(tick_data)
        if not res: return
        
        if res["status"] == "PROGRESS":
            await self.telegram_bot.send_status_message(f"🔍 {res['symbol']}: {res['count']}/500 ticks.")
        elif res["status"] == "TRADE":
            self.is_trade_in_progress, self.trade_sent_time = True, time.time()
            if self.deriv_api.buy_contract(**res):
                await self.telegram_bot.send_trade_notification(res)
            else: self.is_trade_in_progress = False

    async def on_trade_result(self, res, details):
        self.is_trade_in_progress = False
        p = float(details.get('profit', 0.0))
        self.total_profit += p
        if res == "WIN": self.total_wins += 1
        else: self.total_losses += 1
        await self.telegram_bot.send_result_notification(res, p, self.total_profit)
        self.trading_strategy.on_trade_result(res)

if __name__ == "__main__":
    asyncio.run(TradingBotMain().start())
