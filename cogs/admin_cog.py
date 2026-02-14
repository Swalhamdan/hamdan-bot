"""
Administrative commands for the bot.
"""
from pathlib import Path
import asyncio
import discord
from discord.ext import commands
from config import settings


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

    @commands.command(name="qbitcompose", aliases=["qbcompose", "qbitctl"])
    @commands.has_permissions(administrator=True)
    async def qbit_compose(self, ctx: commands.Context, action: str):
        """
        Control the qBittorrent docker compose stack on the host.
        
        Usage: !qbitcompose <up|down|restart|status>
        """
        action = action.lower().strip()
        allowed_actions = {"up", "down", "restart", "status"}
        if action not in allowed_actions:
            await ctx.send("❌ Invalid action. Use: up, down, restart, status")
            return
        
        compose_dir = settings.QBIT_COMPOSE_DIR
        compose_file = settings.QBIT_COMPOSE_FILE or "docker-compose.yml"
        compose_path = Path(compose_dir) / compose_file
        
        if not compose_path.exists():
            await ctx.send(
                f"❌ Compose file not found: `{compose_path}`\n"
                f"Set `QBIT_COMPOSE_DIR` and `QBIT_COMPOSE_FILE` in `.env` if needed."
            )
            return
        
        base_cmd = [
            "docker",
            "compose",
            "--project-directory",
            str(compose_dir),
            "-f",
            str(compose_path),
        ]
        
        if action == "up":
            cmd = base_cmd + ["up", "-d"]
        elif action == "down":
            cmd = base_cmd + ["down"]
        elif action == "restart":
            cmd = base_cmd + ["restart"]
        else:  # status
            cmd = base_cmd + ["ps"]
        
        await ctx.send(f"🧰 Running: `docker compose {action}`")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            if process.returncode != 0:
                if "docker: command not found" in error or "docker: not found" in error:
                    error = "Docker CLI not found. Please install Docker on the host."
                await ctx.send(f"❌ Command failed:\n```{error or 'Unknown error'}```")
                return
            
            if not output:
                output = "Command completed successfully."
            if len(output) > 1800:
                output = output[:1800] + "\n... (truncated)"
            
            await ctx.send(f"✅ Done:\n```{output}```")
        except Exception as e:
            await ctx.send(f"❌ Error executing compose command: {str(e)}")


async def setup(bot):
    """Called when the cog is loaded."""
    await bot.add_cog(AdminCog(bot))

