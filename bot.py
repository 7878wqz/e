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
import json  # เพิ่มสำหรับ load JSON จาก env ถ้าต้องการ

# ดึง token จาก env (set บน Railway)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# สำหรับ Firebase: ถ้าใช้ไฟล์ JSON, set path จาก env หรือ load จาก string
FIREBASE_JSON_PATH = os.getenv("FIREBASE_JSON_PATH", "discordbotdata-29400-firebase-adminsdk-fbsvc-cdabe4a5ba.json")
FIREBASE_URL = "https://discordbotdata-29400-default-rtdb.asia-southeast1.firebasedatabase.app/jobids"
MAX_RECORDS = 1000

# Initialize Firebase
if not firebase_admin._apps:
    # ถ้าใช้ไฟล์ JSON ใน repo
    cred = credentials.Certificate(FIREBASE_JSON_PATH)
    # ถ้าอยาก secure กว่า: load JSON จาก env var (string)
    # FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    # if FIREBASE_SERVICE_ACCOUNT:
    #     cred = credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT))
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL.rsplit('/',1)[0]})
ref = db.reference('jobids')

# ... (ส่วนที่เหลือของโค้ดเหมือนเดิม: intents, bot, cleanup_old_records, delete_all_records, on_ready, on_message, commands ต่าง ๆ)

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("❌ ERROR: No DISCORD_TOKEN found!")
