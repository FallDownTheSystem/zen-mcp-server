/**
 * Test Suite Configuration for Converse MCP Server
 * 
 * This file organizes tests into logical suites for different execution contexts:
 * - Unit tests: Fast, isolated tests with mocked dependencies
 * - Integration tests: Tests with real dependencies but no external API calls
 * - Real API tests: Tests that make actual API calls (require valid API keys)
 * - Performance tests: Tests focused on performance and scalability
 * - CI/CD tests: Tests suitable for continuous integration environments
 */

export const testSuites = {
  /**
   * Unit Tests - Fast, isolated tests with mocked dependencies
   * Suitable for: Development, CI/CD
   * Requirements: None (no API keys needed)
   * Execution time: ~30 seconds
   */
  unit: {
    include: [
      'tests/providers/**/*.test.js',
      'tests/tools/**/*.test.js'
    ],
    exclude: [
      'tests/integration/**/*'
    ],
    testTimeout: 10000, // 10 seconds
    setupFiles: [],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'error'
    }
  },

  /**
   * Integration Tests - Real dependencies, no external API calls
   * Suitable for: Development, CI/CD
   * Requirements: None (uses mocked providers)
   * Execution time: ~2 minutes
   */
  integration: {
    include: [
      'tests/integration/mcp-protocol.test.js',
      'tests/integration/mcp-protocol-enhanced.test.js',
      'tests/integration/mcp-server-lifecycle.test.js',
      'tests/integration/tools-integration.test.js',
      'tests/integration/continuation-flow.test.js',
      'tests/integration/error-recovery.test.js',
    ],
    exclude: [
      'tests/integration/real-api*.test.js',
      'tests/integration/performance*.test.js'
    ],
    testTimeout: 30000, // 30 seconds
    setupFiles: [],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'error'
    }
  },

  /**
   * Real API Tests - Tests that make actual API calls
   * Suitable for: Local development with API keys
   * Requirements: Valid API keys in environment
   * Execution time: ~5-10 minutes
   */
  'real-api': {
    include: [
      'tests/integration/real-api.test.js',
      'tests/integration/real-api-enhanced.test.js'
    ],
    exclude: [],
    testTimeout: 60000, // 1 minute per test
    setupFiles: ['tests/setup/api-keys-check.js'],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'warn'
    }
  },

  /**
   * Performance Tests - Performance and scalability focused tests
   * Suitable for: Performance validation, load testing
   * Requirements: Valid API keys recommended
   * Execution time: ~5-15 minutes
   */
  performance: {
    include: [
      'tests/integration/performance-consensus.test.js'
    ],
    exclude: [],
    testTimeout: 300000, // 5 minutes per test
    setupFiles: [],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'info'
    }
  },

  /**
   * CI/CD Tests - Tests suitable for continuous integration
   * Suitable for: GitHub Actions, automated testing
   * Requirements: None (skips tests requiring API keys)
   * Execution time: ~3 minutes
   */
  ci: {
    include: [
      'tests/providers/**/*.test.js',
      'tests/tools/**/*.test.js',
      'tests/integration/mcp-protocol.test.js',
      'tests/integration/mcp-protocol-enhanced.test.js',
      'tests/integration/mcp-server-lifecycle.test.js',
      'tests/integration/tools-integration.test.js',
      'tests/integration/continuation-flow.test.js',
      'tests/integration/error-recovery.test.js',
    ],
    exclude: [
      'tests/integration/real-api*.test.js',
      'tests/integration/performance*.test.js'
    ],
    testTimeout: 30000, // 30 seconds
    setupFiles: [],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'error',
      CI: 'true'
    }
  },

  /**
   * All Tests - Complete test suite (development only)
   * Suitable for: Comprehensive local testing
   * Requirements: Valid API keys for full functionality
   * Execution time: ~15-20 minutes
   */
  all: {
    include: [
      'tests/**/*.test.js'
    ],
    exclude: [],
    testTimeout: 300000, // 5 minutes per test
    setupFiles: [],
    env: {
      NODE_ENV: 'test',
      LOG_LEVEL: 'info'
    }
  }
}

/**
 * Get test configuration for a specific suite
 * @param {string} suiteName - Name of the test suite
 * @returns {Object} Test configuration object
 */
export function getTestConfig(suiteName) {
  const suite = testSuites[suiteName]
  if (!suite) {
    throw new Error(`Unknown test suite: ${suiteName}`)
  }

  return {
    test: {
      include: suite.include,
      exclude: suite.exclude,
      testTimeout: suite.testTimeout,
      setupFiles: suite.setupFiles,
      env: {
        ...suite.env,
        TEST_SUITE: suiteName
      }
    }
  }
}

/**
 * Get available test suites
 * @returns {string[]} Array of suite names
 */
export function getAvailableSuites() {
  return Object.keys(testSuites)
}

/**
 * Validate environment for a specific test suite
 * @param {string} suiteName - Name of the test suite
 * @returns {Object} Validation result with warnings and errors
 */
export function validateSuiteEnvironment(suiteName) {
  const suite = testSuites[suiteName]
  const warnings = []
  const errors = []

  if (!suite) {
    errors.push(`Unknown test suite: ${suiteName}`)
    return { valid: false, warnings, errors }
  }

  // Check for API keys if needed
  if (suiteName === 'real-api' || suiteName === 'all') {
    const apiKeys = {
      openai: process.env.OPENAI_API_KEY,
      xai: process.env.XAI_API_KEY,
      google: process.env.GOOGLE_API_KEY
    }

    const missingKeys = Object.entries(apiKeys)
      .filter(([, value]) => !value)
      .map(([key]) => key.toUpperCase() + '_API_KEY')

    if (missingKeys.length === 3) {
      errors.push('No API keys found. Real API tests will be skipped.')
    } else if (missingKeys.length > 0) {
      warnings.push(`Missing API keys: ${missingKeys.join(', ')}. Some tests may be skipped.`)
    }
  }

  // Check Node.js version
  const nodeVersion = process.version
  const majorVersion = parseInt(nodeVersion.slice(1).split('.')[0])
  if (majorVersion < 18) {
    warnings.push(`Node.js version ${nodeVersion} detected. Recommended: Node.js 18+`)
  }

  // Check memory for performance tests
  if (suiteName === 'performance' || suiteName === 'all') {
    const memLimit = process.memoryUsage().heapTotal
    const memLimitMB = memLimit / 1024 / 1024
    if (memLimitMB < 512) {
      warnings.push(`Low memory detected (${Math.round(memLimitMB)}MB). Performance tests may be affected.`)
    }
  }

  return {
    valid: errors.length === 0,
    warnings,
    errors
  }
}

// Default export for convenience
export default testSuites