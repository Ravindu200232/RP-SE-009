/**
 * DeepSeekService — SRS generation engine using deepseek-v3.1:671b-cloud via Ollama.
 *
 * Responsibilities:
 *  1. analyzeGaps() — given project description + IEEE template, identify missing info → questions
 *  2. generateSRS() — given complete info, produce full IEEE SRS JSON
 *  3. streamingGenerate() — streaming version for live token display
 */

import axios from 'axios';
import fs from 'fs';
import dotenv from 'dotenv';

dotenv.config();

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-v3.1:671b-cloud';
const SRS_TEMPLATE_PATH = process.env.SRS_TEMPLATE_PATH || 'C:/Users/ravin/Downloads/ieee_srs_training_template.json';

// Load IEEE SRS template once
let IEEE_TEMPLATE = null;
function getTemplate() {
  if (!IEEE_TEMPLATE) {
    try {
      IEEE_TEMPLATE = JSON.parse(fs.readFileSync(SRS_TEMPLATE_PATH, 'utf8'));
    } catch {
      IEEE_TEMPLATE = { document_type: 'Software Requirements Specification', standard: 'IEEE SRS' };
    }
  }
  return IEEE_TEMPLATE;
}

// ── Always fixed — we only build MERN web apps ───────────────────────────────
const FIXED_TECH = {
  application_type: 'Web',
  database_type:    'MongoDB',
  performance_target: '< 2 seconds',
  stack: 'MERN (MongoDB, Express, React, Node.js) microservices',
};

// ── User-friendly display → technical value mappings ─────────────────────────
const DOMAIN_MAP = {
  'Online Shopping':      'E-Commerce',
  'Health & Medical':     'Healthcare',
  'Learning & Courses':   'Education',
  'Finance & Payments':   'Finance',
  'Tasks & Projects':     'Task Management',
  'Social & Community':   'Social Media',
  'Travel & Bookings':    'Travel',
  'Food & Restaurants':   'Food & Restaurant',
  'HR & Team Management': 'HR & Recruitment',
  'Smart Devices':        'IoT & Smart',
  'Something Else':       'General',
};

const AUTH_MAP = {
  'Email & password (most common)':          'Email & Password',
  'Sign in with Google or Facebook':         'OAuth/Social Login',
  'Email & password + Google login':         'Email & Password + OAuth',
  'Extra security code sent to phone (2FA)': 'Multi-Factor Authentication',
  'No login needed — everyone can see it':   'None (Public Access)',
};

const COMPLIANCE_MAP = {
  'Medical or health records (HIPAA)':    'HIPAA',
  'Credit card / online payments (PCI)':  'PCI-DSS',
  'European users data (GDPR)':           'GDPR',
  'Financial / banking data (SOC 2)':     'SOC 2',
  "No sensitive data — it's a normal app":'None',
  "I'm not sure yet":                     'None',
};

// ── Questions asked to the user (plain language, no tech jargon) ──────────────
const REQUIRED_INFO = [
  {
    key: 'project_name',
    section: 'basics',
    question: "What do you want to call your website or app?",
    inputType: 'text',
    placeholder: 'e.g. ShopEasy, HealthHub, LearnSpace, TaskFlow...',
  },
  {
    key: 'domain',
    section: 'basics',
    question: "What is your app mainly about? Pick the closest option:",
    inputType: 'select',
    options: Object.keys(DOMAIN_MAP),
  },
  {
    key: 'target_users',
    section: 'users',
    question: "Who will use your app? Pick everyone that applies:",
    inputType: 'multiselect',
    options: [
      'Customers / Buyers',
      'Business Owners / Admins',
      'Employees / Staff',
      'Managers / Supervisors',
      'Students',
      'Teachers / Trainers',
      'General Public (anyone)',
      'Doctors / Healthcare Workers',
      'Delivery / Field Workers',
    ],
  },
  {
    key: 'core_features',
    section: 'features',
    question: "What should people be able to do on your app? Describe it simply — no tech words needed!",
    inputType: 'textarea',
    placeholder: 'e.g. Browse products, add to cart, pay, track my order, get notified when it arrives, leave reviews...',
  },
  {
    key: 'auth_method',
    section: 'accounts',
    question: "How do you want people to sign in?",
    inputType: 'select',
    options: Object.keys(AUTH_MAP),
  },
  {
    key: 'compliance',
    section: 'privacy',
    question: "Does your app deal with any sensitive information? Pick all that apply:",
    inputType: 'multiselect',
    options: Object.keys(COMPLIANCE_MAP),
  },
];

