import httpx
from websockets import connect
import asyncio
from typing import Optional
from asyncio import Queue
import json

from tool import get_json_or, parse_satori_html

def _cqmsg_to_arr(cqmsg) -> list:
    # 将 string 格式的 message 转化为 array 格式
    # https://github.com/botuniverse/onebot-11/blob/master/message/README.md
    if isinstance(cqmsg,list):
        return cqmsg
    cqstr = cqmsg
    text = ""
    type_ = ""
    key = ""
    val = ""
    jsonarr = []
    cqcode = {}
    stat = 0
    i = 0
    while i < len(cqstr):
        cur_ch = cqstr[i]
        if stat == 0:
            if cur_ch == '[':
                t = ""
                if i + 4 > len(cqstr):
                    t = ""
                else:
                    t = cqstr[i:i+4]
                if t == "[CQ:":
                    if len(text) != 0:
                        node = {}
                        node["type"] = "text"
                        node["data"] = {"text": text}
                        jsonarr.append(node)
                        text = ""
                    stat = 1
                    i += 3
                else:
                    text += cqstr[i]
            elif cur_ch == '&':
                t = ""
                if i + 5 > len(cqstr):
                    t = ""
                else:
                    t = cqstr[i : i+5]
                if t == "&#91;":
                    text += '['
                    i += 4
                elif t == "&#93;":
                    text += ']'
                    i += 4
                elif t == "&amp;":
                    text += '&'
                    i += 4
                else:
                    text += cqstr[i]
            else:
                text += cqstr[i]
        elif stat == 1:
            if cur_ch == ',':
                stat = 2
            elif cur_ch == '&':
                t = ""
                if i + 5 > len(cqstr):
                    t = ""
                else:
                    t = cqstr[i : i+5]
                if t == "&#91;":
                    type_ += '['
                    i += 4
                elif t == "&#93;":
                    type_ += ']'
                    i += 4
                elif t == "&amp;":
                    type_ += '&'
                    i += 4
                elif t == "&#44;":
                    type_ += ','
                    i += 4
                else:
                    type_ += cqstr[i]
            else:
                type_ += cqstr[i]
        elif stat == 2:
            if cur_ch == '=':
                stat = 3
            elif cur_ch == '&':
                t = ""
                if i + 5 > len(cqstr):
                    t = ""
                else:
                    t = cqstr[i : i+5]
                if t == "&#91;":
                    key += '['
                    i += 4
                elif t == "&#93;":
                    key += ']'
                    i += 4
                elif t == "&amp;":
                    key += '&'
                    i += 4
                elif t == "&#44;":
                    key += ','
                    i += 4
                else:
                    key += cqstr[i]
            else:
                key += cqstr[i]
        elif stat == 3:
            if cur_ch == ']':
                node = {}
                cqcode[key] = val
                node["type"] = type_
                node["data"] = cqcode
                jsonarr.append(node)
                key = ""
                val = ""
                type_ = ""
                cqcode = {}
                stat = 0
            elif cur_ch == ',':
                cqcode[key] = val
                key = ""
                val = ""
                stat = 2
            elif cur_ch == '&':
                t = ""
                if i + 5 > len(cqstr):
                    t = ""
                else:
                    t = cqstr[i : i+5]
                if t == "&#91;":
                    val += '['
                    i += 4
                elif t == "&#93;":
                    val += ']'
                    i += 4
                elif t == "&amp;":
                    val += '&'
                    i += 4
                elif t == "&#44;":
                    val += ','
                    i += 4
                else:
                    val += cqstr[i]
            else:
                val += cqstr[i]
        i += 1
    if len(text) != 0:
        node = {}
        node["type"] = "text"
        node["data"] = {"text": text}
        jsonarr.append(node)
    return jsonarr


def _cq_text_encode(data: str) -> str:
    ret_str = ""
    for ch in data:
        if ch == "&":
            ret_str += "&amp;"
        elif ch == "[":
            ret_str += "&#91;"
        elif ch == "]":
            ret_str += "&#93;"
        else:
            ret_str += ch
    return ret_str

