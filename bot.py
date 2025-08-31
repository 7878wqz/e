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
import json

# Environment variables with multiple fallbacks
DISCORD_TOKEN = (
    os.getenv("DISCORD_TOKEN") or 
    os.getenv("DISCORD_TOKENN") or 
    "MTQxMTc1MTMwMDMyODA2MzE0Nw.GemOiJ.qcJPcHY8hSm0QXvkrQI63XMxLY2pLO5Ecn-HH0"
)

# Debug token information
print(f"🔍 Using token: {DISCORD_TOKEN[:20]}...")
print(f"🔍 Token source: {'Environment Variable' if os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_TOKENN') else 'Hard-coded'}")

# Validate token format
if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 50:
    print("❌ Token appears to be invalid or too short!")
    exit(1)
FIREBASE_URL = "https://discordbotdata-29400-default-rtdb.asia-southeast1.firebasedatabase.app/jobids"
MAX_RECORDS = 1000

# Initialize Firebase
try:
    # Try to get Firebase credentials from environment variable first
    firebase_creds = os.getenv("FIREBASE_CREDENTIALS")
    
    if firebase_creds:
        # If credentials are in environment variable (Railway preferred method)
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback to JSON file (for local development)
        FIREBASE_JSON = "discordbotdata-29400-firebase-adminsdk-fbsvc-cdabe4a5ba.json"
        cred = credentials.Certificate(FIREBASE_JSON)
    
    # Initialize Firebase if not already initialized
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL.rsplit('/',1)[0]
        })
    
    ref = db.reference('jobids')
    print("✅ Firebase initialized successfully")

except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    ref = None

# Initialize Discord Bot (ensure only one instance)
bot_instance = None

try:
    if not bot_instance:
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix='!', intents=intents)
        bot_instance = bot
        print("✅ Discord bot initialized successfully")
except Exception as e:
    print(f"❌ Discord bot initialization error: {e}")
    exit(1)

def cleanup_old_records():
    """Clean up old records to maintain MAX_RECORDS limit"""
    try:
        response = requests.get(f"{FIREBASE_URL}.json", timeout=10)
        if response.status_code != 200: 
            return
        
        all_data = response.json() or {}
        total_records = len(all_data)
        
        if total_records <= MAX_RECORDS: 
            return

        # Sort by timestamp and keep only recent records
        sorted_records = sorted(all_data.items(), key=lambda x: x[1].get('timestamp', 0))
        records_to_delete = sorted_records[:-MAX_RECORDS]
        
        for key, _ in records_to_delete:
            try:
                requests.delete(f"{FIREBASE_URL}/{key}.json", timeout=5)
            except Exception as e:
                print(f"Error deleting record {key}: {e}")
                
    except Exception as e:
        print(f"Error in cleanup_old_records: {e}")

def delete_all_records():
    """Delete all records from Firebase"""
    try:
        response = requests.delete(f"{FIREBASE_URL}.json", timeout=10)
        if response.status_code == 200:
            print("All records deleted successfully")
    except Exception as e:
        print(f"Error deleting all records: {e}")

@tasks.loop(minutes=30)
async def auto_cleanup():
    """Automatic cleanup task that runs every 30 minutes"""
    try:
        cleanup_old_records()
        print("🧹 Auto cleanup completed")
    except Exception as e:
        print(f"Error in auto_cleanup: {e}")

@bot.event
async def on_ready():
    """Event triggered when bot is ready"""
    print(f'✅ {bot.user} พร้อมใช้งาน!')
    if not auto_cleanup.is_running():
        auto_cleanup.start()
        print("🔄 Auto cleanup task started")

@bot.event
async def on_message(message):
    """Event triggered when a message is sent"""
    if message.author == bot.user: 
        return
    
    if "jobid:" in message.content.lower():
        try:
            jobid = message.content.split("jobid:")[1].strip()
            
            if not jobid:
                await message.channel.send("❌ JobID ไม่ถูกต้อง!")
                return
            
            data = {
                "id": jobid,
                "timestamp": int(time.time()),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(message.author),
                "channel": str(message.channel)
            }
            
            if ref:
                ref.push(data)
                await message.channel.send(f"✅ บันทึก JobID: {jobid} แล้ว!")
                cleanup_old_records()
            else:
                await message.channel.send("❌ ไม่สามารถเชื่อมต่อฐานข้อมูลได้!")
                
        except Exception as e:
            print(f"Error processing JobID: {e}")
            await message.channel.send("❌ เกิดข้อผิดพลาดในการบันทึก JobID!")
    
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    """Ping command to test bot responsiveness"""
    await ctx.send("pong 🏓")

@bot.command(name='stats')
async def show_stats(ctx):
    """Show database statistics"""
    try:
        response = requests.get(f"{FIREBASE_URL}.json", timeout=10)
        if response.status_code == 200:
            data = response.json() or {}
            total = len(data)
            await ctx.send(f"📊 Total JobIDs: {total}\nMax Allowed: {MAX_RECORDS}")
        else:
            await ctx.send("❌ ไม่สามารถดึงข้อมูลได้!")
    except Exception as e:
        print(f"Error in stats command: {e}")
        await ctx.send("❌ ดึงข้อมูลไม่สำเร็จ")

@bot.command(name='cleanup')
async def manual_cleanup(ctx):
    """Manual cleanup command"""
    try:
        cleanup_old_records()
        await ctx.send("🧹 ทำความสะอาดเสร็จสิ้น!")
    except Exception as e:
        print(f"Error in manual cleanup: {e}")
        await ctx.send("❌ เกิดข้อผิดพลาดในการทำความสะอาด!")

@bot.command(name='clear_all')
async def clear_all_data(ctx):
    """Clear all data command"""
    try:
        delete_all_records()
        await ctx.send("🗑️ ลบทั้งหมดเรียบร้อย!")
    except Exception as e:
        print(f"Error in clear_all command: {e}")
        await ctx.send("❌ เกิดข้อผิดพลาดในการลบข้อมูล!")

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f"An error occurred in {event}: {args}, {kwargs}")

# Main execution
if __name__ == "__main__":
    if DISCORD_TOKEN:
        # Debug: Check token format (don't print the actual token!)
        print(f"Token length: {len(DISCORD_TOKEN)}")
        print(f"Token starts with: {DISCORD_TOKEN[:10]}...")
        
        try:
            print("🚀 Starting Discord bot...")
            # Ensure bot runs only once
            bot.run(DISCORD_TOKEN, reconnect=True)
        except discord.LoginFailure:
            print("❌ LOGIN FAILED: Invalid Discord token!")
            print("Please check your DISCORD_TOKEN environment variable")
            print("Make sure it's a valid bot token from Discord Developer Portal")
            print("\n🔍 Troubleshooting steps:")
            print("1. Go to https://discord.com/developers/applications")
            print("2. Select your application")
            print("3. Go to 'Bot' section")
            print("4. Click 'Reset Token'")
            print("5. Copy the new token and update your code")
            print("6. Make sure MESSAGE CONTENT INTENT is enabled")
        except KeyboardInterrupt:
            print("👋 Bot stopped by user")
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ ERROR: No DISCORD_TOKEN found!")
        print("Please set DISCORD_TOKEN environment variable")
        print("Available environment variables:")
        for key in os.environ.keys():
            if 'TOKEN' in key.upper():
                print(f"  - {key}")
