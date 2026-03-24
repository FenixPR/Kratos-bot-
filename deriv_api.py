import websocket
import json
import logging
import threading
import time
import asyncio

class DerivAPI:
    def __init__(self, app_id, api_token):
        self.app_id = app_id
        self.api_token = api_token
        self.ws = None
        self.callbacks = {}
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self.loop = None

    def set_callback(self, name, callback, loop):
        """Define os callbacks para eventos de Tick e Resultado de Trade."""
        self.callbacks[name] = callback
        self.loop = loop

    def connect(self):
        """Estabelece a conexão WebSocket com a Deriv."""
        self.logger.info("A tentar conectar à Deriv API...")
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        
        # Aguarda conexão estabilizar
        retry = 0
        while not self.is_connected and retry < 10:
            time.sleep(1)
            retry += 1
            
        return self.is_connected

    def on_open(self, ws):
        self.logger.info("Websocket connected")
        # Autorização imediata ao abrir
        auth_data = {"authorize": self.api_token}
        self.ws.send(json.dumps(auth_data))

    def on_message(self, ws, message):
        data = json.loads(message)
        msg_type = data.get("msg_type")

        if msg_type == "authorize":
            if "error" in data:
                self.logger.error(f"Erro de autorização: {data['error']['message']}")
            else:
                self.logger.info("Autorização bem-sucedida")
                self.is_connected = True

        elif msg_type == "tick":
            if "tick" in data and "tick" in self.callbacks:
                asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data["tick"]), self.loop)

        elif msg_type == "proposal_open_contract":
            contract = data.get("proposal_open_contract")
            if contract and contract.get("is_sold"):
                result = "WIN" if float(contract.get("profit", 0)) > 0 else "LOSS"
                if "trade_result" in self.callbacks:
                    asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](result, contract), self.loop)

    def subscribe_to_ticks(self, symbol):
        """Inscreve o bot para receber ticks em tempo real de um ativo."""
        if self.is_connected:
            request = {"ticks": symbol, "subscribe": 1}
            self.ws.send(json.dumps(request))

    def buy_contract(self, contract_type, amount, duration, duration_unit, symbol):
        """
        Executa a compra real. 
        RETORNA: O objeto da compra se sucesso, False se erro.
        """
        if not self.is_connected:
            self.logger.error("API não conectada. Impossível comprar.")
            return False

        buy_request = {
            "buy": 1,
            "price": float(amount),
            "parameters": {
                "amount": float(amount),
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": int(duration),
                "duration_unit": duration_unit,
                "symbol": symbol
            }
        }

        try:
            # Enviamos a ordem e aguardamos a resposta de confirmação de compra
            # Como o WebSocketApp é assíncrono, usamos um mecanismo de envio direto
            self.ws.send(json.dumps(buy_request))
            self.logger.info(f"Ordem de {contract_type} enviada para {symbol} no valor de ${amount}")
            
            # Nota: O resultado final (Win/Loss) virá pelo callback 'proposal_open_contract'
            # Esta função retorna True apenas para confirmar que a mensagem foi disparada.
            # No main.py, a trava is_trade_in_progress segurará o bot.
            return True
        except Exception as e:
            self.logger.error(f"Erro ao disparar ordem de compra: {e}")
            return False

    def on_error(self, ws, error):
        self.logger.error(f"Erro no WebSocket: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.info("Conexão encerrada")
        self.is_connected = False

    def disconnect(self):
        if self.ws:
            self.ws.close()
