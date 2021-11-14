import io
import math
import os
import datetime
from subprocess import Popen, DEVNULL
import typing
import asyncio
import aiofiles
from discord.ext import commands
import wavelink
import requests
import lavalink
import re
from .Views.Confirm import Confirm
import aiohttp
import discord  # pyright: reportMissingImports=false
from discord import Color
from typing import Optional, Union
from youtubesearchpython.__future__ import VideosSearch
from async_timeout import timeout
import humanize
import asyncio.subprocess

url_rx = re.compile(r"https?://(?:www\.)?.+")

class ImageTrack(lavalink.models.AudioTrack):
    def __init__(self, data: dict, requester: int, **extra):
        super().__init__(data, requester, **extra)
        self.image = extra['image']


def get_spotify_token():
    response = requests.get("https://open.spotify.com/get_access_token/")
    return response.json()["accessToken"]


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lavalink_proc = None

    def cog_unload(self):
        """Cog unload handler. This removes any event hooks that were registered."""
        self.bot.lavalink._event_hooks.clear()
        self.lavalink_proc.kill()

    async def cog_before_invoke(self, ctx):
        """Command before-invoke handler."""

        guild_check = ctx.guild is not None

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author are in the same voicechannel.

        return guild_check

    async def ensure_voice(self, ctx):
        """This check ensures that the bot and command author are in the same voicechannel."""
        player = self.bot.lavalink.player_manager.create(
            ctx.guild.id, endpoint=str(ctx.guild.region)
        )
        # Create returns a player if one exists, otherwise creates.
        # This line is important because it ensures that a player always exists for a guild.

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Our cog_command_error handler catches this and sends it to the voicechannel.
            # Exceptions allow us to "short-circuit" command invocation via checks so the
            # execution state of the command goes no further.
            raise commands.CommandInvokeError("Join a voicechannel first.")

        if not player.is_connected:
            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if (
                not permissions.connect or not permissions.speak
            ):  # Check user limit too?
                raise commands.CommandInvokeError(
                    "I need the `CONNECT` and `SPEAK` permissions."
                )

            player.store("channel", ctx.channel.id)
            await ctx.author.voice.channel.connect(cls=self.bot.classes.LavalinkVoiceClient)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError("You need to be in my voicechannel.")

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            # When this track_hook receives a "QueueEndEvent" from lavalink.py
            # it indicates that there are no tracks left in the player's queue.
            # To save on resources, we can tell the bot to disconnect from the voicechannel.
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            await guild.voice_client.disconnect(force=True)

        elif (
            isinstance(event, lavalink.events.TrackStartEvent)
            and not event.player.paused is True
        ):
            channel = event.player.fetch("channel")
            channel = self.bot.get_channel(channel)
            await asyncio.sleep(1)
            player: lavalink.models.DefaultPlayer = event.player
            if player.current.stream:
                duration = "🔴 LIVE"
            else:
                duration = lavalink.utils.format_time(player.current.duration)
            song = player.current.title
            embed = discord.Embed(
                title="__**Now Playing**__", description=f"Current: `{song}`"
            )
            if player.current.image is not None:
                embed.set_thumbnail(url=player.current.image)
            else:
                pass

            embed.add_field(name="⏳ Duration", value=f"`{duration}`", inline=True)
            if player.current.stream:
                embed.add_field(name="🕛 Next song in:", value="🔴 Live", inline=True)
            else:
                embed.add_field(
                    name="🕛 Next song in:",
                    value=f"`{lavalink.utils.format_time(player.current.duration - player.position)}`",
                    inline=True,
                )
            embed.add_field(
                name="🎤 Artist:", value=f"`{player.current.author}`", inline=True
            )
            embed.add_field(name="🔊 Volume: ", value=f"`{player.volume}%`", inline=True)
            embed.add_field(
                name="🔁 Repeat: ",
                value=f"`{'Off' if not player.repeat else 'On'}`",
                inline=True,
            )
            if not player.current.uri:
                pass
            else:
                embed.add_field(
                    name="🖥️ Url:",
                    value=f"[click here]({player.current.uri})",
                    inline=True,
                )
            if channel is not None:
                await channel.send(embed=embed)

    async def cog_command_error(self, ctx, error):
        """
        Error handler for user induced exceptions.
        """
        if isinstance(error, discord.ext.commands.errors.CommandInvokeError):
            await ctx.send(error.original)
        else:
            self.bot.log(error.original, "error")

    async def initialize_lavalink(self):
        # This ensures the client isn't overwritten during cog reloads.
        if not hasattr(self.bot, "lavalink"):
            self.bot.lavalink_running = False
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            self.bot.add_listener(self.bot.lavalink.voice_update_handler, "on_socket_response")
        lavalink.add_event_hook(self.track_hook)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/repos/cog-creators/lavalink-jars/releases/latest"
            ) as latest_release:
                release_info = await latest_release.json()
                latest_release_download_url = release_info["assets"][0][
                    "browser_download_url"
                ]
                latest_release_build = release_info["tag_name"][-4:]
                async with session.get(latest_release_download_url) as raw_download:
                    if (
                        os.path.exists("Music/Lavalink/Lavalink.jar")
                        and latest_release_build
                        in str(Popen(
                            "java", "-jar", "Lavalink.jar", "--version"
                        ).stdout.read())
                    ):
                        return
                    Popen(["rm", "cogs/Music/Lavalink/Lavalink.jar"], stderr=DEVNULL)
                    download_dest = await aiofiles.open(
                        "cogs/Music/Lavalink/Lavalink.jar", "wb"
                    )
                    self.bot.log(
                        "Downloading Lavalink jar, please do not shut down the bot...",
                        "info",
                    )
                    raw_download = await raw_download.read()
                    await download_dest.write(raw_download)
                    self.bot.log("Downloaded Lavalink jar. Executing...", "info")
                    # Wait for the Lavalink server to start. On a 64 bit x86 ubuntu machine, this typically takes about 13 seconds
                    self.lavalink_proc = (  # pylint:disable=no-member
                        await asyncio.subprocess.create_subprocess_exec(
                            *[
                                self.bot.get_config("java-home"),
                                "-Djdk.tls.client.protocols=TLSv1.2",
                                "-jar",
                                "Lavalink.jar",
                            ],
                            stdout=asyncio.subprocess.PIPE,
                            cwd="cogs/Music/Lavalink",
                        )
                    )
                    stdout = await self.lavalink_proc.stdout.readline()
                    if "Unable to access jarfile" in str(stdout):
                        self.log("Your jarfile may be corrupted. Try restarting the bot.", "error")
                    self.bot.log(
                        f"Lavalink is executable started, PID {self.lavalink_proc.pid}", "info"
                    )
                    try:
                        await asyncio.wait_for(self.wait_for_lavalink(), timeout=120)
                        self.bot.log(
                            "Started internal lavalink server. You can ignore the reflective access warning; see https://github.com/freyacodes/Lavalink/issues/295.",
                            "info",
                        )
                        self.bot.lavalink_running = True
                    except TimeoutError:
                        self.bot.log(
                            "Timed out waiting for internal lavalink server to start",
                            "error"
                        )

                    for node in self.bot.get_config("lavalink-nodes"):
                        self.bot.lavalink.add_node(
                            node["host"],
                            node["port"],
                            node["password"],
                            node["region"],
                            node["name"],
                        )

    async def wait_for_lavalink(self) -> None:
        """
        This function is a modified version from Red discord bot, which is released under the MIT lisence.
        https://github.com/Cog-Creators/Red-DiscordBot/blob/b7d8b0552e6d5379cf2426895f1565cd9d87326e/redbot/cogs/audio/manager.py#L230.
        """
        for i in range(50):
            line = await self.lavalink_proc.stdout.readline()
            if "Started Launcher in" in str(line):
                break
            elif "Invalid or corrupt jarfile" in str(line):
                self.bot.log("Lavalink jar is corrupt, re-downloading...", "error")
            else:
                if i == 50:
                    await asyncio.sleep(0.1)
        

    @commands.command(name="join")
    async def connect_(
        self,
        ctx,
        *,
        channel: typing.Union[discord.VoiceChannel, discord.StageChannel] = None,
    ):
        """Connect to a valid voice channel."""
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise discord.DiscordException(
                    "No channel to join. Please either specify a valid channel or join one."
                )

        await ctx.send(f"Connecting to **`{channel.name}`**", delete_after=15)

    @commands.command(aliases=["p"])
    async def play(self, ctx, *, query: str):
        """Searches and plays a song from a given query."""
        # Get the player for this guild from cache.
        player: lavalink.DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip("<>")

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a Soundcloud search for it instead.

        if player.paused:
            await player.set_pause(False)
            await ctx.send("⏯ | Resumed")
        if not query.startswith("https://") and not query.startswith("ytsearch:"):
            query = f"scsearch:{query}"

        if "open.spotify.com" in query:
            token = get_spotify_token()
            async with aiohttp.ClientSession() as cs:
                if "album" in query:
                    if "?highlight=" in query:
                        query = query.split("?highlight=")
                        query = query[0]
                    if "?si=" in query:
                        query = query.split("?si=")
                        query = query[0]
                    async with cs.get(
                        "https://api.spotify.com/v1/albums/"
                        + query.replace("https://open.spotify.com/album/", "")
                        + "/tracks?type=track,episode&access_token="
                        + token
                    ) as r:
                        res = await r.json()
                        if player.paused:
                            player.set_pause(False)
                        counter = 0
                        await ctx.send("Loading album...")
                        for track in res["items"]:
                            if counter == 0 and not player.is_playing:
                                await player.play()
                            artist = track["artists"][0]["name"]
                            if len(artist) < 15:
                                search = VideosSearch(
                                    track["name"] + " " + artist, limit=1
                                )
                            else:
                                search = VideosSearch(track["name"], limit=1)
                            ytresult = await search.next()
                            tracktoadd = ytresult["result"][0]["link"]
                            results = await player.node.get_tracks(tracktoadd)
                            track = results["tracks"][0]
                            track = lavalink.models.AudioTrack(
                                track, ctx.author.id, recommended=True
                            )
                            player.add(requester=ctx.author.id, track=track)
                            counter += 1
                        if not player.is_playing:
                            await player.play()
                        await ctx.send(f"Added {str(counter)} tracks to the queue")
                        return
                elif "open.spotify.com/track/" in query:
                    if "?si=" in query:
                        query = query.split("?si=")
                        query = query[0]
                    async with cs.get(
                        "https://api.spotify.com/v1/tracks/"
                        + query.replace("https://open.spotify.com/track/", "")
                        + "?access_token="
                        + token
                    ) as r:
                        res = await r.json()
                        if player.paused:
                            player.set_pause(False)
                        artist = res["artists"][0]["name"]
                        name = res["name"]
                        if len(artist) < 15:
                            results = await player.node.get_tracks(
                                f"scsearch:{name} {artist}"
                            )
                        else:
                            results = await player.node.get_tracks("scsearch:" + name)
                        if not results["tracks"][0]:
                            results = await player.node.get_tracks("scsearch:" + name)
                            if not results["tracks"][0]:
                                return await ctx.send(
                                    "Sorry, there are no results on Soundcloud for that track"
                                )
                        track = results["tracks"][0]
                        track = lavalink.models.AudioTrack(track, ctx.author.id)
                        player.add(requester=ctx.author.id, track=track)
                        if not player.is_playing:
                            await player.play()
                        await ctx.send("Added track to queue")
                        return
                elif "open.spotify.com/playlist/" in query:
                    if "?si=" in query:
                        query = query.split("?si=")
                        query = query[0]

                    async with cs.get(
                        "https://api.spotify.com/v1/playlists/"
                        + query.replace("https://open.spotify.com/playlist/", "")
                        + "?access_token="
                        + token
                    ) as r:
                        await ctx.send("Loading playlist...")
                        res = await r.json()
                        counter = 0
                        if player.paused:
                            player.set_pause(False)
                        for track in res["tracks"]["items"]:
                            name = res["tracks"]["items"][counter]["track"]["name"]
                            artist = res["tracks"]["items"][counter]["track"]["album"][
                                "artists"
                            ][0]["name"]
                            if len(artist) < 15:
                                results = await player.node.get_tracks(
                                    f"{name} {artist}"
                                )
                            else:
                                results = await player.node.get_tracks(
                                    "scsearch:" + name
                                )
                            try:
                                track = results["tracks"][0]
                            except IndexError:
                                results = await player.node.get_tracks(name)
                                results = results["tracks"][0]

                            track = lavalink.models.AudioTrack(track, ctx.author.id)
                            player.add(requester=ctx.author.id, track=track)
                            counter += 1
                        if not player.is_playing:
                            await player.play()
                        return

                elif "open.spotify.com/artist/" in query:
                    if "?si=" in query:
                        query = query.split("?si=")
                        query = query[0]

                    async with cs.get(
                        "https://api.spotify.com/v1/artists/"
                        + query.replace("https://open.spotify.com/artist/", "")
                        + "/top-tracks"
                        + "?access_token="
                        + token
                        + "&market=US"
                    ) as r:
                        await ctx.send("Loading playlist...")
                        res = await r.json()
                        counter = 0
                        if player.paused:
                            player.set_pause(False)
                        for track in res["tracks"]:
                            name = res["tracks"][counter]["name"]
                            artist = res["tracks"][counter]["artists"][0]["name"]
                            if len(artist) < 15:
                                results = await player.node.get_tracks(
                                    f"scsearch:{name} {artist}"
                                )
                            else:
                                results = await player.node.get_tracks(
                                    "scsearch:" + name
                                )
                            try:
                                track = results["tracks"][0]
                            except IndexError:
                                results = await player.node.get_tracks(name)
                                track = results["tracks"][0]
                            track = lavalink.models.AudioTrack(
                                track, ctx.author.id, recommended=True
                            )
                            player.add(requester=ctx.author.id, track=track)
                            counter += 1
                        if not player.is_playing:
                            await player.play()
                        return

        # Get the results for the query from lavalink.py.
        results = await player.node.get_tracks(query)

        if not results or not results["tracks"]:
            return await ctx.send(f"Nothing found for `{query}`")

        if results["loadType"] == "PLAYLIST_LOADED":
            tracks = results["tracks"]

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)
        else:
            track = results["tracks"][0]

            track = ImageTrack(data=track, requester=ctx.author.id, image=await self.bot.get_soundcloud_artwork(track["info"]["uri"]))
            track.image = await self.bot.get_soundcloud_artwork(track.uri)
            player.add(requester=ctx.author.id, track=track)

        if not player.is_playing:
            await player.play()

        embed = discord.Embed(
            title="Added track to queue", description=f"`{track.title}`", color=0xFF8800
        )
        embed.set_author(
            name="Soundcloud",
            icon_url="https://i1.sndcdn.com/avatars-wQ2we7uDPoXzUVzW-qdr1Yg-t500x500.jpg",
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=["resume"])
    async def pause(self, ctx):
        """Pauses/Resumes the current track."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        if player.paused:
            await player.set_pause(False)
            await ctx.send("⏯ | Resumed")
        else:
            await player.set_pause(True)
            await ctx.send("⏯ | Paused")

    @commands.command(aliases=["vol"])
    async def volume(self, ctx, volume: int = None):
        """Changes the player's volume (0-100)."""

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not volume:
            return await ctx.send(f"🔈 Volume set to {player.volume}%")
        vol = volume
        # wavelink will automatically cap values between, or equal to 0-1000.
        await player.set_volume(vol)
        await ctx.send(f"🔈 | Set to {player.volume}%")

    @commands.command(help="seek a certain part of the song playing e.g. `pb!seek -10`")
    async def seek(self, ctx, *, seconds: int):
        """Seeks to a given position in a track."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        track_time = player.position + (seconds * 1000)
        await player.seek(track_time)

        await ctx.send(f"Moved track to **{lavalink.utils.format_time(track_time)}**")

    @commands.command(aliases=["forceskip"])
    async def skip(self, ctx, times: int = 1):
        """Skips the current track."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        await player.set_pause(True)
        for _ in range(times):
            await player.skip()
        await player.set_pause(False)
        await ctx.send(f'⏭ | Skipped {times} {"songs" if times != 1 else "song"}.')

    @commands.command(aliases=["dc", "stop"])
    async def disconnect(self, ctx):
        """Disconnects the player from the voice channel and clears its queue."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not ctx.author.voice or (
            player.is_connected
            and ctx.author.voice.channel.id != int(player.channel_id)
        ):
            # Abuse prevention. Users not in voice channels, or not in the same voice channel as the bot
            # may not disconnect the bot.
            return await ctx.send("You're not in my voicechannel!")

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("⏹️ | Disconnected.")

    @commands.command(aliases=["np", "n", "playing"])
    async def now(self, ctx):
        """Shows some stats about the currently playing song."""
        player: lavalink.models.DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )
        if player.current.stream:
            duration = "🔴 LIVE"
        else:
            duration = lavalink.utils.format_time(player.current.duration)
        song = player.current.title
        embed = discord.Embed(
            title="__**Now Playing**__", description=f"Current: `{song}`"
        )
        if player.fetch("current_thumbnail"):
            embed.set_thumbnail(url=player.fetch("current_thumbnail"))
        else:
            pass
        embed.add_field(name="⏳ Duration", value=f"`{duration}`", inline=True)
        if player.current.stream:
            embed.add_field(name="🕛 Next song in:", value=f"`{duration}`", inline=True)
        else:
            embed.add_field(
                name="🕛 Next song in:",
                value=f"`{lavalink.utils.format_time(player.current.duration - player.position)}`",
                inline=True,
            )
        embed.add_field(
            name="🎤 Artist:", value=f"`{player.current.author}`", inline=True
        )
        embed.add_field(name="🔊 Volume: ", value=f"`{player.volume}%`", inline=True)
        embed.add_field(
            name="🔁 Repeat: ",
            value=f"`{'Off' if not player.repeat else 'On'}`",
            inline=True,
        )
        if not player.current.uri:
            pass
        else:
            embed.add_field(
                name="🖥️ Url:", value=f"[click here]({player.current.uri})", inline=True
            )
        await ctx.send(embed=embed)

    @commands.cooldown(rate=1,per=5.0,type=commands.BucketType.member)
    @commands.command(name="sharequeue", aliases=["sq", "shareq", "share"])
    async def share(self, ctx: commands.Context):
        """
        Share the queue of the current player. This has a cooldown of 5 seconds to stop people abusing it to fill up the server storage.
        """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued.")

        queue_list = []
        for track in player.queue:
            queue_list.append(track.uri)
        await ctx.send("What do you want the name to be? (Type in the chat below)")
        message = await self.bot.wait_for(
            "message", check=lambda m: m.author == ctx.author
        )
        if os.path.exists(f"data/savedqueues/{message.content}.txt"):
            return await ctx.send("Sorry, this name already exists.")

        await ctx.send(
            "That name is available. Please set a password for your saved queue."
        )

        with open(f"data/savedqueues/{message.author.id}-{message.content}.txt", "x", encoding="utf8") as f:
            f.write(player.current.uri + "\n")
            for track in queue_list:
                f.write(track + "\n")
            f.close()

        await ctx.send(
            f"Successfully saved queue. You can listen again by running `d!loadqueue {message.content}`"
        )

    @commands.command(aliases=["lq"])
    async def loadqueue(self, ctx: commands.Context, queue_name: str = None):
        if not queue_name:
            return await ctx.send(
                "Please provide a name of a saved queue e.g. d!loadqueue myawesomequeue"
            )
        if not os.path.exists(f"data/savedqueues/{queue_name}.txt"):
            return await ctx.send("❌ Sorry, I couldn't find a queue by that name. Either it doesn't exist or isn't owned by you.")
        view = Confirm()
        confirmation_message = await ctx.send(
            "This will delete the current queue. Are you sure you want to continue?",
            view=view,
        )
        await view.wait()
        if view.value is None:
            return await ctx.send("❌ Timed out waiting for a response")
        elif view.value:
            player: lavalink.DefaultPlayer = self.bot.lavalink.player_manager.get(
                ctx.guild.id
            )
            player.queue.clear()
            with open(f"data/savedqueues/{ctx.message.author.id}-{queue_name}.txt", "r", encoding="utf8") as f:
                for line in f.readlines():
                    track = await player.node.get_tracks(line.replace("\n", ""))
                    track = lavalink.models.AudioTrack(
                        track["tracks"][0], ctx.author.id, recommended=True
                    )
                    player.add(track=track, requester=ctx.author.id)
                    if not player.is_playing:
                        await player.play()
                f.close()
            await confirmation_message.edit(content="✅ Loaded tracks.", view=None)
        else:
            await confirmation_message.edit(content="Cancelled.", view=None)

    @commands.command(aliases=["q"])
    async def queue(self, ctx, page: typing.Optional[int] = 1):
        """Shows the player's queue."""

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued.")

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ""
        for index, track in enumerate(player.queue[start:end], start=start):
            queue_list += f"`{index + 1}.` [**{track.title}**]({track.uri})\n"

        embed = discord.Embed(
            colour=discord.Color.blurple(),
            description=f"**{len(player.queue)} tracks**\n\n{queue_list}",
        )
        embed.set_footer(text=f"Viewing page {page}/{pages}")
        await ctx.send(embed=embed)

    @commands.command()
    async def shuffle(self, ctx):
        """Shuffles the player's queue."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player.is_playing:
            return await ctx.send("Nothing playing.")

        player.shuffle = not player.shuffle
        await ctx.send("🔀 | Shuffle " + ("enabled" if player.shuffle else "disabled"))

    @commands.command()
    async def remove(self, ctx, index: int):
        """Removes an item from the player's queue with the given index."""
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued.")

        if index > len(player.queue) or index < 1:
            return await ctx.send(
                f"Index has to be **between** 1 and {len(player.queue)}"
            )

        removed = player.queue.pop(index - 1)  # Account for 0-index.

        await ctx.send(f"Removed **{removed.title}** from the queue.")

    @commands.command(aliases=["loop"])
    async def repeat(self, ctx):
        """Repeats the current song until the command is invoked again."""
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Nothing playing.")

        player.repeat = not player.repeat
        await ctx.send("🔁 | Repeat " + ("enabled" if player.repeat else "disabled"))

    @commands.command(name="bassboost", aliases=["bb"])
    async def _bassboost(self, ctx, level: str = None):
        """Changes the player's bass frequencies up to 4 levels. OFF, LOW, MEDIUM, HIGH and INSANE."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        levels = {
            "OFF": [(0, 0), (1, 0)],
            "LOW": [(0, 0.25), (1, 0.15)],
            "MEDIUM": [(0, 0.50), (1, 0.25)],
            "HIGH": [(0, 0.75), (1, 0.50)],
            "INSANE": [(0, 1), (1, 0.75)],
        }

        if not level:
            for k, v in levels.items():
                if [(0, player.equalizer[0]), (1, player.equalizer[1])] == v:
                    level = k
                    break
            return await ctx.send(
                "Bass boost currently set as `{}`.".format(level if level else "CUSTOM")
            )

        gain = None

        for k in levels.keys():
            if k.startswith(level.upper()):
                gain = levels[k]
                break

        if not gain:
            return await ctx.send("Invalid level.")

        await player.set_gains(*gain)

        await ctx.send(f"Bass boost set on `{k}`.")

    @commands.command()
    async def info(self, ctx):
        """
        Retrieve various Node/Server/Player information.
        """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = (
            f"**Lavalink.py:** `{lavalink.__version__}`\n\n"
            f"Connected to `{len(self.bot.lavalink.node_manager.nodes)}` nodes.\n"
            f"`{len(self.bot.lavalink.stats.playing_players)}` players are distributed on nodes.\n"
            f"`{node.stats.playing_players}` players are playing on server.\n\n"
            f"Server Memory: `{used}/{total}` | `({free} free)`\n"
            f"Server CPU: `{cpu}`\n\n"
            f"Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`"
        )
        await ctx.send(fmt)


def setup(bot):
    bot.add_cog(Music(bot))
