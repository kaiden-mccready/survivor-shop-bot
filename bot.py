# TODO: update show_customers command to display a bit nicer
# TODO: maybe add a "show customer <userID>" command to show more detailed info/stats about a specific customer?
# TODO: update add_customer to include real name requirement + get discord data and update help message accordingly
'''
Made by: Kaiden McCready 2/2025
'''

import atexit
import asyncio
import json
import signal
import sys
import discord
from discord.ext import commands, tasks
from discord.utils import get

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
intents.members = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

print("Setting up shop...")

todaysShop = shop.Shop(backup_folder=DEFAULT_BACKUP_FOLDER_NAME, from_backup=True, prefix = COMMAND_PREFIX)

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
                print(f"Error with {ctx.author}: {error}")
            else: print(f"potential problem with {ctx.author}... {error}")

##### Commands #####

# castaway commands (beginning with prefix)



@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def help(ctx):
    await ctx.send("Hello there, traveler! Here are the commands you can use to interact with my shop:" \
                   + f"\n* {todaysShop.prefix}help - View this help message" \
                   + f"\n* {todaysShop.prefix}check_shop - View items currently in stock" \
                   + f"\n* {todaysShop.prefix}check_inventory - View your own inventory" \
                   + f"\n* {todaysShop.prefix}buy \"<item name>\" - Buy an item from the shop" \
                   + f"\n* {todaysShop.prefix}use \"<item name>\" - Use an item from your inventory" \
                   + f"\n* {todaysShop.prefix}give_away \"<item name>\" - Give an item from your inventory to someone else on your tribe (you will be prompted to choose a recipient)")

@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def check_shop(ctx):
    await ctx.send("Hello, weary traveler, it's good to see you. Welcome to my shop! Here's what's for sale:\n" + todaysShop.display())

@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def check_inventory(ctx, user: str | None = None):
    if user is None or user.lower() == "myself":
        user = ctx.author.name
    if (ctx.author.guild_permissions.administrator or any(role.name in ADMIN_ROLES for role in ctx.author.roles)) and user != ctx.author.name:
        await ctx.send(f"You look inside {user}'s pouch to find...\n")
        customer = shop.id_to_customer(todaysShop, user)
        if customer is None:
            await ctx.send(f"That you could not find a customer with the ID '{user}'.")
            return
        else:
            await ctx.send(customer.check_inventory())
    else:
        await ctx.send("You look inside your pouch to find...\n")
        customer = shop.id_to_customer(todaysShop, ctx.author.name)
        if customer is None:
            await ctx.send("That you aren't a customer yet!")
            return
        else:
            await ctx.send(customer.check_inventory())

@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def buy(ctx, item_name: str):
    await ctx.send(todaysShop.attemptBuy(ctx.author.name, item_name))
    update_shop_displays.start() # Update shop displays after a purchase

@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def use(ctx, item_name: str):
    customer = shop.id_to_customer(todaysShop, ctx.author.name)
    await ctx.send(customer.use(item_name))

