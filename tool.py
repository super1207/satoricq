import copy
from html.parser import HTMLParser

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
            
