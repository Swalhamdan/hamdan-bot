"""
Discord commands for qBittorrent integration.
"""
import discord
from discord.ext import commands, tasks
from core.errors import IntegrationError
from core.database import DownloadJobDB
from config import settings
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import subprocess
import asyncio


def extract_torrent_info(torrent: Union[Dict[str, Any], Any]) -> Dict[str, str]:
    """
    Extract torrent information from either a dict or object.
    Handles both callable methods and properties.
    
    Returns:
        Dictionary with title, size, seeds, leeches, file_url, desc_url
    """
    if isinstance(torrent, dict):
        # Handle search results format: fileName, fileSize, nbSeeders, nbLeechers
        title = torrent.get("fileName") or torrent.get("title", "Unknown")
        file_size = torrent.get("fileSize") or torrent.get("size", "Unknown")
        
        # Format file size (convert bytes to human readable)
        if isinstance(file_size, (int, float)) and file_size > 0:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if file_size < 1024.0:
                    file_size = f"{file_size:.2f} {unit}"
                    break
                file_size /= 1024.0
        else:
            file_size = str(file_size)
        
        seeds = torrent.get("nbSeeders") or torrent.get("seeders", "N/A")
        leeches = torrent.get("nbLeechers") or torrent.get("leechers", "N/A")
        
        return {
            "title": str(title),
            "size": str(file_size),
            "seeds": str(seeds),
            "leeches": str(leeches),
            "file_url": str(torrent.get("fileUrl", torrent.get("file_url", ""))),
            "desc_url": str(torrent.get("descrLink", torrent.get("descr_link", "")))
        }
    else:
        # Handle object attributes (may be methods or properties)
        def get_attr_value(attr_name, default=""):
            attr = getattr(torrent, attr_name, None)
            if attr is None:
                return default
            # Try alternative names
            if attr_name == "file_url":
                attr = getattr(torrent, "fileUrl", None) or attr
            elif attr_name == "desc_url":
                attr = getattr(torrent, "descrLink", None) or getattr(torrent, "descr_link", None) or attr
            elif attr_name == "title":
                attr = getattr(torrent, "fileName", None) or attr
            elif attr_name == "size":
                attr = getattr(torrent, "fileSize", None) or attr
            elif attr_name == "seeds":
                attr = getattr(torrent, "nbSeeders", None) or getattr(torrent, "seeders", None) or attr
            elif attr_name == "leeches":
                attr = getattr(torrent, "nbLeechers", None) or getattr(torrent, "leechers", None) or attr
            return attr() if callable(attr) else attr
        
        title = get_attr_value("title", "Unknown")
        file_size = get_attr_value("size", "Unknown")
        
        # Format file size if it's a number
        if isinstance(file_size, (int, float)) and file_size > 0:
            size_val = file_size
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_val < 1024.0:
                    file_size = f"{size_val:.2f} {unit}"
                    break
                size_val /= 1024.0
        else:
            file_size = str(file_size)
        
        return {
            "title": str(title),
            "size": str(file_size),
            "seeds": str(get_attr_value("seeds", "N/A")),
            "leeches": str(get_attr_value("leeches", "N/A")),
            "file_url": str(get_attr_value("file_url", "")),
            "desc_url": str(get_attr_value("desc_url", ""))
        }


class SearchResultsSelect(discord.ui.Select):
    """Select menu for displaying search results (read-only)."""
    
    def __init__(self, torrents: List[Dict[str, Any]]):
        self.torrents = torrents
        
        # Create options from torrents (Discord limit is 25 options)
        options = []
        for i, torrent in enumerate(torrents[:25], 1):
            # Extract torrent info using helper function
            info = extract_torrent_info(torrent)
            
            # Truncate title for display (Discord limit is 100 chars for label)
            display_title = info["title"][:80]
            description = f"Size: {info['size']} | Seeds: {info['seeds']}"[:100]  # Limit description to 100 chars
            
            options.append(
                discord.SelectOption(
                    label=display_title,
                    description=description,
                    value=str(i - 1)  # Store index as value
                )
            )
        
        super().__init__(
            placeholder="View search results...",
            min_values=1,
            max_values=1,
            options=options,
            disabled=True  # Make it read-only
        )
    
    async def callback(self, interaction: discord.Interaction):
        """This shouldn't be called since the select is disabled."""
        pass


