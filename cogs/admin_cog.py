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
        compose_file = (settings.QBIT_COMPOSE_FILE or "").strip()
        compose_path = Path(compose_dir) / compose_file if compose_file else None

        if not compose_path or not compose_path.exists():
            # Try common compose filenames if not explicitly set or missing
            candidates = [
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
            ]
            compose_path = None
            for candidate in candidates:
                candidate_path = Path(compose_dir) / candidate
                if candidate_path.exists():
                    compose_path = candidate_path
                    break

        if not compose_path:
            await ctx.send(
                f"❌ Compose file not found in `{compose_dir}`.\n"
                f"Set `QBIT_COMPOSE_DIR` and `QBIT_COMPOSE_FILE` in `.env` if needed."
            )
            return
        
        base_cmd = [
            "-f",
            str(compose_path),
        ]
        
        if action == "up":
            sub_cmd = ["up", "-d"]
        elif action == "down":
            sub_cmd = ["down"]
        elif action == "restart":
            sub_cmd = ["restart"]
        else:  # status
            sub_cmd = ["ps"]

        async def run_compose(command_prefix):
            cmd = command_prefix + base_cmd + sub_cmd
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(compose_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode().strip(), stderr.decode().strip(), cmd

        await ctx.send("🧰 Running compose command...")

        try:
            returncode, output, error, cmd = await run_compose(["docker", "compose"])

            # Fallback for older Docker versions without 'docker compose'
            if returncode != 0 and (
                "unknown shorthand flag: 'f'" in error.lower()
                or "docker: 'compose' is not a docker command" in error.lower()
                or "unknown flag: -f" in error.lower()
            ):
                returncode, output, error, cmd = await run_compose(["docker-compose"])
            
            if returncode != 0:
                if "docker: command not found" in error or "docker: not found" in error:
                    error = "Docker CLI not found. Please install Docker on the host."
                if not error:
                    error = "Unknown error"
                if len(error) > 1800:
                    error = error[:1800] + "\n... (truncated)"
                await ctx.send(f"❌ Command failed:\n```{error}```")
                return
            
            if not output:
                output = "Command completed successfully."
            if len(output) > 1800:
                output = output[:1800] + "\n... (truncated)"
            
            pretty_cmd = " ".join(cmd)
            await ctx.send(f"✅ Done (`{pretty_cmd}`):\n```{output}```")
        except Exception as e:
            await ctx.send(f"❌ Error executing compose command: {str(e)}")


async def setup(bot):
    """Called when the cog is loaded."""
    await bot.add_cog(AdminCog(bot))

