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
        
        # Obter o caminho absoluto para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "bot_config.json")
        
        self.config_manager = ConfigManager(config_path)

        self.deriv_api = DerivAPI(
            app_id=self.config_manager.get("deriv.app_id"),
            api_token=self.config_manager.get("deriv.api_token")
        )
        
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        self.telegram_bot = TelegramTradingBot(
            bot_token=self.config_manager.get("telegram.bot_token"),
            chat_id=self.config_manager.get("telegram.chat_id"),
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
        self.logger.info("Sinal de encerramento recebido.")
        self.stop()

    async def start_trading(self):
        if self.is_running: return
        self.is_running = True
        
        # Zera a sessão sempre que você dá o /start
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.last_report_time = time.time()
        self.trading_strategy.reset()
        
        await self.telegram_bot.send_status_message("✅ <b>Bot INICIADO.</b>\nSessão zerada. Monitorando o mercado no modo Sniper.")

    async def stop_trading(self):
        if not self.is_running: return
        self.is_running = False
        
        mensagem = (f"🛑 <b>Bot PARADO.</b>\n\n"
                    f"Você pode configurar novas metas agora:\n"
                    f"👉 /stopwin [valor]\n"
                    f"👉 /stoploss [valor]\n\n"
                    f"Depois digite /start para iniciar uma nova sessão.")
        
        await self.telegram_bot.send_status_message(mensagem)

    async def set_target_profit(self, new_profit: float):
        self.target_profit = new_profit
        # Salva no arquivo bot_config.json
        self.config_manager.set('trading.target_profit', new_profit)
        self.config_manager.save_config()
        await self.telegram_bot.send_status_message(f"🎯 <b>Stop Win</b> (Meta de Lucro) atualizado para: ${new_profit:.2f}")

    async def set_max_loss(self, new_loss: float):
        self.max_loss = -abs(new_loss) # Garante que fique negativo para o cálculo matemático
        # Salva no arquivo bot_config.json
        self.config_manager.set('trading.max_loss', self.max_loss)
        self.config_manager.save_config()
        await self.telegram_bot.send_status_message(f"🛡️ <b>Stop Loss</b> (Perda Máxima) atualizado para: ${abs(self.max_loss):.2f}")

    async def set_stake_amount(self, new_stake: float):
        self.trading_strategy.set_stake(new_stake)
        await self.telegram_bot.send_status_message(f"💸 Valor de entrada (Stake) atualizado para: ${new_stake:.2f}")

    # --- FUNÇÃO DO SERVIDOR WEB (PARA MANTER ONLINE NO RENDER.COM) ---
    async def web_server(self):
        """Mini servidor para enganar o Render e manter o bot acordado."""
        async def health_check(request):
            return web.Response(text="Bot Kratos 100% Online e Operando!")
            
        app = web.Application()
        app.router.add_get('/', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # O Render fornece a porta automaticamente nesta variável de ambiente
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        self.logger.info(f"🌐 Servidor Web de Manutenção rodando na porta {port}")

    async def start(self):
        try:
            if not await self.telegram_bot.test_connection(): raise Exception("Falha Telegram")
            if not self.deriv_api.connect(): raise Exception("Falha Deriv")
            
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            symbols = ["R_100", "R_75", "R_50", "R_25", "R_10"]
            for s in symbols: self.deriv_api.subscribe_to_ticks(s)
            
            # Inicia o servidor web junto com o bot
            asyncio.create_task(self.web_server())
            
            telegram_task = asyncio.create_task(self.telegram_bot.run_polling())
            await self.telegram_bot.send_status_message("🤖 Bot Conectado.\n\nComandos disponíveis:\n/start\n/stop\n/stopwin [valor]\n/stoploss [valor]\n/set_stake [valor]")
            
            while not self.shutdown_requested:
                current_time = time.time()
                
                # Relatório a cada 5 minutos (300 segundos)
                if self.is_running and (current_time - self.last_report_time) >= 300:
                    self.last_report_time = current_time
                    await self.telegram_bot.send_periodic_report(self.total_profit, self.total_wins, self.total_losses)
                
                await asyncio.sleep(5)
            telegram_task.cancel()
        except Exception as e:
            self.logger.error(f"Erro: {e}")
        finally: 
            self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress: return
        try:
            trade_signal = self.trading_strategy.analyze_tick(tick_data)
            if trade_signal:
                self.is_trade_in_progress = True
                await self.telegram_bot.send_trade_notification(trade_signal)
                self.deriv_api.buy_contract(**trade_signal)
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

            self.is_trade_in_progress = False

            if self.total_profit >= self.target_profit or self.total_profit <= self.max_loss:
                self.is_running = False
                await self.telegram_bot.send_status_message(f"🏁 Meta atingida! Lucro/Perda Final da sessão: ${self.total_profit:.2f}\nO bot foi pausado automaticamente.")
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
