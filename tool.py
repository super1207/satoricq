from html.parser import HTMLParser
from enum import Enum

def get_json_or(js,key,default):
    '''获取json中的字段'''
    if key in js:
        if js[key] != None:
            return js[key]
    return default

def remove_json_null(js) -> dict:
    '''将json中的None字段删除'''
    if isinstance(js,dict):
        st = {}
        for key in js:
            if js[key] != None:
                st[key] = remove_json_null(js[key])
        return st
    elif isinstance(js,list):
        lst = []
        for it in js:
            lst.append(remove_json_null(it))
        return lst
    else:
        return js

class _MyHTMLParser(HTMLParser):
    def __init__(self, *, convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self.data = {
            "data":[]
        }
        self.temp_data = self.data
    def handle_starttag(self, tag, attrs):
        tag_obj = {
            "pre": self.temp_data,
            "type":tag,
            "data":[]
        }
        obj = dict()
        for it in attrs:
            obj[it[0]] = it[1]
        tag_obj["attrs"] = obj
        self.temp_data["data"].append(tag_obj)
        self.temp_data = tag_obj

    def handle_endtag(self, tag):
        last = self.temp_data["pre"]
        del self.temp_data["pre"]
        self.temp_data["data"] = self.temp_data["data"]
        self.temp_data = last

    def handle_data(self, data):
        self.temp_data["data"].append(data)

def parse_satori_html(text):
    parser = _MyHTMLParser()
    parser.feed(text)
    ret = parser.data["data"]
    return ret

def satori_to_plain(text):
    '''将text转为satori的纯文本'''
    ret = ""
    for ch in text:
        if ch == "\"":
            ret += "&quot;"
        elif ch == "&":
            ret += "&amp;"
        elif ch == "<":
            ret += "&lt;"
        elif ch == ">":
            ret += "&gt;"
        else:
            ret += ch
    return ret


class SatoriUser():
    def __init__(self,id:str,name:str = None,avatar:str = None,is_bot:bool = None) -> None:
        self.id = id
        self.name = name
        self.nick = name
        self.avatar = avatar
        self.is_bot = is_bot
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "name":self.name,
            "nick":self.nick,
            "avatar":self.avatar,
            "is_bot":self.is_bot,
        }
    
class SatoriGuildMember():
    def __init__(self,user:SatoriUser = None,nick:str = None,avatar:str = None,joined_at:int = None) -> None:
        self.user = user
        self.nick = nick
        self.avatar = avatar
        self.joined_at = joined_at
    def to_dict(self) -> dict:
        return {
            "user":self.user.to_dict() if self.user else None,
            "nick":self.nick,
            "avatar":self.avatar,
            "joined_at":self.joined_at,
        }
    
class SatoriGuildRole():
    def __init__(self,id,name:str = None) -> None:
        self.id = id
        self.name = name
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "name":self.name,
        }

class SatoriGuild():
    def __init__(self,id,name:str = None,avatar:str = None) -> None:
        self.id = id
        self.name = name
        self.avatar = avatar
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "name":self.name,
            "avatar":self.avatar,
        }
    
class SatoriChannel():
    class ChannelType(Enum):
        TEXT = 0
        DIRECT = 1
        CATEGORY = 2
        VOICE = 3
        
    def __init__(self,id:str,type:ChannelType,name:str = None,parent_id:str = None) -> None:
        self.id = id
        self.type = type
        self.name = name
        self.parent_id = parent_id
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "type":self.type.value,
            "name":self.name,
            "parent_id":self.parent_id,
        }
    
class SatoriGuild():
    def __init__(self,id:str,name:str = None,avatar:str = None) -> None:
        self.id = id
        self.name = name
        self.avatar = avatar
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "name":self.name,
            "avatar":self.avatar,
        }
class SatoriLogin():
    class LoginStatus(Enum):
        OFFLINE = 0
        ONLINE = 1
        CONNECT = 2
        DISCONNECT = 3
        RECONNECT = 4
    def __init__(self,status:LoginStatus,user:SatoriUser = None,self_id:str = None,platform:str = None) -> None:
        self.status = status
        self.user = user
        self.self_id = self_id
        self.platform = platform
    def to_dict(self) -> dict:
        return {
            "status":self.status.value,
            "user":self.user.to_dict() if self.user else None,
            "self_id":self.self_id,
            "platform":self.platform,
        }
    
class SatoriMessage():
    def __init__(self,id:str,content:str,
                 channel:SatoriChannel = None,
                 guild:SatoriGuild = None,
                 member = None,
                 user:SatoriUser = None,
                 created_at:int = None,
                 updated_at:int = None) -> None:
        self.id = id
        self.content = content
        self.channel = channel
        self.guild = guild
        self.member = member
        self.user = user
        self.created_at = created_at
        self.updated_at = updated_at
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "content":self.content,
            "channel":self.channel.to_dict() if self.channel else None,
            "guild":self.guild.to_dict() if self.guild else None,
            "member":self.member.to_dict() if self.member else None,
            "user":self.user.to_dict() if self.user else None,
            "created_at":self.created_at,
            "updated_at":self.updated_at,
        }

class SatoriPrivateMessageCreatedEvent():
    def __init__(self,id:int,platform:str,self_id:str,timestamp:int,channel:SatoriChannel,message:SatoriMessage,user:SatoriUser) -> None:
        self.id = id
        self.type = "message-created"
        self.platform = platform
        self.self_id = self_id
        self.timestamp = timestamp
        self.channel = channel
        self.message = message
        self.user = user
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "type":self.type,
            "platform":self.platform,
            "self_id":self.self_id,
            "timestamp":self.timestamp,
            "channel":self.channel.to_dict(),
            "message":self.message.to_dict(),
            "user":self.user.to_dict(),
        }
    
class SatoriGroupMessageCreatedEvent():
    def __init__(self,id:int,platform:str,self_id:str,timestamp:int,channel:SatoriChannel,message:SatoriMessage,user:SatoriUser,member:SatoriGuildMember,guild:SatoriGuild,role:SatoriGuildRole) -> None:
        self.id = id
        self.type = "message-created"
        self.platform = platform
        self.self_id = self_id
        self.timestamp = timestamp
        self.channel = channel
        self.message = message
        self.user = user
        self.guild = guild
        self.member = member
        self.role = role
    def to_dict(self) -> dict:
        return {
            "id":self.id,
            "type":self.type,
            "platform":self.platform,
            "self_id":self.self_id,
            "timestamp":self.timestamp,
            "channel":self.channel.to_dict(),
            "message":self.message.to_dict(),
            "user":self.user.to_dict(),
            "guild":self.guild.to_dict(),
            "member":self.member.to_dict(),
            "role":self.role.to_dict(),
        }
