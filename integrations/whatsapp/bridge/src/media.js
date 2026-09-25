/**
 * Media Management for WhatsApp Bridge.
 * Downloads incoming media streams into temporary local storage for Jarvis ingestion.
 * Transport-only: Cleans up temporary artifacts on demand.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DEFAULT_TEMP_DIR = path.resolve(__dirname, "../../../data/whatsapp_temp");

function ensureTempDir(tempDir = DEFAULT_TEMP_DIR) {
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }
  return tempDir;
}

async function saveMediaBuffer(buffer, mimeType, filenameHint = "media", tempDir = DEFAULT_TEMP_DIR) {
  ensureTempDir(tempDir);
  const hash = crypto.createHash("sha256").update(buffer).digest("hex").slice(0, 16);
  let ext = ".bin";

  if (mimeType.includes("image/jpeg")) ext = ".jpg";
  else if (mimeType.includes("image/png")) ext = ".png";
  else if (mimeType.includes("audio/ogg") || mimeType.includes("opus")) ext = ".ogg";
  else if (mimeType.includes("audio/wav")) ext = ".wav";
  else if (mimeType.includes("audio/mp4") || mimeType.includes("audio/m4a")) ext = ".m4a";
  else if (mimeType.includes("application/pdf")) ext = ".pdf";
  else if (mimeType.includes("text/plain")) ext = ".txt";

  const safeBase = path.basename(filenameHint, path.extname(filenameHint)).replace(/[^a-zA-Z0-9_-]/g, "_");
  const fileName = `${Date.now()}_${safeBase}_${hash}${ext}`;
  const filePath = path.join(tempDir, fileName);

  await fs.promises.writeFile(filePath, buffer);

  return {
    file_path: filePath,
    filename: fileName,
    mimetype: mimeType,
    size_bytes: buffer.length,
    sha256: hash
  };
}

function cleanupMediaFile(filePath) {
  try {
    if (filePath && fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      return true;
    }
  } catch (err) {
    // Ignore cleanup error
  }
  return false;
}

module.exports = {
  ensureTempDir,
  saveMediaBuffer,
  cleanupMediaFile
};