/**
 * Translate user-friendly answers to technical values for SRS generation.
 */
function normalizeTechnicalValues(info) {
  const out = { ...info };
  if (out.domain && DOMAIN_MAP[out.domain])       out.domain      = DOMAIN_MAP[out.domain];
  if (out.auth_method && AUTH_MAP[out.auth_method]) out.auth_method = AUTH_MAP[out.auth_method];
  if (Array.isArray(out.compliance)) {
    out.compliance = out.compliance.map(c => COMPLIANCE_MAP[c] || c).filter(c => c !== 'None');
    if (!out.compliance.length) out.compliance = ['None'];
  }
  // Normalize target_users (strip display labels)
  if (Array.isArray(out.target_users)) {
    out.target_users = out.target_users.map(u => u.split(' / ')[0].split(' (')[0]);
  }
  return out;
}

const TARGET_USER_CHOICES = [
  'Customers / Buyers',
  'Business Owners / Admins',
  'Employees / Staff',
  'Managers / Supervisors',
  'Students',
  'Teachers / Trainers',
  'General Public (anyone)',
  'Doctors / Healthcare Workers',
  'Delivery / Field Workers',
];

const QUESTION_DEFAULTS = [
  ...REQUIRED_INFO,
  {
    key: 'integrations',
    section: 'technical',
    question: 'Does your app need to connect to any outside systems or APIs?',
    inputType: 'textarea',
    placeholder: 'e.g. payment gateway, maps, email, SMS, delivery partner, or an existing company database...',
  },
  {
    key: 'reports_and_notifications',
    section: 'features',
    question: 'What reports, alerts, or notifications should the app send?',
    inputType: 'textarea',
    placeholder: 'e.g. order updates, admin dashboard reports, low stock alerts, appointment reminders...',
  },
];

const QUESTION_DEFAULT_MAP = Object.fromEntries(QUESTION_DEFAULTS.map((question) => [question.key, question]));
const QUESTION_INPUT_TYPES = new Set(['text', 'textarea', 'select', 'multiselect']);
const QUESTION_SECTIONS = new Set(['basics', 'users', 'features', 'accounts', 'privacy', 'technical', 'interfaces', 'integrations', 'operations']);

function buildTemplateOutline(node, path = 'root', depth = 0, maxDepth = 3) {
  if (depth > maxDepth || node === null || node === undefined) {
    return [];
  }

  if (Array.isArray(node)) {
    if (!node.length) {
      return [`${path}[]`];
    }
    return [`${path}[]`, ...buildTemplateOutline(node[0], `${path}[0]`, depth + 1, maxDepth)];
  }

  if (typeof node === 'object') {
    const lines = [path];
    for (const [key, value] of Object.entries(node)) {
      lines.push(...buildTemplateOutline(value, `${path}.${key}`, depth + 1, maxDepth));
    }
    return lines;
  }

  return [`${path}: ${String(node)}`];
}

function getTemplateExcerpt(limit = 5000) {
  const outline = buildTemplateOutline(getTemplate()).join('\n');
  return outline.length > limit ? `${outline.slice(0, limit)}...` : outline;
}

function stripJsonFence(value = '') {
  return value.replace(/```json\s*/gi, '').replace(/```\s*/g, '').trim();
}

function normalizeKnownFields(rawKnown = {}) {
  const known = { ...rawKnown };
  if (typeof known.target_users === 'string') {
    known.target_users = [known.target_users];
  }
  if (typeof known.compliance === 'string') {
    known.compliance = [known.compliance];
  }
  if (typeof known.integrations === 'string' && !known.integrations.trim()) {
    delete known.integrations;
  }
  return known;
}

function sanitizeQuestionKey(value, index) {
  const normalized = String(value || `detail_${index + 1}`)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');

  return normalized || `detail_${index + 1}`;
}

