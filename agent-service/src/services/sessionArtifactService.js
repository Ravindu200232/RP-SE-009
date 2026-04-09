import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_DIR = path.join(__dirname, '../../../uploads/session-artifacts');

async function ensureDir() {
  await fs.mkdir(ARTIFACT_DIR, { recursive: true });
}

function buildPath(sessionId, suffix) {
  return path.join(ARTIFACT_DIR, `${sessionId}.${suffix}.json`);
}

class SessionArtifactService {
  async writeArtifact(sessionId, suffix, payload) {
    await ensureDir();
    const filePath = buildPath(sessionId, suffix);
    await fs.writeFile(filePath, JSON.stringify(payload, null, 2), 'utf8');
    return filePath;
  }

  async writeQuestionPlan(sessionId, payload) {
    return this.writeArtifact(sessionId, 'questions', payload);
  }

  async readQuestionPlan(sessionId) {
    try {
      const filePath = buildPath(sessionId, 'questions');
      const content = await fs.readFile(filePath, 'utf8');
      return JSON.parse(content);
    } catch {
      return null;
    }
  }

  async writeValidationReport(sessionId, payload) {
    return this.writeArtifact(sessionId, 'validation', payload);
  }

  async writeSrsJson(sessionId, payload) {
    return this.writeArtifact(sessionId, 'srs', payload);
  }
}

export default new SessionArtifactService();
