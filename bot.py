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
import aiohttp

# Set proper event loop policy for Railway
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
else:
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

# Environment variables with multiple fallbacks
DISCORD_TOKEN = (
    os.getenv("DISCORD_TOKEN") or 
    os.getenv("DISCORD_TOKENN") or 
    "MTQxMTc1MzQ3Nzg4NTEzMjgyMA.GXMDMq.iLifOfLIeX-UOq2KDnCpaEKwiH8KKgxJjjgX14"
)

# Debug token information
print(f"🔍 Using token: {DISCORD_TOKEN[:20]}...")
print(f"🔍 Token source: {'Environment Variable' if os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_TOKENN') else 'Hard-coded'}")

# Validate token format
if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 50:
    print("❌ Token appears to be invalid or too short!")
    exit(1)

FIREBASE_URL = "https://discordbotdata-29400-default-rtdb.asia-southeast1.firebasedatabase.app/jobids"
MAX_RECORDS = 1200

# Initialize Firebase - แก้ไขส่วนนี้
firebase_initialized = False
ref = None

def initialize_firebase():
    global firebase_initialized, ref
    try:
        # ลบ Firebase apps ที่มีอยู่แล้ว (ถ้ามี)
        if firebase_admin._apps:
            for app in firebase_admin._apps.copy():
                firebase_admin.delete_app(app)
        
        # Try to get Firebase credentials from environment variable first
        firebase_creds = os.getenv("FIREBASE_CREDENTIALS")
        
        if firebase_creds:
            print("🔍 Using Firebase credentials from environment variable")
            cred_dict = json.loads(firebase_creds)
            cred = credentials.Certificate(cred_dict)
        else:
            print("🔍 Using Firebase credentials from JSON file")
            # Fallback to JSON file (for local development)
            FIREBASE_JSON = "discordbotdata-29400-firebase-adminsdk-fbsvc-cdabe4a5ba.json"
            
            # ตรวจสอบว่าไฟล์มีอยู่จริง
            if not os.path.exists(FIREBASE_JSON):
                print(f"❌ Firebase JSON file not found: {FIREBASE_JSON}")
                return False
                
            cred = credentials.Certificate(FIREBASE_JSON)
        
        # Initialize Firebase
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL.rsplit('/',1)[0]
        })
        
        ref = db.reference('jobids')
        firebase_initialized = True
        print("✅ Firebase initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Firebase initialization error: {e}")
        firebase_initialized = False
        return False

# Initialize Firebase
initialize_firebase()

# Initialize Discord Bot
try:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    print("✅ Discord bot initialized successfully")
except Exception as e:
    print(f"❌ Discord bot initialization error: {e}")
    exit(1)

