import copy

def get_json_or(js,key,default):
    if key in js:
        if js[key] != None:
            return js[key]
    return default

def remove_json_null(js) -> dict:
    if isinstance(js,dict):
        st = {}
        for key in js:
            if js[key] != None:
                st[key] = remove_json_null(js[key])
        return st
    else:
        return js