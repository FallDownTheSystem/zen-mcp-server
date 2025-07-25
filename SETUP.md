# Converse MCP Server - Setup Guide

## 🚀 Quick Start Options

### Option 1: NPX (Recommended for Users)

```bash
# Install and run directly from GitHub
npx FallDownTheSystem/converse

# Alternative with pnpm
pnpm dlx FallDownTheSystem/converse

# Alternative with yarn
yarn dlx FallDownTheSystem/converse
```

### Option 2: NPM Package (When Published)

```bash
# Install globally
npm install -g converse-mcp-server

# Run
converse

# Or run without installing
npx converse-mcp-server
```

### Option 3: From Source (For Developers)

```bash
# Clone repository
git clone https://github.com/FallDownTheSystem/converse.git
cd converse

# Install dependencies
npm install

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start server
npm start
```

## 🔑 API Key Setup

### 1. Get Your API Keys

| Provider | Sign Up | Key Format | Free Tier |
|----------|---------|------------|-----------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com/api-keys) | `sk-proj-...` | $5 credit |
| **Google** | [makersuite.google.com](https://makersuite.google.com/app/apikey) | `AIzaSy...` | 50 requests/day |
| **X.AI** | [console.x.ai](https://console.x.ai/) | `xai-...` | $5 credit |

### 2. Configure Environment

Create `.env` file:

```bash
# Required: At least one API key
OPENAI_API_KEY=sk-proj-your_openai_key_here
GOOGLE_API_KEY=your_google_api_key_here
XAI_API_KEY=xai-your_xai_key_here

# Optional: Advanced settings
MAX_MCP_OUTPUT_TOKENS=200000
LOG_LEVEL=info
PORT=3000
```

## 🔌 MCP Client Integration

### Claude Desktop Configuration

Add to your Claude Desktop config file:

**Location:**
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration:**

```json
{
  "mcpServers": {
    "converse": {
      "command": "npx",
      "args": ["FallDownTheSystem/converse"],
      "env": {
        "OPENAI_API_KEY": "sk-proj-your_key_here",
        "GOOGLE_API_KEY": "your_google_key_here",
        "XAI_API_KEY": "xai-your_xai_key_here",
        "MAX_MCP_OUTPUT_TOKENS": "200000"
      }
    }
  }
}
```

### Alternative: Using NPM Package

If published to NPM:

```json
{
  "mcpServers": {
    "converse": {
      "command": "npx",
      "args": ["converse-mcp-server"],
      "env": {
        "OPENAI_API_KEY": "sk-proj-your_key_here",
        "GOOGLE_API_KEY": "your_google_key_here",
        "XAI_API_KEY": "xai-your_xai_key_here"
      }
    }
  }
}
```

### Other MCP Clients

For other MCP clients, use the same command structure:

```bash
# Command
npx FallDownTheSystem/converse

# Environment variables
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIzaSy...
XAI_API_KEY=xai-...
MAX_MCP_OUTPUT_TOKENS=200000
```

## ⚙️ Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | * | - | OpenAI API key |
| `GOOGLE_API_KEY` | * | - | Google API key |
| `XAI_API_KEY` | * | - | X.AI API key |
| `PORT` | No | `3000` | Server port |
| `LOG_LEVEL` | No | `info` | Logging level |
| `MAX_MCP_OUTPUT_TOKENS` | No | `25000` | Max response tokens |
| `GOOGLE_LOCATION` | No | `us-central1` | Google API region |
| `XAI_BASE_URL` | No | `https://api.x.ai/v1` | XAI API endpoint |

**Note**: At least one API key is required.

### Model Selection

Use these model identifiers:

**OpenAI Models:**
- `o3` - Strong reasoning (200K context)
- `o3-mini` - Fast O3 variant
- `o4-mini` - Latest balanced model
- `gpt-4o` - Multimodal flagship
- `gpt-4o-mini` - Fast multimodal

**Google Models:**
- `gemini-2.5-flash` (alias: `flash`) - Ultra-fast
- `gemini-2.5-pro` (alias: `pro`) - Deep reasoning
- `gemini-2.0-flash` - Latest with thinking

**X.AI Models:**
- `grok-4-0709` (alias: `grok`) - Latest advanced
- `grok-3` - Previous generation
- `grok-3-fast` - High performance

**Auto-Selection:**
- `auto` - Automatically choose best available model

## 🐛 Troubleshooting

### Common Issues

**"Module not found" errors:**
```bash
# Ensure Node.js >= 20.0.0
node --version

# Clear npm cache if using npx
npx --clear-cache
```

**"API key not found" errors:**
```bash
# Check your .env file format
cat .env

# Verify environment variables are set
echo $OPENAI_API_KEY
```

**Port conflicts:**
```bash
# Use different port
PORT=3001 npx FallDownTheSystem/converse
```

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=debug npx FallDownTheSystem/converse

# Trace all operations
LOG_LEVEL=trace npx FallDownTheSystem/converse
```

### Test Your Setup

```bash
# Download and run test script
npx FallDownTheSystem/converse --test

# Or manually test API keys
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

## 📋 System Requirements

### Minimum Requirements
- **Node.js**: >= 20.0.0 (LTS recommended)
- **Memory**: 256MB RAM
- **Storage**: 50MB for dependencies
- **Network**: Internet connection for API calls

### Recommended
- **Node.js**: 22.x LTS
- **Memory**: 512MB RAM
- **Storage**: 100MB for development

### Supported Platforms
- ✅ Windows 10/11
- ✅ macOS 12+ (Intel & Apple Silicon)
- ✅ Linux (Ubuntu 20.04+, RHEL 8+)
- ✅ Docker containers

## 🔄 Updates

### NPX Auto-Updates
When using `npx FallDownTheSystem/converse`, you automatically get the latest version.

### Manual Updates
```bash
# If installed globally
npm update -g converse-mcp-server

# If using from source
git pull origin main
npm install
```

### Version Check
```bash
npx FallDownTheSystem/converse --version
```

## 🚀 Advanced Setup

### Docker

```dockerfile
FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY src/ src/
COPY bin/ bin/

EXPOSE 3000
CMD ["npm", "start"]
```

### PM2 Process Manager

```bash
# Install PM2
npm install -g pm2

# Create ecosystem file
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'converse-mcp',
    script: 'npx FallDownTheSystem/converse',
    env: {
      NODE_ENV: 'production',
      OPENAI_API_KEY: 'your_key_here',
      GOOGLE_API_KEY: 'your_key_here',
      XAI_API_KEY: 'your_key_here'
    }
  }]
}
EOF

# Start with PM2
pm2 start ecosystem.config.js
```

### Systemd Service (Linux)

```bash
# Create service file
sudo cat > /etc/systemd/system/converse-mcp.service << 'EOF'
[Unit]
Description=Converse MCP Server
After=network.target

[Service]
Type=simple
User=node
WorkingDirectory=/opt/converse
ExecStart=/usr/bin/npx FallDownTheSystem/converse
Environment=NODE_ENV=production
Environment=OPENAI_API_KEY=your_key_here
Environment=GOOGLE_API_KEY=your_key_here
Environment=XAI_API_KEY=your_key_here
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable converse-mcp
sudo systemctl start converse-mcp
```

## 📚 Next Steps

1. **Verify Setup**: Test with your MCP client
2. **Read Documentation**: Check [API.md](docs/API.md) for usage examples
3. **Join Community**: Report issues on [GitHub](https://github.com/FallDownTheSystem/converse/issues)
4. **Contribute**: See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup

---

**Need Help?** Open an issue on [GitHub](https://github.com/FallDownTheSystem/converse/issues) with your setup details.