import traceback
import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json
import time
import base64

from tool import *


class AdapterKook:
    def __init__(self,config = {}) -> None:
        '''用于初始化一些配置信息，尽量不要在这里阻塞，因为此处不具备异步环境，如果你需要读写配置文件，请在init_after中进行'''
        self._access_token = config["access_token"]
        self._http_url = "https://www.kookapp.cn/api/v3"
        self._is_stop = False
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT
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
    

    async def _ws_recv(self,websocket):
        try:
            reply = await asyncio.wait_for(websocket.recv(),0.1)
            return reply
        except asyncio.TimeoutError:
            return None

    async def _ws_connect(self):
        self._login_status = SatoriLogin.LoginStatus.CONNECT
        ws_url = (await self._api_call("/gateway/index?compress=0"))["url"]
        async with connect(ws_url) as websocket:
            tm = time.time()
            while not self._is_stop:
                reply = await self._ws_recv(websocket)
                if not reply:
                    now_time = time.time()
                    if now_time - tm > 30:
                        tm = now_time
                        await websocket.send(json.dumps({"s": 2,"sn": self._sn}))
                    continue
                js = json.loads(reply)
                s = js["s"]
                if s == 5:raise Exception("recv reset ws")
                elif s == 3:pass # heartbeat
                elif s == 1:
                    self._login_status = SatoriLogin.LoginStatus.ONLINE
                    print("kook:ws连接成功")
                elif s == 0:
                    self._sn = js["sn"]
                    asyncio.create_task(self._event_deal(js["d"]))

    async def _ws_server(self) -> None:
        while not self._is_stop:
            try:
                await self._ws_connect()
            except:
                self._login_status = SatoriLogin.LoginStatus.DISCONNECT
                print(traceback.format_exc())
                await asyncio.sleep(3)
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT

    async def init_after(self) -> None:
        '''适配器创建之后会调用一次，应该在这里进行ws连接等操作，如果不需要，可以不写'''
        asyncio.create_task(self._ws_server())

    def _kook_msg_to_satori(self,msg_type:int,message:str)->str:
        ret = ""
        if msg_type == 2: #图片
            ret += "<img src={}/>".format(json.dumps(message))
        else:
            def kook_msg_f(msg):
                ret = ""
                is_f = False
                for ch in msg:
                    if is_f:
                        is_f = False
                        ret += ch
                    elif ch == "\\":
                        is_f = True
                    else:
                        ret += ch
                return ret
            
            index = 0
            msg_list = message.split("(met)")
            for it in msg_list:
                if index % 2 == 0:
                    ret += satori_to_plain(kook_msg_f(it))
                else:
                    if it == "all":
                        ret += "<at type=\"all\"/>"
                    else:
                        ret += "<at id=\"{}\"/>".format(it)
                index += 1
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

        satori_evt = SatoriGroupMessageCreatedEvent(
            id=self._id,
            self_id=self._self_id,
            timestamp=data["msg_timestamp"],
            platform="kook",
            channel=SatoriChannel(
                id="GROUP_"+group_id,
                type=SatoriChannel.ChannelType.TEXT,
                name=extra["channel_name"]
            ),
            message=SatoriMessage(
                id=data["msg_id"],
                content=satori_msg,
                created_at=data["msg_timestamp"]
            ),
            user=SatoriUser(
                id=author["id"],
                name=author["username"],
                avatar=author["avatar"],
                is_bot=author["bot"]
            ),
            member=SatoriGuildMember(
                nick=author["nickname"],
                avatar=author["avatar"]
            ),
            guild=SatoriGuild(
                id=extra["guild_id"]
            ),
            role=SatoriGuildRole(
                id=json.dumps(sorted(author["roles"]))
            )
        )
        self._id += 1
        self._queue.put_nowait(satori_evt.to_dict())

    async def _deal_private_message_event(self,data,user_id:str):

        kook_msg = data["content"]
        extra = data["extra"]
        author = extra["author"]
        msg_type  = data["type"]

        if msg_type == 10:#卡牌
            return
        satori_msg = self._kook_msg_to_satori(msg_type,kook_msg)

        satori_evt = SatoriPrivateMessageCreatedEvent(
            id=self._id,
            self_id=self._self_id,
            timestamp=data["msg_timestamp"],
            channel=SatoriChannel(
                id=user_id,
                type=SatoriChannel.ChannelType.TEXT,
                name=author["username"]
            ),
            message=SatoriMessage(
                id=data["msg_id"],
                content=satori_msg,
                created_at=data["msg_timestamp"]
            ),
            user=SatoriUser(
                id=user_id,
                name=author["username"],
                avatar=author["avatar"],
                is_bot=author["bot"]
            ),
            platform="kook"
        ).to_dict()
        self._id += 1
        self._queue.put_nowait(satori_evt)

    async def _deal_group_increase_event(self,data):
        extra = data["extra"]
        satori_evt = {
            "id":self._id,
            "type":"guild-member-added",
            "platform":"kook",
            "self_id":self._self_id,
            "timestamp":data["msg_timestamp"],
            "guild":SatoriGuild(id=data["target_id"]).to_dict(),
            "member":SatoriGuildMember(joined_at=extra["body"]["joined_at"]).to_dict(),
            "user":SatoriUser(id=extra["body"]["user_id"]).to_dict()
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
        try:
            tp = data["channel_type"]
            if tp == "GROUP":
                await self._deal_group_evt(data)
            else:
                await self._deal_person_evt(data)
        except:
            print(traceback.format_exc())
    
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
                        text = "(met){}(met)".format(self._make_kook_text(id))
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
                        if img_url.startswith("data:image/"):
                            base64_start = img_url.find("base64,")
                            img_content = base64.b64decode(img_url[base64_start + 7:])
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
                to_ret.append(SatoriMessage(id=ret["msg_id"],content="").to_dict())
            return to_ret
        else:
            to_ret = []
            for it in to_sends:
                ret = await self._api_call("/direct-message/create",{"content":it["content"],"type":it["type"],"target_id":channel_id})
                to_ret.append(SatoriMessage(id=ret["msg_id"],content="").to_dict())
            return to_ret
    
    async def get_login(self,platform:Optional[str],self_id:Optional[str]) -> [dict]:
        '''获取登录信息，如果platform和self_id为空，那么应该返回一个列表'''
        obret =  (await self._api_call("/user/me"))
        satori_ret = SatoriLogin(
            status=self._login_status,
            user=SatoriUser(
                id=obret["id"],
                name=obret["username"],
                avatar=get_json_or(obret,"avatar",None),
                is_bot=True
            ),
            self_id=obret["id"],
            platform="kook"
        ).to_dict()
        self._self_id = obret["id"]
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret
        
    async def get_guild_member(self,platform:Optional[str],self_id:Optional[str],guild_id:str,user_id:str) -> [dict]:
        '''获取群组成员信息'''
        url = "/user/view?user_id={}&guild_id={}".format(user_id,guild_id)
        obret =  (await self._api_call(url))
        satori_ret = SatoriGuildMember(
            user=SatoriUser(
                id=obret["id"],
                name=get_json_or(obret,"username",None),
                avatar=get_json_or(obret,"avatar",None),
                is_bot=get_json_or(obret,"bot",None)
            ),
            nick=get_json_or(obret,"nickname",None),
            avatar=get_json_or(obret,"avatar",None),
            joined_at=get_json_or(obret,"join_time",None)
        ).to_dict()
        return satori_ret