@bot.command()
@commands.check_any(commands.has_role([*CUSTOMER_ROLES, *ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def give_away(ctx, item_name: str):
    customer = shop.id_to_customer(todaysShop, ctx.author.name)
    if customer is None:
        await ctx.send("You aren't a customer yet! You can't give away items if you don't have any...")
        return
    await ctx.send("Please enter the name of the person you want to give the item to:\n" + todaysShop.print_customers(tribe=customer.tribe))
    recipientStr = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    recipient = shop.id_to_customer(todaysShop, recipientStr)
    if recipient is None:
        await ctx.send(f"Could not find a customer with the ID '{recipientStr}'. Make sure you entered it correctly and that the recipient is registered as a customer.")
        return
    if recipient.tribe != customer.tribe:
        await ctx.send(f"Nice try... {recipient.realname} is **not** in your party, sneaky sneaky.")
        return
    await ctx.send(customer.give(item_name, recipient))

# admin commands (beginning with prefix)

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def help_admin(ctx):
    await ctx.send("Here are the admin commands you can use:" + \
                   f"\n* {todaysShop.prefix}check_customers - View a list of all customers (use verbose=True for more details)" + \
                   f"\n* {todaysShop.prefix}move_money <userID> <amount> - Add or remove money from a user's account (you can say \"myself\")" + \
                   f"\n* {todaysShop.prefix}move_money_tribe <tribe> <amount> - Add or remove money from all members of a tribe" +
                   f"\n* {todaysShop.prefix}add_shop_item - Add a new item to the shop (you will be prompted for item details)" +
                   f"\n* {todaysShop.prefix}remove_shop_item <item name> - Remove an item from the shop" +
                   f"\n* {todaysShop.prefix}change_item_quantity <item name> <new quantity> - Change the quantity of an item in the shop" + \
                   f"\n* {todaysShop.prefix}add_customer <userID> <wealth> <tribe> - Add a new customer to the shop with an optional starting wealth and tribe (you can say \"myself\")" + \
                   f"\n* {todaysShop.prefix}remove_customer <userID> - Remove a customer from the shop (you can say \"myself\")" + \
                   "\n**Mega Admin Commands (usable by hosts only):**" + \
                   f"\n* {todaysShop.prefix}backup - Manually trigger a backup of the shop's state" + \
                   f"\n* {todaysShop.prefix}restore - Manually restore the shop's state from the latest backup" + \
                   f"\n* {todaysShop.prefix}clear_shop - Clear all items and customer data from the shop (use with extreme caution!)" + \
                   f"\n* {todaysShop.prefix}restore_specific <n> - Restore the shop's state from a specific backup file (you will be prompted to choose from recent n backups, default 10)" + \
                   f"\n* {todaysShop.prefix}add_folder_items <folder path> - Add all items from a specified folder to the shop" + \
                   f"\n* {todaysShop.prefix}add_folder_customers <folder path> - Add all customers from a specified folder to the shop")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def check_customers(ctx, verbose: bool = False):
    await ctx.send(todaysShop.print_customers(verbose=verbose))

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def move_money(ctx, userID: str, howMuch: int):
    if userID == "myself":
        userID = ctx.author.name
    customer = shop.id_to_customer(todaysShop, userID)
    if customer is None:
        await ctx.send(f"Could not find a customer with the ID '{userID}'.")
        return
    customer.wealth += howMuch
    await ctx.send(f"done. {userID}'s wealth is now {customer.wealth}")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def move_money_tribe(ctx, tribe: str, howMuch: int):
    for customer in todaysShop.customers:
        if customer.tribe == tribe:
            customer.wealth += howMuch
    await ctx.send(f"All members of {tribe} have had their wealth adjusted by {howMuch} coins.")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def add_shop_item(ctx):
    await ctx.send("Please enter the name of the item:")
    item_name = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content

    await ctx.send("Please enter the price of the item:")
    item_price = int((await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content)

    await ctx.send("Please enter a description for the item (or type 'none'):")
    item_description = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if item_description.lower() == 'none':
        item_description = None

    await ctx.send("Please enter a description for the item when used (or type 'none'):")
    item_description_on_use = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if item_description_on_use.lower() == 'none':
        item_description_on_use = None

    new_item = shop.Item(name=item_name, price=item_price, description=item_description, description_on_use=item_description_on_use)
    todaysShop.stock(new_item)
    await ctx.send(f"{item_name} has been added to the shop with a price of {item_price} coins.")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def remove_shop_item(ctx, item_name: str):
    for item in todaysShop.inventory:
        if item.name.lower() == item_name.lower():
            todaysShop.remove_all_of(item)
            await ctx.send(f"{item_name} has been removed from the shop.")
            return
    await ctx.send(f"Could not find an item named {item_name} in the shop.")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def change_item_quantity(ctx, item_name: str, new_quantity: int):
    for item in todaysShop.inventory:
        if item.name.lower() == item_name.lower():
            item.quantity = new_quantity
            await ctx.send(f"The quantity of {item_name} has been updated to {new_quantity}.")
            return
    await ctx.send(f"Could not find an item named {item_name} in the shop.")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def add_customer(ctx, userID: str, wealth: int = 0, tribe: str | None = None):
    if userID == "myself":
        userID = ctx.author.name
    if shop.id_to_customer(todaysShop, userID) is not None:
        await ctx.send(f"{userID} is already registered as a customer.")
        return
    await ctx.send(f"Please enter the real name of the customer (or type 'none'):")
    realname = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if realname.lower() == 'none':
        realname = userID
    new_customer = shop.Customer(
        realname=realname, 
        discordIDstr=userID, 
        discordIDint=await get_discord_id_from_str(userID), 
        servernickname=await get_server_nickname_from_str(userID), 
        wealth=wealth,
        tribe=tribe
    )
    todaysShop.customers.append(new_customer)
    await ctx.send(f"{userID} has been added as a customer with {wealth} coins.")

@bot.command()
@commands.check_any(commands.has_role([*ADMIN_ROLES]), commands.has_permissions(administrator=True))
async def remove_customer(ctx, userID: str):
    if userID == "myself":
        userID = ctx.author.name
    customer = shop.id_to_customer(todaysShop, userID)
    if customer is None:
        await ctx.send(f"Could not find a customer with the ID '{userID}'.")
        return
    await ctx.send(f"Are you sure you want to remove {customer.realname} from the shop? Type 'yes' to confirm.")
    confirmation = (await bot.wait_for('message', check=lambda m: m.author == ctx.author)).content
    if confirmation.lower() != 'yes':
        await ctx.send("Customer removal cancelled.")
        return
    todaysShop.customers.remove(customer)
    await ctx.send(f"{customer.realname} has been removed from the shop.")

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
async def restore_specific(ctx, n: int = 10):
    backup_folder = DEFAULT_BACKUP_FOLDER_NAME
    if backup_folder and os.path.exists(backup_folder):
        backup_files = [f for f in os.listdir(backup_folder) if f.startswith("shop_backup") and f.endswith(".json")]
        if backup_files:
            backup_files.sort(key=lambda f: os.path.getctime(os.path.join(backup_folder, f)), reverse=True)
            recent_backups = backup_files[:n] # show n most recent backups
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
    todaysShop = shop.Shop(backup_folder=DEFAULT_BACKUP_FOLDER_NAME, from_backup=False, prefix=COMMAND_PREFIX)
    todaysShop.backup()
    await ctx.send("Shop cleared!")


@bot.command()
@commands.has_permissions(administrator=True)
async def add_folder_customers(ctx, folder_path: str = "customers"):
    await import_folder(todaysShop, folder_path, object_type="customer")
    await ctx.send(f"All customers from folder '{folder_path}' have been added to the shop.")

@bot.command()
@commands.has_permissions(administrator=True)
async def add_folder_items(ctx, folder_path: str = "items"):
    await import_folder(todaysShop, folder_path, object_type="item")
    await ctx.send(f"All items from folder '{folder_path}' have been added to the shop.")

async def get_discord_id_from_str(discordIDstr: str) -> int:
    users = bot.get_all_members()
    print(f"Looking for user with global name '{discordIDstr}'...")
    for user in users:
        if user.name == discordIDstr:
            return user.id or "No ID"
    raise ValueError(f"Could not find user with global name '{discordIDstr}' for finding Discord ID.")

async def get_server_nickname_from_str(discordIDstr: str) -> str:
    users = bot.get_all_members()
    print(f"Looking for user with global name '{discordIDstr}'...")
    for user in users:
        if user.name == discordIDstr:
            return user.global_name or "No nickname"
    raise ValueError(f"Could not find user with global name '{discordIDstr}' for finding server nickname")

async def import_folder(shop_to_add_to: shop.Shop, folder_path: str, object_type: str):
    if not os.path.exists(folder_path):
            raise Exception(f"Folder '{folder_path}' does not exist.")
    for filename in os.listdir(folder_path):
        if filename.endswith('.json') and not filename.startswith('.'): # don't include hidden files
            if object_type == "customer":
                with open(os.path.join(folder_path, filename), 'r') as f:
                    customer_data = json.load(f)
                    new_customer = shop.Customer(
                        realname=customer_data['realname'], 
                        discordIDstr=customer_data['discordIDstr'], 
                        discordIDint=customer_data.get('discordIDint') or await get_discord_id_from_str(customer_data['discordIDstr']), 
                        servernickname=customer_data.get('servernickname') or await get_server_nickname_from_str(customer_data['discordIDstr']), 
                        wealth=customer_data.get('wealth', None),
                        tribe=customer_data.get('tribe', None))
                    new_customer.inventory = [shop.Item(**item) for item in customer_data.get('inventory', [])]
                    shop_to_add_to.populate(new_customer)
            elif object_type == "item":
                with open(os.path.join(folder_path, filename), 'r') as f:
                    item_data = json.load(f)
                    new_item = shop.Item(name=item_data['name'], price=item_data['price'], description=item_data.get('description'), description_on_use=item_data.get('description_on_use'))
                    shop_to_add_to.stock(new_item)
            else:
                raise Exception(f"Invalid object type '{object_type}' specified. Must be 'folder' or 'item'.")
            # change file to hidden
            os.rename(os.path.join(folder_path, filename), os.path.join(folder_path, '.' + filename))
            print(f"Imported {object_type} '{filename}' and hid filename.")


##### Run the bot #####

bot.run(API_KEY)

async def update_shop_displays():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                async for message in channel.history(limit=100):
                    if message.author == bot.user and message.content.startswith("Hello, weary traveler, it's good to see you. Welcome to my shop! Here's what's for sale:"):
                        await message.edit(content="Hello, weary traveler, it's good to see you. Welcome to my shop! Here's what's for sale:\n" + todaysShop.display())
            except discord.Forbidden:
                pass
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
