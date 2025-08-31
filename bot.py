import discord
from discord.ext import commands, tasks
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import asyncio
import requests
import time
from datetime import datetime
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

FIREBASE_JSON = "discordbotdata-29400-firebase-adminsdk-fbsvc-cdabe4a5ba.json"
FIREBASE_URL = "https://discordbotdata-29400-default-rtdb.asia-southeast1.firebasedatabase.app/jobids"
MAX_RECORDS = 1000

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_JSON)
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL.rsplit('/',1)[0]})
ref = db.reference('jobids')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def cleanup_old_records():
    try:
        response = requests.get(f"{FIREBASE_URL}.json")
        if response.status_code != 200: return
        all_data = response.json() or {}
        total_records = len(all_data)
        if total_records <= MAX_RECORDS: return

        sorted_records = sorted(all_data.items(), key=lambda x: x[0])
        records_to_delete = sorted_records[:-MAX_RECORDS]
        for key, _ in records_to_delete:
            try:
                requests.delete(f"{FIREBASE_URL}/{key}.json", timeout=5)
            except: pass
    except: pass

def delete_all_records():
    try:
        requests.delete(f"{FIREBASE_URL}.json")
    except: pass

@tasks.loop(minutes=30)
async def auto_cleanup():
    cleanup_old_records()

@bot.event
async def on_ready():
    print(f'✅ {bot.user} พร้อมใช้งาน!')
    auto_cleanup.start()

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if "jobid:" in message.content.lower():
        jobid = message.content.split("jobid:")[1].strip()
        data = {
            "id": jobid,
            "timestamp": int(time.time()),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": str(message.author),
            "channel": str(message.channel)
        }
        ref.push(data)
        await message.channel.send(f"✅ บันทึก JobID: {jobid} แล้ว!")
        cleanup_old_records()
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send("pong 🏓")

@bot.command(name='stats')
async def show_stats(ctx):
    try:
        data = requests.get(f"{FIREBASE_URL}.json").json() or {}
        total = len(data)
        await ctx.send(f"📊 Total JobIDs: {total}\nMax Allowed: {MAX_RECORDS}")
    except:
        await ctx.send("❌ ดึงข้อมูลไม่สำเร็จ")

@bot.command(name='cleanup')
async def manual_cleanup(ctx):
    cleanup_old_records()
    await ctx.send("🧹 ทำความสะอาดเสร็จสิ้น!")

@bot.command(name='clear_all')
async def clear_all_data(ctx):
    delete_all_records()
    await ctx.send("🗑️ ลบทั้งหมดเรียบร้อย!")

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("❌ ERROR: No DISCORD_TOKEN found!")
