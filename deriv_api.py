import websocket, json, logging, threading, time, asyncio

class DerivAPI:
    def __init__(self, app_id, api_token):
        self.app_id, self.api_token = app_id, api_token
        self.ws, self.is_connected, self.callbacks = None, False, {}
        self.loop = None

    def connect(self):
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        self.ws = websocket.WebSocketApp(
            ws_url, on_open=self.on_open, on_message=self.on_message, 
            on_error=lambda ws,e: logging.error(f"Erro WS: {e}"), 
            on_close=lambda ws,a,b: setattr(self, 'is_connected', False)
        )
        t = threading.Thread(target=self.ws.run_forever, daemon=True)
        t.start()
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
            self.is_connected = True
            logging.info("✅ Conexão Autorizada!")

        elif m_type == "buy":
            # Assim que compra, pede para monitorar o contrato
            if "buy" in data:
                contract_id = data["buy"]["contract_id"]
                self.ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id, "subscribe": 1}))

        elif m_type == "tick" and self.loop:
            asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data["tick"]), self.loop)

        elif m_type == "proposal_open_contract" and self.loop:
            c = data.get("proposal_open_contract")
            # VERIFICA SE O CONTRATO FOI VENDIDO (FINALIZADO)
            if c and c.get("is_sold"):
                res = "WIN" if float(c.get("profit", 0)) > 0 else "LOSS"
                asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](res, c), self.loop)

    def set_callback(self, name, cb, loop):
        self.callbacks[name] = cb
        self.loop = loop

    def subscribe_to_ticks(self, s):
        if self.ws: self.ws.send(json.dumps({"ticks": s, "subscribe": 1}))

    def buy_contract(self, **kwargs):
        try:
            req = {"buy": 1, "price": kwargs['amount'], "parameters": {
                "amount": kwargs['amount'], "basis": "stake", "contract_type": kwargs['contract_type'],
                "currency": "USD", "duration": kwargs['duration'], "duration_unit": "t", "symbol": kwargs['symbol']
            }}
            self.ws.send(json.dumps(req))
            return True
        except: return False

    def disconnect(self): 
        if self.ws: self.ws.close()