def _cq_params_encode(data: str) -> str:
    ret_str = ""
    for ch in data:
        if ch == "&":
            ret_str += "&amp;"
        elif ch == "[":
            ret_str += "&#91;"
        elif ch == "]":
            ret_str += "&#93;"
        elif ch == ",":
            ret_str += "&#44;"
        else:
            ret_str += ch
    return ret_str


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

    def _cqarr_to_satori(self,cqarr):
        ret = ""
        for node in cqarr:
            if node["type"] == "text":
                ret += node["data"]["text"]
            elif node["type"] == "at":
                qq = node["data"]["qq"]
                if qq == "all":
                    ret += "<at type=\"all\"/>"
                else:
                    ret += "<at id={}/>".format(json.dumps(qq))
            elif node["type"] == "image":
                url = node["data"]["url"]
                ret += "<img src={}/>".format(json.dumps(url))
        return ret

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
                try:
                    self._login_status = 2 # CONNECT
                    async with connect(self._ws_url) as websocket:
                        print("onebot:ws已经连接")
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
                except Exception as e:
                    print(e)
                    print("onebot:ws连接已经断开")
                    self._login_status = 3 # DISCONNECT
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
                    "content":self._cqarr_to_satori(_cqmsg_to_arr(evt["message"])),
                    "created_at":int(str(evt["time"] ) + "000")
                }
                role_obj = {
                        "id":get_json_or(sender,"role","member"),
                        "name":get_json_or(sender,"role","member")
                    }
                satori_evt = {
                    "id":self._id,
                    "type":"message-created",
                    "platform":"onebot",
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
                        "type":3,
                        "name":None,
                        "parent_id":None
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
                    "content":self._cqarr_to_satori(_cqmsg_to_arr(evt["message"])),
                    "created_at":int(str(evt["time"] ) + "000")
                }
                satori_evt = {
                    "id":self._id,
                    "type":"message-created",
                    "platform":"onebot",
                    "self_id":str(evt["self_id"]),
                    "timestamp":int(str(evt["time"] ) + "000"),
                    "channel":channel_obj,
                    "message":message_obj,
                    "user":user_obj
                }
                self._id += 1
                self._queue.put_nowait(satori_evt)
        elif post_type == "notice":
            notice_type = evt["notice_type"]
            if notice_type == "group_increase":
                guild_obj = {
                    "id":"GROUP_"+str(evt["group_id"]),
                    "name":None,
                    "avatar":None
                }
                member_obj = {
                    "nick":None,
                    "avatar":get_json_or(evt,"avatar",None),
                    "joined_at":int(str(evt["time"] ) + "000")
                }
                user_obj = {
                    "id":str(evt["user_id"]),
                    "name":None,
                    "nick":None,
                    "avatar":None,
                    "is_bot":None
                }
                satori_evt = {
                    "id":self._id,
                    "type":"guild-member-added",
                    "platform":"onebot",
                    "self_id":str(evt["self_id"]),
                    "timestamp":int(str(evt["time"] ) + "000"),
                    "guild":guild_obj,
                    "member":member_obj,
                    "user":user_obj
                }
                self._id += 1
                self._queue.put_nowait(satori_evt)

    async def _api_call(self,path,data) -> dict:
        url:str = self._http_url + path
        if self._access_token:
            headers = {"Authorization":"Bearer {}".format(self._access_token)}
        else:
            headers = {}
        async with httpx.AsyncClient() as client:
            return (await client.post(url,headers=headers,data=data)).json()
    
    async def _satori_to_cq(self,satori_obj) -> str:
        ret = ""
        for node in satori_obj:
            if isinstance(node,str):
                ret += _cq_text_encode(node)
            else:
                if node["type"] == "at":
                    type = get_json_or(node["attrs"],"type",None)
                    id = get_json_or(node["attrs"],"id",None)
                    if type == "all":
                        ret += "[CQ:at,qq=all]"
                    elif id != None:
                        ret += "[CQ:at,qq={}]".format(_cq_params_encode(id))
                elif node["type"] == "img":
                    ret += "[CQ:image,file={}]".format(_cq_params_encode(node["attrs"]["src"])) 

        return ret


    async def create_message(self,platform:str,self_id:str,channel_id:str,content:str):
        '''发送消息'''
        satori_obj = parse_satori_html(content)
        to_send = await self._satori_to_cq(satori_obj)
        if channel_id.startswith("GROUP_"):
            group_id = int(channel_id[6:])
            ret = await self._api_call("/send_group_msg",{"group_id":group_id,"message":to_send})
            return [{"id":str(ret["data"]["message_id"]),"content":""}]
        else:
            user_id = int(channel_id)
            ret = await self._api_call("/send_private_msg",{"user_id":user_id,"message":to_send})
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
            "platform":"onebot",
            "status":self._login_status,
        }
        if platform == None and self_id == None:
            return [satori_ret]
        else:
            return satori_ret
        
    async def get_guild_member(self,platform:Optional[str],self_id:Optional[str],guild_id:str,user_id:str) -> [dict]:
        '''获取群组成员信息，如果platform和self_id为空，那么应该返回一个列表'''
        obret =  (await self._api_call("/get_group_member_info",{
            "group_id":int(guild_id[6:]),
            "user_id":int(user_id)
        }))["data"]
        joined_at = get_json_or(obret,"join_time",None)
        if joined_at:
            joined_at = int(str(joined_at) + "000")
        satori_ret = {
            "user":{
                "id":str(obret["user_id"]),
                "name":get_json_or(obret,"nickname",None),
                "nick":get_json_or(obret,"card",None),
                "avatar":get_json_or(obret,"avatar",None),
                "is_bot":None
            },
            "nick":get_json_or(obret,"card",None),
            "avatar":get_json_or(obret,"avatar",None),
            "joined_at":joined_at,
        }
        return satori_ret