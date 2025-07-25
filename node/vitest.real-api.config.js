import { defineConfig } from 'vitest/config'
import { getTestConfig } from './tests/suites.config.js'

const suiteConfig = getTestConfig('real-api')

export default defineConfig({
  test: {
    // Test environment
    environment: 'node',
    
    // Test file patterns - real API tests only
    include: suiteConfig.test.include,
    exclude: suiteConfig.test.exclude,
    
    // Timeout configuration - longer for real API calls
    testTimeout: suiteConfig.test.testTimeout,
    hookTimeout: 30000,
    
    // Coverage configuration - relaxed for real API tests
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json'],
      exclude: [
        'node_modules/**',
        'tests/**',
        'dev-server.js',
        'scripts/**',
        '**/*.config.js'
      ]
    },
    
    // Mock configuration
    clearMocks: true,
    restoreMocks: true,
    
    // Sequential execution for real API tests to avoid rate limiting
    pool: 'threads',
    poolOptions: {
      threads: {
        maxThreads: 1,
        minThreads: 1
      }
    },
    
    // Reporter configuration
    reporters: ['verbose'],
    
    // Environment variables
    env: suiteConfig.test.env,
    
    // Setup files
    setupFiles: suiteConfig.test.setupFiles,
    
    // Retry configuration for flaky API tests
    retry: 1
  }
})