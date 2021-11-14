import re
import aiohttp
import discord
from discord.ext import commands, tasks
from clint.textui import colored
from time import time
from requests import get
import requests as req
import lavalink
from lavalink import DefaultPlayer
from aiohttp import web

start = time()

RURL = re.compile(r"https?:\/\/(?:www\.)?.+")

app = web.Application()
routes = web.RouteTableDef()


class ActiveUser:
    """
    This class represents an active user on Delta's dashboard.
    """

    def __init__(self, access_token:str, code:str) -> None:
        self.access_token = access_token
        self.code = code


class APIServer(commands.Cog):
    """
    Cog to handle backend of Delta's website.
    If you like, you can use this to create your own frontend.
    """

    def __init__(self, bot: commands.Bot):
        self.oauth_codes = {}
        self.bot = bot
        self.web_server.start()
        self.active_users = {}

        @routes.get("/api/userinfo/{code}/")
        async def userinfo(request):
            client_id = bot.get_config("discord-oauth-client-id")
            client_secret = bot.get_config("discord-oauth-client-secret")
            api_endpoint = "https://discord.com/api/v8"
            access_token_url = "https://discord.com/api/oauth2/token"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    access_token_url,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "authorization_code",
                        "code": request.match_info["code"],
                        "redirect_uri": "https://delta-beats.github.io/dashboard",
                        "scopes": "identify,guilds",
                    },
                ) as response:
                    access_token = await response.json()

            if "access_token" in access_token.keys():
                user_object = req.get(
                    url=f"{api_endpoint}/users/@me",
                    headers={"Authorization": f'Bearer {access_token["access_token"]}'},
                ).json()
                self.active_users[user_object["id"]] = ActiveUser(
                    access_token=access_token["access_token"],
                    code=request.match_info["code"],
                )
            else:
                user_object = '{"Status": "403"}'
            return web.json_response(user_object)

        @routes.get("/api/update/{id}/{code}/")
        async def update(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    print(self.verify(request.match_info["code"], request.match_info["id"]))
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player: lavalink.DefaultPlayer = (
                                    self.bot.lavalink.player_manager.get(
                                        int(guild["id"])
                                    )
                                )
                                if player is not None and player.is_connected:
                                    if player.is_playing:
                                        artwork = await self.bot.get_soundcloud_artwork(
                                            player.current.uri.replace("https://", "")
                                        )
                                    else:
                                        artwork = "https://i.imgur.com/0hZ5lnE.png"
                                    queue = [_.title for _ in player.queue]
                                    return web.json_response(
                                        {
                                            "paused": player.paused,
                                            "completed": player.position
                                            if player.is_playing
                                            else 100,
                                            "target": player.current.duration
                                            if player.is_playing
                                            else 0,
                                            "volume": player.volume,
                                            "current": player.current.uri
                                            if player.is_playing
                                            else None,
                                            "current_title": player.current.title
                                            if player.is_playing
                                            else "Nothing playing",
                                            "artwork": artwork,
                                            "connected": True,
                                            "queue": queue,
                                        }
                                    )
                                else:
                                    joined = await self.maybe_join_voice_channel(
                                        guild_object, voice_channel.id, user.id
                                    )
                                    return web.json_response(
                                        {"connected": True if joined == 200 else False},
                                        status=406,
                                    )

        @routes.get("/api/addsong/{query}/{id}/{code}/")
        async def addsong(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player = self.bot.lavalink.player_manager.get(
                                    int(guild["id"])
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    query = request.match_info["query"]

                                    if not query.startswith("https://"):
                                        query = f"scsearch:{query}"

                                    results = await player.node.get_tracks(query)

                                    if not results or not results["tracks"]:
                                        return web.json_response(
                                            {"success": False}, status=200
                                        )

                                    if results["loadType"] == "PLAYLIST_LOADED":
                                        tracks = results["tracks"]

                                        for track in tracks:
                                            track = bot.classes.ImageTrack(
                                                data=track,
                                                requester=request.match_info["id"],
                                                image=await self.bot.get_soundcloud_artwork(
                                                    track["info"]["uri"]
                                                ),
                                            )
                                            player.add(
                                                requester=request.match_info["id"],
                                                track=track,
                                            )
                                        return web.json_response(
                                            {"success": True, "type": "playlist"},
                                            status=200,
                                        )
                                    else:
                                        track = results["tracks"][0]

                                        track = bot.classes.ImageTrack(
                                            data=track,
                                            requester=request.match_info["id"],
                                            image=await self.bot.get_soundcloud_artwork(
                                                track["info"]["uri"]
                                            ),
                                        )
                                        track.image = (
                                            await self.bot.get_soundcloud_artwork(
                                                track.uri
                                            )
                                        )
                                        player.add(
                                            request.match_info["id"], track=track
                                        )
                                        return web.json_response(
                                            {"success": True, "type": "track"},
                                            status=200,
                                        )
                                else:
                                    await self.maybe_join_voice_channel(
                                        guild_object, voice_channel.id, user.id
                                    )
                                    return web.json_response(
                                        {"success": False}, status=406
                                    )

        @routes.get("/api/toggleplaypause/{id}/{code}/")
        async def toggle_play_pause(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player = self.bot.lavalink.player_manager.get(
                                    int(guild["id"])
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    if player.paused:
                                        await player.set_pause(False)
                                        return web.Response(
                                            status=200, text="was_paused"
                                        )
                                    elif not player.paused:
                                        await player.set_pause(True)
                                        return web.Response(
                                            status=200, text="was_not_paused"
                                        )
                                else:
                                    return web.Response(
                                        status=406, text="not_connected"
                                    )

        @routes.get("/api/shuffle/{id}/{code}/")
        async def shuffle(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player: DefaultPlayer = (
                                    self.bot.lavalink.player_manager.get(
                                        int(guild["id"])
                                    )
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    player.shuffle = not player.shuffle
                                    return web.Response(status=200)
                                else:
                                    return web.Response(
                                        status=406, text="not_connected"
                                    )

        @routes.get("/api/skip_forward/{id}/{code}/")
        async def skip_forward(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player: DefaultPlayer = (
                                    self.bot.lavalink.player_manager.get(
                                        int(guild["id"])
                                    )
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    await player.set_pause(False)
                                    await player.skip()
                                    return web.Response(status=200)
                                else:
                                    return web.Response(
                                        status=406, text="not_connected"
                                    )

        @routes.get("/api/stop/{id}/{code}/")
        async def stop(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player = self.bot.lavalink.player_manager.get(
                                    int(guild["id"])
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    await player.stop()
                                    return web.Response(status=200)
                                else:
                                    return web.Response(
                                        status=406, text="not_connected"
                                    )

        @routes.get("/api/skip_back/{id}/{code}/")
        async def skip_back(request):
            verified = self.verify(request.match_info["code"], request.match_info["id"])
            if not verified:
                return web.Response(status=403)
            guilds = await self.get_guilds(request.match_info["id"])
            for guild in guilds:
                guild_object = self.bot.get_guild(int(guild["id"]))
                if guild_object is not None:
                    for voice_channel in guild_object.voice_channels:
                        for user in voice_channel.members:
                            if str(user.id) == request.match_info["id"]:
                                player = self.bot.lavalink.player_manager.get(
                                    int(guild["id"])
                                )
                                if (
                                    hasattr(player, "is_connected")
                                    and player.is_connected
                                ):
                                    track_time = player.position - 5000
                                    await player.seek(track_time)
                                    return web.Response(status=200)
                                else:
                                    return web.Response(
                                        status=406, text="not_connected"
                                    )

        @routes.get("/")
        async def slash(_request):
            return web.Response(text="API server running.")

        self.webserver_port = 1234
        app.add_routes(routes)

    def fetch_player(self, guild_id: int, region: str):
        player = self.bot.lavalink.player_manager.get(int(guild_id))
        if not player:
            player = self.bot.lavalink.player_manager.create(
                guild_id, endpoint=str(region)
            )
        return player

    def verify(self, code:str, user_id:int):
        user = self.active_users[user_id]
        if user.code == code:
            return True
        else:
            return False

    async def get_guilds(self, user_id: int):
        """Function to fetch the guilds a user is in from the access token provided with a user's session

        Args:
            user_id (int): ID of the user to fetch guilds for

        Returns:
            guild_object (list): list of guild dicts.
        """
        access_token = self.active_users[user_id].access_token
        api_endpoint = "https://discord.com/api/v9/"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_endpoint}users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                guilds = await response.json()
        return guilds

    async def maybe_join_voice_channel(
        self, guild: discord.Guild, channel_id: int, user_id: int
    ):
        """Function to join a voice channel if the bot is not already in it

        Args:
            guild_id (int): ID of the guild to join
            channel_id (int): ID of the voice channel to join
        """
        member = guild.get_member(user_id)
        player = self.bot.lavalink.player_manager.get(guild.id)
        if player is None:
            player = self.bot.lavalink.player_manager.create(
                guild.id, endpoint=str(guild.region)
            )
        if player.current is not None:
            if player.current.requester != user_id:
                return 403

        if guild is not None:
            voice_channel = guild.get_channel(channel_id)
            if voice_channel is not None:
                if hasattr(player, "channel") and player.channel != voice_channel:
                    await player.move_to(voice_channel)
                    return 200
                else:
                    await member.voice.channel.connect(
                        cls=self.bot.classes.LavalinkVoiceClient
                    )
                    return 200
        else:
            return 500

    @tasks.loop()
    async def web_server(self):
        """
        This task ensures that the web server is reloaded every time a change is made to the cog.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.ipify.org/") as response:
                ip_address = await response.text()

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=self.webserver_port)
        await site.start()
        self.bot.log(
            f"Initialised api server in {round(time()-start, 1)} seconds", "info"
        )
        self.bot.log(f"My public IP address is: {ip_address}", "info")

    @web_server.before_loop
    async def web_server_before_loop(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(APIServer(bot))