def save_jobid_fallback(jobid, author, channel):
    """ใช้ HTTP API เป็น fallback เมื่อ Firebase Admin SDK ใช้ไม่ได้"""
    try:
        # ตรวจสอบ JobID ที่มีอยู่แล้ว
        response = requests.get(f"{FIREBASE_URL}.json", timeout=10)
        if response.status_code == 200:
            data = response.json() or {}
            existing_ids = {item['id'] for item in data.values() if 'id' in item}
            if jobid in existing_ids:
                print(f"❌ JobID {jobid} already exists, skipping save")
                return False

        data = {
            "id": jobid,
            "timestamp": int(time.time()),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": str(author),
            "channel": str(channel)
        }
        
        response = requests.post(f"{FIREBASE_URL}.json", json=data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Saved JobID using HTTP API: {jobid}")
            return True
        else:
            print(f"❌ HTTP API failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fallback save error: {e}")
        return False

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
            return True
        return False
    except Exception as e:
        print(f"Error deleting all records: {e}")
        return False

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
    print(f'🔗 Firebase Status: {"Connected" if firebase_initialized else "Disconnected (using HTTP API)"}')
    
    if not auto_cleanup.is_running():
        auto_cleanup.start()
        print("🔄 Auto cleanup task started")

@bot.event
async def on_message(message):
    """Event triggered when a message is sent"""
    if message.author == bot.user: 
        return
    
    # ตรวจสอบ JobID (ทั้ง jobid: และ !jobid)
    content_lower = message.content.lower()
    if "jobid:" in content_lower or content_lower.startswith("!jobid"):
        try:
            # Extract JobID
            if "jobid:" in content_lower:
                jobid = message.content.split("jobid:")[1].strip()
            else:
                # สำหรับ !jobid command
                parts = message.content.split()
                if len(parts) > 1:
                    jobid = parts[1].strip()
                else:
                    jobid = ""
            
            if not jobid:
                await message.channel.send("❌ JobID ไม่ถูกต้อง! ใช้รูปแบบ: `jobid:YOUR_ID` หรือ `!jobid YOUR_ID`")
                return
            
            # ลองบันทึกด้วย Firebase Admin SDK ก่อน
            saved = False
            
            if firebase_initialized and ref:
                try:
                    # ตรวจสอบ JobID ที่มีอยู่แล้ว
                    response = requests.get(f"{FIREBASE_URL}.json", timeout=10)
                    if response.status_code == 200:
                        data = response.json() or {}
                        existing_ids = {item['id'] for item in data.values() if 'id' in item}
                        if jobid in existing_ids:
                            await message.channel.send(f"❌ JobID `{jobid}` ถูกบันทึกไปแล้ว!")
                            return

                    data = {
                        "id": jobid,
                        "timestamp": int(time.time()),
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "added_by": str(message.author),
                        "channel": str(message.channel)
                    }
                    
                    ref.push(data)
                    saved = True
                    print(f"✅ Saved JobID using Firebase Admin SDK: {jobid}")
                    
                except Exception as e:
                    print(f"❌ Firebase Admin SDK error: {e}")
                    # ลอง reinitialize Firebase
                    if "invalid_grant" in str(e).lower():
                        print("🔄 Trying to reinitialize Firebase...")
                        initialize_firebase()
            
            # ถ้าบันทึกด้วย Admin SDK ไม่ได้ ใช้ HTTP API
            if not saved:
                print("🔄 Trying HTTP API fallback...")
                saved = save_jobid_fallback(jobid, message.author, message.channel)
            
            if saved:
                await message.channel.send(f"✅ บันทึก JobID: `{jobid}` แล้ว!")
                # ทำความสะอาดข้อมูลเก่า
                try:
                    cleanup_old_records()
                except:
                    pass
            else:
                await message.channel.send("❌ ไม่สามารถบันทึก JobID ได้ กรุณาลองใหม่อีกครั้ง!")
                
        except Exception as e:
            print(f"Error processing JobID: {e}")
            await message.channel.send("❌ เกิดข้อผิดพลาดในการบันทึก JobID!")
    
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    """Ping command to test bot responsiveness"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: {latency}ms\n🔗 Firebase: {'Connected' if firebase_initialized else 'HTTP API Mode'}")

@bot.command(name='stats')
async def show_stats(ctx):
    """Show database statistics"""
    try:
        response = requests.get(f"{FIREBASE_URL}.json", timeout=10)
        if response.status_code == 200:
            data = response.json() or {}
            total = len(data)
            
            # หาข้อมูลล่าสุด
            if data:
                latest_record = max(data.values(), key=lambda x: x.get('timestamp', 0))
                latest_date = latest_record.get('date', 'Unknown')
                latest_id = latest_record.get('id', 'Unknown')
            else:
                latest_date = 'No records'
                latest_id = 'No records'
            
            embed = discord.Embed(title="📊 Database Statistics", color=0x00ff00)
            embed.add_field(name="Total JobIDs", value=f"{total:,}", inline=True)
            embed.add_field(name="Max Allowed", value=f"{MAX_RECORDS:,}", inline=True)
            embed.add_field(name="Latest JobID", value=latest_id, inline=False)
            embed.add_field(name="Latest Date", value=latest_date, inline=False)
            embed.add_field(name="Firebase Status", value="Connected" if firebase_initialized else "HTTP API Mode", inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ ไม่สามารถดึงข้อมูลได้!")
    except Exception as e:
        print(f"Error in stats command: {e}")
        await ctx.send("❌ เกิดข้อผิดพลาดในการดึงข้อมูล!")

@bot.command(name='cleanup')
async def manual_cleanup(ctx):
    """Manual cleanup command"""
    try:
        cleanup_old_records()
        await ctx.send("🧹 ทำความสะอาดข้อมูลเก่าเรียบร้อย!")
    except Exception as e:
        print(f"Error in manual cleanup: {e}")
        await ctx.send("❌ เกิดข้อผิดพลาดในการทำความสะอาด!")

@bot.command(name='clear_all')
async def clear_all_data(ctx):
    """Clear all data command (ระวัง!)"""
    await ctx.send("⚠️ คุณแน่ใจหรือไม่ที่จะลบข้อมูลทั้งหมด? พิมพ์ `ยืนยัน` ภายใน 10 วินาที")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content == "ยืนยัน"
    
    try:
        await bot.wait_for('message', check=check, timeout=10.0)
        if delete_all_records():
            await ctx.send("🗑️ ลบข้อมูลทั้งหมดเรียบร้อย!")
        else:
            await ctx.send("❌ เกิดข้อผิดพลาดในการลบข้อมูล!")
    except asyncio.TimeoutError:
        await ctx.send("⏰ หมดเวลา ยกเลิกการลบข้อมูล")

@bot.command(name='jobid')
async def add_jobid(ctx, *, jobid=None):
    """เพิ่ม JobID ผ่านคำสั่ง !jobid"""
    if not jobid:
        await ctx.send("❌ กรุณาระบุ JobID! ใช้รูปแบบ: `!jobid YOUR_ID`")
        return
    
    # สร้าง fake message สำหรับ reuse logic
    class FakeMessage:
        def __init__(self, content, author, channel):
            self.content = f"jobid:{content}"
            self.author = author
            self.channel = channel
    
    fake_msg = FakeMessage(jobid, ctx.author, ctx.channel)
    await on_message(fake_msg)

@bot.command(name='firebase_status')
async def firebase_status(ctx):
    """ตรวจสอบสถานะ Firebase"""
    embed = discord.Embed(title="🔥 Firebase Status", color=0xff9500)
    embed.add_field(name="Admin SDK", value="✅ Connected" if firebase_initialized else "❌ Disconnected", inline=False)
    
    # ทดสอบ HTTP API
    try:
        response = requests.get(f"{FIREBASE_URL}.json", timeout=5)
        http_status = "✅ Working" if response.status_code == 200 else f"❌ Error {response.status_code}"
    except:
        http_status = "❌ Failed"
    
    embed.add_field(name="HTTP API", value=http_status, inline=False)
    embed.add_field(name="Database URL", value=FIREBASE_URL, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='reinit_firebase')
async def reinit_firebase(ctx):
    """Reinitialize Firebase connection"""
    global firebase_initialized
    old_status = firebase_initialized
    
    success = initialize_firebase()
    
    if success:
        await ctx.send(f"✅ Firebase reinitialized successfully! (was {'connected' if old_status else 'disconnected'})")
    else:
        await ctx.send("❌ Failed to reinitialize Firebase")

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f"An error occurred in {event}: {args}, {kwargs}")

# Main execution
async def main():
    if DISCORD_TOKEN:
        # Debug: Check token format
        print(f"Token length: {len(DISCORD_TOKEN)}")
        print(f"Token starts with: {DISCORD_TOKEN[:10]}...")
        
        try:
            print("🚀 Starting Discord bot...")
            await bot.start(DISCORD_TOKEN)
            
        except discord.LoginFailure as e:
            print("❌ LOGIN FAILED: Invalid Discord token!")
            print(f"Error details: {e}")
        except KeyboardInterrupt:
            print("👋 Bot stopped by user")
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                if not bot.is_closed():
                    await bot.close()
            except:
                pass
    else:
        print("❌ ERROR: No DISCORD_TOKEN found!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
