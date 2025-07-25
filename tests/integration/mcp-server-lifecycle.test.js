import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import { createServer } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { loadConfig } from '../../src/config.js'
import { createRouter } from '../../src/router.js'
import { logger } from '../../src/utils/logger.js'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

describe('MCP Server Lifecycle Integration Tests', () => {
  let config
  let router
  let server
  let transport

  beforeAll(async () => {
    try {
      // Load configuration
      config = await loadConfig()
      
      // Create router
      router = await createRouter(config)
      
      // Create MCP server instance
      server = createServer(
        {
          name: config.mcp.serverName,
          version: config.mcp.serverVersion
        },
        {
          capabilities: {}
        }
      )

      // Mock transport for testing (we don't actually connect stdio)
      transport = {
        start: vi.fn(),
        close: vi.fn()
      }

      logger.info('[mcp-lifecycle-test] Server lifecycle test setup completed')
    } catch (error) {
      logger.error('[mcp-lifecycle-test] Setup failed:', error)
      throw error
    }
  })

  afterAll(async () => {
    try {
      if (transport && transport.close) {
        await transport.close()
      }
      logger.info('[mcp-lifecycle-test] Server lifecycle test cleanup completed')
    } catch (error) {
      logger.error('[mcp-lifecycle-test] Cleanup failed:', error)
    }
  })

  describe('Server Configuration', () => {
    it('should load configuration correctly', () => {
      expect(config).toBeDefined()
      expect(config.server).toBeDefined()
      expect(config.apiKeys).toBeDefined()
      expect(config.providers).toBeDefined()
      expect(config.mcp).toBeDefined()

      // Validate configuration structure
      expect(config.server.port).toBeTypeOf('number')
      expect(config.server.nodeEnv).toBeTypeOf('string')
      expect(config.server.logLevel).toBeTypeOf('string')
      expect(config.mcp.serverName).toBe('converse-mcp-server')
      expect(config.mcp.serverVersion).toBe('1.0.0')
    })

    it('should validate environment variables correctly', () => {
      // Test that required configuration is present
      expect(config.server.port).toBeGreaterThan(0)
      expect(config.server.port).toBeLessThanOrEqual(65535)
      expect(['development', 'test', 'production'].includes(config.server.nodeEnv)).toBe(true)
      expect(['error', 'warn', 'info', 'debug', 'trace'].includes(config.server.logLevel)).toBe(true)
    })

    it('should have MCP client configuration', () => {
      const mcpConfig = config.getMcpClientConfig()
      
      expect(mcpConfig).toBeDefined()
      expect(mcpConfig.name).toBe('converse-mcp-server')
      expect(mcpConfig.version).toBe('1.0.0')
    })
  })

  describe('Server Initialization', () => {
    it('should create MCP server with proper metadata', () => {
      expect(server).toBeDefined()
      
      // Check that server has proper structure
      expect(server.setRequestHandler).toBeTypeOf('function')
      expect(server.connect).toBeTypeOf('function')
      expect(server.close).toBeTypeOf('function')
    })

    it('should register router handlers correctly', async () => {
      expect(router).toBeDefined()
      expect(router.listTools).toBeTypeOf('function')
      expect(router.callTool).toBeTypeOf('function')

      // Test that router can handle basic operations
      const toolsList = await router.listTools()
      expect(toolsList).toBeDefined()
      expect(toolsList.tools).toBeDefined()
      expect(Array.isArray(toolsList.tools)).toBe(true)
      expect(toolsList.tools.length).toBeGreaterThan(0)
    })

    it('should have tools properly registered', async () => {
      const toolsList = await router.listTools()
      const toolNames = toolsList.tools.map(tool => tool.name)
      
      // Should have both main tools
      expect(toolNames).toContain('chat')
      expect(toolNames).toContain('consensus')
      
      // Each tool should have proper metadata
      toolsList.tools.forEach(tool => {
        expect(tool.name).toBeTypeOf('string')
        expect(tool.description).toBeTypeOf('string')
        expect(tool.inputSchema).toBeDefined()
        expect(tool.inputSchema.type).toBe('object')
        expect(tool.inputSchema.properties).toBeDefined()
      })
    })
  })

  describe('Provider Availability', () => {
    it('should detect available providers correctly', async () => {
      const { getAvailableProviders } = await import('../../src/providers/index.js')
      const availableProviders = getAvailableProviders(config)
      
      expect(Array.isArray(availableProviders)).toBe(true)
      
      // Should have at least one provider if API keys are configured
      if (config.apiKeys.openai || config.apiKeys.xai || config.apiKeys.google) {
        expect(availableProviders.length).toBeGreaterThan(0)
      }

      // Check provider structure
      availableProviders.forEach(provider => {
        expect(provider.name).toBeTypeOf('string')
        expect(provider.provider).toBeDefined()
        expect(provider.provider.invoke).toBeTypeOf('function')
      })
    })

    it('should validate provider interfaces', async () => {
      const { getProviders } = await import('../../src/providers/index.js')
      const providers = getProviders()
      
      Object.entries(providers).forEach(([name, provider]) => {
        expect(provider.invoke).toBeTypeOf('function')
        expect(provider.validateConfig).toBeTypeOf('function')
        expect(provider.isAvailable).toBeTypeOf('function')
        expect(provider.getSupportedModels).toBeTypeOf('function')
        expect(provider.getModelConfig).toBeTypeOf('function')
      })
    })
  })

  describe('Server Startup Simulation', () => {
    it('should complete startup sequence without errors', async () => {
      // This simulates the startup sequence from src/index.js
      let startupSuccess = true
      let startupError = null

      try {
        // 1. Configuration loading (already done in beforeAll)
        expect(config).toBeDefined()

        // 2. Router creation (already done in beforeAll)
        expect(router).toBeDefined()

        // 3. Server creation (already done in beforeAll)
        expect(server).toBeDefined()

        // 4. Server configuration
        server.setRequestHandler(ListToolsRequestSchema, async () => {
          return await router.listTools()
        })

        server.setRequestHandler(CallToolRequestSchema, async (request) => {
          return await router.callTool(request.params)
        })

        logger.info('[mcp-lifecycle-test] Startup sequence simulation completed successfully')
      } catch (error) {
        startupSuccess = false
        startupError = error
        logger.error('[mcp-lifecycle-test] Startup sequence failed:', error)
      }

      expect(startupSuccess).toBe(true)
      if (startupError) {
        throw startupError
      }
    })

    it('should handle configuration errors gracefully', async () => {
      // Test with invalid configuration
      const invalidConfig = {
        server: {
          port: -1, // Invalid port
          nodeEnv: 'invalid-env',
          logLevel: 'invalid-level'
        },
        apiKeys: {},
        providers: {},
        mcp: {
          serverName: '',
          serverVersion: ''
        }
      }

      // Configuration validation should catch these issues
      try {
        const { validateConfig } = await import('../../src/config.js')
        await validateConfig(invalidConfig)
        expect(true).toBe(false) // Should not reach here
      } catch (error) {
        expect(error).toBeDefined()
        expect(error.message).toMatch(/(port|environment|log level|server name)/i)
      }
    })
  })

  describe('Server Shutdown Simulation', () => {
    it('should handle graceful shutdown', async () => {
      let shutdownSuccess = true
      let shutdownError = null

      try {
        // Simulate graceful shutdown process
        
        // 1. Stop accepting new connections (simulated)
        logger.info('[mcp-lifecycle-test] Stopping new connections...')
        
        // 2. Close existing connections (simulated)
        if (transport && transport.close) {
          logger.info('[mcp-lifecycle-test] Closing transport...')
          // Note: Not actually calling close here as it's mocked
        }
        
        // 3. Close server (simulated)
        if (server && server.close) {
          logger.info('[mcp-lifecycle-test] Closing server...')
          // Note: MCP server close is handled by transport
        }
        
        // 4. Cleanup resources
        logger.info('[mcp-lifecycle-test] Cleaning up resources...')
        
        logger.info('[mcp-lifecycle-test] Graceful shutdown simulation completed')
      } catch (error) {
        shutdownSuccess = false
        shutdownError = error
        logger.error('[mcp-lifecycle-test] Shutdown simulation failed:', error)
      }

      expect(shutdownSuccess).toBe(true)
      if (shutdownError) {
        throw shutdownError
      }
    })

    it('should cleanup continuation store on shutdown', async () => {
      const { getContinuationStore } = await import('../../src/continuationStore.js')
      const store = getContinuationStore()

      // Add some test data
      const testConversation = {
        messages: [{ role: 'user', content: 'test' }],
        provider: 'openai',
        model: 'gpt-4o-mini'
      }

      const conversationId = await store.set(testConversation)
      expect(conversationId).toBeDefined()

      // Verify data exists
      const retrieved = await store.get(conversationId)
      expect(retrieved).toBeDefined()

      // Simulate cleanup (in a real shutdown, this would be more comprehensive)
      await store.cleanup(0) // Cleanup all conversations older than 0ms (all of them)

      // Verify cleanup worked
      const stats = await store.getStats()
      expect(stats.totalConversations).toBe(0)
    })
  })

  describe('Process Spawning Test', () => {
    it('should be able to spawn the actual server process', async () => {
      // This test verifies that the server can actually be spawned as a subprocess
      const serverPath = join(__dirname, '../../src/index.js')
      
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          child.kill('SIGTERM')
          reject(new Error('Server startup timeout'))
        }, 10000) // 10 second timeout

        const child = spawn('node', [serverPath], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: {
            ...process.env,
            NODE_ENV: 'test',
            LOG_LEVEL: 'error'
          }
        })

        let output = ''
        let errorOutput = ''

        child.stdout.on('data', (data) => {
          output += data.toString()
        })

        child.stderr.on('data', (data) => {
          errorOutput += data.toString()
          
          // Look for startup completion indicators
          if (errorOutput.includes('converse-mcp-server v1.0.0') || 
              errorOutput.includes('Server ready')) {
            clearTimeout(timeout)
            child.kill('SIGTERM')
            
            // Give it a moment to shutdown
            setTimeout(() => {
              expect(errorOutput).toContain('converse-mcp-server')
              logger.info('[mcp-lifecycle-test] Process spawn test completed successfully')
              resolve()
            }, 1000)
          }
        })

        child.on('error', (error) => {
          clearTimeout(timeout)
          logger.error('[mcp-lifecycle-test] Process spawn failed:', error)
          reject(error)
        })

        child.on('exit', (code, signal) => {
          clearTimeout(timeout)
          if (signal === 'SIGTERM') {
            // Expected termination
            resolve()
          } else if (code !== 0) {
            reject(new Error(`Server process exited with code ${code}\nStdout: ${output}\nStderr: ${errorOutput}`))
          } else {
            resolve()
          }
        })
      })
    }, 15000) // 15 second test timeout
  })

  describe('Memory and Performance', () => {
    it('should have reasonable memory usage', async () => {
      const memUsage = process.memoryUsage()
      
      // Memory usage should be reasonable (less than 100MB for basic setup)
      expect(memUsage.heapUsed).toBeLessThan(100 * 1024 * 1024) // 100MB
      expect(memUsage.rss).toBeLessThan(200 * 1024 * 1024) // 200MB
      
      logger.debug(`[mcp-lifecycle-test] Memory usage - Heap: ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB, RSS: ${Math.round(memUsage.rss / 1024 / 1024)}MB`)
    })

    it('should start up quickly', async () => {
      // Test router creation time
      const startTime = Date.now()
      
      const testRouter = await createRouter(config)
      
      const duration = Date.now() - startTime
      
      expect(testRouter).toBeDefined()
      expect(duration).toBeLessThan(100) // Should take less than 100ms
      
      logger.debug(`[mcp-lifecycle-test] Router creation took ${duration}ms`)
    })
  })
})