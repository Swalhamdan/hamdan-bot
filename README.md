# Discord Home Automation Bot

A modular Discord bot built with discord.py that integrates with various home automation services, starting with qBittorrent.

## Project Structure

```
bot/
├── main.py                 # Entry point
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── core/                   # Core bot functionality
│   ├── bot.py             # Main bot class with integration management
│   ├── errors.py          # Custom exceptions
│   └── logging.py         # Logging configuration
├── integrations/           # Service integration modules
│   ├── __init__.py
│   ├── base.py            # Base integration abstract class
│   └── qbittorrent.py     # qBittorrent integration
└── cogs/                   # Discord command modules
    ├── __init__.py
    ├── qbittorrent_cog.py # qBittorrent commands
    └── admin_cog.py       # Administrative commands
```

## Architecture

### Integration System

The bot uses a modular integration system where each external service (qBittorrent, etc.) is implemented as an integration module:

1. **Base Integration** (`integrations/base.py`): Abstract base class that all integrations must inherit from
2. **Service Integrations** (`integrations/*.py`): Specific implementations for each service
3. **Cogs** (`cogs/*_cog.py`): Discord command modules that use the integrations

### Key Features

- **Modular Design**: Easy to add new integrations without modifying existing code
- **Dynamic Loading**: Cogs are automatically discovered and loaded
- **Error Handling**: Centralized error handling with custom exceptions
- **Type Safety**: Type hints throughout the codebase

## Setup

### Option 1: Docker Compose (Recommended)

1. **Configure Environment Variables**:
   Create a `.env` file in the project root:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   PREFIX=!
   
   # qBittorrent (optional)
   # If qBittorrent is running on the host, use host.docker.internal
   # If qBittorrent is in another container, use the container name or service name
   QBIT_HOST=http://host.docker.internal:8080
   QBIT_USERNAME=admin
   QBIT_PASSWORD=adminadmin
   ```

2. **Build and Run**:
   ```bash
   docker-compose up -d
   ```

3. **View Logs**:
   ```bash
   docker-compose logs -f bot
   ```

4. **Stop the Bot**:
   ```bash
   docker-compose down
   ```

## Server Deployment

### Prerequisites

1. **Install Docker and Docker Compose** on your server:
   ```bash
   # For Ubuntu/Debian
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Compose (if not included)
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   
   # Log out and back in for group changes to take effect
   ```

2. **Verify Installation**:
   ```bash
   docker --version
   docker compose version
   ```

### Deployment Steps

**Option A: Clone from Git Repository** (Recommended)

1. **SSH into Your Server**:
   ```bash
   ssh user@your-server
   ```

2. **Clone the Repository**:
   ```bash
   # Install git if not already installed
   sudo apt-get update && sudo apt-get install -y git
   
   # Clone the repository
   git clone <your-repository-url> /opt/discord-bot
   cd /opt/discord-bot
   ```

3. **Create `.env` File**:
   ```bash
   nano .env
   ```
   Add your configuration:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   PREFIX=!
   
   # qBittorrent configuration
   # If qBittorrent is on the same server, use the server's IP or hostname
   # If qBittorrent is in another container, use the container name
   QBIT_HOST=http://localhost:8080
   QBIT_USERNAME=admin
   QBIT_PASSWORD=adminadmin
   ```

4. **Build and Start the Container**:
   ```bash
   # Build the image
   docker compose build
   
   # Start in detached mode
   docker compose up -d
   ```

5. **Verify It's Running**:
   ```bash
   # Check container status
   docker compose ps
   
   # View logs
   docker compose logs -f bot
   ```

**Option B: Transfer Files Manually**

1. **Transfer Files to Server** (from your local machine):
   ```bash
   # Using scp
   scp -r . user@your-server:/opt/discord-bot/
   
   # Or using rsync (excludes .git, __pycache__, etc.)
   rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' . user@your-server:/opt/discord-bot/
   ```

2. **SSH into Your Server**:
   ```bash
   ssh user@your-server
   cd /opt/discord-bot
   ```

3. **Continue from step 3 above** (Create `.env` file)

### Managing the Service

**View Logs**:
```bash
# Follow logs in real-time
docker compose logs -f bot

# View last 100 lines
docker compose logs --tail=100 bot
```

**Restart the Bot**:
```bash
docker compose restart bot
```

**Stop the Bot**:
```bash
docker compose stop bot
```

**Start the Bot**:
```bash
docker compose start bot
```

