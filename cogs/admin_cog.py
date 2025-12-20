"""
Administrative commands for the bot.
"""
import discord
from discord.ext import commands


class AdminCog(commands.Cog, name="Admin"):
    """Administrative commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")
    
    @commands.command(name="integrations", aliases=["modules", "mods"])
    async def list_integrations(self, ctx: commands.Context):
        """List all loaded integrations."""
        integrations = self.bot.get_all_integrations()
        
        if not integrations:
            await ctx.send("No integrations loaded.")
            return
        
        embed = discord.Embed(
            title="Loaded Integrations",
            color=discord.Color.blue()
        )
        
        for name, integration in integrations.items():
            status = integration.get_status()
            embed.add_field(
                name=name,
                value=f"Connected: {status['connected']}",
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog: str):
        """
        Reload a cog.
        
        Usage: !reload <cog_name>
        """
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Reloaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"❌ Error reloading cog: {str(e)}")


async def setup(bot):
    """Called when the cog is loaded."""
    await bot.add_cog(AdminCog(bot))

