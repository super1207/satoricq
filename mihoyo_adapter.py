import traceback
import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json
import time
import hashlib
import imghdr

import mihoyo.vila_bot as pbvb

from tool import *


class AdapterMihoyo:
    def __init__(self,config = {}) -> None:
        '''用于初始化一些配置信息，尽量不要在这里阻塞，因为此处不具备异步环境，如果你需要读写配置文件，请在init_after中进行'''
        self._http_url = "https://bbs-api.miyoushe.com"
        self._is_stop = False
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT
        self._queue = Queue(maxsize=100)
        self._id = 0
        self._sn = 1
        self._self_id = config["bot_id"]
        self._secret = config["secret"]
        self._villa_id = config["villa_id"]


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

    async def _send_ws_pack(self,ws,ws_dat,biztype):
        magic = 0xBABEFACE.to_bytes(length=4, byteorder='little', signed=False)
        if biztype == 7:
            pb_pack = bytes(pbvb.PLogin(
                uid=int(ws_dat["uid"]),
                token=self._villa_id + "." + self._secret + "." + self._self_id,
                platform=ws_dat["platform"],
                app_id=ws_dat["app_id"],
                device_id=ws_dat["device_id"]
            ))
        elif biztype == 6:
            pb_pack = bytes(pbvb.PHeartBeat(
                client_timestamp=str(int(round(time.time() * 1000)))
            ))
        else:
            raise Exception("unkonw biztype:{}".format(biztype))
        
        wid = self._sn
        self._sn += 1

        flag = 1
        appid = 104
        headerlen = 24
        datalen = headerlen +  len(pb_pack)

        to_send = magic
        to_send += datalen.to_bytes(length=4, byteorder='little', signed=False)
        to_send += headerlen.to_bytes(length=4, byteorder='little', signed=False)
        to_send += wid.to_bytes(length=8, byteorder='little', signed=False)
        to_send += flag.to_bytes(length=4, byteorder='little', signed=False)
        to_send += biztype.to_bytes(length=4, byteorder='little', signed=False)
        to_send += appid.to_bytes(length=4, byteorder='little', signed=True)
        to_send += pb_pack

        await ws.send(to_send)
        
    async def _ws_recv(self,websocket):
        try:
            reply = await asyncio.wait_for(websocket.recv(),0.1)
            return reply
        except asyncio.TimeoutError:
            return None

    async def _ws_connect(self):
        self._login_status = SatoriLogin.LoginStatus.CONNECT
        ws_dat = (await self._api_call("/vila/api/bot/platform/getWebsocketInfo"))
        # print(ws_dat)
        ws_url = ws_dat["websocket_url"]
        async with connect(ws_url) as websocket:
            await self._send_ws_pack(websocket,ws_dat,biztype=7)
            tm = time.time()
            while not self._is_stop:
                reply = await self._ws_recv(websocket)
                if not reply:
                    now_time = time.time()
                    if now_time - tm > 30:
                        tm = now_time
                        await self._send_ws_pack(websocket,ws_dat,biztype=6)
                    continue
                biztype = int.from_bytes(reply[24:28],byteorder='little',signed=False)
                if biztype == 7: # 登录返回
                    login_reply = pbvb.PLoginReply().parse(reply[32:])
                    if login_reply.code == 0:
                        print("mihoyo:ws连接成功")
                        self._login_status = SatoriLogin.LoginStatus.ONLINE
                        continue
                    else:
                        print("mihoyo:ws连接失败",login_reply.to_json())
                        break
                elif biztype == 53:
                    print("mihoyo:ws被踢下线")
                    pkoff = pbvb.PKickOff().parse(reply[32:])
                    print("mihoyo:" + pkoff.reason)
                    break
                elif biztype == 52:
                    print("mihoyo:ws服务关机")
                    break
                elif biztype == 6:
                    heart_reply = pbvb.PHeartBeatReply().parse(reply[32:])
                    if heart_reply.code != 0:
                        print("mihoyo:ws心跳失败")
                        break
                elif biztype == 30001: # 正常处理
                    evt = pbvb.RobotEvent().parse(reply[32:]).to_dict()
                    asyncio.create_task(self._event_deal(evt))

    async def _ws_server(self) -> None:
        while not self._is_stop:
            try:
                await self._ws_connect()
            except:
                self._login_status = SatoriLogin.LoginStatus.DISCONNECT
                traceback.print_exc()
                await asyncio.sleep(3)
        self._login_status = SatoriLogin.LoginStatus.DISCONNECT

    async def init_after(self) -> None:
        asyncio.create_task(self._ws_server())

    def _mihoyo_msg_to_satori(self,content_obj)->str:
        ret = ""
        entities = content_obj["content"]["entities"]
        text = content_obj["content"]["text"]
        l = len(text)
        i = 0
        while i < l:
            for en in entities:
                if en["offset"] == i:
                    print(en)
                    i += en["length"]
                    if en["entity"]["type"] == "mention_all": # 实际上收不到
                        ret += "<at type=\"all\"/>"
                    elif en["entity"]["type"] == "mentioned_robot":
                        ret += "<at id=\"{}\"/>".format(en["entity"]["bot_id"])
                    elif en["entity"]["type"] == "mentioned_user":
                        ret += "<at id=\"{}\"/>".format(en["entity"]["user_id"])
                    break
            else:
                ret += satori_to_plain(text[i])
                i += 1
        return ret
    async def _deal_group_message_event(self,data):
        extendData = data["extendData"]

        sendMessage = extendData["sendMessage"]
        user_id = sendMessage["fromUserId"]
        villaId = sendMessage["villaId"]
        roomId = sendMessage["roomId"]

        villaRoomId = villaId + "_" + roomId

        content_obj = json.loads(sendMessage["content"])

        extra_obj = json.loads(content_obj["user"]["extra"])

        satori_msg = self._mihoyo_msg_to_satori(content_obj) # todo

        satori_evt = SatoriGroupMessageCreatedEvent(
            id=self._id,
            self_id=self._self_id,
            timestamp=int(data["sendAt"]) * 1000,
            platform="mihoyo",
            channel=SatoriChannel(
                id=villaRoomId,
                type=SatoriChannel.ChannelType.TEXT,
            ),
            message=SatoriMessage(
                id=data["id"],
                content=satori_msg,
                created_at=int(sendMessage["sendAt"])
            ),
            user=SatoriUser(
                id=user_id,
                name=sendMessage["nickname"],
                avatar=content_obj["user"]["portraitUri"]
            ),
            member=SatoriGuildMember(
                nick=sendMessage["nickname"],
                avatar=content_obj["user"]["portraitUri"]
            ),
            guild=SatoriGuild(
                id=villaId
            ),
            role=SatoriGuildRole(
                id=extra_obj["member_roles"]["name"],
                name=extra_obj["member_roles"]["name"]
            )
        )
        self._id += 1
        self._queue.put_nowait(satori_evt.to_dict())

    async def _event_deal(self,data:dict):
        try:
            event_type = data["type"]
            if event_type == "SendMessage":
                await self._deal_group_message_event(data)
        except:
            print(traceback.format_exc())

    
    async def _api_call(self,path,data = None,villa_id = 0) -> dict:
        url:str = self._http_url + path
        headers = {"x-rpc-bot_id":self._self_id,"x-rpc-bot_secret":self._secret}
        if villa_id == 0:
            headers["x-rpc-bot_villa_id"] = self._villa_id
        else:
            headers["x-rpc-bot_villa_id"] = villa_id
        if data == None:
            async with httpx.AsyncClient() as client:
                return (await client.get(url,headers=headers)).json()["data"]
        else:
            headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient() as client:
                ret =  (await client.post(url,headers=headers,data=data)).json()
                if ret["retcode"] != 0:
                    print("mihoyo:",ret)
                return ret["data"]

    
    async def _satori_to_mihoyo(self,satori_obj,villa_id) -> [dict]:
        to_send_data = []
        last_type = 1
        for node in satori_obj:
            if isinstance(node,str):
                text = node
                if last_type == 1 and len(to_send_data) != 0:
                    l = len(to_send_data)
                    to_send_data[l - 1]["text"] += text
                else:
                    to_send_data.append({
                        "type":1,
                        "text":text,
                        "entities":[]
                    })
                    last_type = 1
            else:
                if node["type"] == "at":
                    type = get_json_or(node["attrs"],"type",None)
                    id = get_json_or(node["attrs"],"id",None)
                    if type == "all":
                        text = "@全体成员"
                    elif id != None:
                        text = "@" + id
                    else:
                        continue

                    if last_type != 1 or len(to_send_data) == 0:
                        to_send_data.append({
                            "type":1,
                            "text":"",
                            "entities":[]
                        })
                        last_type = 1

                    l = len(to_send_data)
                    ll = len(to_send_data[l - 1]["text"])
                    to_send_data[l - 1]["text"] += text
                    if type == "all":
                        to_send_data[l - 1]["entities"].append({
                            "entity": {
                                "type": "mention_all"
                            },
                            "length":5,
                            "offset":ll
                        })
                    else:
                        if id.startswith("bot_"):
                            to_send_data[l - 1]["entities"].append({
                                "entity": {
                                    "type": "mentioned_robot",
                                    "bot_id": id
                                },
                                "length":len(id) + 1,
                                "offset":ll
                            })
                        else:
                            to_send_data[l - 1]["entities"].append({
                                "entity": {
                                    "type": "mentioned_user",
                                    "user_id": id
                                },
                                "length":len(id) + 1,
                                "offset":ll
                            })

                elif node["type"] == "img":
                    img_url:str = node["attrs"]["src"]
                    mihoyo_img_url = ""

                    async with httpx.AsyncClient() as client:
                        img_content =  (await client.get(img_url)).content
                    ext = imghdr.what(file = "",h=img_content)
                    m = hashlib.md5()
                    m.update(img_content)
                    headers = {"x-rpc-bot_id":self._self_id,"x-rpc-bot_secret":self._secret,"x-rpc-bot_villa_id":villa_id}
                    upload_info_url = self._http_url + "/vila/api/bot/platform/getUploadImageParams"
                    async with httpx.AsyncClient() as client:
                        req = client.build_request("GET",upload_info_url,json={
                            "md5":m.hexdigest(),
                            "ext":ext
                        },headers=headers)
                        file_params = (await client.send(req)).json()["data"]["params"]
                    files = {
                        "x:extra":file_params["callback_var"]["x:extra"],
                        "OSSAccessKeyId":file_params["accessid"],
                        "signature":file_params["signature"],
                        "success_action_status":file_params["success_action_status"],
                        "name":file_params["name"],
                        "callback":file_params["callback"],
                        "x-oss-content-type":file_params["x_oss_content_type"],
                        "key":file_params["key"],
                        "policy":file_params["policy"],
                        "Content-Disposition":file_params["content_disposition"],
                        'file':('test',img_content)
                    }
                    async with httpx.AsyncClient() as client:
                        ret =  (await client.post(file_params["host"],files=files)).json()
                        mihoyo_img_url = ret["data"]["url"]
                    to_send_data.append({
                            "type":2,
                            "url":mihoyo_img_url,
                    })
                    last_type = 2
        to_send_data2 = []
        for it in to_send_data:
            type = it["type"]
            if type == 1:
                to_send_data2.append({
                    "object_name":"MHY:Text",
                    "msg_content":json.dumps({
                        "content":{
                            "text":it["text"],
                            "entities":it["entities"]
                        }
                })})
            elif type == 2:
                to_send_data2.append({
                    "object_name":"MHY:Image",
                    "msg_content":json.dumps({
                        "content":{
                            "url":it["url"]
                        }
                        
                })})
                
        return to_send_data2
    
    async def create_message(self,platform:str,self_id:str,channel_id:str,content:str):
        '''发送消息'''
        villa_id = channel_id.split("_")[0]
        satori_obj = parse_satori_html(content)
        to_sends = await self._satori_to_mihoyo(satori_obj,villa_id)
        to_ret = []
        # print(to_sends)
        for it in to_sends:
            it["room_id"] = channel_id.split("_")[1]
            ret = await self._api_call("/vila/api/bot/platform/sendMessage",json.dumps(it),villa_id=villa_id)
            to_ret.append(SatoriMessage(id=ret["bot_msg_id"],content="").to_dict())
        return to_ret
      
    
    async def get_login(self,platform:Optional[str],self_id:Optional[str]) -> [dict]:
        '''获取登录信息，如果platform和self_id为空，那么应该返回一个列表'''
        satori_ret = SatoriLogin(
            status=self._login_status,
            user=SatoriUser(
                id=self._self_id,
                is_bot=True
            ),
            self_id=self._self_id,
            platform="mihoyo"
        ).to_dict()
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret

    async def get_guild_member(self,platform:Optional[str],self_id:Optional[str],guild_id:str,user_id:str) -> [dict]:
        '''获取群组成员信息'''
        url = self._http_url + "/vila/api/bot/platform/getMember"
        headers = {"x-rpc-bot_id":self._self_id,"x-rpc-bot_secret":self._secret,"x-rpc-bot_villa_id":guild_id}
        async with httpx.AsyncClient() as client:
            req = client.build_request("GET",url,json={
                "uid":user_id
            },headers=headers)
            obret = (await client.send(req)).json()["data"]["member"]
        satori_ret = SatoriGuildMember(
            user=SatoriUser(
                id=obret["basic"]["uid"],
                name=obret["basic"]["nickname"],
                avatar=obret["basic"]["avatar_url"],
                is_bot=False
            ),
            nick=obret["basic"]["nickname"],
            avatar=obret["basic"]["avatar_url"],
            joined_at=int(obret["joined_at"] + "000")
        ).to_dict()
        return satori_ret