"""
This file is used to load the required cogs for Delta.
"""

from time import time
import os
from clint.textui import colored
import discord
from discord.ext import commands

def load_all(bot:commands.Bot):
    """
    Loads every cog in the cogs directory.
    """
    os.chdir('cogs')
    start = time()
    cogs_loaded = 0
    cogs = [folder for folder in os.listdir() if not folder.startswith('_')]
    for folder in cogs:
        print(colored.cyan('Loading cog ' + folder))
        try:
            bot.load_extension(f'cogs.{folder}.__init__')
            cogs_loaded += 1
        except discord.ExtensionFailed as exception:
            print(colored.red(
                f'Unable to load cog {folder} because the following error occurred: {exception}'))
        if cogs_loaded == len(cogs):
            print('\n')
            bot.log(
                  message=f'Loaded {cogs_loaded} cogs in {round(time()-start, 1)} seconds.',
                  log_type='info')

    os.chdir('..')
