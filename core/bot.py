import discord
from discord.ext import commands
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Optional
from integrations.base import BaseIntegration
from config import settings


class DiscordBot(commands.Bot):
    """
    Main Discord bot class with integration management.
    """
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required for message commands
        super().__init__(command_prefix=settings.PREFIX, intents=intents)
        
        # Dictionary to store all integrations
        self._integrations: Dict[str, BaseIntegration] = {}
    
    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Initialize integrations
        await self._load_integrations()
        
        # Load all cogs dynamically
        await self._load_cogs()
    
    async def _load_integrations(self):
        """Load and initialize all integrations from config."""
        from integrations.qbittorrent import QBittorrentIntegration
        
        # Load qBittorrent integration if configured
        if settings.QBIT_HOST:
            qbit_config = {
                "host": settings.QBIT_HOST,
                "username": settings.QBIT_USERNAME or '',
                "password": settings.QBIT_PASSWORD or ''
            }
            qbit = QBittorrentIntegration(qbit_config)
            self._integrations["qBittorrent"] = qbit
            
            # Try to connect
            try:
                await qbit.connect()
                print(f"✅ Connected to {qbit.name}")
            except Exception as e:
                print(f"⚠️  Failed to connect to {qbit.name}: {e}")
        
        # Add more integrations here as you create them
        # Example:
        # if hasattr(settings, 'SOME_SERVICE_API_KEY'):
        #     some_service = SomeServiceIntegration({...})
        #     self._integrations["SomeService"] = some_service
    
    async def _load_cogs(self):
        """Dynamically load all cogs from the cogs directory."""
        cogs_path = Path(__file__).parent.parent / "cogs"
        
        # Find all Python files in cogs directory
        for module_info in pkgutil.iter_modules([str(cogs_path)]):
            if module_info.name.endswith("_cog"):
                try:
                    await self.load_extension(f"cogs.{module_info.name}")
                    print(f"✅ Loaded cog: {module_info.name}")
                except Exception as e:
                    print(f"❌ Failed to load cog {module_info.name}: {e}")
    
    def get_integration(self, name: str) -> Optional[BaseIntegration]:
        """
        Get an integration by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Integration instance or None if not found
        """
        return self._integrations.get(name)
    
    def get_all_integrations(self) -> Dict[str, BaseIntegration]:
        """
        Get all loaded integrations.
        
        Returns:
            Dictionary of all integrations
        """
        return self._integrations.copy()
    
    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"✅ {self.user} is online!")
        print(f"📊 Connected to {len(self.guilds)} guild(s)")
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param.name}")
            return
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
            return
        
        # Log other errors
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)}")
    
    async def close(self):
        """
        Clean up when the bot is shutting down.
        Disconnects all integrations gracefully.
        """
        print("🛑 Shutting down bot...")
        
        # Disconnect all integrations
        for name, integration in self._integrations.items():
            if integration.is_connected:
                try:
                    await integration.disconnect()
                    print(f"✅ Disconnected from {name}")
                except Exception as e:
                    print(f"⚠️  Error disconnecting from {name}: {e}")
        
        # Call parent close method
        await super().close()
