"""
Discord commands for qBittorrent integration.
"""
import discord
from discord.ext import commands
from core.errors import IntegrationError
from typing import List, Dict, Any, Union


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
    
    def __init__(self, torrents: List[Dict[str, Any]], qbit_integration):
        self.torrents = torrents
        self.qbit = qbit_integration
        
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
            await self.qbit.add_torrent(download_url)
            await interaction.response.send_message(
                f"✅ Added torrent: **{title[:100]}**\nDownload started!",
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
    
    def __init__(self, torrents: List[Dict[str, Any]], qbit_integration, *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.add_item(DownloadSelect(torrents, qbit_integration))


class QBittorrentCog(commands.Cog, name="qBittorrent"):
    """Commands for managing qBittorrent."""
    
    def __init__(self, bot):
        self.bot = bot
        self.qbit = None
        # Store search results per user (user_id -> list of torrents)
        self.user_search_results: Dict[int, List[Dict[str, Any]]] = {}
    
    async def cog_load(self):
        """Called when the cog is loaded."""
        # Get qBittorrent integration from bot
        self.qbit = self.bot.get_integration("qBittorrent")
        if self.qbit:
            try:
                await self.qbit.connect()
            except IntegrationError as e:
                print(f"Warning: Failed to connect to qBittorrent: {e}")
    
    async def cog_unload(self):
        """Called when the cog is unloaded."""
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
            await self.qbit.add_torrent(torrent)
            await ctx.send("✅ Torrent added successfully!")
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
        view = DownloadSelectView(results[:25], self.qbit)  # Discord limit is 25 options
        
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


async def setup(bot):
    """Called when the cog is loaded."""
    await bot.add_cog(QBittorrentCog(bot))

