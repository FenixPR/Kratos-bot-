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
        self.is_connected = False
        self.callbacks = {}
        self.loop = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
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
        
        for _ in range(10):
            if self.is_connected: return True
            time.sleep(1)
        return False

    def on_open(self, ws):
        self.ws.send(json.dumps({"authorize": self.api_token}))

    def on_message(self, ws, message):
        data = json.loads(message)
        msg_type = data.get("msg_type")
        
        if msg_type == "authorize":
            if "error" in data:
                logging.error(f"Erro Auth: {data['error']['message']}")
            else:
                self.is_connected = True
                logging.info("✅ Deriv Autorizada e Conectada!")

        elif msg_type == "tick":
            if "tick" in data and "tick" in self.callbacks:
                asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data["tick"]), self.loop)

        elif msg_type == "proposal_open_contract":
            c = data.get("proposal_open_contract")
            if c and c.get("is_sold"):
                res = "WIN" if float(c.get("profit", 0)) > 0 else "LOSS"
                asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](res, c), self.loop)

    def set_callback(self, name, cb, loop):
        self.callbacks[name] = cb
        self.loop = loop

    def subscribe_to_ticks(self, symbol):
        if self.ws:
            self.ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))

    def buy_contract(self, **kwargs):
        try:
            req = {
                "buy": 1, 
                "price": kwargs['amount'], 
                "parameters": {
                    "amount": kwargs['amount'], 
                    "basis": "stake", 
                    "contract_type": kwargs['contract_type'],
                    "currency": "USD", 
                    "duration": kwargs['duration'], 
                    "duration_unit": "t", 
                    "symbol": kwargs['symbol']
                }
            }
            self.ws.send(json.dumps(req))
            return True
        except Exception as e:
            logging.error(f"Erro ao comprar: {e}")
            return False

    def on_error(self, ws, error): logging.error(f"WS Error: {error}")
    def on_close(self, ws, a, b): self.is_connected = False
    def disconnect(self): 
        if self.ws: self.ws.close()
