'''
Made by: Kaiden McCready 2/2025
'''

import atexit
import asyncio
import signal
import sys
import discord
from discord.ext import commands, tasks
import regex as re
from pathlib import Path
import os

from config import *
import shop

# set working directory to script's parent directory
script_dir = Path(__file__).resolve().parent
os.chdir(script_dir)

# set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

print("Setting up shop...")

todaysShop = shop.Shop(backup_folder=DEFAULT_BACKUP_FOLDER_NAME, from_backup=True)

##### Bot events #####

@tasks.loop(minutes = 60) # Backup every hour
async def automatic_backup():
    todaysShop.backup() # Backup the shop's state

    # only for testing: print backup report to a specific channel (replace channel ID with your own to enable)
    '''channel_id = 1473923988223823942 # Replace with channel ID to print report to
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(todaysShop.str_detailed_summary())
    '''

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}.')
    if not automatic_backup.is_running():
        automatic_backup.start() # Start the loop when the bot is ready

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingAnyRole):
            await ctx.send("Who do you think you are? *(You don't have the required role to use this command.)*")
        else:
            # if author has admin roles, print error to channel for debugging
            if ctx.author is not None and (any(role.name in ADMIN_ROLES for role in ctx.author.roles) or ctx.author.guild_permissions.administrator):
                await ctx.send(f"{error}")
            else: print(f"potential problem with {ctx.author}... {error}")

##### Commands #####

# castaway commands (beginning with prefix)

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def help(ctx):
    await ctx.send("Hello there, traveler! Here are the commands you can use to interact with my shop:" \
                   + f"\n* {todaysShop.prefix}help - View this help message" \
                   + f"\n* {todaysShop.prefix}check_shop - View items currently in stock" \
                   + f"\n* {todaysShop.prefix}check_inventory - View your own inventory and wealth" \
                   + f"\n* {todaysShop.prefix}buy \"<item name>\" - Buy an item from the shop" \
                   + f"\n* {todaysShop.prefix}use \"<item name>\" - Use an item from your inventory")

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def check_shop(ctx):
    await ctx.send("Hello, weary traveler, it's good to see you. Welcome to my shop! Here's what's for sale:")
    await ctx.send(todaysShop.display())
    await ctx.send("*To buy an item, use the command !buy \"<item name>\".*")

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def check_inventory(ctx):
    await ctx.send("You look inside your pouch to find...")
    customer = shop.id_to_customer(todaysShop, ctx.author.name)
    await ctx.send(customer.check_inventory())

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def buy(ctx, item_name: str):
    await ctx.send(todaysShop.attemptBuy(ctx.author.name, item_name))

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def use(ctx, item_name: str):
    customer = shop.id_to_customer(todaysShop, ctx.author.name)
    await ctx.send(customer.use(item_name))

@bot.command()
@commands.check_any(commands.has_role(*CUSTOMER_ROLES, *ADMIN_ROLES), commands.has_permissions(administrator=True))
async def give(ctx, recipient: str, item_name: str):
    await ctx.send("Please enter the user ID of the person you want to give the item to:")
    recipient = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    customer = shop.id_to_customer(todaysShop, ctx.author.name)
    await ctx.send(customer.give(item_name, recipient))

