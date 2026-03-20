import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Callable, Awaitable, Optional

class TelegramTradingBot:
    def __init__(self, bot_token: str, chat_id: str, 
                 start_callback: Callable[[], Awaitable[None]], 
                 stop_callback: Callable[[], Awaitable[None]],
                 profit_callback: Optional[Callable[[float], Awaitable[None]]] = None,
                 loss_callback: Optional[Callable[[float], Awaitable[None]]] = None,
                 stake_callback: Optional[Callable[[float], Awaitable[None]]] = None): # <-- NOVO
        if not bot_token or not chat_id:
            raise ValueError("O token do bot e o chat_id não podem ser nulos.")
        
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)

        self.application = Application.builder().token(bot_token).build()

        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.profit_callback = profit_callback
        self.loss_callback = loss_callback
        self.stake_callback = stake_callback # <-- NOVO

        self.application.add_handler(CommandHandler("start_bot", self.start_command))
        self.application.add_handler(CommandHandler("stop_bot", self.stop_command))
        self.application.add_handler(CommandHandler("set_profit", self.set_profit_command))
        self.application.add_handler(CommandHandler("set_loss", self.set_loss_command))
        self.application.add_handler(CommandHandler("set_stake", self.set_stake_command)) # <-- NOVO

    def is_authorized(self, update: Update) -> bool:
        return str(update.effective_chat.id) == self.chat_id

    async def handle_unauthorized(self, update: Update):
        chat_id_recebido = update.effective_chat.id
        self.logger.warning(f"Comando ignorado do chat_id não autorizado: {chat_id_recebido}")
        await update.message.reply_text("❌ **Não Autorizado** ❌")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        await update.message.reply_text("▶️ Comando para iniciar as operações recebido. A iniciar o bot...")
        await self.start_callback()

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        await update.message.reply_text("⏸️ Comando para parar as operações recebido. A parar o bot...")
        await self.stop_callback()

    async def set_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        try:
            new_profit = float(context.args[0])
            if new_profit <= 0:
                await update.message.reply_text("❌ Erro: O valor deve ser maior que zero.")
                return
            if self.profit_callback: await self.profit_callback(new_profit)
        except: await update.message.reply_text("⚠️ Use o formato: `/set_profit <valor>`")

    async def set_loss_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        try:
            new_loss = float(context.args[0])
            if new_loss <= 0:
                await update.message.reply_text("❌ Erro: O valor deve ser maior que zero.")
                return
            if self.loss_callback: await self.loss_callback(new_loss)
        except: await update.message.reply_text("⚠️ Use o formato: `/set_loss <valor>`")

    # --- NOVO COMANDO SET_STAKE ---
    async def set_stake_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        try:
            new_stake = float(context.args[0])
            if new_stake <= 0:
                await update.message.reply_text("❌ Erro: O valor da entrada deve ser maior que zero.")
                return
            if self.stake_callback: await self.stake_callback(new_stake)
        except: await update.message.reply_text("⚠️ Use o formato: `/set_stake <valor>`\nExemplo: `/set_stake 0.60`")

    async def run_polling(self):
        self.logger.info("O bot do Telegram está a ouvir por comandos...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    # --- ATUALIZADO PARA RELATÓRIO DE 5 MINUTOS ---
    async def send_periodic_report(self, total_profit: float, total_wins: int, total_losses: int):
        try:
            win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
            message = f"""
📊 <b>Relatório de 5 Minutos</b> 📊

💰 <b>Saldo Atual:</b> ${total_profit:.2f}

✅ Vitórias (Win): {total_wins}
❌ Derrotas (Loss): {total_losses}
🎯 Taxa de Acerto: {win_rate:.2f}%
            """
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar relatório: {e}")
            return False

    async def send_trade_notification(self, trade_params: dict):
        try:
            message = f"⚙️ <b>Executando Operação</b>\nAtivo: {trade_params['symbol']}\nContrato: {trade_params['contract_type']}\nValor: ${trade_params['amount']:.2f}"
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
        except: pass

    async def send_result_notification(self, result: str, profit: float, total_profit: float):
        try:
            emoji = "✅ WIN" if result == "WIN" else "❌ LOSS"
            profit_text = f"+${profit:.2f}" if profit > 0 else f"${profit:.2f}"
            message = f"{emoji} <b>{result}</b>\nLucro/Perda: {profit_text}\nSaldo Total: ${total_profit:.2f}"
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
        except: pass
            
    async def send_status_message(self, status: str):
        try: await self.bot.send_message(chat_id=self.chat_id, text=status, parse_mode='HTML')
        except: pass

    async def test_connection(self):
        try:
            await self.bot.get_me()
            return True
        except: return False