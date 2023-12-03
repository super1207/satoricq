def get_json_or(js,key,default):
    if key in js:
        if js[key] != None:
            return js[key]
    return default