import discord
import asyncio

# ใส่ token ที่ reset ใหม่ตรงนี้
TOKEN = "MTQxMTc1MTMwMDMyODA2MzE0Nw.GemOiJ.qcJPcHY8hSm0QXvkrQI63XMxLY2pLO5Ecn-HH0"

async def test_token():
    try:
        intents = discord.Intents.default()
        intents.message_content = True
        
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            print(f'✅ Success! Bot logged in as {client.user}')
            print(f'Bot ID: {client.user.id}')
            print(f'Guilds: {len(client.guilds)}')
            await client.close()
        
        await client.start(TOKEN)
        
    except discord.LoginFailure:
        print("❌ Token invalid!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_token())
