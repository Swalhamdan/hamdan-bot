# Quick Server Deployment Guide

## Quick Start

### Option 1: Clone from Git (Recommended)

1. **SSH to server**:
   ```bash
   ssh user@server
   ```

2. **Clone the repository**:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   git clone <your-repository-url> /opt/discord-bot
   cd /opt/discord-bot
   ```

3. **Create `.env` file**:
   ```bash
   nano .env
   ```
   ```env
   BOT_TOKEN=your_token_here
   PREFIX=!
   QBIT_HOST=http://localhost:8080
   QBIT_USERNAME=admin
   QBIT_PASSWORD=adminadmin
   ```

4. **Start the bot**:
   ```bash
   docker compose up -d
   ```

5. **Check logs**:
   ```bash
   docker compose logs -f bot
   ```

### Option 2: Transfer Files Manually

1. **Transfer files to server** (from local machine):
   ```bash
   rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' . user@server:/opt/discord-bot/
   ```

2. **SSH to server**:
   ```bash
   ssh user@server
   cd /opt/discord-bot
   ```

3. **Continue from step 3 above** (Create `.env` file)

## Common Commands

```bash
# View logs
docker compose logs -f bot

# Restart
docker compose restart bot

# Stop
docker compose stop bot

# Start
docker compose start bot

# Update (if using Git, pull first: git pull)
docker compose down
docker compose build
docker compose up -d
```

## Network Configuration

### qBittorrent on Same Server (Host)
- Use: `http://localhost:8080` or `http://host.docker.internal:8080`
- The `extra_hosts` in docker-compose.yml enables `host.docker.internal`

### qBittorrent in Another Container
- Use: `http://qbittorrent-container-name:8080` or service name
- Ensure both containers are on the same Docker network

### qBittorrent on Different Server
- Use: `http://server-ip:8080` or `http://server-hostname:8080`
- Ensure firewall allows connections

## Troubleshooting

**Bot won't start:**
```bash
docker compose logs bot
docker compose ps
```

**Can't connect to qBittorrent:**
- Check qBittorrent is running: `curl http://localhost:8080`
- Test from container: `docker compose exec bot curl http://host.docker.internal:8080`
- Verify QBIT_HOST in .env matches your setup

**Permission denied:**
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

