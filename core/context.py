from discord.ext.commands import Context
from discord import Message
from os import path
from json import load

class DeltaCotext(Context):
    async def send_or_webhook(self, **options):
        message = Message(**options)
        if path.exists(f"../data/webhooks/{self.guild.id}.json"):
            with open(f"../data/webhooks/{self.guild.id}.json", encoding="utf8", ) as json_file_io:
                webhook_data = load(json_file_io)
                webhook_obj = await self.bot.fetch_webhook(webhook_data["id"])
                await webhook_obj.send(message)

        else:
            await self.send(message)
            
