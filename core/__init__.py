import os
import aiohttp
from discord.ext import commands, tasks
import discord
import twitch
from clint.textui import colored
import DeltaBase
import cogloader

os.listdir()

print(colored.red('''
    dMMMMb  dMMMMMP dMP  dMMMMMMP .aMMMb 
   dMP VMP dMP     dMP     dMP   dMP"dMP 
  dMP dMP dMMMP   dMP     dMP   dMMMMMP  
 dMP.aMP dMP     dMP     dMP   dMP dMP   
dMMMMP" dMMMMMP dMMMMMP dMP   dMP dMP    
'''))

players = {}
bot = DeltaBase.Delta(description="An open sourec music bot with a dashboard.", command_prefix=[
                      'd!', 'D!'], case_insensitive=True, help_command=None, intents=discord.Intents.all(), shard_count=10, cogloader=cogloader, debug_guilds=DeltaBase.get_config('debug_guilds'), owner_id=DeltaBase.get_config('owner_id'))

TWITCH_STREAM_API_ENDPOINT_V5 = "https://api.twitch.tv/kraken/streams/{}"

API_HEADERS = {
    'Client-ID': bot.get_config("twitch-client-id"),
    'Accept': 'application/vnd.twitchtv.v5+json',
}


async def checkUser(userID):  # returns true if online, false if not
    url = TWITCH_STREAM_API_ENDPOINT_V5.format(userID)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=API_HEADERS) as req:
                jsondata = await req.json()
                if 'stream' in jsondata:
                    if jsondata['stream'] is not None:  # stream is online
                        return True
                    else:
                        return False
    except Exception as e:
        print("Error checking user: ", e)
        return False

bot.check_user = checkUser

bot.ip = bot.get_config("website-url")
bot.duckdns_token = bot.get_config("duckdns-token")


@tasks.loop(seconds=10)
async def update_ip():
    async with aiohttp.ClientSession() as s:
        async with s.get("https://api.ipify.org/") as res:
            ip_address = await res.text()
        async with s.get(f'https://www.duckdns.org/update?domains=deltadiscordbot.duckdns.org&token={bot.duckdns_token}&ip={ip_address}') as code:
            code = await code.text()

update_ip.start()

@bot.event
async def on_ready():
    bot.cogloader.load_all(bot)
    music = bot.get_cog("Music")
    # This line is essential to ensure the lavalink server is set up correctly.
    await music.initialize_lavalink()

class HelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        global colours
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(title='__**Delta**__', description=page,
                                  colour=discord.Color.red(), url=bot.get_config('website-url'))
            embed.set_thumbnail(
                url='https://images-ext-2.discordapp.net/external/DrsaKdtXk6_XMen3G-lH03b4kK8YD6eXhJjlypqNo50/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/753994539492180029/40aac458bccea808590b6a6e323e2a97.webp?width=1002&height=1002')
            await destination.send(embed=embed)


bot.client2 = twitch.TwitchClient(
    client_id=bot.get_config("twitch-client-id"), oauth_token=bot.get_config('twitch-oauth'))
bot.help_command = HelpCommand()


def author_check(author):
    return lambda message: message.author == author

@bot.event
async def on_message(message):
    await bot.process_commands(message)

bot.run(bot.get_config('token'))