class SearchResultsView(discord.ui.View):
    """View containing the search results select menu (display only)."""
    
    def __init__(self, torrents: List[Dict[str, Any]], *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.add_item(SearchResultsSelect(torrents))


class DownloadSelect(discord.ui.Select):
    """Select menu for choosing a torrent to download."""
    
    def __init__(self, torrents: List[Dict[str, Any]], qbit_integration, db: DownloadJobDB):
        self.torrents = torrents
        self.qbit = qbit_integration
        self.db = db
        
        # Create options from torrents (Discord limit is 25 options)
        options = []
        for i, torrent in enumerate(torrents[:25], 1):
            # Extract torrent info using helper function
            info = extract_torrent_info(torrent)
            
            # Truncate title for display (Discord limit is 100 chars for label)
            display_title = info["title"][:80]
            description = f"Size: {info['size']} | Seeds: {info['seeds']}"[:100]  # Limit description to 100 chars
            
            options.append(
                discord.SelectOption(
                    label=display_title,
                    description=description,
                    value=str(i - 1)  # Store index as value
                )
            )
        
        super().__init__(
            placeholder="Select a torrent to download...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle torrent selection and download."""
        selected_index = int(self.values[0])
        selected_torrent = self.torrents[selected_index]
        
        # Extract torrent info using helper function
        info = extract_torrent_info(selected_torrent)
        title = info["title"]
        
        # Use description link or file URL
        download_url = info["file_url"]
        
        if not download_url:
            await interaction.response.send_message(
                "❌ No download URL found for this torrent.",
                ephemeral=True
            )
            return
        
        # Add torrent to qBittorrent
        try:
            torrent_hash = await self.qbit.add_torrent(download_url)
            
            # Save job to database if we got a hash
            if torrent_hash:
                user_id = interaction.user.id
                channel_id = interaction.channel.id if interaction.channel else None
                message_id = interaction.message.id if interaction.message else None
                
                self.db.add_job(
                    user_id=user_id,
                    torrent_hash=torrent_hash,
                    torrent_name=title,
                    channel_id=channel_id,
                    message_id=message_id
                )
            
            await interaction.response.send_message(
                f"✅ Added torrent: **{title[:100]}**\nDownload started! You'll be notified when it completes.",
                ephemeral=True
            )
        except IntegrationError as e:
            await interaction.response.send_message(
                f"❌ Error adding torrent: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Unexpected error: {str(e)}",
                ephemeral=True
            )


class DownloadSelectView(discord.ui.View):
    """View containing the download select menu."""
    
    def __init__(self, torrents: List[Dict[str, Any]], qbit_integration, db: DownloadJobDB, *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.add_item(DownloadSelect(torrents, qbit_integration, db))


class CopyToSMBButton(discord.ui.Button):
    """Button for copying torrent to SMB share."""
    
    def __init__(self, label: str, smb_path: str, torrent_hash: str, torrent_name: str, qbit_integration, db: DownloadJobDB):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.smb_path = smb_path
        self.torrent_hash = torrent_hash
        self.torrent_name = torrent_name
        self.qbit = qbit_integration
        self.db = db
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click to copy files to SMB share."""
        await interaction.response.defer()
        
        try:
            # Get torrent info to find the content path
            torrent_info = await self.qbit.get_torrent_by_hash(self.torrent_hash)
            if not torrent_info:
                await interaction.followup.send(
                    "❌ Torrent not found. It may have been deleted.",
                    ephemeral=True
                )
                return
            
            # Get the content path (where files are stored in qBittorrent container)
            content_path = torrent_info.get("content_path", "") or torrent_info.get("save_path", "")
            if not content_path:
                await interaction.followup.send(
                    "❌ Could not determine torrent file location.",
                    ephemeral=True
                )
                return
            
            # Construct docker cp command
            # Format: docker cp 'qbittorrent:/app/qBittorrent/downloads/torrent_name' /mnt/SMB_PATH
            # Note: The container name is configurable via QBIT_CONTAINER_NAME environment variable
            # The destination path is on the host filesystem (not in the container)
            container_name = settings.QBIT_CONTAINER_NAME
            dest_path = f"/mnt/{self.smb_path}"
            
            # Send initial message
            await interaction.followup.send(
                f"📋 Copying **{self.torrent_name[:100]}** to **{self.smb_path}**... This may take a while.",
                ephemeral=False
            )
            
            # Execute docker cp command
            # This works from within a container when Docker socket is mounted at /var/run/docker.sock
            # The docker command will communicate with the host's Docker daemon through the socket
            try:
                # Execute docker cp: docker cp <container>:<source_path> <dest_path>
                # The destination path is on the host filesystem
                # Note: The destination directory must exist and be writable on the host
                process = await asyncio.create_subprocess_exec(
                    "docker", "cp", f"{container_name}:{content_path}", dest_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    # Check if docker command was not found
                    if "docker: command not found" in error_msg or "docker: not found" in error_msg:
                        error_msg = "Docker CLI not found in container. Please ensure docker.io is installed in the Dockerfile."
                    # Check for permission denied on destination
                    elif "permission denied" in error_msg.lower() or "mkdir" in error_msg.lower():
                        error_msg = (
                            f"{error_msg}\n\n"
                            f"**Solution:** The destination directory `/mnt/{self.smb_path}` must exist on the host "
                            f"and be writable. Please run on the host:\n"
                            f"```bash\n"
                            f"sudo mkdir -p /mnt/{self.smb_path}\n"
                            f"sudo chmod 777 /mnt/{self.smb_path}\n"
                            f"# Or set appropriate ownership:\n"
                            f"# sudo chown -R $(whoami):$(whoami) /mnt/{self.smb_path}\n"
                            f"```"
                        )
                    
                    await interaction.followup.send(
                        f"❌ Error copying files: {error_msg}\n\n"
                        f"**Debug info:**\n"
                        f"- Container: {container_name}\n"
                        f"- Source: {content_path}\n"
                        f"- Destination: {dest_path}\n"
                        f"- Make sure the destination directory exists and is writable on the host",
                        ephemeral=False
                    )
                    return
                
                # Successfully copied, now delete the torrent
                try:
                    # Delete torrent with files
                    await self.qbit.delete_torrent(self.torrent_hash, delete_files=True)
                    
                    # Update job status
                    self.db.update_job_status(self.torrent_hash, "copied_and_deleted")
                    
                    # Disable all buttons in the view
                    for item in self.view.children:
                        if isinstance(item, discord.ui.Button):
                            item.disabled = True
                    
                    # Try to edit the original message to disable buttons
                    try:
                        await interaction.message.edit(view=self.view)
                    except Exception:
                        pass  # If we can't edit, that's okay
                    
                    await interaction.followup.send(
                        f"✅ Successfully copied **{self.torrent_name[:100]}** to **{self.smb_path}** and deleted from qBittorrent!",
                        ephemeral=False
                    )
                except IntegrationError as e:
                    await interaction.followup.send(
                        f"⚠️ Files copied successfully, but error deleting torrent: {str(e)}",
                        ephemeral=False
                    )
                except Exception as e:
                    await interaction.followup.send(
                        f"⚠️ Files copied successfully, but error deleting torrent: {str(e)}",
                        ephemeral=False
                    )
                    
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error executing copy command: {str(e)}",
                    ephemeral=False
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Unexpected error: {str(e)}",
                ephemeral=False
            )


class CopyToSMBView(discord.ui.View):
    """View containing buttons to copy torrent to SMB shares."""
    
    PRIVATE_CHANNEL_ID = 1451977499553829004
    
    def __init__(
        self,
        torrent_hash: str,
        torrent_name: str,
        qbit_integration,
        db: DownloadJobDB,
        user: Union[discord.Member, discord.User],
        channel_id: int,
        *,
        timeout: float = 300
    ):
        super().__init__(timeout=timeout)
        self.torrent_hash = torrent_hash
        self.torrent_name = torrent_name
        self.qbit = qbit_integration
        self.db = db
        
        # Check if user is admin (only works for Member, not User)
        is_admin = False
        if isinstance(user, discord.Member):
            is_admin = user.guild_permissions.administrator
        elif hasattr(user, 'guild_permissions'):
            is_admin = user.guild_permissions.administrator
        
        # Check if in private channel
        is_private_channel = channel_id == self.PRIVATE_CHANNEL_ID
        
        # Always show Movies and Shows buttons
        self.add_item(CopyToSMBButton("Movies", "Movies", torrent_hash, torrent_name, qbit_integration, db))
        self.add_item(CopyToSMBButton("Shows", "Shows", torrent_hash, torrent_name, qbit_integration, db))
        
        # Only show Private buttons if user is admin AND in private channel
        if is_admin and is_private_channel:
            self.add_item(CopyToSMBButton("PrivateMovies", "PrivateMovies", torrent_hash, torrent_name, qbit_integration, db))
            self.add_item(CopyToSMBButton("PrivateShows", "PrivateShows", torrent_hash, torrent_name, qbit_integration, db))


class QBittorrentCog(commands.Cog, name="qBittorrent"):
    """Commands for managing qBittorrent."""
    
    def __init__(self, bot):
        self.bot = bot
        self.qbit = None
        # Store search results per user (user_id -> list of torrents)
        self.user_search_results: Dict[int, List[Dict[str, Any]]] = {}
        # Initialize database
        self.db = DownloadJobDB()
    
    async def cog_load(self):
        """Called when the cog is loaded."""
        # Get qBittorrent integration from bot
        self.qbit = self.bot.get_integration("qBittorrent")
        if self.qbit:
            try:
                await self.qbit.connect()
            except IntegrationError as e:
                print(f"Warning: Failed to connect to qBittorrent: {e}")
        
        # Start the background task to check download status
        self.check_download_status.start()
    
    async def cog_unload(self):
        """Called when the cog is unloaded."""
        # Stop the background task
        self.check_download_status.cancel()
        
        if self.qbit:
            await self.qbit.disconnect()
    
    def _check_integration(self):
        """Check if qBittorrent integration is available."""
        if not self.qbit or not self.qbit.is_connected:
            raise commands.CommandError(
                "qBittorrent integration is not available or not connected."
            )
    
    @commands.group(name="torrent", aliases=["qbit", "qb"])
    async def torrent_group(self, ctx: commands.Context):
        """qBittorrent management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @torrent_group.command(name="list", aliases=["ls"])
    async def torrent_list(self, ctx: commands.Context, status: str = "all"):
        """
        List torrents.
        
        Usage: !torrent list [status]
        Status options: all, downloading, completed, paused, active, inactive
        """
        self._check_integration()
        
        try:
            torrents = await self.qbit.get_torrents(status_filter=status)
            
            if not torrents:
                await ctx.send(f"No torrents found with status: {status}")
                return
            
            # Create embed with torrent list
            embed = discord.Embed(
                title=f"Torrents ({status})",
                color=discord.Color.blue()
            )
            
            # Limit to first 10 for readability
            for torrent in torrents[:10]:
                name = torrent.get("name", "Unknown")
                progress = torrent.get("progress", 0) * 100
                state = torrent.get("state", "Unknown")
                
                embed.add_field(
                    name=name[:50],  # Limit name length
                    value=f"Progress: {progress:.1f}% | State: {state}",
                    inline=False
                )
            
            if len(torrents) > 10:
                embed.set_footer(text=f"Showing 10 of {len(torrents)} torrents")
            
            await ctx.send(embed=embed)
            
        except IntegrationError as e:
            await ctx.send(f"❌ Error: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ Unexpected error: {str(e)}")
    
    @torrent_group.command(name="add")
    async def torrent_add(self, ctx: commands.Context, *, torrent: str):
        """
        Add a torrent or magnet link.
        
        Usage: !torrent add <magnet_link_or_torrent_file>
        """
        self._check_integration()
        
        try:
            torrent_hash = await self.qbit.add_torrent(torrent)
            
            # Get torrent name if we have a hash
            torrent_name = "Unknown"
            if torrent_hash:
                # Try to get the torrent info to get the name
                try:
                    torrent_info = await self.qbit.get_torrent_by_hash(torrent_hash)
                    if torrent_info:
                        torrent_name = torrent_info.get("name", torrent[:100])
                except Exception:
                    torrent_name = torrent[:100] if len(torrent) > 100 else torrent
                
                # Save job to database
                self.db.add_job(
                    user_id=ctx.author.id,
                    torrent_hash=torrent_hash,
                    torrent_name=torrent_name,
                    channel_id=ctx.channel.id if ctx.channel else None,
                    message_id=ctx.message.id if ctx.message else None
                )
            
            await ctx.send("✅ Torrent added successfully! You'll be notified when it completes.")
        except IntegrationError as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @torrent_group.command(name="pause")
    async def torrent_pause(self, ctx: commands.Context, torrent_hash: str):
        """
        Pause a torrent by its hash.
        
        Usage: !torrent pause <torrent_hash>
        """
        self._check_integration()
        
        try:
            await self.qbit.pause_torrent(torrent_hash)
            await ctx.send("✅ Torrent paused successfully!")
        except IntegrationError as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @torrent_group.command(name="resume")
    async def torrent_resume(self, ctx: commands.Context, torrent_hash: str):
        """
        Resume a paused torrent by its hash.
        
        Usage: !torrent resume <torrent_hash>
        """
        self._check_integration()
        
        try:
            await self.qbit.resume_torrent(torrent_hash)
            await ctx.send("✅ Torrent resumed successfully!")
        except IntegrationError as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @torrent_group.command(name="delete", aliases=["remove", "rm"])
    async def torrent_delete(
        self, 
        ctx: commands.Context, 
        torrent_hash: str,
        delete_files: bool = False
    ):
        """
        Delete a torrent by its hash.
        
        Usage: !torrent delete <torrent_hash> [--delete-files]
        """
        self._check_integration()
        
        try:
            await self.qbit.delete_torrent(torrent_hash, delete_files=delete_files)
            action = "deleted" if not delete_files else "deleted with files"
            await ctx.send(f"✅ Torrent {action} successfully!")
        except IntegrationError as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @torrent_group.command(name="status", aliases=["health"])
    async def torrent_status(self, ctx: commands.Context):
        """Check qBittorrent connection status."""
        if not self.qbit:
            await ctx.send("❌ qBittorrent integration not loaded.")
            return
        
        status = self.qbit.get_status()
        health = await self.qbit.health_check()
        
        embed = discord.Embed(
            title="qBittorrent Status",
            color=discord.Color.green() if health else discord.Color.red()
        )
        embed.add_field(name="Connected", value=status["connected"], inline=True)
        embed.add_field(name="Healthy", value=health, inline=True)
        
        await ctx.send(embed=embed)
    
    @torrent_group.command(name="download", aliases=["dl"])
    async def torrent_download(self, ctx: commands.Context):
        """
        Download a torrent from your last search results.
        
        Usage: !torrent download
        This will show a select menu of torrents from your last search.
        """
        self._check_integration()
        
        # Check if user has search results
        user_id = ctx.author.id
        if user_id not in self.user_search_results or not self.user_search_results[user_id]:
            await ctx.send(
                "❌ No search results found. Please run `!torrent search <pattern>` first."
            )
            return
        
        results = self.user_search_results[user_id]
        
        # Create embed
        embed = discord.Embed(
            title="Select Torrent to Download",
            description=f"Choose a torrent from your last search ({len(results)} result(s) available):",
            color=discord.Color.blue()
        )
        
        # Create select menu for downloading
        view = DownloadSelectView(results[:25], self.qbit, self.db)  # Discord limit is 25 options
        
        await ctx.send(embed=embed, view=view)
    
    @torrent_group.command(name="search")
    async def torrent_search(
        self, 
        ctx: commands.Context, 
        pattern: str,
        plugins: str = "piratebay",
        category: str = "all"
    ):
        """
        Search for torrents using qBittorrent search plugins.
        
        Usage: !torrent search <pattern> [plugins] [category]
        Example: !torrent search "heated rivalry" LimeTorrents all
        
        Plugins: all, LimeTorrents, 1337x, ThePirateBay, etc.
        Category: all, movies, tv, music, games, etc.
        """
        self._check_integration()
        
        # Send initial message
        search_msg = await ctx.send(f"🔍 Searching for '{pattern}'... This may take a moment.")
        
        try:
            # Perform search (waits 10 seconds by default)
            search_data = await self.qbit.search_torrents(
                pattern=pattern,
                plugins=plugins,
                category=category,
                wait_time=10
            )
            
            status = search_data.get("status", {})
            results = search_data.get("results", [])
            
            if not results:
                await search_msg.edit(content=f"❌ No results found for '{pattern}'")
                return
            
            # Store results for this user (for download command)
            self.user_search_results[ctx.author.id] = results
            
            # Get total count from status
            total_count = status.get("total", len(results)) if status else len(results)
            
            # Create embed for search results
            embed = discord.Embed(
                title=f"🔍 Search Results: {pattern}",
                description=f"**Plugin:** {plugins} | **Category:** {category}\n"
                           f"**Found:** {total_count} result(s) (showing {len(results)})\n\n"
                           f"Use `!torrent download` to select and download a torrent.",
                color=discord.Color.blue()
            )
            
            # Add results as fields (Discord limit is 25 fields per embed)
            for i, result in enumerate(results[:25], 1):
                # Extract torrent info using helper function
                info = extract_torrent_info(result)
                
                # Format the value with size, seeds, and peers
                value = f"📦 **Size:** {info['size']}\n"
                value += f"🌱 **Seeds:** {info['seeds']} | 👥 **Peers:** {info['leeches']}"
                
                # Truncate title if too long (Discord field name limit is 256 chars)
                title = info['title'][:200] if len(info['title']) > 200 else info['title']
                
                embed.add_field(
                    name=f"{i}. {title}",
                    value=value,
                    inline=False
                )
            
            # Set footer with total count
            embed.set_footer(text=f"Showing {len(results)} of {total_count} results")
            
            await search_msg.edit(content="", embed=embed)
            
        except IntegrationError as e:
            await search_msg.edit(content=f"❌ Error: {str(e)}")
        except Exception as e:
            await search_msg.edit(content=f"❌ Unexpected error: {str(e)}")
    
    @tasks.loop(minutes=1)
    async def check_download_status(self):
        """Background task to check download status and notify users when complete."""
        if not self.qbit or not self.qbit.is_connected:
            return
        
        try:
            # Get all active jobs from database
            active_jobs = self.db.get_active_jobs()
            
            if not active_jobs:
                return
            
            # Check status of each active job
            for job in active_jobs:
                torrent_hash = job["torrent_hash"]
                user_id = job["user_id"]
                torrent_name = job["torrent_name"]
                
                try:
                    # Get current torrent status from qBittorrent
                    torrent_info = await self.qbit.get_torrent_by_hash(torrent_hash)
                    
                    if not torrent_info:
                        # Torrent not found - might have been deleted
                        self.db.update_job_status(torrent_hash, "deleted")
                        continue
                    
                    state = torrent_info.get("state", "").lower()
                    progress = torrent_info.get("progress", 0.0)
                    
                    # Check if torrent is completed
                    # qBittorrent states: uploading, stalledUP, queuedUP, pausedUP, checkingUP, forcedUP, allocating, downloading, stalledDL, queuedDL, checkingDL, pausedDL, forcedDL, missingFiles, error, unknown
                    # Completed states typically include: uploading, stalledUP, queuedUP, pausedUP, checkingUP, forcedUP
                    is_completed = (
                        progress >= 1.0 or
                        state in ["uploading", "stalledup", "queuedup", "pausedup", "checkingup", "forcedup"] or
                        (state == "downloading" and progress >= 0.999)
                    )
                    
                    if is_completed and not job.get("notified", False):
                        # Update job status
                        self.db.update_job_status(
                            torrent_hash,
                            "completed",
                            completed_at=datetime.now()
                        )
                        
                        # Mark as notified
                        self.db.mark_notified(torrent_hash)
                        
                        # Send notification as reply in the same channel
                        try:
                            # Format file size if available
                            size = torrent_info.get("size", 0)
                            size_str = "Unknown"
                            if isinstance(size, (int, float)) and size > 0:
                                size_val = size
                                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                                    if size_val < 1024.0:
                                        size_str = f"{size_val:.2f} {unit}"
                                        break
                                    size_val /= 1024.0
                            
                            embed = discord.Embed(
                                title="✅ Download Complete!",
                                description=f"Your torrent has finished downloading.",
                                color=discord.Color.green(),
                                timestamp=datetime.now()
                            )
                            embed.add_field(
                                name="Torrent Name",
                                value=torrent_name[:1024],
                                inline=False
                            )
                            embed.add_field(
                                name="Size",
                                value=size_str,
                                inline=True
                            )
                            embed.add_field(
                                name="Status",
                                value=state.title(),
                                inline=True
                            )
                            
                            # Try to reply to the original message
                            channel_id = job.get("channel_id")
                            message_id = job.get("message_id")
                            
                            # Get user and channel for button view
                            user = None
                            member = None
                            channel = None
                            try:
                                if channel_id:
                                    channel = self.bot.get_channel(channel_id)
                                    if channel and hasattr(channel, 'guild'):
                                        # Try to get member from guild (for permission checking)
                                        try:
                                            member = await channel.guild.fetch_member(user_id)
                                        except discord.NotFound:
                                            # User not in guild, use User object
                                            user = await self.bot.fetch_user(user_id)
                                    else:
                                        user = await self.bot.fetch_user(user_id)
                                else:
                                    user = await self.bot.fetch_user(user_id)
                            except Exception as e:
                                print(f"Error fetching user/member: {e}")
                            
                            # Create button view for copying to SMB
                            # Use member if available (for permission checks), otherwise user
                            view_user = member if member else user
                            if view_user and channel:
                                view = CopyToSMBView(
                                    torrent_hash=torrent_hash,
                                    torrent_name=torrent_name,
                                    qbit_integration=self.qbit,
                                    db=self.db,
                                    user=view_user,
                                    channel_id=channel_id
                                )
                            else:
                                view = None
                            
                            if channel_id and message_id:
                                try:
                                    channel = self.bot.get_channel(channel_id)
                                    if channel:
                                        try:
                                            # Try to fetch and reply to the original message
                                            original_message = await channel.fetch_message(message_id)
                                            await original_message.reply(embed=embed, view=view, mention_author=True)
                                            continue  # Successfully sent, skip fallback
                                        except discord.NotFound:
                                            # Message not found, fall through to channel send
                                            pass
                                        except discord.Forbidden:
                                            # No permission to reply, fall through to channel send
                                            pass
                                        
                                        # Fallback: send in channel if reply failed
                                        await channel.send(f"<@{user_id}>", embed=embed, view=view)
                                        continue  # Successfully sent
                                except Exception as e:
                                    print(f"Error sending reply notification: {e}")
                            
                            # Last resort: try to send DM if channel info not available
                            user = await self.bot.fetch_user(user_id)
                            if user:
                                await user.send(embed=embed)
                        except discord.Forbidden:
                            # User has DMs disabled and channel send failed
                            print(f"Could not send notification to user {user_id}: DMs disabled and channel unavailable")
                        except Exception as e:
                            print(f"Error sending notification to user {user_id}: {e}")
                    
                    elif state in ["error", "missingfiles"]:
                        # Torrent has an error
                        self.db.update_job_status(torrent_hash, "error")
                        
                        # Notify user of error as reply in the same channel
                        try:
                            embed = discord.Embed(
                                title="❌ Download Error",
                                description=f"Your torrent encountered an error.",
                                color=discord.Color.red(),
                                timestamp=datetime.now()
                            )
                            embed.add_field(
                                name="Torrent Name",
                                value=torrent_name[:1024],
                                inline=False
                            )
                            embed.add_field(
                                name="Error State",
                                value=state.title(),
                                inline=True
                            )
                            
                            # Try to reply to the original message
                            channel_id = job.get("channel_id")
                            message_id = job.get("message_id")
                            
                            if channel_id and message_id:
                                try:
                                    channel = self.bot.get_channel(channel_id)
                                    if channel:
                                        try:
                                            # Try to fetch and reply to the original message
                                            original_message = await channel.fetch_message(message_id)
                                            await original_message.reply(embed=embed, mention_author=True)
                                            continue  # Successfully sent, skip fallback
                                        except discord.NotFound:
                                            # Message not found, fall through to channel send
                                            pass
                                        except discord.Forbidden:
                                            # No permission to reply, fall through to channel send
                                            pass
                                        
                                        # Fallback: send in channel if reply failed
                                        await channel.send(f"<@{user_id}>", embed=embed)
                                        continue  # Successfully sent
                                except Exception as e:
                                    print(f"Error sending error reply notification: {e}")
                            
                            # Last resort: try to send DM if channel info not available
                            user = await self.bot.fetch_user(user_id)
                            if user:
                                await user.send(embed=embed)
                        except discord.Forbidden:
                            # User has DMs disabled and channel send failed
                            print(f"Could not send error notification to user {user_id}: DMs disabled and channel unavailable")
                        except Exception as e:
                            print(f"Error sending error notification to user {user_id}: {e}")
                
                except IntegrationError as e:
                    print(f"Error checking torrent {torrent_hash}: {e}")
                except Exception as e:
                    print(f"Unexpected error checking torrent {torrent_hash}: {e}")
        
        except Exception as e:
            print(f"Error in check_download_status task: {e}")
    
    @check_download_status.before_loop
    async def before_check_download_status(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()


async def setup(bot):
    """Called when the cog is loaded."""
    await bot.add_cog(QBittorrentCog(bot))

