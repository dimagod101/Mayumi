import discord
from discord import app_commands
from discord.ext import commands, tasks
import httpx
import random

# CONFIGURATION
TOKEN = 'YOUR_BOT_TOKEN_HERE'
SITES = {
    "images": "https://gelbooru.com/index.php",
    "videos": "https://realbooru.com/index.php",
    "comics": "https://rule34.xxx/index.php" # Rule34 often hosts multi-page 'pools'
}

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.auto_tasks = {} # Stores active auto-posts

    async def setup_hook(self):
        await self.tree.sync() # Syncs slash commands to Discord

bot = MyBot()

async def fetch_content(tags, amount, type_key):
    url = SITES.get(type_key, SITES["images"])
    params = {
        "page": "dapi", "s": "post", "q": "index", "json": 1,
        "tags": f"{tags} sort:random", "limit": amount
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        return r.json() if r.status_code == 200 else []

# --- COMMANDS ---

@bot.tree.command(name="nsfw", description="Fetch NSFW content")
@app_commands.describe(type="Choose category", tags="Search tags", amount="Number of posts")
@app_commands.choices(type=[
    app_commands.Choice(name="Images", value="images"),
    app_commands.Choice(name="Videos", value="videos"),
    app_commands.Choice(name="Comics", value="comics")
])
async def nsfw_cmd(interaction: discord.Interaction, type: str, tags: str, amount: int = 1):
    if not interaction.channel.is_nsfw():
        return await interaction.response.send_message("❌ This must be an NSFW channel!", ephemeral=True)
    
    await interaction.response.defer()
    data = await fetch_content(tags, min(amount, 5), type)
    
    if not data:
        return await interaction.followup.send("No results found.")

    for post in data:
        await interaction.followup.send(post.get('file_url', "Error fetching URL"))

@bot.tree.command(name="auto_post", description="Set up an automated posting interval")
async def auto_post(interaction: discord.Interaction, delay_minutes: int, type: str, tags: str):
    channel_id = interaction.channel.id
    
    # Define the loop task
    @tasks.loop(minutes=delay_minutes)
    async def post_loop():
        data = await fetch_content(tags, 1, type)
        if data:
            await interaction.channel.send(data[0]['file_url'])

    if channel_id in bot.auto_tasks:
        bot.auto_tasks[channel_id].stop()

    post_loop.start()
    bot.auto_tasks[channel_id] = post_loop
    await interaction.response.send_message(f"✅ Auto-posting {type} every {delay_minutes}m.")

@bot.tree.command(name="auto_post_cancel", description="Stop the auto-poster in this channel")
async def cancel(interaction: discord.Interaction):
    task = bot.auto_tasks.pop(interaction.channel.id, None)
    if task:
        task.stop()
        await interaction.response.send_message("🛑 Auto-post stopped.")
    else:
        await interaction.response.send_message("No active auto-post found here.")

bot.run(TOKEN)

