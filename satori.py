import asyncio

import aiohttp
from onebot_adapter import AdapterOnebot
from config import Config
from aiohttp import web
import json
import uuid

from tool import remove_json_null

class Satori:
    def __init__(self) -> None:
        self._config:Config = Config()
        self.adapterlist = []
        self.wsmap = {}

    async def _get_adapter(self,platform,self_id):
        ''' 用于获取适配器 '''
        for adapter in self.adapterlist:
            info = adapter["info"]
            for bot in info:
                if self_id == bot["self_id"] and bot["platform"] == platform:
                    return adapter["adapter"]
        return None
    
    async def ws_send_json(ws,js) -> None:
        js = remove_json_null(js)
        print("--------ws_send_json",json.dumps(js))
        await ws.send_json(js)
    
    async def _handle_http_normal(self,request:web.Request):
        print("----http normal",request)
        '''在这里处理普通api调用'''
        # 鉴权
        if self._config.access_token != "":
            if request.headers.get("Authorization") != "Bearer " + self._config.access_token:
                print("token err")
                return web.Response(text="token err")
        method = request.url.path
        platform = request.headers.get("X-Platform")
        self_id = request.headers.get("X-Self-ID")
        adapter:AdapterOnebot = await self._get_adapter(platform,self_id)
        if adapter == None:
            return web.Response(text="bot not found")
        if method == "/v1/login.get":
            ret = await adapter.get_login(platform,self_id)
            return web.Response(text=json.dumps(ret),headers={
                "Content-Type":"application/json; charset=utf-8"
            })
        elif method == "/v1/message.create":
            body = await request.json()
            ret = await adapter.create_message(platform,self_id,body["channel_id"],body["content"])
            return web.Response(text=json.dumps(ret),headers={
                "Content-Type":"application/json; charset=utf-8"
            })
        return web.Response(text="method not found")
    
    async def _handle_http_admin(self,request:web.Request):
        print("----http admin",request)
        '''在这里处理管理api调用'''
        # 鉴权
        if self._config.access_token != "":
            if request.headers.get("Authorization") != "Bearer " + self._config.access_token:
                print("token err")
                return web.Response(text="token err")
        method = request.url.path
        if method == "/v1/admin/login.list":
            ret = []
            for adapter in self.adapterlist:
                ret += await adapter["adapter"].get_login(None,None)
            return web.Response(text=json.dumps(ret),headers={
                "Content-Type":"application/json; charset=utf-8"
            })
        return web.Response(text="method not found")
    
    async def _handle_http_foo(self,request:web.Request):
        '''在这里处理其余任何api调用'''
        print("--------http other",request)
        return web.Response(text="method not found")
    
    async def _handle_events_ws(self,request:web.Request):
        '''在这里处理websocket'''
        ws_id = str(uuid.uuid4())
        ws = web.WebSocketResponse()
        ws.can_prepare(request)
        await ws.prepare(request)
        self.wsmap[ws_id] = {
            "ws":ws,
            "is_access":False
        }
        print("--------http ws",request,ws_id)
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data_json = json.loads(msg.data)
                    print("--------recv_ws",msg.data)
                    op = data_json["op"]
                    if op == 3:
                        if self._config.access_token != "":
                            if data_json["body"]["token"] != self._config.access_token:
                                raise "token err"
                        self.wsmap[ws_id]["is_access"] = True
                        async def get_logins(self,ws):
                            logins = []
                            for adapter in self.adapterlist:
                                logins += await adapter["adapter"].get_login(None,None)
                            await Satori.ws_send_json(ws,{
                                "op":4,
                                "body":{
                                    "logins":logins
                                }
                            })
                        asyncio.create_task(get_logins(self,ws))
                    elif op == 1:
                        async def send_pong(ws):
                            await Satori.ws_send_json(ws,{
                                "op":2
                            })
                        asyncio.create_task(send_pong(ws))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print('ws connection closed with exception %s' %
                        ws.exception())
        finally:
            del self.wsmap[ws_id]
            print("--------http ws close",ws_id)
        return ws

    async def init_after(self):
        async def event_loop(self:Satori,adapter:AdapterOnebot):
            while True:
                msg = await adapter.get_msg()
                for wsid in self.wsmap:
                    ws = self.wsmap[wsid]
                    if ws["is_access"]:
                        asyncio.create_task(Satori.ws_send_json(ws["ws"],{"op":0,"body":msg}))
                # print("recv",msg)
        # 读取配置文件
        await self._config.read_config()
        # 创建 adapter
        for botcfg in self._config.botlist:
            if botcfg["platform"] == "onebot":
                adapter = AdapterOnebot(botcfg)
                if hasattr(adapter,"init_after"):
                    await adapter.init_after()
                if hasattr(adapter,"enable"):
                    await adapter.enable()
                if hasattr(adapter,"get_msg"):
                    asyncio.create_task(event_loop(self,adapter))
                login_info = await adapter.get_login(None,None)
                self.adapterlist.append({
                    "adapter":adapter,
                    "info":login_info,
                })
        # 创建server
        app = web.Application()
        app.add_routes([
            web.post("/v1/admin/{method}",self._handle_http_admin),
            web.get("/v1/events",self._handle_events_ws),
            web.post("/v1/{method}",self._handle_http_normal),
            web.post("/{method}",self._handle_http_foo),
        ])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner,self._config.web_host,self._config.web_port)
        asyncio.create_task(site.start())



async def main():
    satori = Satori()
    await satori.init_after()
    while True:
        await asyncio.sleep(1)
    

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())