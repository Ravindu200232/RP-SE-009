import axios from 'axios';
import fs from 'fs';
import dotenv from 'dotenv';
import promptSkillService from './promptSkillService.js';

dotenv.config();

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-v3.1:671b-cloud';
const SRS_TEMPLATE_PATH = process.env.SRS_TEMPLATE_PATH || 'C:/Users/ravin/Downloads/ieee_srs_training_template.json';

const FIXED_TECH = {
  application_type: 'Web',
  database_type: 'MongoDB',
  performance_target: '< 2 seconds',
  stack: 'MERN (MongoDB, Express, React, Node.js) microservices',
};

const DOMAIN_MAP = {
  'Online Shopping': 'E-Commerce',
  'Health & Medical': 'Healthcare',
  'Learning & Courses': 'Education',
  'Finance & Payments': 'Finance',
  'Tasks & Projects': 'Task Management',
  'Social & Community': 'Social Media',
  'Travel & Bookings': 'Travel',
  'Food & Restaurants': 'Food & Restaurant',
  'HR & Team Management': 'HR & Recruitment',
  'Smart Devices': 'IoT & Smart',
  'Something Else': 'General',
};

const AUTH_MAP = {
  'Email & password (most common)': 'Email & Password',
  'Sign in with Google or Facebook': 'OAuth/Social Login',
  'Email & password + Google login': 'Email & Password + OAuth',
  'Extra security code sent to phone (2FA)': 'Multi-Factor Authentication',
  'No login needed - everyone can see it': 'None (Public Access)',
};

const COMPLIANCE_MAP = {
  'Medical or health records (HIPAA)': 'HIPAA',
  'Credit card / online payments (PCI)': 'PCI-DSS',
  'European users data (GDPR)': 'GDPR',
  'Financial / banking data (SOC 2)': 'SOC 2',
  "No sensitive data - it's a normal app": 'None',
  "I'm not sure yet": 'None',
};

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
  {
    key: 'project_name',
    section: 'basics',
    question: 'What do you want to call your website or app?',
    inputType: 'text',
    placeholder: 'e.g. ShopEasy, HealthHub, LearnSpace, TaskFlow...',
    template_paths: ['metadata.project_name', 'metadata.project_id'],
  },
  {
    key: 'domain',
    section: 'basics',
    question: 'What is your app mainly about? Pick the closest option:',
    inputType: 'select',
    options: Object.keys(DOMAIN_MAP),
    template_paths: ['metadata.domain', 'sections.introduction.product_scope.summary'],
  },
  {
    key: 'target_users',
    section: 'users',
    question: 'Who will use your app? Pick everyone that applies:',
    inputType: 'multiselect',
    options: TARGET_USER_CHOICES,
    template_paths: ['sections.overall_description.user_classes_and_characteristics'],
  },
  {
    key: 'core_features',
    section: 'features',
    question: 'What should people be able to do on your app? Describe it simply - no tech words needed.',
    inputType: 'textarea',
    placeholder: 'e.g. Browse products, add to cart, pay, track orders, get updates, leave reviews...',
    template_paths: ['sections.overall_description.product_functions', 'sections.system_features'],
  },
  {
    key: 'auth_method',
    section: 'accounts',
    question: 'How do you want people to sign in?',
    inputType: 'select',
    options: Object.keys(AUTH_MAP),
    template_paths: ['sections.other_nonfunctional_requirements.security_requirements', 'services'],
  },
  {
    key: 'compliance',
    section: 'privacy',
    question: 'Does your app deal with any sensitive information? Pick all that apply:',
    inputType: 'multiselect',
    options: Object.keys(COMPLIANCE_MAP),
    template_paths: ['sections.other_requirements.legal_requirements', 'sections.other_nonfunctional_requirements.security_requirements'],
  },
  {
    key: 'integrations',
    section: 'integrations',
    question: 'Does your app need to connect to any outside systems or APIs?',
    inputType: 'textarea',
    placeholder: 'e.g. payment gateway, maps, email, SMS, delivery partner, or an existing company database...',
    template_paths: ['sections.external_interface_requirements.software_interfaces', 'services'],
  },
  {
    key: 'reports_and_notifications',
    section: 'operations',
    question: 'What reports, alerts, or notifications should the app send?',
    inputType: 'textarea',
    placeholder: 'e.g. order updates, admin dashboard reports, low stock alerts, appointment reminders...',
    template_paths: ['sections.system_features', 'sections.external_interface_requirements.user_interfaces'],
  },
];

