import discord
from discord.ext import commands, tasks
import aiohttp
import random


colours = [
    discord.Colour.red(),
    discord.Colour.gold(),
    discord.Colour.green(),
    discord.Colour.blurple(),
    discord.Colour.gold(),
]


class fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def meme(self, ctx):
        global colours
        embed = discord.Embed(description="", color=random.choice(colours))
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        async with aiohttp.ClientSession() as cs:
            async with cs.get(
                "https://www.reddit.com/r/dankmemes/new.json?sort=hot"
            ) as r:
                res = await r.json()
                rand = random.randint(0, 20)
                if not res["data"]["children"][0]["data"]["url"]:
                    pass
                else:
                    embed.set_image(url=res["data"]["children"][rand]["data"]["url"])
                embed.title = res["data"]["children"][rand]["data"]["title"]
                embed.url = res["data"]["children"][rand]["data"]["url"]
                embed.set_footer(
                    text="👍"
                    + str(res["data"]["children"][0]["data"]["ups"])
                    + "      👎"
                    + str(res["data"]["children"][0]["data"]["downs"])
                )
                await ctx.send_or_webhook(embed=embed)

    @commands.command(
        aliases=["r", "re"],
        help='get the first image from a subreddit e.g. `"reddit softwaregore`',
    )
    async def reddit(self, ctx, *, subreddit):
        embed = discord.Embed(description="", color=discord.Colour.red())
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        async with aiohttp.ClientSession() as cs:
            async with cs.get(
                f"https://www.reddit.com/r/{subreddit}/new.json?sort=hot"
            ) as r:
                res = await r.json()
                if (
                    res["data"]["children"][0]["data"]["over_18"] == True
                    and not ctx.message.channel.is_nsfw()
                ):
                    return await ctx.send_or_webhook("This is not an NSFW channel.")

                if not res["data"]["children"][0]["data"]["url"]:
                    pass
                else:
                    embed.set_image(url=res["data"]["children"][0]["data"]["url"])
                embed.title = res["data"]["children"][0]["data"]["title"]
                embed.url = res["data"]["children"][0]["data"]["url"]
                embed.set_footer(
                    text="👍"
                    + str(res["data"]["children"][0]["data"]["ups"])
                    + "      👎"
                    + str(res["data"]["children"][0]["data"]["downs"])
                )
                await ctx.send_or_webhook(embed=embed)

    @commands.command(aliases=["short", "sh"])
    async def shorten(self, ctx, *, url):
        async with aiohttp.ClientSession() as cs:
            data = {"url": url}
            async with cs.post("https://cleanuri.com/api/v1/shorten", data=data) as r:
                resp = await r.json()
                embed = discord.Embed(
                    title="__Shortened url__",
                    description=resp["result_url"],
                    color=discord.Color.random(),
                )
                await ctx.send_or_webhook(embed=embed)

    @commands.command(aliases=["qr"])
    async def qrcode(self, ctx, data):
        emb = discord.Embed(title="__qr code__", color=discord.Color.random())
        emb.set_image(
            url=f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={data}"
        )
        await ctx.send_or_webhook(embed=emb)

    @commands.command(aliases=["inspireme", "quote"])
    async def inspirobot(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://inspirobot.me/api?generate=true") as r:
                resp = await r.text()
                embed = discord.Embed(title="Quote", color=discord.Colour.random())
                embed.set_image(url=resp)
                await ctx.send(embed=embed)

    @commands.command(name="changepresence", aliases=["cp", "presence"])
    async def commandName(self, ctx: commands.Context, game):
        await self.bot.change_presence(activity=discord.Game(game))

    @commands.command(aliases=["ns"])
    async def nasa(self, ctx):
        url = "https://api.nasa.gov/planetary/apod?api_key=523p5hPYHGzafYGLCkqa54kKMTV2vbP0XcPxkcLm"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                resp = await r.json()
                await ctx.send_or_webhook(resp["url"].replace("/embed/", "/watch?v="))

    @commands.command(aliases=["dj", "dadj"])
    async def dadjoke(self, ctx):
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://icanhazdadjoke.com/", headers={"accept": "text/plain"}
            ) as r:
                resp = await r.text()
                await ctx.send_or_webhook(resp)

    @commands.command(aliases=["db", "dash"])
    async def dashboard(self, ctx):
        embed = discord.Embed(
            title="Website",
            description="[Click here](http://delta-beats.github.io/login/)",
            color=discord.Color.blue(),
        )
        await ctx.send_or_webhook(embed=embed)

    @commands.command()
    async def twitch(self, ctx, user: str):
        users = self.bot.client2.users.translate_usernames_to_ids([user])
        user = users[0]
        info = self.bot.check_user(user.id)
        await ctx.send_or_webhook(
            f"{'The user is online' if info == True else 'This user is offline'}"
        )

    @commands.command(hidden=True)
    async def redditspam(self, ctx, subreddit, number: int):
        userids = [579699536000188417, 753299189210808430, 412673854842863616]
        if ctx.author.id in userids:
            for x in range(number):
                y = random.randint(1, 20)
                embed = discord.Embed(description="", color=discord.Colour.red())
                embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(
                        f"https://www.reddit.com/r/{subreddit}/new.json?sort=new"
                    ) as r:
                        res = await r.json()
                        if (
                            res["data"]["children"][y]["data"]["over_18"] == True
                            and not ctx.message.channel.is_nsfw()
                        ):
                            await ctx.send_or_webhook(
                                f'{"This is not an NSFW channel." if not ctx.author.id in userids else "This is not an NSFW channel but Ill let you off"}'
                            )
                            if not ctx.author.id == 753299189210808430:
                                return

                        if not res["data"]["children"][y]["data"]["url"]:
                            pass
                        else:
                            embed.set_image(
                                url=res["data"]["children"][y]["data"]["url"]
                            )
                        embed.title = res["data"]["children"][y]["data"]["title"]
                        embed.url = res["data"]["children"][y]["data"]["url"]
                        embed.set_footer(
                            text="👍"
                            + str(res["data"]["children"][y]["data"]["ups"])
                            + "      👎"
                            + str(res["data"]["children"][y]["data"]["downs"])
                        )
                        await ctx.send_or_webhook(embed=embed)
        else:
            await ctx.send_or_webhook("You don't have permission to run this command.")


def setup(bot):
    bot.add_cog(fun(bot))
