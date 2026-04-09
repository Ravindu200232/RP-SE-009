import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SKILLS_DIR = path.join(__dirname, '../../skills');
const cache = new Map();

function stripFrontmatter(content = '') {
  if (!content.startsWith('---')) {
    return content.trim();
  }

  const end = content.indexOf('\n---', 3);
  if (end === -1) {
    return content.trim();
  }

  return content.slice(end + 4).trim();
}

function readSkill(skillName) {
  if (cache.has(skillName)) {
    return cache.get(skillName);
  }

  const filePath = path.join(SKILLS_DIR, skillName, 'SKILL.md');
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const stripped = stripFrontmatter(content);
    cache.set(skillName, stripped);
    return stripped;
  } catch {
    cache.set(skillName, '');
    return '';
  }
}

class PromptSkillService {
  getInterviewGuidance() {
    return readSkill('human-srs-interviewer');
  }

  getWriterGuidance() {
    return readSkill('ieee-srs-writer');
  }
}

export default new PromptSkillService();
