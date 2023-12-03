import aiofiles
import json

class Config:
    def __init__(self) -> None:
        self.botlist:list = []
        self.web_port:int = 8080
        self.web_host:str = "127.0.0.1"
        self.access_token:str = ""
    
    async def read_config(self):
        async with aiofiles.open('config.json', mode='r') as f:
            json_dat = json.loads(await f.read())
        self.botlist = json_dat["botlist"]
        self.web_port = json_dat["web_port"]
        self.web_host = json_dat["web_host"]
        self.access_token = json_dat["access_token"]