import websocket, json, logging, threading, time, asyncio

class DerivAPI:
    def __init__(self, app_id, api_token):
        self.app_id, self.api_token = app_id, api_token
        self.ws, self.is_connected, self.callbacks = None, False, {}
        self.loop = None
        self.last_buy_status = None # Novo: Armazena se a compra foi aceita

    def connect(self):
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        self.ws = websocket.WebSocketApp(
            ws_url, on_open=self.on_open, on_message=self.on_message, 
            on_error=lambda ws,e: logging.error(f"Erro WS: {e}"), 
            on_close=lambda ws,a,b: setattr(self, 'is_connected', False)
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
        for _ in range(10):
            if self.is_connected: return True
            time.sleep(1)
        return False

    def on_open(self, ws):
        ws.send(json.dumps({"authorize": self.api_token}))

    def on_message(self, ws, message):
        data = json.loads(message)
        m_type = data.get("msg_type")
        
        if m_type == "authorize":
            if "error" in data: logging.error(f"Auth Erro: {data['error']['message']}")
            else: self.is_connected = True

        elif m_type == "buy":
            # Aqui está o segredo: capturamos a resposta exata da tentativa de compra
            self.last_buy_status = data
            if "buy" in data:
                c_id = data["buy"]["contract_id"]
                self.ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": c_id, "subscribe": 1}))

        elif m_type == "tick" and self.loop:
            asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data["tick"]), self.loop)

        elif m_type == "proposal_open_contract" and self.loop:
            c = data.get("proposal_open_contract")
            if c and c.get("is_sold"):
                res = "WIN" if float(c.get("profit", 0)) > 0 else "LOSS"
                asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](res, c), self.loop)

    def set_callback(self, name, cb, loop):
        self.callbacks[name] = cb; self.loop = loop

    def subscribe_to_ticks(self, s):
        if self.ws: self.ws.send(json.dumps({"ticks": s, "subscribe": 1}))

    async def buy_contract_sync(self, **kwargs):
        """Nova função: Envia a compra e ESPERA a resposta do servidor."""
        self.last_buy_status = None
        req = {"buy": 1, "price": kwargs['amount'], "parameters": {
            "amount": kwargs['amount'], "basis": "stake", "contract_type": kwargs['contract_type'],
            "currency": "USD", "duration": kwargs['duration'], "duration_unit": "t", "symbol": kwargs['symbol']
        }}
        self.ws.send(json.dumps(req))
        
        # Espera até 5 segundos pela resposta da Deriv
        for _ in range(50):
            if self.last_buy_status:
                if "error" in self.last_buy_status:
                    return {"success": False, "error": self.last_buy_status["error"]["message"]}
                return {"success": True, "id": self.last_buy_status["buy"]["contract_id"]}
            await asyncio.sleep(0.1)
        return {"success": False, "error": "Timeout na resposta da Deriv"}

    def disconnect(self): 
        if self.ws: self.ws.close()
