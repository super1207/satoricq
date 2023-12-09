import traceback
import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json
import time
import re

from tool import *


class AdapterQQ:
    def __init__(self,config = {}) -> None:
        '''用于初始化一些配置信息，尽量不要在这里阻塞，因为此处不具备异步环境，如果你需要读写配置文件，请在init_after中进行'''
        self._botqq = config["botqq"]
        self._appid = config["appid"]
        self._token = config["token"]
        self._appsecret = config["appsecret"]
        self._http_url = "https://api.sgroup.qq.com"
        self._is_stop = False
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT
        self._queue = Queue(maxsize=100)
        self._id = 0
        self._sn = 0
        # self._self_id = None
        self._access_token = None
        self._expires_in = 0
        # self._self_name = None


    async def enable(self) -> None:
        '''适配器启用的时候会调用，可以不理，也可以没这个函数
            配合下面的停用函数，适配器可以得到自己在整个系统中的状态，进而进行一些优化
            如，如果适配器处于停用状态，适配器可以自行选择关闭网络连接，以节省资源，当然，也可以不理会
        '''
        pass

    async def disable(self) -> None:
        '''适配器停用的时候会调用，可以不理，也可以没这个函数'''
        pass
    
    async def release(self) -> None:
        '''适配器释放的时候会调用一次，应该在这里停用ws连接
            一般认为，适配器会和真正的协议端建立连接，所以，这个函数大多数时候是需要写的
            但是，这个函数允许资源延迟释放，只要能释放就行
            你可以在这个函数里面进行数据保存之类的，这种用途下，请阻塞这个函数，直到保存完成
        '''
        self._is_stop = True

    async def get_msg(self) -> dict:
        '''阻塞并等待消息返回，如果你的适配器不具备接收消息的能力，请不要写这个函数'''
        return await self._queue.get()
    

    async def _ws_recv(self,websocket):
        try:
            reply = await asyncio.wait_for(websocket.recv(),0.1)
            return reply
        except asyncio.TimeoutError:
            return None

    async def _ws_connect(self):
        self._login_status = SatoriLogin.LoginStatus.CONNECT
        ws_url = (await self._api_call("/gateway"))["url"]
        async with connect(ws_url) as websocket:
            tm = time.time()
            while not self._is_stop:
                reply = await self._ws_recv(websocket)
                if not reply:
                    now_time = time.time()
                    if now_time - tm > 30:
                        tm = now_time
                        await websocket.send(json.dumps({"op": 1,"d": self._sn}))
                    continue
                js = json.loads(reply)
                op = js["op"]
                if op == 0: # 事件
                    self._sn = js["s"]
                    t = js["t"]
                    if t == "READY":
                        print("qq:ws连接成功")
                        print(js)
                        self._login_status = SatoriLogin.LoginStatus.ONLINE
                    else:
                        print(json.dumps(js))
                elif op == 1: # 心跳
                    await websocket.send(json.dumps({"op":11}))
                elif op == 7: # 重连
                    print("qq:服务端要求重连")
                    break
                elif op == 9: # 参数错误
                    print("qq:参数错误:",json.dumps(js))
                    break
                elif op == 10: # ws建立成功
                    await websocket.send(json.dumps({
                        "op":2,
                        "d":{
                            "token":"QQBot {}".format(self._access_token),
                            "intents":0 | (1 << 0) | (1 << 1) | (1 << 30),
                            "shard":[0, 1],
                        }
                    }))
                elif op == 11: # HTTP Callback ACK
                    pass

    async def _ws_server(self) -> None:
        while not self._is_stop:
            try:
                await self._ws_connect()
            except:
                self._login_status = SatoriLogin.LoginStatus.DISCONNECT
                print(traceback.format_exc())
                await asyncio.sleep(3)
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT

    async def _token_refresh(self):
        async with httpx.AsyncClient() as client:
            if not self._expires_in or int(self._expires_in) < 60 * 5:
                url = "https://bots.qq.com/app/getAppAccessToken"
                ret = (await client.post(url,json={
                    "appId":self._appid,
                    "clientSecret":self._appsecret
                })).json()
                self._access_token = ret["access_token"]
                self._expires_in = ret["expires_in"]
                print(ret)

    async def _token_refresh_task(self):
        while True:
            try:
                await self._token_refresh()
                index = 0
                while index < 60: # 每60秒检测一次token是否过期
                    await asyncio.sleep(1)
                    if self._is_stop:
                        break
                    index += 1
                if self._is_stop:break
            except:
                print(traceback.format_exc())

    async def init_after(self) -> None:
        '''适配器创建之后会调用一次，应该在这里进行ws连接等操作，如果不需要，可以不写'''
        try:
            await self._token_refresh()
        except:
            print(traceback.format_exc())
        asyncio.create_task(self._token_refresh_task())
        asyncio.create_task(self._ws_server())

    async def _api_call(self,path,data = None) -> dict:
        url:str = self._http_url + path
        headers = {"Authorization":"QQBot {}".format(self._access_token),"X-Union-Appid":self._appid}
        if data == None:
            async with httpx.AsyncClient() as client:
                return (await client.get(url,headers=headers)).json()
        else:
            async with httpx.AsyncClient() as client:
                ret = (await client.post(url,headers=headers,json=data))
                print(ret.content)
                return ret.json()

    def _make_qq_text(self,text:str):
        ret = text
        ret = ret.replace("&","&amp;")
        ret = ret.replace("<","&lt;")
        ret = ret.replace(">","&gt;")
        return ret
    
    async def _satori_to_qq(self,satori_obj) -> [dict]:
        to_send_data = []
        last_type = 1
        for node in satori_obj:
            if isinstance(node,str):
                text = self._make_qq_text(node)
                if last_type == 1 and len(to_send_data) != 0:
                    l = len(to_send_data)
                    to_send_data[l - 1]["content"] += text
                else:
                    to_send_data.append({
                        "type":1,
                        "content":text
                    })
                    last_type = 1
            else:
                if node["type"] == "at":
                    type = get_json_or(node["attrs"],"type",None)
                    id = get_json_or(node["attrs"],"id",None)
                    if type == "all":
                        # 注意，机器人不支持at all，不能发，也不能收，这里假装at all了
                        text = "@全体成员"
                        # text = "<@everyone>"
                    elif id != None:
                        text = "<@{}>".format(self._make_qq_text(id))
                    if last_type == 1 and len(to_send_data) != 0:
                        l = len(to_send_data)
                        to_send_data[l - 1]["content"] += text
                    else:
                        to_send_data.append({
                            "type":1,
                            "content":text
                        })
                        last_type = 1
        return to_send_data
    
    async def create_message(self,platform:str,self_id:str,channel_id:str,content:str):
        '''发送消息'''
        satori_obj = parse_satori_html(content)
        to_sends = await self._satori_to_qq(satori_obj)
        if channel_id.startswith("CHANNEL_"):
            channel_id = int(channel_id[8:])
            to_ret = []
            for it in to_sends:
                ret = await self._api_call("/channels/{}/messages".format(channel_id),{
                    "content":it["content"],
                    "msg_id":"AT_MESSAGE_CREATE:4d21a4cc-207c-4c84-9162-dd9bdc7dbf0a"
                                                                                       })
                to_ret.append(SatoriMessage(id=ret["id"],content="").to_dict())
            return to_ret
    
    async def get_login(self,platform:Optional[str],self_id:Optional[str]) -> [dict]:
        '''获取登录信息，如果platform和self_id为空，那么应该返回一个列表'''
        obret =  (await self._api_call("/users/@me"))
        satori_ret = SatoriLogin(
            status=self._login_status,
            user=SatoriUser(
                id=obret["id"],
                name=obret["username"],
                avatar=obret["avatar"],
                is_bot=True
            ),
            self_id=obret["id"],
            platform="qq"
        ).to_dict()
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret
        
    async def get_guild_member(self,platform:Optional[str],self_id:Optional[str],guild_id:str,user_id:str) -> [dict]:
        '''获取群组成员信息'''
        url = "/guilds/{}/members/{}".format(guild_id,user_id)
        obret =  (await self._api_call(url))
        satori_ret = SatoriGuildMember(
            user=SatoriUser(
                id=obret["user"]["id"],
                name=obret["user"]["username"],
                avatar=obret["user"]["avatar"],
                is_bot=obret["user"]["bot"]
            ),
            nick=get_json_or(obret,"nick",None),
            avatar=obret["user"]["avatar"],
            joined_at=int(time.mktime(time.strptime(obret["joined_at"], "%Y-%m-%dT%H:%M:%S%z"))) * 1000
        ).to_dict()
        return satori_ret