**Update and Rebuild**:
```bash
# If using Git, pull latest changes:
git pull

# Then rebuild and restart:
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Check Container Health**:
```bash
docker compose ps
docker inspect discord-home-automation-bot | grep -A 10 Health
```

### Optional: Auto-Start on Boot (systemd)

Create a systemd service for automatic startup:

1. **Create Service File**:
   ```bash
   sudo nano /etc/systemd/system/discord-bot.service
   ```

2. **Add the Following** (adjust paths as needed):
   ```ini
   [Unit]
   Description=Discord Home Automation Bot
   Requires=docker.service
   After=docker.service

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/path/to/bot
   ExecStart=/usr/bin/docker compose up -d
   ExecStop=/usr/bin/docker compose down
   TimeoutStartSec=0

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and Start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable discord-bot.service
   sudo systemctl start discord-bot.service
   ```

4. **Check Status**:
   ```bash
   sudo systemctl status discord-bot.service
   ```

### Troubleshooting

**Container won't start**:
```bash
# Check logs for errors
docker compose logs bot

# Check if port is already in use
sudo netstat -tulpn | grep :8080
```

**Can't connect to qBittorrent**:
- If qBittorrent is on the host: Use `http://host.docker.internal:8080` (Linux) or the host's IP address
- If qBittorrent is in another container: Use the container name or service name
- Ensure qBittorrent's Web UI is enabled and accessible

**Permission Issues**:
```bash
# Ensure Docker group is set up
sudo usermod -aG docker $USER
# Log out and back in
```

### Option 2: Local Development

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the project root:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   PREFIX=!
   
   # qBittorrent (optional)
   QBIT_HOST=http://localhost:8080
   QBIT_USERNAME=admin
   QBIT_PASSWORD=adminadmin
   ```

3. **Run the Bot**:
   ```bash
   python main.py
   ```

## Adding a New Integration

To add a new service integration, follow these steps:

### 1. Create Integration Module

Create a new file in `integrations/` (e.g., `integrations/myservice.py`):

```python
from typing import Dict, Any, Optional
from .base import BaseIntegration
from core.errors import IntegrationError

class MyServiceIntegration(BaseIntegration):
    """Integration for MyService."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
    
    @property
    def name(self) -> str:
        return "MyService"
    
    async def connect(self) -> bool:
        # Implement connection logic
        # Set self._connected = True on success
        pass
    
    async def disconnect(self) -> None:
        # Implement disconnection logic
        pass
    
    async def health_check(self) -> bool:
        # Implement health check
        pass
    
    # Add service-specific methods here
```

### 2. Update Configuration

Add configuration variables to `config.py`:

```python
MY_SERVICE_API_KEY: Optional[str] = os.getenv("MY_SERVICE_API_KEY", None)
```

### 3. Register Integration in Bot

Update `core/bot.py` in the `_load_integrations` method:

```python
from integrations.myservice import MyServiceIntegration

# In _load_integrations method:
if hasattr(settings, 'MY_SERVICE_API_KEY') and settings.MY_SERVICE_API_KEY:
    my_service = MyServiceIntegration({
        "api_key": settings.MY_SERVICE_API_KEY
    })
    self._integrations["MyService"] = my_service
    try:
        await my_service.connect()
    except Exception as e:
        print(f"⚠️  Failed to connect to MyService: {e}")
```

### 4. Create Discord Commands Cog

Create `cogs/myservice_cog.py`:

```python
import discord
from discord.ext import commands
from core.errors import IntegrationError

class MyServiceCog(commands.Cog, name="MyService"):
    """Commands for MyService."""
    
    def __init__(self, bot):
        self.bot = bot
        self.service = None
    
    async def cog_load(self):
        self.service = self.bot.get_integration("MyService")
        if self.service:
            try:
                await self.service.connect()
            except IntegrationError as e:
                print(f"Warning: Failed to connect to MyService: {e}")
    
    async def cog_unload(self):
        if self.service:
            await self.service.disconnect()
    
    @commands.command(name="myservice")
    async def my_command(self, ctx: commands.Context):
        """Example command."""
        if not self.service or not self.service.is_connected:
            await ctx.send("❌ MyService integration is not available.")
            return
        
        # Use self.service to interact with the service
        await ctx.send("Command executed!")

async def setup(bot):
    await bot.add_cog(MyServiceCog(bot))
```

The cog will be automatically loaded by the bot!

## Usage

### qBittorrent Commands

- `!torrent list [status]` - List torrents (status: all, downloading, completed, etc.)
- `!torrent add <magnet_link>` - Add a torrent or magnet link
- `!torrent pause <hash>` - Pause a torrent
- `!torrent resume <hash>` - Resume a torrent
- `!torrent delete <hash> [--delete-files]` - Delete a torrent
- `!torrent status` - Check qBittorrent connection status

### Admin Commands

- `!ping` - Check bot latency
- `!integrations` - List all loaded integrations
- `!reload <cog>` - Reload a cog (admin only)

## Best Practices

1. **Error Handling**: Always use `IntegrationError` for integration-specific errors
2. **Async Operations**: All integration methods should be async
3. **Connection Management**: Always implement proper connect/disconnect logic
4. **Health Checks**: Implement health checks for monitoring
5. **Type Hints**: Use type hints for better code clarity and IDE support

## License

[Your License Here]

