from discord import *
from discord.ext import commands
from discord.ext import tasks
from datetime import *
import pymongo
import asyncio

bot = commands.Bot(command_prefix='.')


SECONDS_IN_A_DAY = 86400
SECONDS_IN_A_MINUTE = 60
SECONDS_IN_A_HOUR = 3600


myclient = pymongo.MongoClient(
    "mongodb+srv://Poodlers:eduardo2347@cluster0.uxbfa.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")

mydb = myclient["mydatabase"]
mycol = mydb["reminders"]


@tasks.loop(seconds=30)
async def lookup_database():
    await bot.wait_until_ready()
    timeQuery = {
        "reminder_remind_time": {"$lte": datetime.now()}
    }
    for reminder in mycol.find(timeQuery):
        # create an Embed
        embed = Embed(title=reminder["reminder_msg"],
                      description="Reminder created by rika jinga")
        embed.set_author(name="ReminderBot",
                         icon_url="https://i.imgur.com/DZzUh2z.jpg")
        embed.add_field(name="Remind Time: ",
                        value=reminder["reminder_limit"].strftime("%d/%m/%Y %H:%M"), inline=False)
        embed.add_field(name="Created at: ",
                        value=reminder["reminder_creation"].strftime("%d/%m/%Y"), inline=False)

        user = await bot.fetch_user(reminder["u_id"])
        await send_dm(user, embed)
        # erase this entry from database
        if reminder["reminder_limit"] != reminder["reminder_remind_time"]:
            new_entry = {
                "u_id": reminder["u_id"],
                "reminder_msg": reminder["reminder_msg"],
                "reminder_limit": reminder["reminder_limit"],
                "reminder_remind_time": reminder["reminder_limit"],
                "reminder_creation": reminder["reminder_creation"]
            }
            mycol.delete_one(reminder)
            mycol.insert_one(new_entry)
        else:
            mycol.delete_one(reminder)


def read_token():
    with open("token.txt", "r") as f:
        lines = f.readlines()
        return lines[0].strip()


lookup_database.start()
token = read_token()
bot = commands.Bot(command_prefix='!')


async def send_dm(member, content):
    channel = await member.create_dm()
    await channel.send(embed=content)


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


# !copy @Nigga <all | message for the reminder in question>


@bot.command(name='copy')
async def copy(ctx, user_to_copy: User, *args):
    user_wanting_to_copy = ctx.message.author
    if len(args) != 1:
        await ctx.send("Please format the command correctly: !copy <@person-to-copy-from> <reminder_to_copy_text | all>")
        return
    if(user_wanting_to_copy.id == user_to_copy.id):
        await ctx.send("Hey you cant copy your own reminders! \n")
        return

    reminders_to_copy = args[0]
    if reminders_to_copy == "all":
        embed_all_perms = Embed(title=f' Hey {user_to_copy.display_name}! {user_wanting_to_copy.display_name} over here wants to copy ALL of your reminders! ',
                                description="React with ✅ to allow him or ❌ to deny! ")
        embed_message = await ctx.send(embed=embed_all_perms)
        await embed_message.add_reaction("✅")
        await embed_message.add_reaction("❌")
        await asyncio.sleep(10)
        message = await embed_message.channel.fetch_message(embed_message.id)

        has_answered = False
        will_copy = False
        for reaction in message.reactions:
            reaction_users = await reaction.users().flatten()
            reaction_users.pop(0)  # this is the bot own reaction
            if reaction.emoji == "❌" and user_to_copy in reaction_users:
                if has_answered:
                    await ctx.send("Please react with only one emote!")
                    return
                else:
                    has_answered = True
                    will_copy = False
            if reaction.emoji == "✅" and user_to_copy in reaction_users:
                if has_answered:
                    await ctx.send("Please react with only one emote!")
                    return
                else:
                    has_answered = True
                    will_copy = False

        if will_copy:
            await ctx.send(f"Permission has been granted to copy ALL reminders from {user_to_copy.mention} to {user_wanting_to_copy.mention} !")
            query_reminder = {
                "u_id": user_to_copy.id,
            }
            for reminder in mycol.find(query_reminder):
                new_entry = {
                    "u_id": user_wanting_to_copy.id,
                    "reminder_msg": reminder["reminder_msg"],
                    "reminder_limit": reminder["reminder_limit"],
                    "reminder_remind_time": reminder["reminder_remind_time"],
                    "reminder_creation": datetime.now()
                }
                mycol.insert_one(new_entry)

        else:
            await ctx.send(f"Permission has been DENIED {user_wanting_to_copy.mention} ! Fail")
    else:
        # check in database if such reminder actually exists
        query_reminder = {
            "u_id": user_to_copy.id,
            "reminder_msg": reminders_to_copy

        }
        reminder = mycol.find(query_reminder)
        if reminder == None:
            await ctx.send("Sorry seems like they don't have a reminder like that! ")
            return
        new_entry = {
            "u_id": user_wanting_to_copy.id,
            "reminder_msg": reminder["reminder_msg"],
            "reminder_limit": reminder["reminder_limit"],
            "reminder_remind_time": reminder["reminder_remind_time"],
            "reminder_creation": datetime.now()
        }
        mycol.insert_one(new_entry)
        await ctx.send(f'Successfully added {reminders_to_copy} to {user_wanting_to_copy.mention()} !')


# setReminder "what you want to be reminded" [day/month/year] [hour:minutes] [how much in advance do you want to be notified ex. 1w 5d 5h]


@bot.command(name='setReminder')
async def setReminder(ctx, *args):
    guild = ctx.guild
    date_ = args[1].split("/")
    date_day = int(date_[0])
    date_month = int(date_[1])
    date_year = int(date_[2])

    if(date_day < 0 or date_day > 31 or date_month < 0 or date_month > 12 or date_year < int(date.today().strftime("%Y"))):
        await ctx.send("Please insert a valid date")
        return

    date_hour = args[2].split(":")
    hour = int(date_hour[0])
    minutes = int(date_hour[1])
    if(hour < 0 or hour > 23 or minutes < 0 or minutes > 59):
        await ctx.send("Please insert a valid date")
        return

    date_time_str = f'{date_year}-{date_month}-{date_day} {hour}:{minutes}'
    date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')

    time_to_warning_total = timedelta(minutes=0)
    # create a datetime timedelta object
    for i in range(3, len(args)):
        time_unit = args[i][-1]
        amount_time = int(args[i][0:-1])
        if(time_unit == "w"):
            time_to_warning_total += timedelta(weeks=amount_time)
        elif(time_unit == "h"):
            time_to_warning_total += timedelta(hours=amount_time)
        elif(time_unit == "m"):
            time_to_warning_total += timedelta(minutes=amount_time)
        elif(time_unit == "d"):
            time_to_warning_total += timedelta(days=amount_time)
        elif(time_unit == "s"):
            time_to_warning_total += timedelta(seconds=amount_time)

    date_when_to_notify = date_time_obj - time_to_warning_total
    final_obj = {
        "u_id": ctx.message.author.id,
        "reminder_msg": args[0],
        "reminder_limit": date_time_obj,
        "reminder_remind_time": date_when_to_notify,
        "reminder_creation": datetime.now()
    }
    myquery = {"u_id": ctx.message.author.id}
    for query in mycol.find(myquery):
        if(query["reminder_msg"] == final_obj["reminder_msg"] and query["reminder_limit"] == final_obj["reminder_limit"] and query["reminder_remind_time"] == final_obj["reminder_remind_time"]):
            await ctx.send("It seems you have already set a reminder exactly like this one! ")
            return

    mycol.insert_one(final_obj)

bot.run(token)
