import { defineConfig } from 'vitest/config'
import { getTestConfig } from './tests/suites.config.js'

const suiteConfig = getTestConfig('integration')

export default defineConfig({
  test: {
    // Test environment
    environment: 'node',
    
    // Test file patterns - integration tests only (no real API calls)
    include: suiteConfig.test.include,
    exclude: suiteConfig.test.exclude,
    
    // Timeout configuration - longer for integration tests
    testTimeout: suiteConfig.test.testTimeout,
    hookTimeout: 15000,
    
    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/**',
        'tests/**',
        'dev-server.js',
        'scripts/**',
        '**/*.config.js'
      ],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 60,
        statements: 70
      }
    },
    
    // Mock configuration
    clearMocks: true,
    restoreMocks: true,
    
    // Parallel execution - reduced for integration tests
    pool: 'threads',
    poolOptions: {
      threads: {
        maxThreads: 2,
        minThreads: 1
      }
    },
    
    // Reporter configuration
    reporters: ['verbose'],
    
    // Environment variables
    env: suiteConfig.test.env,
    
    // Setup files
    setupFiles: suiteConfig.test.setupFiles
  }
})