function normalizeQuestion(rawQuestion, index) {
  const fallback = QUESTION_DEFAULT_MAP[rawQuestion?.key] || null;
  const key = sanitizeQuestionKey(rawQuestion?.key || fallback?.key, index);
  const section = QUESTION_SECTIONS.has(rawQuestion?.section) ? rawQuestion.section : (fallback?.section || 'basics');
  const inputType = QUESTION_INPUT_TYPES.has(rawQuestion?.inputType) ? rawQuestion.inputType : (fallback?.inputType || 'textarea');
  const question = String(rawQuestion?.question || fallback?.question || `Please provide detail ${index + 1}.`).trim();
  const placeholder = String(rawQuestion?.placeholder || fallback?.placeholder || '').trim();
  const templatePaths = Array.isArray(rawQuestion?.template_paths)
    ? rawQuestion.template_paths.map((value) => String(value)).filter(Boolean)
    : [];

  let options = [];
  if ((inputType === 'select' || inputType === 'multiselect') && Array.isArray(rawQuestion?.options)) {
    options = rawQuestion.options.map((value) => String(value).trim()).filter(Boolean);
  }
  if (!options.length && (inputType === 'select' || inputType === 'multiselect') && Array.isArray(fallback?.options)) {
    options = [...fallback.options];
  }

  return {
    key,
    section,
    question,
    inputType: (inputType === 'select' || inputType === 'multiselect') && !options.length ? 'textarea' : inputType,
    placeholder,
    options,
    template_paths: templatePaths,
    importance: String(rawQuestion?.importance || 'medium').toLowerCase(),
  };
}

function dedupeQuestions(questions = []) {
  const seen = new Set();
  const ordered = [];

  for (const question of questions) {
    const normalized = normalizeQuestion(question, ordered.length);
    if (seen.has(normalized.key)) {
      continue;
    }
    seen.add(normalized.key);
    ordered.push(normalized);
  }

  return ordered;
}

