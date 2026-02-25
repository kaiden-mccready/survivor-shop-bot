import json
import os
import discord
from datetime import timedelta

from config import *

class Item:
    def __init__(self, name: str, price: int = 0, quantity: int = 1, \
                 description: str | None = None, description_on_use: str | None = None):
        self.name = name
        self.price = price
        self.quantity = quantity
        self.description = description
        self.description_on_use = description_on_use
    
    def discountHalf(self):
        self.price = (self.price // 2) + 1

    def use(self):
        return self.description_on_use or f"You used the {self.name}!"
     
    def copy(self):
        return Item(self.name, self.price, self.quantity, self.description, self.description_on_use)
    
class Customer:
    def __init__(self, realname: str, discordIDstr: str, servernickname: str, discordIDint: int, wealth: int | None = 0, tribe: str | None = None):
          self.realname = realname
          self.discordIDstr = discordIDstr
          self.servernickname = servernickname
          self.discordIDint = discordIDint
          self.tribe = tribe
          self.wealth = wealth
          self.inventory = []
    
    def add_item(self, item: Item):
         self.inventory.append(item)
         
    def buy(self, newItem: Item):
        newItem.quantity = 1
        if newItem.price > self.wealth:
             raise Exception("Sorry, something went VERY wrong in my code... Tell Kaiden 'Exit code 0'.") 
        self.wealth = self.wealth - newItem.price
        for item in self.inventory:
            if item.name == newItem.name:
                item.quantity += 1
                return
        del newItem.price
        self.inventory.append(newItem)
    
    def use(self, requestedItemName: str) -> str:
        for item in self.inventory:
             if item.name == requestedItemName:
                item.quantity += -1
                if item.quantity <= 0:
                    self.inventory.remove(item)
                return item.use()
        return f"No item in your inventory by the name of {requestedItemName}... did you misspell it?"
    
    def check_inventory(self) -> str:
        output = ''
        if self.wealth > 0:
            output += f"* {self.wealth}x Gold Coins \n"
        for item in self.inventory:
             output += f"* {item.quantity}x {item.name}: {"\n-# \"" + item.description + "\"\n" if item.description else "\n"}"
        if output == '':
            return "Nothing! It seems material wealth alludes you..."
        else: 
            return output
         
class Shop:
    def __init__(self, prefix: str, backup_folder: str | None = None, from_backup: bool = False, import_items_from_folder: str | None = None):
        self.inventory = []
        self.customers = []
        self.backup_folder = backup_folder
        self.name = "Carl Nook"
        self.prefix = prefix
        if from_backup:
            self.restore()
        if import_items_from_folder:
            self.import_items_from_folder(import_items_from_folder)
            
    def restore(self):
        backup_folder = self.backup_folder or DEFAULT_BACKUP_FOLDER_NAME
        if backup_folder and os.path.exists(backup_folder):
            backup_files = [f for f in os.listdir(backup_folder) if f.startswith("shop_backup") and f.endswith(".json")]
            if backup_files:
                latest_backup = max(backup_files, key=lambda f: os.path.getctime(os.path.join(backup_folder, f)))
                self.load_backup(os.path.join(backup_folder, latest_backup))
                print(f"Loaded backup from {latest_backup}")
            else:
                print("No backup files found. Starting with an empty shop.")

    def backup(self, backup_folder: str = DEFAULT_BACKUP_FOLDER_NAME):
        backup_data = {
            'inventory': [vars(item) for item in self.inventory],
            'customers': [{'servernickname': customer.servernickname,
                           'discordIDstr': customer.discordIDstr,
                           'realname': customer.realname,
                           'discordIDint': customer.discordIDint,
                           'wealth': customer.wealth, 
                           'inventory': [vars(item) for item in customer.inventory]
                           } for customer in self.customers]
        }
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        # get timestamp for EST time zone (UTC-5)
        timestamp = (discord.utils.utcnow() + timedelta(hours=-5)).strftime('%Y-%m-%d_%H:%M:%S')
        backup_file_path = os.path.join(backup_folder, f'shop_backup_{timestamp}.json')
        with open(backup_file_path, 'w') as file:
            json.dump(backup_data, file, indent=4)
        print(f"Shop state backed up to {backup_file_path}")

    def load_backup(self, backup_file_path: str):
        with open(backup_file_path, 'r') as file:
            data = json.load(file)
            self.inventory = [Item(**item) for item in data.get('inventory', [])]
            self.customers = []
            for customer_data in data.get('customers', []):
                customer = Customer(
                    servernickname = customer_data['servernickname'],
                    discordIDstr = customer_data['discordIDstr'],
                    realname = customer_data['realname'],
                    discordIDint = customer_data['discordIDint'],
                    tribe = customer_data.get('tribe'),
                    wealth = customer_data['wealth']
                )
                customer.inventory = [Item(**item) for item in customer_data.get('inventory', [])]
                self.customers.append(customer)

    def stock(self, item: Item):
        self.inventory.append(item)
        
    def populate(self, customers):
        if isinstance(customers, Customer):
            if customers not in self.customers:
                self.customers.append(customers)
        elif isinstance(customers, dict):
            for customer in customers.values():
                if customer not in self.customers:
                    self.customers.append(customer)

    def remove_one_of(self, item: Item):
        item.quantity += -1
        if item.quantity < 1:
            self.inventory.remove(item)
    
    def remove_all_of(self, item: Item):
        self.inventory.remove(item)

    def attemptBuy(self, customer_id, requestedItemName: str) -> str:

        # gets internal customer object from user asking to buy
        customer = id_to_customer(self, customer_id)

        wealth = customer.wealth
        def canAfford(itemPrice, wealth): return wealth >= itemPrice
        
        for item in self.inventory:
            if item.name == requestedItemName:
                if canAfford(item.price, wealth):
                    customer.buy(item.copy())
                    self.remove_one_of(item)
                    return f"Thank you for your patronage! One {requestedItemName} coming up! \n*You felt your pockets get slightly heavier, and your gold supply drop to ${customer.wealth}*"
                else:
                    return f"It seems you're a bit too low on funds for that purchase by about {item.price - wealth}g... Perhaps another ware catches your eye? Maybe one a bit... cheaper?"
        return f"Doesn't look like we sell anything by the name of {requestedItemName}, exactly... did you misspell it?"
    
    def print_customers(self, verbose = False):
        if verbose:
            return [f"{customer.name} (ID: {customer.userID}, Wealth: {customer.wealth} coins, Tribe: {customer.tribe})" for customer in self.customers]
        return [f"{customer.realname} \"{customer.servernickname}\"" for customer in self.customers]
    
    def display(self):
        output = f'~~' + " " * 10 + "~~\n"
        for item in self.inventory:
             output += f"* {item.quantity}x {item.name} - {item.price}g {"\n-# \"" + item.description + "\"\n" if item.description else "\n"}"
        if self.inventory == []:
            output += "[We're sold out!]\n"
        output += f'~~' + " " * 10 + "~~\n"
        if self.inventory != []:
            output = "*To buy an item, use the command !buy \"<item name>\".*" + output
        return output

    def str_detailed_summary(self):
        output = ""
        output += f"> Timestamp: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        output += "**Shop Inventory:**"
        if len(self.inventory) == 0:
            output += "  - (Out of Stock)\n"
        for item in self.inventory:
            output += f"  - {item.quantity}x {item.name} ({item.price}g)\n"
            if item.description:
                output += f"    Description: {item.description}\n"
        output += "Customers:"
        if len(self.customers) == 0:
            output += "  - (No Current Customers)\n"
        for customer in self.customers:
            output += f"  - {customer.name} (id: {customer.userID}, wealth: {customer.wealth}g)\n"
            if customer.inventory:
                output += "    Inventory:\n"
                for item in customer.inventory:
                    output += f"      - {item.quantity}x {item.name}\n"
                    if item.description:
                        output += f"        Description: {item.description}\n"
        output += "-" * 20
        return output

def id_to_customer(shop: Shop, user_identifier: str) -> Customer:
    for customer in shop.customers:
        if customer.discordIDint == user_identifier:
            return customer
        elif customer.discordIDstr.lower() == user_identifier.lower():
            return customer
        elif customer.realname.lower() == user_identifier.lower():
            return customer
        elif customer.servernickname.lower() == user_identifier.lower():
            return customer
    # not in database :(
    return None