# admin commands (beginning with prefix)

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def help_admin(ctx):
    await ctx.send("Here are the admin commands you can use:" + \
                   f"\n* {todaysShop.prefix}add_remove_money <userID> <amount> - Add or remove money from a user's account (you can say \"myself\")" + \
                   f"\n* {todaysShop.prefix}add_remove_money_tribe <tribe> <amount> - Add or remove money from all members of a tribe" +
                   f"\n* {todaysShop.prefix}check_inventory_of <userID> - View the inventory of a specific user" +
                   f"\n* {todaysShop.prefix}add_shop_item - Add a new item to the shop (you will be prompted for item details)" +
                   f"\n* {todaysShop.prefix}remove_shop_item <item name> - Remove an item from the shop" +
                   f"\n* {todaysShop.prefix}change_item_quantity <item name> <new quantity> - Change the quantity of an item in the shop" + \
                   f"\n* {todaysShop.prefix}add_myself_as_customer - Add yourself as a customer (if you haven't already) to be able to use customer commands" + \
                   "\n**Mega Admin Commands (use with caution):**" + \
                   f"\n* {todaysShop.prefix}backup - Manually trigger a backup of the shop's state" + \
                   f"\n* {todaysShop.prefix}restore - Manually restore the shop's state from the latest backup" + \
                   f"\n* {todaysShop.prefix}clear_shop - Clear all items and customer data from the shop (use with extreme caution!)" + \
                   f"\n* {todaysShop.prefix}restore_specific - Restore the shop's state from a specific backup file (you will be prompted to choose from recent backups)" + \
                   f"\n* {todaysShop.prefix}add_all_folder_items <folder path> - Add all items from a specified folder to the shop")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def add_remove_money(ctx, userID: str, howMuch: int):
    if userID == "myself":
        userID = ctx.author.name
    customer = shop.id_to_customer(todaysShop, userID)
    customer.wealth += howMuch
    await ctx.send(f"done. {customer.name}'s wealth is now {customer.wealth}")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def add_remove_money_tribe(ctx, tribe: str, howMuch: int):
    for customer in todaysShop.customers:
        if customer.tribe == tribe:
            customer.wealth += howMuch
    await ctx.send(f"All members of {tribe} have had their wealth adjusted by {howMuch} coins.")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def check_inventory_of(ctx, user: str):
    await ctx.send(f"You look inside {user}'s pouch to find...")
    customer = shop.id_to_customer(todaysShop, user)
    await ctx.send(customer.check_inventory())

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def add_shop_item(ctx):
    await ctx.send("Please enter the name of the item:")
    item_name = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content

    await ctx.send("Please enter the price of the item:")
    item_price = int((await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content)

    await ctx.send("Please enter a description for the item (or type 'none'):")
    item_description = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if item_description.lower() == 'none':
        item_description = None

    new_item = shop.Item(name=item_name, price=item_price, description=item_description)
    todaysShop.stock(new_item)
    await ctx.send(f"{item_name} has been added to the shop with a price of {item_price} coins.")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def remove_shop_item(ctx, item_name: str):
    for item in todaysShop.inventory:
        if item.name.lower() == item_name.lower():
            todaysShop.remove_all_of(item)
            await ctx.send(f"{item_name} has been removed from the shop.")
            return
    await ctx.send(f"Could not find an item named {item_name} in the shop.")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def change_item_quantity(ctx, item_name: str, new_quantity: int):
    for item in todaysShop.inventory:
        if item.name.lower() == item_name.lower():
            item.quantity = new_quantity
            await ctx.send(f"The quantity of {item_name} has been updated to {new_quantity}.")
            return
    await ctx.send(f"Could not find an item named {item_name} in the shop.")

@bot.command()
@commands.check_any(commands.has_role(*ADMIN_ROLES), commands.has_permissions(administrator=True))
async def add_myself_as_customer(ctx, wealth: int | None = None):
    if shop.id_to_customer(todaysShop, ctx.author.name) is not None:
        await ctx.send("You are already registered as a customer.")
        return
    new_customer = shop.Customer(name=ctx.author.name, userID=ctx.author.name, wealth=wealth or 0)
    todaysShop.customers.populate(new_customer)
    await ctx.send("You have been added as a customer!")

# mega admin commands (use with caution)
@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx):
    todaysShop.backup()
    await ctx.send("Backup complete!")

@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx):
    todaysShop.restore(backup_folder=DEFAULT_BACKUP_FOLDER_NAME)
    await ctx.send("Restore complete!")

@bot.command()
@commands.has_permissions(administrator=True)
async def restore_specific(ctx):
    # show user past 10 backups to choose from
    backup_folder = DEFAULT_BACKUP_FOLDER_NAME
    if backup_folder and os.path.exists(backup_folder):
        backup_files = [f for f in os.listdir(backup_folder) if f.startswith("shop_backup") and f.endswith(".json")]
        if backup_files:
            backup_files.sort(key=lambda f: os.path.getctime(os.path.join(backup_folder, f)), reverse=True)
            recent_backups = backup_files[:10]
            backup_list_message = "Please choose a backup to restore from the list below by typing its number:\n"
            for i, backup in enumerate(recent_backups):
                backup_list_message += f"{i + 1}. {backup}\n"
            await ctx.send(backup_list_message)

            def check(m):
                return m.author == ctx.author and m.content.isdigit() and 1 <= int(m.content) <= len(recent_backups)

            try:
                response = await bot.wait_for('message', check=check, timeout=60)
                chosen_backup = recent_backups[int(response.content) - 1]
                todaysShop.load_backup(os.path.join(backup_folder, chosen_backup))
                await ctx.send(f"Restore from {chosen_backup} complete!")
            except asyncio.TimeoutError:
                await ctx.send("No response received. Restore cancelled.")
        else:
            await ctx.send("No backup files found. Cannot restore.")

@bot.command()
@commands.has_permissions(administrator=True)
async def clear_shop(ctx):
    await ctx.send("Are you sure you want to clear the shop? This will delete all items and customer data. Type 'yes' to confirm.")
    confirmation = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if confirmation.lower() != 'yes':
        await ctx.send("Shop clear cancelled.")
        return
    global todaysShop
    todaysShop = shop.Shop(backup_folder=DEFAULT_BACKUP_FOLDER_NAME, from_backup=False)
    todaysShop.backup()
    await ctx.send("Shop cleared!")

@bot.command()
@commands.has_permissions(administrator=True)
async def add_all_folder_items(ctx, folder_path: str = "items"):
    todaysShop.import_items_from_folder(folder_path)
    await ctx.send(f"All items from folder '{folder_path}' have been added to the shop.")

##### Run the bot #####

bot.run(API_KEY)

##### Shutdown handlers #####

def exit_handler():
    print('Initiating shutdown...')
    todaysShop.backup()

atexit.register(exit_handler)

def sigint_handler(sig, frame):
    print('Initiating shutdown...')
    todaysShop.backup()
    asyncio.create_task(bot.close())
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)