class DeepSeekService {
  /**
   * Analyze project description to identify which required info is already present.
   * Returns list of questions for missing information.
   */
  async analyzeGaps(projectDescription, fewShotExamples = [], logFn = () => {}) {
    logFn('🔬 DeepSeek: Understanding your idea...', 'info');

    const examples = fewShotExamples.map(e =>
      `Example (${e.domain}): ${e.training_text}`
    ).join('\n\n');

    const prompt = `You are helping build a web application. Analyze this project description and extract what is already known about the project.

PROJECT DESCRIPTION:
${projectDescription}

${examples ? `SIMILAR PROJECTS FOR REFERENCE:\n${examples}\n` : ''}

Extract the following information if it can be clearly understood from the description:
- project_name: The name of the app (or null if not mentioned)
- domain: The type of app — one of: E-Commerce, Healthcare, Education, Finance, Task Management, Social Media, Travel, Food & Restaurant, HR & Recruitment, IoT & Smart, General (or null)
- target_users: List of who will use it — e.g. ["Customer", "Admin"] (or null)
- core_features: Brief description of what the app does (or null if too vague)
- auth_method: How users sign in — e.g. "Email & Password", "OAuth/Social Login" (or null)
- compliance: Regulatory requirements — e.g. ["HIPAA", "GDPR"] (or [] if none/unknown)

RESPOND with ONLY this JSON:
{
  "known": {
    "project_name": "<value or null>",
    "domain": "<value or null>",
    "target_users": ["<user>"] or null,
    "core_features": "<description or null>",
    "auth_method": "<value or null>",
    "compliance": [] or ["<req>"]
  },
  "summary": "<friendly 1-2 sentence summary of what you understood>"
}

No markdown. Only valid JSON.`;

    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: DEEPSEEK_MODEL,
        messages: [
          { role: 'system', content: 'You are an expert IEEE SRS requirements analyst. Extract structured information from project descriptions. Respond ONLY with valid JSON.' },
          { role: 'user', content: prompt }
        ],
        stream: false,
        options: { temperature: 0.1, num_predict: 2000 }
      }, { timeout: 300000 });

      const content = response.data?.message?.content || '{}';
      const cleaned = content.replace(/```json\n?|```\n?/g, '').trim();
      const start = cleaned.indexOf('{');
      const end = cleaned.lastIndexOf('}') + 1;
      const parsed = JSON.parse(cleaned.slice(start, end));

      logFn(`✅ Gap analysis complete. Summary: ${parsed.summary || 'Analyzed'}`, 'success');
      return parsed;
    } catch (err) {
      logFn(`⚠️ Gap analysis error: ${err.message}. Using default questions.`, 'warning');
      return { known: {}, summary: projectDescription.slice(0, 200) };
    }
  }

  /**
   * Determine which questions still need to be asked.
   * Returns ordered list of question objects.
   */
  getUnansweredQuestions(knownInfo) {
    return REQUIRED_INFO.filter(field => {
      const val = knownInfo[field.key];
      if (!val) return true;
      if (Array.isArray(val) && val.length === 0) return true;
      return false;
    });
  }

  /**
   * Generate the complete IEEE SRS JSON from all collected information.
   * Uses DeepSeek with IEEE template + training examples for guidance.
   */
  async generateSRS(projectDescription, collectedInfo, fewShotExamples = [], logFn = () => {}, onToken = null) {
    logFn('🏗️ DeepSeek: Generating complete IEEE SRS JSON...', 'info');

    const template = getTemplate();
    const examples = fewShotExamples.slice(0, 2).map(e =>
      `Example (${e.domain}): ${e.training_text}`
    ).join('\n\n');

    // Normalize user-friendly answers → technical values + always hardcode MERN/Web
    const info = normalizeTechnicalValues({
      ...FIXED_TECH,
      ...collectedInfo,
    });

    const complianceStr = Array.isArray(info.compliance)
      ? info.compliance.filter(c => c !== 'None').join(', ') || 'None'
      : info.compliance || 'None';

    const prompt = `You are an expert IEEE SRS document generator. Generate a COMPLETE, detailed IEEE SRS JSON for this project.

PROJECT DESCRIPTION:
${projectDescription}

COLLECTED INFORMATION:
- Project Name: ${info.project_name || 'My Application'}
- Domain / Industry: ${info.domain || 'General'}
- Application Type: Web Application (MERN stack microservices)
- Target Users: ${Array.isArray(info.target_users) ? info.target_users.join(', ') : info.target_users || 'General users'}
- Core Features: ${info.core_features || 'To be defined'}
- Database: MongoDB (MERN stack)
- Backend: Node.js + Express microservices
- Frontend: React.js
- Authentication: ${info.auth_method || 'Email & Password'}
- Performance Target: < 2 seconds response time
- Compliance / Privacy: ${complianceStr}

${examples ? `REFERENCE EXAMPLES:\n${examples}\n` : ''}

IEEE SRS TEMPLATE STRUCTURE TO FOLLOW:
${JSON.stringify(template, null, 2).slice(0, 3000)}

REQUIREMENTS:
1. Follow IEEE SRS standard exactly
2. Generate at least 5-8 features with functional requirements
3. Each feature must have: feature_id, feature_name, description_and_priority, functional_requirements (min 2-3 per feature)
4. Include performance, security, safety NFRs
5. Generate realistic business rules
6. Include proper metadata, revision history, appendices
7. Use "The system shall..." format for requirements
8. Replace ALL <placeholders> with real content based on the project
9. services[] array must be MERN microservices compatible:
   - services[].name uses kebab-case
   - services[].port starts at 3001
   - services[].endpoints[] has method, path (/api/v1/...), description
   - services[].entities[] has MongoDB collection names
   - Always include an auth-service at port 3001

OUTPUT: Complete IEEE SRS JSON. No markdown, no explanation. Only the JSON object.`;

    if (onToken) {
      // Streaming mode
      return await this._streamGenerate(prompt, logFn, onToken);
    } else {
      // Non-streaming
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: DEEPSEEK_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You are an IEEE SRS expert. Generate complete, professional Software Requirements Specification documents in JSON format. All content must be detailed, realistic, and follow IEEE standards. Respond ONLY with valid JSON.'
          },
          { role: 'user', content: prompt }
        ],
        stream: false,
        options: { temperature: 0.15, num_predict: 8192, repeat_penalty: 1.1 }
      }, { timeout: 600000 });

      const content = response.data?.message?.content || '';
      return this._parseSRSResponse(content, info);
    }
  }

  /**
   * Streaming SRS generation — emits tokens live.
   */
  async _streamGenerate(prompt, logFn, onToken) {
    let fullResponse = '';

    const response = await axios({
      method: 'POST',
      url: `${OLLAMA_URL}/api/chat`,
      data: {
        model: DEEPSEEK_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You are an IEEE SRS expert. Generate complete, professional Software Requirements Specification documents in JSON format. All content must be detailed, realistic, and follow IEEE standards. Respond ONLY with valid JSON.'
          },
          { role: 'user', content: prompt }
        ],
        stream: true,
        options: { temperature: 0.15, num_predict: 8192, repeat_penalty: 1.1 }
      },
      responseType: 'stream',
      timeout: 600000
    });

    return new Promise((resolve, reject) => {
      response.data.on('data', (chunk) => {
        const lines = chunk.toString().split('\n').filter(Boolean);
        for (const line of lines) {
          try {
            const parsed = JSON.parse(line);
            if (parsed.message?.content) {
              const token = parsed.message.content;
              fullResponse += token;
              if (onToken) onToken(token);
            }
            if (parsed.done) {
              resolve(this._parseSRSResponse(fullResponse, {}));
            }
          } catch {}
        }
      });
      response.data.on('end', () => {
        resolve(this._parseSRSResponse(fullResponse, {}));
      });
      response.data.on('error', reject);
    });
  }

  /**
   * Parse and validate the SRS JSON response.
   */
  _parseSRSResponse(content, collectedInfo) {
    try {
      const cleaned = content.replace(/```json\n?|```\n?/g, '').trim();
      const start = cleaned.indexOf('{');
      const end = cleaned.lastIndexOf('}') + 1;
      if (start === -1 || end <= start) throw new Error('No JSON found');
      const srs = JSON.parse(cleaned.slice(start, end));

      // Ensure it has the correct document_type
      if (!srs.document_type) srs.document_type = 'Software Requirements Specification';
      if (!srs.standard) srs.standard = 'IEEE SRS';

      // Add services[] structure if missing (for code-developer-agent compatibility)
      if (!srs.services) {
        srs.services = this._inferServices(srs, collectedInfo);
      }

      return srs;
    } catch (err) {
      // Return a structured fallback SRS
      return this._buildFallbackSRS(collectedInfo, content);
    }
  }

  /**
   * Infer services from SRS features for code-developer-agent compatibility.
   */
  _inferServices(srs, info) {
    const features = srs.sections?.system_features || [];
    const services = [];
    let port = 3001;

    // Always add auth service
    services.push({
      name: 'auth-service',
      description: 'User authentication and authorization',
      port: port++,
      entities: ['User'],
      endpoints: [
        { method: 'POST', path: '/api/v1/auth/register', description: 'Register new user' },
        { method: 'POST', path: '/api/v1/auth/login', description: 'Login and get JWT token' },
        { method: 'GET', path: '/api/v1/auth/profile', description: 'Get user profile' }
      ],
      dependencies: []
    });

    // Add services for main features
    const projectName = info.project_name || srs.metadata?.project_name || 'app';
    const kebab = projectName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

    features.slice(0, 3).forEach((feat, i) => {
      const featureName = feat.feature_name || `feature-${i + 1}`;
      const svcName = featureName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') + '-service';
      services.push({
        name: svcName,
        description: feat.description_and_priority?.description || featureName,
        port: port++,
        entities: [featureName.split(' ')[0]],
        endpoints: (feat.functional_requirements || []).slice(0, 3).map(req => ({
          method: 'POST',
          path: `/api/v1/${svcName.replace('-service', '')}/${req.requirement_id?.toLowerCase() || 'action'}`,
          description: req.title || req.description || 'Action'
        })),
        dependencies: []
      });
    });

    return services;
  }

  /**
   * Fallback SRS when JSON parsing fails.
   */
  _buildFallbackSRS(info, rawContent) {
    const name = info.project_name || 'My Application';
    return {
      document_type: 'Software Requirements Specification',
      standard: 'IEEE SRS',
      metadata: {
        project_name: name,
        domain: info.domain || 'General',
        application_type: info.application_type || 'Web',
        version: '1.0',
        status: 'draft',
        date_created: new Date().toISOString().split('T')[0],
        language: 'en'
      },
      sections: {
        introduction: {
          purpose: `This SRS describes the software requirements for ${name}.`,
          product_scope: {
            summary: info.core_features || 'Application features to be defined',
            business_objectives: ['Deliver core functionality', 'Ensure user satisfaction'],
            goals: ['Build reliable system', 'Scale with user growth']
          }
        },
        system_features: [{
          feature_id: 'FEAT-001',
          feature_name: 'User Management',
          description_and_priority: { description: 'Core user authentication and management', priority: 'High' },
          functional_requirements: [{
            requirement_id: 'REQ-001',
            title: 'User Registration',
            description: `The system shall allow users to register for ${name}.`,
            priority: 'High', status: 'TBD'
          }]
        }]
      },
      services: this._inferServices({}, info),
      _raw_ai_response: rawContent.slice(0, 500)
    };
  }
}

export default new DeepSeekService();
