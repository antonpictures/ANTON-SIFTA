import os
import json
import discord

CONFIG_PATH = "sifta_channels.json"

class SwarmDiscordClient(discord.Client):
    async def on_ready(self):
        print("╔══════════════════════════════════════════════╗")
        print(f"║   SIFTA SWARM — Discord Channel Active      ║")
        print(f"║   Logged in as: {self.user}                 ║")
        print("╚══════════════════════════════════════════════╝")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # TODO: Route message.content to the SIFTA Relay or Agent loop
        reply = f"[SWARM RECEIPT]: Acknowledged your discord message: {message.content}"
        await message.channel.send(reply)

def main():
    if not os.path.exists(CONFIG_PATH):
        print("sifta_channels.json not found. Please run the setup GUI.")
        return
        
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except:
        config = {}
        
    token = config.get("DISCORD_BOT_TOKEN")
    if not token:
        print("No Discord token found! Setup Discord via the Setup GUI.")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = SwarmDiscordClient(intents=intents)
    client.run(token)

if __name__ == "__main__":
    main()
