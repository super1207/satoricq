from urllib.parse import urlencode
import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json
import time
import re

from tool import get_json_or, parse_satori_html


class AdapterKook:
    def __init__(self,config = {}) -> None:
        '''用于初始化一些配置信息，尽量不要在这里阻塞，因为此处不具备异步环境，如果你需要读写配置文件，请在init_after中进行'''
        self._access_token = config["access_token"]
        self._http_url = "https://www.kookapp.cn/api/v3"
        self._is_stop = False
        self._login_status = 3  # DISCONNECT
        self._queue = Queue(maxsize=100)
        self._id = 0
        self._sn = 0
        self._self_id = None


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
        async def _ws_server(self:AdapterKook) -> None:
            while not self._is_stop:
                try:
                    self._login_status = 2 # CONNECT
                    ws_url = (await self._api_call("/gateway/index?compress=0"))["url"]
                    async with connect(ws_url) as websocket:
                        tm = time.time()
                        try:
                            while True:
                                try:
                                    reply = await asyncio.wait_for(websocket.recv(),0.1)
                                    js = json.loads(reply)
                                    if js["s"] == 5:
                                        raise Exception("recv reset ws")
                                    elif js["s"] == 0:
                                        self._sn = js["sn"]
                                        await self._event_deal(js["d"])
                                    elif js["s"] == 3:
                                        pass
                                    elif js["s"] == 1:
                                        self._login_status = 1 # ONLINE
                                        print("kook:ws连接成功")
                                except asyncio.TimeoutError:
                                    if self._is_stop:
                                        await websocket.close()
                                    if time.time() - tm > 30:
                                        tm = time.time()
                                        # print("发送KOOK心跳")
                                        await websocket.send(json.dumps({"s": 2,"sn": self._sn}))
                                except asyncio.QueueFull:
                                    print("队列满")
                        except Exception as e:
                            print("err",e)
                except Exception as e:
                    print(e)
                    print("kook:ws连接已经断开")
                    self._login_status = 3 # DISCONNECT
        asyncio.create_task(_ws_server(self))

    def _kook_msg_to_satori(self,msg_type:int,message:str)->str:
        ret = ""
        if msg_type == 2: #图片
            ret += "<img src={}/>".format(json.dumps(message))
        else:
            is_f = False
            message2 = re.sub(r"\(met\)((\d+))\(met\)", "<at id=\"\\2\"/>", message)
            message3 = re.sub(r"\(met\)((all))\(met\)", "<at type=\"\\2\"/>", message2)
            for ch in message3:
                if is_f:
                    is_f = False
                    ret += ch
                elif ch == "\\":
                    is_f = True
                else:
                    ret += ch
        return ret


    async def _deal_group_message_event(self,data,user_id:str):
        group_id = data["target_id"]
        kook_msg = data["content"]
        extra = data["extra"]
        author = extra["author"]
        msg_type  = data["type"]


        if msg_type == 10:#卡牌
            return
        satori_msg = self._kook_msg_to_satori(msg_type,kook_msg)

        channel_obj = {
                "id":"GROUP_"+group_id,
                "type":0,
                "name":extra["channel_name"],
                "parent_id":None
            }
        guild_obj = {
            "id":extra["guild_id"],
            "name":None,
            "avatar":None
        }
        user_obj = {
            "id":author["id"],
            "name":author["username"],
            "nick":author["username"],
            "avatar":author["avatar"],
            "is_bot":author["bot"]
        }
        joined_at = None
        member_obj = {
            "nick":author["nickname"],
            "avatar":author["avatar"],
            "joined_at":joined_at
        }
        message_obj = {
            "id":data["msg_id"],
            "content":satori_msg,
            "created_at":data["msg_timestamp"]
        }
        role = json.dumps(author["roles"])
        role_obj = {
            "id":role,
            "name":role
        }
        satori_evt = {
            "id":self._id,
            "type":"message-created",
            "platform":"kook",
            "self_id":self._self_id,
            "timestamp":data["msg_timestamp"],
            "channel":channel_obj,
            "guild":guild_obj,
            "member":member_obj,
            "message":message_obj,
            "role":role_obj,
            "user":user_obj
        }
        self._id += 1
        self._queue.put_nowait(satori_evt)

    async def _deal_private_message_event(self,data,user_id:str):

        kook_msg = data["content"]
        extra = data["extra"]
        author = extra["author"]
        msg_type  = data["type"]

        if msg_type == 10:#卡牌
            return
        satori_msg = self._kook_msg_to_satori(msg_type,kook_msg)

        channel_obj = {
            "id":user_id,
            "type":3,
            "name":author["username"],
            "parent_id":None
        }
        user_obj = {
            "id":user_id,
            "name":author["username"],
            "nick":author["username"],
            "avatar":author["avatar"],
            "is_bot":author["bot"]
        }
        message_obj = {
            "id":data["msg_id"],
            "content":satori_msg,
            "created_at":data["msg_timestamp"]
        }
        satori_evt = {
            "id":self._id,
            "type":"message-created",
            "platform":"kook",
            "self_id":self._self_id,
            "timestamp":data["msg_timestamp"],
            "channel":channel_obj,
            "message":message_obj,
            "user":user_obj
        }
        self._id += 1
        self._queue.put_nowait(satori_evt)

    async def _deal_group_increase_event(self,data):
        extra = data["extra"]
        guild_obj = {
            "id":data["target_id"],
            "name":None,
            "avatar":None
        }
        member_obj = {
            "nick":None,
            "avatar":None,
            "joined_at":extra["body"]["joined_at"]
        }
        user_obj = {
            "id":extra["body"]["user_id"],
            "name":None,
            "nick":None,
            "avatar":None,
            "is_bot":None
        }
        satori_evt = {
            "id":self._id,
            "type":"guild-member-added",
            "platform":"kook",
            "self_id":self._self_id,
            "timestamp":data["msg_timestamp"],
            "guild":guild_obj,
            "member":member_obj,
            "user":user_obj
        }
        self._id += 1
        self._queue.put_nowait(satori_evt)



    async def _deal_group_evt(self,data):
        user_id:str = data["author_id"]
        if user_id == "1": # system message
            tp = data["type"]
            if tp != 255:
                return
            sub_type = data["extra"]["type"]
            if sub_type == "joined_guild":
                await self._deal_group_increase_event(data)
        else:
            if self._self_id:
                if user_id != self._self_id:
                    await self._deal_group_message_event(data,user_id)


    async def _deal_person_evt(self,data):
        user_id:str = data["author_id"]
        if user_id != 1: # 不是系统消息
            if self._self_id:
                if user_id != self._self_id:
                    await self._deal_private_message_event(data,user_id)


    async def _event_deal(self,data:dict):
        tp = data["channel_type"]
        if tp == "GROUP":
            await self._deal_group_evt(data)
        else:
            await self._deal_person_evt(data)
    
    async def _api_call(self,path,data = None) -> dict:
        url:str = self._http_url + path
        headers = {"Authorization":"Bot {}".format(self._access_token)}
        if data == None:
            async with httpx.AsyncClient() as client:
                return (await client.get(url,headers=headers)).json()["data"]
        else:
            async with httpx.AsyncClient() as client:
                return (await client.post(url,headers=headers,data=data)).json()["data"]

    def _make_kook_text(self,text):
        ret = ""
        for ch in text:
            if ch in ["\\","*","~","[","(",")","]","-",">","`"]:
                ret += "\\"
            ret += ch
        return ret
    
    async def _satori_to_kook(self,satori_obj) -> [dict]:
        to_send_data = []
        last_type = 1
        for node in satori_obj:
            if isinstance(node,str):
                text = self._make_kook_text(node)
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
                        text = "(met)all(met)"
                    elif id != None:
                        text = "(met){}(met)".format(id)
                    if last_type == 1 and len(to_send_data) != 0:
                        l = len(to_send_data)
                        to_send_data[l - 1]["content"] += text
                    else:
                        to_send_data.append({
                            "type":1,
                            "content":text
                        })
                        last_type = 1
                elif node["type"] == "img":
                    img_url:str = node["attrs"]["src"]
                    kook_img_url = ""
                    if img_url.startswith("https://img.kookapp.cn"):
                        kook_img_url = img_url
                    else:
                        async with httpx.AsyncClient() as client:
                            img_content =  (await client.get(img_url)).content
                        files = {
                            'file':('test',img_content)
                        }
                        headers = {"Authorization":"Bot {}".format(self._access_token)}
                        async with httpx.AsyncClient() as client:
                            ret =  (await client.post(self._http_url + "/asset/create",files=files,headers=headers)).json()
                            kook_img_url = ret["data"]["url"]
                    to_send_data.append({
                        "type":2,
                        "content":kook_img_url
                    })
                    last_type = 2
        return to_send_data
    
    async def create_message(self,platform:str,self_id:str,channel_id:str,content:str):
        '''发送消息'''
        satori_obj = parse_satori_html(content)
        to_sends = await self._satori_to_kook(satori_obj)
        if channel_id.startswith("GROUP_"):
            channel_id = int(channel_id[6:])
            to_ret = []
            for it in to_sends:
                ret = await self._api_call("/message/create",{"content":it["content"],"type":it["type"],"target_id":channel_id})
                to_ret.append({"id":ret["msg_id"],"content":""})
            return to_ret
        else:
            to_ret = []
            for it in to_sends:
                ret = await self._api_call("/direct-message/create",{"content":it["content"],"type":it["type"],"target_id":channel_id})
                to_ret.append({"id":ret["msg_id"],"content":""})
            return to_ret
    
    async def get_login(self,platform:Optional[str],self_id:Optional[str]) -> [dict]:
        '''获取登录信息，如果platform和self_id为空，那么应该返回一个列表'''
        obret =  (await self._api_call("/user/me"))
        satori_ret = {
            "user":{
                "id":obret["id"],
                "name":obret["username"],
                "nick":obret["username"],
                "avatar":get_json_or(obret,"avatar",None),
                "is_bot":None
            },
            "self_id":obret["id"],
            "platform":"kook",
            "status":self._login_status,
        }
        self._self_id = obret["id"]
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret
        
    async def get_guild_member(self,platform:Optional[str],self_id:Optional[str],guild_id:str,user_id:str) -> [dict]:
        '''获取群组成员信息，如果platform和self_id为空，那么应该返回一个列表'''
        url = "/user/view?user_id={}&guild_id={}".format(user_id,guild_id)
        obret =  (await self._api_call(url))
        joined_at = get_json_or(obret,"join_time",None)
        satori_ret = {
            "user":{
                "id":obret["id"],
                "name":get_json_or(obret,"username",None), # 用户昵称
                "nick":get_json_or(obret,"username",None), # 用户昵称
                "avatar":get_json_or(obret,"avatar",None),
                "is_bot":get_json_or(obret,"bot",None)
            },
            "nick":get_json_or(obret,"nickname",None), # 用户在群组中的名字
            "avatar":get_json_or(obret,"avatar",None),
            "joined_at":joined_at,
        }
        return satori_ret