const QUESTION_DEFAULT_MAP = Object.fromEntries(QUESTION_DEFAULTS.map((question) => [question.key, question]));
const QUESTION_INPUT_TYPES = new Set(['text', 'textarea', 'select', 'multiselect']);
const QUESTION_SECTIONS = new Set(['basics', 'users', 'features', 'accounts', 'privacy', 'technical', 'interfaces', 'integrations', 'operations']);

let IEEE_TEMPLATE = null;

function getTemplate() {
  if (!IEEE_TEMPLATE) {
    try {
      IEEE_TEMPLATE = JSON.parse(fs.readFileSync(SRS_TEMPLATE_PATH, 'utf8'));
    } catch {
      IEEE_TEMPLATE = {
        document_type: 'Software Requirements Specification',
        standard: 'IEEE SRS',
      };
    }
  }

  return IEEE_TEMPLATE;
}

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

function normalizeTechnicalValues(info) {
  const normalized = { ...info };

  if (normalized.domain && DOMAIN_MAP[normalized.domain]) {
    normalized.domain = DOMAIN_MAP[normalized.domain];
  }

  if (normalized.auth_method && AUTH_MAP[normalized.auth_method]) {
    normalized.auth_method = AUTH_MAP[normalized.auth_method];
  }

  if (Array.isArray(normalized.compliance)) {
    normalized.compliance = normalized.compliance
      .map((value) => COMPLIANCE_MAP[value] || value)
      .filter((value) => value !== 'None');

    if (!normalized.compliance.length) {
      normalized.compliance = ['None'];
    }
  }

  if (Array.isArray(normalized.target_users)) {
    normalized.target_users = normalized.target_users.map((value) => value.split(' / ')[0].split(' (')[0]);
  }

  return normalized;
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
    : Array.isArray(fallback?.template_paths)
      ? fallback.template_paths.map((value) => String(value)).filter(Boolean)
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
    order: index + 1,
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

class DeepSeekEnhancedService {
  getTemplateSummary(limit = 5000) {
    return getTemplateExcerpt(limit);
  }

  async analyzeGaps(projectDescription, fewShotExamples = [], logFn = () => {}) {
    logFn('DeepSeek: understanding the project and planning questions...', 'info');
    const interviewGuidance = promptSkillService.getInterviewGuidance();

    const examples = fewShotExamples
      .slice(0, 2)
      .map((example) => `Example (${example.domain}): ${example.training_text}`)
      .join('\n\n');

    const prompt = `You are planning a requirements interview for a non-technical user.

PROJECT DESCRIPTION:
${projectDescription}

${examples ? `SIMILAR PROJECTS FOR CONTEXT:\n${examples}\n` : ''}

IEEE SRS TEMPLATE OUTLINE:
${this.getTemplateSummary(4500)}

INTERVIEW SKILL GUIDANCE:
${interviewGuidance || 'Ask minimal, friendly, business-focused questions tied to missing IEEE sections.'}

SUPPORTED QUESTION SHAPES:
- key: short snake_case identifier
- section: one of basics, users, features, accounts, privacy, technical, interfaces, integrations, operations
- inputType: one of text, textarea, select, multiselect

USE THESE FRIENDLY CHOICE LISTS WHEN THEY FIT:
- domain options: ${Object.keys(DOMAIN_MAP).join(' | ')}
- auth_method options: ${Object.keys(AUTH_MAP).join(' | ')}
- compliance options: ${Object.keys(COMPLIANCE_MAP).join(' | ')}
- target_users options: ${TARGET_USER_CHOICES.join(' | ')}

TASK:
1. Extract what is already clearly known.
2. Write a short friendly summary.
3. Generate the minimum ordered list of questions still needed to fill important missing IEEE template parts.
4. Keep the questions simple, specific, and business-friendly.
5. Do not ask about stack or database unless the prompt explicitly conflicts; this app defaults to a MERN web app.
6. Ask at most 8 questions.
7. Every question must include the IEEE template_paths it helps fill.
8. Make the interview feel like a human analyst guiding a real client.

RESPOND WITH ONLY VALID JSON:
{
  "known": {
    "project_name": "<value or null>",
    "domain": "<value or null>",
    "target_users": ["<user>"] or null,
    "core_features": "<value or null>",
    "auth_method": "<value or null>",
    "compliance": ["<value>"],
    "integrations": "<value or null>",
    "reports_and_notifications": "<value or null>"
  },
  "summary": "<friendly 1-2 sentence summary>",
  "questions": [
    {
      "key": "project_name",
      "section": "basics",
      "question": "What do you want to call your website or app?",
      "inputType": "text",
      "placeholder": "Optional placeholder",
      "options": [],
      "template_paths": ["metadata.project_name"],
      "importance": "high"
    }
  ]
}`;

    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: DEEPSEEK_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You are an IEEE SRS requirements analyst. Extract only grounded facts, then ask the smallest useful set of missing questions. Respond ONLY with valid JSON.',
          },
          { role: 'user', content: prompt },
        ],
        stream: false,
        options: { temperature: 0.1, num_predict: 2600 },
      }, { timeout: 300000 });

      const content = stripJsonFence(response.data?.message?.content || '{}');
      const start = content.indexOf('{');
      const end = content.lastIndexOf('}') + 1;
      const parsed = JSON.parse(content.slice(start, end));

      return {
        known: normalizeKnownFields(parsed.known || {}),
        summary: parsed.summary || projectDescription.slice(0, 200),
        questions: dedupeQuestions(parsed.questions || []),
      };
    } catch (error) {
      logFn(`Question planning fell back to defaults: ${error.message}`, 'warning');
      return {
        known: {},
        summary: projectDescription.slice(0, 200),
        questions: this.getUnansweredQuestions({}, QUESTION_DEFAULTS),
      };
    }
  }

  getUnansweredQuestions(knownInfo, generatedQuestions = []) {
    const questions = dedupeQuestions(generatedQuestions.length ? generatedQuestions : QUESTION_DEFAULTS);

    return questions.filter((question) => {
      const value = knownInfo[question.key];
      if (value === undefined || value === null) {
        return true;
      }
      if (typeof value === 'string' && !value.trim()) {
        return true;
      }
      if (Array.isArray(value) && value.length === 0) {
        return true;
      }
      return false;
    });
  }

  async generateSRS(projectDescription, collectedInfo, fewShotExamples = [], logFn = () => {}, onToken = null) {
    logFn('DeepSeek: generating the IEEE SRS JSON...', 'info');
    const writerGuidance = promptSkillService.getWriterGuidance();

    const examples = fewShotExamples
      .slice(0, 2)
      .map((example) => `Example (${example.domain}): ${example.training_text}`)
      .join('\n\n');

    const info = normalizeTechnicalValues({
      ...FIXED_TECH,
      ...collectedInfo,
    });

    const complianceStr = Array.isArray(info.compliance)
      ? info.compliance.filter((value) => value !== 'None').join(', ') || 'None'
      : info.compliance || 'None';

    const prompt = `You are an expert IEEE SRS document generator. Produce a COMPLETE machine-readable IEEE SRS JSON.

PROJECT DESCRIPTION:
${projectDescription}

COLLECTED INFORMATION:
- Project Name: ${info.project_name || 'My Application'}
- Domain / Industry: ${info.domain || 'General'}
- Application Type: Web application
- Target Users: ${Array.isArray(info.target_users) ? info.target_users.join(', ') : info.target_users || 'General users'}
- Core Features: ${info.core_features || 'To be defined'}
- Authentication: ${info.auth_method || 'Email & Password'}
- Integrations: ${info.integrations || 'None specified'}
- Reports / Notifications: ${info.reports_and_notifications || 'None specified'}
- Database: MongoDB
- Backend: Node.js + Express microservices
- Frontend: React
- Compliance / Privacy: ${complianceStr}
- Performance Target: < 2 seconds response time

${examples ? `REFERENCE EXAMPLES:\n${examples}\n` : ''}

IEEE TEMPLATE OUTLINE:
${this.getTemplateSummary(6000)}

SRS WRITER SKILL GUIDANCE:
${writerGuidance || 'Write a complete, formal, human-readable IEEE SRS with clean section content and no placeholders.'}

STRICT REQUIREMENTS:
1. Include all major IEEE sections: introduction, overall_description, external_interface_requirements, system_features, other_nonfunctional_requirements, other_requirements, appendices.
2. Do not leave placeholders such as <Project Name>, TBD, or empty arrays for major sections.
3. Generate 5 to 8 realistic system_features.
4. Each feature must have feature_id, feature_name, description_and_priority, and at least 2 functional_requirements.
5. Functional requirements must use "The system shall..." wording.
6. Include realistic user classes, interfaces, business rules, constraints, database requirements, legal/privacy requirements, and appendices.
7. revision_history must have at least one item.
8. services[] must be MERN microservices compatible:
   - auth-service must exist at port 3001
   - additional services use kebab-case names
   - endpoints use /api/v1/... paths
   - each service has method, path, description, entities, dependencies
9. Return ONLY the JSON object with no markdown and no commentary.
10. Preserve internal consistency between metadata, sections, services, and appendices.
11. Fill missing details with realistic assumptions based on the project instead of leaving blanks.
12. quality_check must NOT be generated by you; the application will add it later.
`;

    if (onToken) {
      return this._streamGenerate(prompt, info, onToken);
    }

    const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
      model: DEEPSEEK_MODEL,
      messages: [
        {
          role: 'system',
          content: 'You are an IEEE SRS expert. Generate complete, professional SRS JSON documents. Respond ONLY with valid JSON.',
        },
        { role: 'user', content: prompt },
      ],
      stream: false,
      options: { temperature: 0.15, num_predict: 8192, repeat_penalty: 1.1 },
    }, { timeout: 600000 });

    return this._parseSRSResponse(response.data?.message?.content || '', info);
  }

  async repairSRS(currentSrs, context = {}, logFn = () => {}) {
    const issues = Array.isArray(context.issues) ? context.issues : [];
    const issueSummary = issues.length
      ? issues.map((issue, index) => `${index + 1}. ${issue.path} -> ${issue.message}`).join('\n')
      : 'General completeness repair';
    const writerGuidance = promptSkillService.getWriterGuidance();

    logFn('DeepSeek: repairing missing or empty SRS sections...', 'info');

    const prompt = `You are repairing an IEEE SRS JSON that has missing or placeholder content.

PROJECT DESCRIPTION:
${context.projectDescription || 'Not provided'}

KNOWN INFORMATION:
${JSON.stringify(context.collectedInfo || {}, null, 2)}

TEMPLATE OUTLINE:
${this.getTemplateSummary(6000)}

SRS WRITER SKILL GUIDANCE:
${writerGuidance || 'Preserve good content, repair missing sections, and keep the document formal and export-friendly.'}

ISSUES TO FIX:
${issueSummary}

CURRENT SRS JSON:
${JSON.stringify(currentSrs, null, 2)}

RULES:
1. Keep good existing content whenever it is already consistent.
2. Repair only by returning one COMPLETE corrected JSON object.
3. Fill missing major sections and replace placeholders with realistic content.
4. Keep the document aligned with a MERN web application architecture and keep services[] valid.
5. Do not output markdown or explanations.
`;

    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: DEEPSEEK_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You repair IEEE SRS JSON documents. Preserve valid content, fill missing sections, and respond ONLY with valid JSON.',
          },
          { role: 'user', content: prompt },
        ],
        stream: false,
        options: { temperature: 0.05, num_predict: 8192, repeat_penalty: 1.1 },
      }, { timeout: 600000 });

      return this._parseSRSResponse(response.data?.message?.content || '', context.collectedInfo || {});
    } catch (error) {
      logFn(`SRS repair failed: ${error.message}`, 'warning');
      return currentSrs;
    }
  }

  async _streamGenerate(prompt, collectedInfo, onToken) {
    let fullResponse = '';

    const response = await axios({
      method: 'POST',
      url: `${OLLAMA_URL}/api/chat`,
      data: {
        model: DEEPSEEK_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You are an IEEE SRS expert. Generate complete, professional SRS JSON documents. Respond ONLY with valid JSON.',
          },
          { role: 'user', content: prompt },
        ],
        stream: true,
        options: { temperature: 0.15, num_predict: 8192, repeat_penalty: 1.1 },
      },
      responseType: 'stream',
      timeout: 600000,
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
              onToken?.(token);
            }
            if (parsed.done) {
              resolve(this._parseSRSResponse(fullResponse, collectedInfo));
            }
          } catch {
            continue;
          }
        }
      });

      response.data.on('end', () => {
        resolve(this._parseSRSResponse(fullResponse, collectedInfo));
      });

      response.data.on('error', reject);
    });
  }

  _parseSRSResponse(content, collectedInfo) {
    try {
      const cleaned = stripJsonFence(content);
      const start = cleaned.indexOf('{');
      const end = cleaned.lastIndexOf('}') + 1;
      if (start === -1 || end <= start) {
        throw new Error('No JSON found');
      }

      const srs = JSON.parse(cleaned.slice(start, end));
      if (!srs.document_type) {
        srs.document_type = 'Software Requirements Specification';
      }
      if (!srs.standard) {
        srs.standard = 'IEEE SRS';
      }
      if (!Array.isArray(srs.services) || !srs.services.length) {
        srs.services = this._inferServices(srs, collectedInfo);
      }

      return srs;
    } catch {
      return this._buildFallbackSRS(collectedInfo, content);
    }
  }

  _inferServices(srs, info) {
    const features = srs.sections?.system_features || [];
    const services = [];
    let port = 3001;

    services.push({
      name: 'auth-service',
      description: 'User authentication and authorization',
      port: port++,
      entities: ['User'],
      endpoints: [
        { method: 'POST', path: '/api/v1/auth/register', description: 'Register a new user' },
        { method: 'POST', path: '/api/v1/auth/login', description: 'Authenticate and return a session token' },
        { method: 'GET', path: '/api/v1/auth/profile', description: 'Return the authenticated user profile' },
      ],
      dependencies: [],
    });

    features.slice(0, 4).forEach((feature, index) => {
      const featureName = feature.feature_name || `feature-${index + 1}`;
      const serviceBase = featureName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
      const serviceName = `${serviceBase || 'feature'}-service`;
      services.push({
        name: serviceName,
        description: feature.description_and_priority?.description || featureName,
        port: port++,
        entities: [featureName.split(' ')[0] || 'Record'],
        endpoints: (feature.functional_requirements || []).slice(0, 3).map((requirement, requirementIndex) => ({
          method: requirementIndex === 0 ? 'POST' : 'GET',
          path: `/api/v1/${serviceName.replace(/-service$/, '')}/${(requirement.requirement_id || `req-${requirementIndex + 1}`).toLowerCase()}`,
          description: requirement.title || requirement.description || 'Feature operation',
        })),
        dependencies: ['auth-service'],
      });
    });

    return services;
  }

  _buildFallbackSRS(info, rawContent) {
    const name = info.project_name || 'My Application';
    const today = new Date().toISOString().split('T')[0];

    return {
      document_type: 'Software Requirements Specification',
      standard: 'IEEE SRS',
      metadata: {
        project_name: name,
        project_id: `SRS-${name.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'APP'}`,
        domain: info.domain || 'General',
        application_type: info.application_type || 'Web',
        version: '1.0',
        status: 'draft',
        author: 'AI',
        organization: 'SRS Maker Agent',
        date_created: today,
        last_updated: today,
        language: 'en',
      },
      revision_history: [
        {
          revision_id: 'REV-001',
          name: 'AI',
          date: today,
          reason_for_changes: 'Initial generated draft',
          version: '0.1',
        },
      ],
      sections: {
        introduction: {
          purpose: `This SRS describes the software requirements for ${name}.`,
          product_scope: {
            summary: info.core_features || 'Application features to be refined',
            business_objectives: ['Deliver the main user journey', 'Support reliable day-to-day use'],
            benefits: ['Faster task completion', 'Clearer digital workflow'],
            goals: ['Build a reliable web application', 'Support future growth'],
          },
        },
        overall_description: {
          product_perspective: {
            system_context: `${name} operates as a standalone MERN web application.`,
            product_origin: 'New system',
            related_systems: [],
            context_diagram_reference: '',
          },
          product_functions: [
            {
              function_id: 'PF-001',
              name: 'Core workflow',
              description: info.core_features || `Support the main workflow for ${name}.`,
            },
          ],
          user_classes_and_characteristics: [
            {
              user_class_id: 'UC-001',
              user_class_name: 'Primary user',
              description: 'Main business user of the system.',
              technical_expertise: 'Low',
              security_or_privilege_level: 'Standard',
              education_or_experience: 'Basic digital literacy',
              frequency_of_use: 'Daily',
              importance_rank: 1,
              notes: '',
            },
          ],
        },
        external_interface_requirements: {
          user_interfaces: [],
          hardware_interfaces: [],
          software_interfaces: [],
          communications_interfaces: [],
        },
        system_features: [
          {
            feature_id: 'FEAT-001',
            feature_name: 'User Management',
            description_and_priority: {
              description: 'Core user authentication and management.',
              priority: 'High',
            },
            functional_requirements: [
              {
                requirement_id: 'REQ-001',
                title: 'User registration',
                description: `The system shall allow users to register for ${name}.`,
                priority: 'High',
                status: 'draft',
              },
              {
                requirement_id: 'REQ-002',
                title: 'User sign-in',
                description: 'The system shall authenticate users before protected actions.',
                priority: 'High',
                status: 'draft',
              },
            ],
          },
        ],
        other_nonfunctional_requirements: {
          performance_requirements: [
            {
              requirement_id: 'NFR-PERF-001',
              description: 'The system shall respond within 2 seconds under normal load.',
            },
          ],
          safety_requirements: [],
          security_requirements: [
            {
              requirement_id: 'NFR-SEC-001',
              description: 'The system shall protect user data in transit and at rest.',
            },
          ],
          software_quality_attributes: [
            {
              attribute_id: 'QA-001',
              attribute_name: 'Reliability',
              description: 'The platform should remain available during normal business use.',
            },
          ],
          business_rules: [],
        },
        other_requirements: {
          database_requirements: [],
          internationalization_requirements: [],
          legal_requirements: [],
          reuse_objectives: [],
          additional_requirements: [],
        },
      },
      appendices: {
        glossary: [
          { term: 'SRS', definition: 'Software Requirements Specification' },
          { term: 'NFR', definition: 'Non-functional requirement' },
        ],
        analysis_models: [],
        to_be_determined_list: [],
      },
      services: this._inferServices({}, info),
      _raw_ai_response: rawContent.slice(0, 500),
    };
  }
}

export default new DeepSeekEnhancedService();
