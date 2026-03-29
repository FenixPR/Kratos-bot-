import logging
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

class TelegramTradingBot:
    def __init__(self, bot_token, chat_id, start_cb, stop_cb, profit_cb, loss_cb, stake_cb):
        self.application = ApplicationBuilder().token(bot_token).build()
        self.chat_id = chat_id
        self.start_cb = start_cb
        self.stop_cb = stop_cb
        self.profit_cb = profit_cb
        self.loss_cb = loss_cb
        self.stake_cb = stake_cb
        self.logger = logging.getLogger(__name__)
        self._add_handlers()

    def _add_handlers(self):
        self.application.add_handler(CommandHandler("start", self._start))
        self.application.add_handler(CommandHandler("stop", self._stop))
        self.application.add_handler(CommandHandler("stopwin", self._set_profit))
        self.application.add_handler(CommandHandler("stoploss", self._set_loss))
        self.application.add_handler(CommandHandler("set_stake", self._set_stake))

    async def _start(self, u, c): await self.start_cb()
    async def _stop(self, u, c): await self.stop_cb()
    async def _set_profit(self, u, c): await self.profit_cb(float(c.args[0]))
    async def _set_loss(self, u, c): await self.loss_cb(float(c.args[0]))
    async def _set_stake(self, u, c): await self.stake_cb(float(c.args[0]))

    async def send_status_message(self, text):
        await self.application.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.HTML)

    async def send_trade_notification(self, trade):
        msg = f"⚙️ <b>Executando Operação</b>\nAtivo: {trade['symbol']}\nContrato: {trade['contract_type']}\nValor: ${trade['amount']}"
        await self.send_status_message(msg)

    async def send_result_notification(self, res, p, total):
        icon = "✅" if res == "WIN" else "❌"
        msg = f"{icon} <b>Resultado: {res}</b>\nLucro: ${p:.2f}\nAcumulado: ${total:.2f}"
        await self.send_status_message(msg)

    async def run_polling(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
