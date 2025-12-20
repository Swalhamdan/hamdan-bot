"""
Main entry point for the Discord bot.
"""
from core.bot import DiscordBot
from core.logging import setup_logging
from config import settings


def main():
    """Initialize and run the Discord bot."""
    # Setup logging
    setup_logging()
    
    # Create and run bot
    # When the bot shuts down (Ctrl+C, SIGTERM, etc.), 
    # discord.py will automatically call bot.close() which
    # disconnects all integrations gracefully
    bot = DiscordBot()
    bot.run(settings.DISCORD_TOKEN)


if __name__ == "__main__":
    main()