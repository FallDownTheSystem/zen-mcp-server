/**
 * Context Processor Utilities
 *
 * Utilities for processing file contents, images, and other context
 * to include in AI conversations.
 */

import { readFile, stat } from 'fs/promises';
import { extname } from 'path';

/**
 * Supported file types for context processing
 */
const SUPPORTED_TEXT_EXTENSIONS = [
  '.txt', '.md', '.js', '.ts', '.json', '.yaml', '.yml',
  '.py', '.java', '.c', '.cpp', '.h', '.css', '.html',
  '.xml', '.csv', '.sql', '.sh', '.bat', '.log'
];

const SUPPORTED_IMAGE_EXTENSIONS = [
  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
];

/**
 * Process file content for inclusion in AI context
 * @param {string} filePath - Path to the file
 * @param {object} options - Processing options
 * @returns {object} Processed content with metadata
 */
export async function processFileContent(filePath, options = {}) {
  try {
    const fileStats = await stat(filePath);
    const extension = extname(filePath).toLowerCase();

    const result = {
      path: filePath,
      size: fileStats.size,
      extension,
      type: 'unknown',
      content: null,
      error: null,
    };

    // Check file size limits
    const maxTextSize = options.maxTextSize || 1024 * 1024; // 1MB default
    const maxImageSize = options.maxImageSize || 10 * 1024 * 1024; // 10MB default

    if (SUPPORTED_TEXT_EXTENSIONS.includes(extension)) {
      result.type = 'text';

      if (fileStats.size > maxTextSize) {
        result.error = `File too large (${fileStats.size} bytes, max ${maxTextSize})`;
        return result;
      }

      const content = await readFile(filePath, 'utf8');
      result.content = content;
      result.lineCount = content.split('\n').length;

    } else if (SUPPORTED_IMAGE_EXTENSIONS.includes(extension)) {
      result.type = 'image';

      if (fileStats.size > maxImageSize) {
        result.error = `Image too large (${fileStats.size} bytes, max ${maxImageSize})`;
        return result;
      }

      // For images, we'll read as base64 for AI processing
      const buffer = await readFile(filePath);
      result.content = buffer.toString('base64');
      result.mimeType = getMimeType(extension);

    } else {
      result.error = `Unsupported file type: ${extension}`;
    }

    return result;

  } catch (error) {
    return {
      path: filePath,
      type: 'error',
      error: error.message,
      content: null,
    };
  }
}

/**
 * Process multiple files for context
 * @param {string[]} filePaths - Array of file paths
 * @param {object} options - Processing options
 * @returns {object[]} Array of processed file contents
 */
export async function processMultipleFiles(filePaths, options = {}) {
  const results = await Promise.all(
    filePaths.map(path => processFileContent(path, options))
  );

  return results;
}

/**
 * Create context message from file contents
 * @param {object[]} processedFiles - Array of processed file contents
 * @returns {object} Context message for AI
 */
export function createFileContext(processedFiles) {
  const textFiles = processedFiles.filter(f => f.type === 'text' && !f.error);
  const imageFiles = processedFiles.filter(f => f.type === 'image' && !f.error);
  const errors = processedFiles.filter(f => f.error);

  let contextText = '';

  if (textFiles.length > 0) {
    contextText += '=== FILE CONTEXT ===\n\n';
    for (const file of textFiles) {
      contextText += `--- ${file.path} ---\n`;
      contextText += `${file.content}\n\n`;
    }
  }

  if (errors.length > 0) {
    contextText += '=== FILE ERRORS ===\n';
    for (const error of errors) {
      contextText += `${error.path}: ${error.error}\n`;
    }
    contextText += '\n';
  }

  const message = {
    role: 'user',
    content: [],
  };

  if (contextText) {
    message.content.push({
      type: 'text',
      text: contextText,
    });
  }

  // Add images
  for (const image of imageFiles) {
    message.content.push({
      type: 'image',
      source: {
        type: 'base64',
        media_type: image.mimeType,
        data: image.content,
      },
    });
  }

  return message.content.length > 0 ? message : null;
}

/**
 * Get MIME type for file extension
 * @param {string} extension - File extension
 * @returns {string} MIME type
 */
function getMimeType(extension) {
  const mimeTypes = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
  };

  return mimeTypes[extension] || 'application/octet-stream';
}

/**
 * Validate file paths
 * @param {string[]} filePaths - Array of file paths to validate
 * @returns {object} Validation result with valid/invalid paths
 */
export async function validateFilePaths(filePaths) {
  const results = {
    valid: [],
    invalid: [],
  };

  for (const path of filePaths) {
    try {
      await stat(path);
      results.valid.push(path);
    } catch (error) {
      results.invalid.push({ path, error: error.message });
    }
  }

  return results;
}
