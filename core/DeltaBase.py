import json
import logging
from discord.ext import commands
from discord.ext.commands import CommandInvokeError
from clint.textui import colored
from datetime import datetime
from aiohttp import ClientSession
import classes

log = logging.getLogger(__name__)


class Delta(commands.Bot):
    """
    Base class for Delta
    """

    def __init__(self, command_prefix, description, cogloader, **options):
        super().__init__(command_prefix, description=description, **options)
        self.classes = classes
        self.cogloader = cogloader
        self.debug_guilds=self.get_config('test_guilds')

    def get_config(self, key_type: str):
        json_file = open("../data.json", "rt", encoding="utf8", )
        api_keys = json.load(json_file)
        json_file.close()
        if key_type in api_keys:
            return api_keys[key_type]
        else:
            raise CommandInvokeError(
                f"""The shared API key {key_type} has not been set. Please set it in data.json"""
            )

    def log(self, message, log_type: str, newline_prefix: bool = False):
        if log_type == "info":
            now = datetime.now()
            print(
                colored.cyan(
                    now.strftime("%m/%d/%Y %H:%M:%S ")
                ),
                colored.blue("INFO - "),
                message,
            )
            log.info(now.strftime("%m/%d/%Y %H:%M:%S ") ,"INFO - ", message)

        elif log_type == "error":
            now = datetime.now()
            print(
                colored.cyan(
                    "\n" if newline_prefix else "", now.strftime("%m/%d/%Y %H:%M:%S")
                ),
                colored.red("ERROR - "),
                message,
            )
            log.error(now.strftime("%m/%d/%Y %H:%M:%S ") ,"INFO - ", str(message))

    async def get_soundcloud_artwork(self, track_url:str):
        if track_url.startswith("soundcloud.com"):
            async with ClientSession() as session:
                async with session.get(f'https://scimagefetcher.ddb08.repl.co/?url={track_url}/') as result:
                    if result.status == 500:
                        return None
                    text_result = await result.text()
                    return text_result.replace('-large', '-t500x500')
        else:
            return None
