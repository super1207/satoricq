from urllib import parse
import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json

from tool import get_json_or

class AdapterOnebot:
    def __init__(self,config = {}) -> None:
        '''用于初始化一些配置信息，尽量不要在这里阻塞，因为此处不具备异步环境，如果你需要读写配置文件，请在init_after中进行'''
        self._http_url = config["http_url"]
        self._ws_url = config["ws_url"]
        if "access_token" in config:
            self._access_token = config["access_token"]
        else:
            self._access_token = None
        self._is_stop = False
        self._login_status = 3  # DISCONNECT
        self._queue = Queue(maxsize=100)
        self._id = 0

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

    async def init_after(self) -> None:
        '''适配器创建之后会调用一次，应该在这里进行ws连接等操作，如果不需要，可以不写'''
        async def _ws_server(self:AdapterOnebot) -> None:
            while not self._is_stop:
                self._login_status = 2 # CONNECT
                async with connect(self._ws_url) as websocket:
                    self._login_status = 1 # ONLINE
                    try:
                        while True:
                            try:
                                reply = await asyncio.wait_for(websocket.recv(),0.1)
                                await self._event_deal(json.loads(reply))
                            except asyncio.TimeoutError:
                                if self._is_stop:
                                    await websocket.close()
                            except asyncio.QueueFull:
                                print("队列满")
                    except Exception as e:
                        print(e)
                        self._login_status = 3 # DISCONNECT
                        print("ws连接已经断开")
                        self._is_connect = False
        asyncio.create_task(_ws_server(self))
    
    async def _event_deal(self,evt:dict):
        '''自己定义的事件转化函数'''
        post_type = evt["post_type"]
        if post_type == "message":
            message_type = evt["message_type"]
            sender = evt["sender"]
            if message_type == "group":
                channel_obj = {
                        "id":"GROUP_"+str(evt["group_id"]),
                        "type":0,
                        "name":None,
                        "parent_id":None
                    }
                guild_obj = {
                    "id":"GROUP_"+str(evt["group_id"]),
                    "name":None,
                    "avatar":None
                }
                user_obj = {
                    "id":str(evt["user_id"]),
                    "name":get_json_or(sender,"nickname",None),
                    "nick":get_json_or(sender,"nickname",None),
                    "avatar":get_json_or(sender,"avatar",None),
                    "is_bot":None
                }
                joined_at = get_json_or(sender,"join_time",None)
                if joined_at:
                    joined_at = int(str(joined_at) + "000")
                member_obj = {
                    "nick":get_json_or(sender,"card",None),
                    "avatar":get_json_or(sender,"avatar",None),
                    "joined_at":joined_at
                }
                message_obj = {
                    "id":str(evt["message_id"]),
                    "content":evt["raw_message"], # todo
                    "created_at":int(str(evt["time"] ) + "000")
                }
                role_obj = {
                        "id":get_json_or(sender,"role","member"),
                        "name":get_json_or(sender,"role","member")
                    }
                satori_evt = {
                    "id":self._id,
                    "type":"message-created",
                    "platform":"satori",
                    "self_id":str(evt["self_id"]),
                    "timestamp":int(str(evt["time"] ) + "000"),
                    "channel":channel_obj,
                    "guild":guild_obj,
                    "member":member_obj,
                    "message":message_obj,
                    "role":role_obj,
                    "user":user_obj
                }
                self._id += 1
                self._queue.put_nowait(satori_evt)
            elif message_type == "private":
                channel_obj = {
                        "id":str(evt["user_id"]),
                        "type":0,
                        "name":None,
                        "parent_id":None
                    }
                guild_obj = {
                    "id":str(evt["user_id"]),
                    "name":None,
                    "avatar":None
                }
                user_obj = {
                    "id":str(evt["user_id"]),
                    "name":get_json_or(sender,"nickname",None),
                    "nick":get_json_or(sender,"nickname",None),
                    "avatar":get_json_or(sender,"avatar",None),
                    "is_bot":None
                }
                joined_at = get_json_or(sender,"join_time",None)
                if joined_at:
                    joined_at = int(str(joined_at) + "000")
                message_obj = {
                    "id":str(evt["message_id"]),
                    "content":evt["raw_message"], # todo
                    "created_at":int(str(evt["time"] ) + "000")
                }
                satori_evt = {
                    "id":self._id,
                    "type":"message-created",
                    "platform":"satori",
                    "self_id":str(evt["self_id"]),
                    "timestamp":int(str(evt["time"] ) + "000"),
                    "channel":channel_obj,
                    "message":message_obj,
                    "user":user_obj
                }
                self._id += 1
                self._queue.put_nowait(satori_evt)

    async def _api_call(self,path,data) -> dict:
        url:str = parse.urljoin(self._http_url,path)
        if self._access_token:
            headers = {"Authorization":"Bearer {}".format([self._access_token])}
        else:
            headers = {}
        async with httpx.AsyncClient() as client:
            return (await client.post(url,headers=headers,data=data)).json()
        
    async def create_message(self,platform:str,self_id:str,channel_id:str,content:str):
        '''发送消息'''
        if channel_id.startswith("GROUP_"):
            group_id = int(channel_id[6:])
            ret = await self._api_call("/send_group_msg",{"group_id":group_id,"message":content})
            return [{"id":str(ret["data"]["message_id"]),"content":""}]
        else:
            user_id = int(channel_id)
            ret = await self._api_call("/send_private_msg",{"user_id":user_id,"message":content})
            return [{"id":str(ret["data"]["message_id"]),"content":""}]
    
    async def get_login(self,platform:Optional[str],self_id:Optional[str]) -> [dict]:
        '''获取登录信息，如果platform和self_id为空，那么应该返回一个列表'''
        obret =  (await self._api_call("/get_login_info",{}))["data"]
        satori_ret = {
            "user":{
                "id":str(obret["user_id"]),
                "name":obret["nickname"],
                "nick":obret["nickname"],
                "avatar":get_json_or(obret,"avatar",None),
                "is_bot":None
            },
            "self_id":str(obret["user_id"]),
            "platform":"satori",
            "status":self._login_status,
        }
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret