import websocket, json, logging, threading, time, asyncio

class DerivAPI:
    def __init__(self, app_id, api_token):
        self.app_id, self.api_token = app_id, api_token
        self.ws, self.is_connected, self.callbacks = None, False, {}

    def connect(self):
        self.ws = websocket.WebSocketApp(
            f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}",
            on_open=self.on_open, on_message=self.on_message
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
        for _ in range(10):
            if self.is_connected: return True
            time.sleep(1)
        return False

    def on_open(self, ws): ws.send(json.dumps({"authorize": self.api_token}))

    def on_message(self, ws, message):
        data = json.loads(message)
        t = data.get("msg_type")
        if t == "authorize": self.is_connected = True
        elif t == "tick" and "tick" in self.callbacks:
            asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data["tick"]), self.loop)
        elif t == "proposal_open_contract":
            c = data.get("proposal_open_contract")
            if c and c.get("is_sold"):
                res = "WIN" if float(c.get("profit", 0)) > 0 else "LOSS"
                asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](res, c), self.loop)

    def set_callback(self, name, cb, loop): self.callbacks[name] = cb; self.loop = loop
    def subscribe_to_ticks(self, s): self.ws.send(json.dumps({"ticks": s, "subscribe": 1}))

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
