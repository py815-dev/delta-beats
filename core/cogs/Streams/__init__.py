import asyncio
from aiohttp import ClientSession
from discord.ext import commands, tasks
from discord.ext.commands import slash_command


class Streams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.description = """A cog to send you a youtube notification when a youtube channel is live."""
        self.streams = {}

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Sorry, this command is on cooldown and can be used again in {round(error.retry_after, 2)} seconds.")
        
        else: 
            await ctx.send(error.original)
            self.bot.log(error.original, "error")

    @tasks.loop(seconds=10)
    async def stream_loop(self):
        for channel, list in self.streams.items():
            # List[0] is the stream url, stream[1] is the message to send.
            async with ClientSession() as session:
                async with session.get(list[0]+"/live") as resp:
                    if resp.status == 302:
                        channel_obj = await self.bot.get_channel(channel)
                        await channel_obj.send(list[1])
            await asyncio.sleep(0.1) # Prevent busy looping.


    @commands.guild_only()
    @commands.group(name="streamalert", aliases=["alert"])
    async def streamalert(self, ctx:commands.Context):
        """
        Command group for stream commands
        """
        pass

    @commands.cooldown(1, 60, commands.BucketType.guild)
    @streamalert.command(name="youtube", aliases=["yt"])
    async def set(self, ctx, channel:str=None):
        if self.streams[ctx.channel.id]:
            await ctx.send("You are already set to recieve notifications for a channel, only one notification is allowed per channel.")

        if not channel:
            return await ctx.send("Please provide a channel url")

        if not channel.startswith("https://www.youtube.com/channel/"):
            return await ctx.send("Invalid channel, please ensure it is a url.")

        await ctx.send("what message would you like me to send when this user is live?")

        try:
            message = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long to respond, please run the command again.")
        
        await ctx.send(f"OK, I will now alert you when this user is live on YouTube! Please note that if the bot restarts, you will not be notified.")
        self.streams[channel.id] = [channel.id, message]
    
    @streamalert.command(name="cancel", aliases=["c"])
    async def cancel(self, ctx):
        if self.streams.get(ctx.channel.id):
            del self.streams[ctx.channel.id]
            await ctx.send("OK, I will no longer alert you when this channel is live.")
        else:
            await ctx.send("You are not currently being notified of any streams.")


def setup(bot):
    bot.add_cog(Streams(bot))
