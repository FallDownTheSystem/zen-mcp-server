# NPM Publishing Guide - Converse MCP Server

## 📦 Publishing to NPM

### Prerequisites

1. **NPM Account**: Create account at [npmjs.com](https://www.npmjs.com)
2. **NPM CLI**: Ensure npm is installed and updated
3. **Package Name**: Check availability of `converse-mcp-server`

### Pre-Publishing Checklist

```bash
# 1. Verify package.json is complete
cat package.json

# 2. Test package build
npm run build

# 3. Run full test suite
npm run validate

# 4. Check files that will be published
npm pack --dry-run

# 5. Test bin script works
node bin/converse.js --help
```

### Publishing Steps

#### 1. Version Management

```bash
# Check current version
npm version

# Bump version (choose one)
npm version patch    # 1.0.0 -> 1.0.1 (bug fixes)
npm version minor    # 1.0.0 -> 1.1.0 (new features)
npm version major    # 1.0.0 -> 2.0.0 (breaking changes)
```

#### 2. Login to NPM

```bash
# Login to npm
npm login

# Verify login
npm whoami
```

#### 3. Publish Package

```bash
# Dry run (test without publishing)
npm publish --dry-run

# Publish to NPM
npm publish

# Publish with tag (for beta versions)
npm publish --tag beta
```

#### 4. Verify Publication

```bash
# Check package on NPM
npm view converse-mcp-server

# Test installation
npm install -g converse-mcp-server
converse --version
```

### Package Configuration

The `package.json` is configured with:

```json
{
  "name": "converse-mcp-server",
  "bin": {
    "converse": "./bin/converse.js",
    "converse-mcp-server": "./bin/converse.js"
  },
  "files": [
    "src/",
    "bin/",
    "docs/",
    "README.md",
    ".env.example"
  ]
}
```

This enables:
- `npx converse-mcp-server` (full name)
- `npx converse` (short alias)
- Global installation: `npm install -g converse-mcp-server`

### Testing After Publication

#### 1. Test NPX Execution

```bash
# Test direct execution
npx converse-mcp-server

# Test short alias
npx converse

# Test with different package managers
pnpm dlx converse-mcp-server
yarn dlx converse-mcp-server
```

#### 2. Test MCP Client Integration

Update Claude Desktop config to use NPM package:

```json
{
  "mcpServers": {
    "converse": {
      "command": "npx",
      "args": ["converse-mcp-server"],
      "env": {
        "OPENAI_API_KEY": "your_key_here"
      }
    }
  }
}
```

#### 3. Test Global Installation

```bash
# Install globally
npm install -g converse-mcp-server

# Test command
converse --version

# Test in MCP client with direct command
{
  "command": "converse",
  "args": []
}
```

### Alternative: GitHub Package Registry

If NPM name is unavailable, publish to GitHub:

#### 1. Configure for GitHub Packages

```json
{
  "name": "@falldownthesystem/converse",
  "publishConfig": {
    "registry": "https://npm.pkg.github.com"
  }
}
```

#### 2. Authenticate with GitHub

```bash
# Create .npmrc file
echo "@falldownthesystem:registry=https://npm.pkg.github.com" > .npmrc

# Login with GitHub token
npm login --registry=https://npm.pkg.github.com
```

#### 3. Publish to GitHub

```bash
npm publish --registry=https://npm.pkg.github.com
```

#### 4. Usage from GitHub Packages

```bash
# Install from GitHub
npm install -g @falldownthesystem/converse

# Use in MCP clients
npx @falldownthesystem/converse
```

### Automated Publishing

#### 1. GitHub Actions Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to NPM

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          registry-url: 'https://registry.npmjs.org'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm run validate
      
      - name: Publish to NPM
        run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

#### 2. Version Management Script

Create `scripts/release.js`:

```javascript
#!/usr/bin/env node

import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';

const type = process.argv[2] || 'patch';

console.log(`🚀 Releasing ${type} version...`);

// Run tests
execSync('npm run validate', { stdio: 'inherit' });

// Bump version
execSync(`npm version ${type}`, { stdio: 'inherit' });

// Get new version
const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
const version = pkg.version;

console.log(`✅ Ready to publish v${version}`);
console.log('Run: npm publish');
```

### Maintenance

#### 1. Update Dependencies

```bash
# Check for updates
npm outdated

# Update dependencies
npm update

# Update major versions manually
npm install @modelcontextprotocol/sdk@latest
```

#### 2. Security Audits

```bash
# Check for vulnerabilities
npm audit

# Fix vulnerabilities
npm audit fix
```

#### 3. Deprecation

If need to deprecate a version:

```bash
# Deprecate specific version
npm deprecate converse-mcp-server@1.0.0 "Please upgrade to 1.0.1"

# Deprecate all versions
npm deprecate converse-mcp-server "Package has been renamed"
```

### Package Name Strategy

#### Option 1: Try to Claim `converse`

```bash
# Check if available
npm view converse

# If available, update package.json
{
  "name": "converse"
}
```

#### Option 2: Use Scoped Package

```bash
# If main name unavailable
{
  "name": "@falldownthesystem/converse"
}

# Usage becomes:
npx @falldownthesystem/converse
```

#### Option 3: Alternative Names

If `converse-mcp-server` is taken:
- `converse-mcp`
- `mcp-converse`
- `converse-ai-server`
- `converse-chat-server`

### Documentation Updates

After publishing, update:

1. **README.md**: Add NPM installation instructions
2. **SETUP.md**: Update with NPM package commands
3. **GitHub README**: Add NPM badge and links

### NPM Badge for README

```markdown
[![npm version](https://badge.fury.io/js/converse-mcp-server.svg)](https://badge.fury.io/js/converse-mcp-server)
[![npm downloads](https://img.shields.io/npm/dm/converse-mcp-server.svg)](https://www.npmjs.com/package/converse-mcp-server)
```

---

**Ready to Publish?** Follow the checklist above and run `npm publish`!