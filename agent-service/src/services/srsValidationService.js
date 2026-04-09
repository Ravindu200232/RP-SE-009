import deepSeekService from './deepSeekEnhancedService.js';

const REQUIRED_CHECKS = [
  { path: 'metadata.project_name', type: 'string' },
  { path: 'metadata.project_id', type: 'string' },
  { path: 'metadata.domain', type: 'string' },
  { path: 'metadata.application_type', type: 'string' },
  { path: 'revision_history', type: 'array', min: 1 },
  { path: 'sections.introduction.purpose', type: 'string' },
  { path: 'sections.introduction.product_scope.summary', type: 'string' },
  { path: 'sections.introduction.product_scope.goals', type: 'array', min: 1 },
  { path: 'sections.overall_description.product_perspective.system_context', type: 'string' },
  { path: 'sections.overall_description.product_perspective.product_origin', type: 'string' },
  { path: 'sections.overall_description.product_functions', type: 'array', min: 1 },
  { path: 'sections.overall_description.user_classes_and_characteristics', type: 'array', min: 1 },
  { path: 'sections.external_interface_requirements.user_interfaces', type: 'array', min: 1 },
  { path: 'sections.external_interface_requirements.software_interfaces', type: 'array', min: 1 },
  { path: 'sections.system_features', type: 'array', min: 3 },
  { path: 'sections.other_nonfunctional_requirements.performance_requirements', type: 'array', min: 1 },
  { path: 'sections.other_nonfunctional_requirements.security_requirements', type: 'array', min: 1 },
  { path: 'sections.other_nonfunctional_requirements.software_quality_attributes', type: 'array', min: 1 },
  { path: 'sections.other_requirements.database_requirements', type: 'array', min: 1 },
  { path: 'sections.other_requirements.legal_requirements', type: 'array', min: 1 },
  { path: 'appendices.glossary', type: 'array', min: 1 },
  { path: 'services', type: 'array', min: 2 },
];

function clone(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function getValueAtPath(root, path) {
  return path
    .replace(/\[(\d+)\]/g, '.$1')
    .split('.')
    .filter(Boolean)
    .reduce((accumulator, key) => (accumulator === undefined || accumulator === null ? undefined : accumulator[key]), root);
}

function isPlaceholderString(value) {
  if (typeof value !== 'string') {
    return false;
  }

  const trimmed = value.trim();
  return /<[^>]+>/.test(trimmed) || /^TBD(?:-\d+)?$/i.test(trimmed) || /^to be defined$/i.test(trimmed);
}

function collectPlaceholderIssues(node, path = 'root', issues = []) {
  if (Array.isArray(node)) {
    node.forEach((value, index) => collectPlaceholderIssues(value, `${path}[${index}]`, issues));
    return issues;
  }

  if (node && typeof node === 'object') {
    Object.entries(node).forEach(([key, value]) => collectPlaceholderIssues(value, `${path}.${key}`, issues));
    return issues;
  }

  if (isPlaceholderString(node)) {
    issues.push({
      path,
      message: 'Placeholder value still present',
      type: 'placeholder',
    });
  }

  return issues;
}

function buildProjectId(projectName = 'APP') {
  const slug = projectName.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return `SRS-${slug || 'APP'}`;
}

function needsText(value) {
  return typeof value !== 'string' || !value.trim() || isPlaceholderString(value);
}

function toSentenceList(value, fallback = []) {
  if (Array.isArray(value)) {
    return value
      .map((entry) => String(entry || '').trim())
      .filter(Boolean);
  }

  if (typeof value !== 'string' || !value.trim()) {
    return [...fallback];
  }

  const separator = value.includes('\n') ? /\r?\n+/ : /[,;]+/;
  const items = value
    .split(separator)
    .map((entry) => entry.replace(/^[-*]\s*/, '').trim())
    .filter(Boolean);

  return items.length ? items : [value.trim()];
}

function titleCase(value = '') {
  return String(value)
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ensureSystemShall(text, fallback) {
  const normalized = String(text || '').trim();
  if (!normalized) {
    return fallback;
  }
  return /^the system shall\b/i.test(normalized)
    ? normalized
    : `The system shall ${normalized.charAt(0).toLowerCase()}${normalized.slice(1)}`;
}

function makeRequirementId(prefix, index) {
  return `${prefix}-${String(index + 1).padStart(3, '0')}`;
}

function normalizeRequirement(requirement = {}, featureName, featureIndex, requirementIndex) {
  const title = String(requirement.title || `${featureName} workflow ${requirementIndex + 1}`).trim();
  return {
    requirement_id: requirement.requirement_id || makeRequirementId(`REQ${featureIndex + 1}`, requirementIndex),
    title,
    description: ensureSystemShall(
      requirement.description || requirement.statement,
      `The system shall support ${featureName.toLowerCase()} for authorized users.`
    ),
    priority: requirement.priority || 'Medium',
    status: requirement.status || 'draft',
  };
}

function buildFeature(featureName, index, projectName) {
  const normalizedName = titleCase(featureName || `Core Feature ${index + 1}`);

  return {
    feature_id: `FEAT-${String(index + 1).padStart(3, '0')}`,
    feature_name: normalizedName,
    description_and_priority: {
      description: `${projectName} shall support ${normalizedName.toLowerCase()} as part of the main business workflow.`,
      priority: index === 0 ? 'High' : 'Medium',
    },
    functional_requirements: [
      normalizeRequirement(
        {
          title: `${normalizedName} submission`,
          description: `allow users to perform ${normalizedName.toLowerCase()} tasks through the web interface`,
          priority: 'High',
        },
        normalizedName,
        index,
        0
      ),
      normalizeRequirement(
        {
          title: `${normalizedName} tracking`,
          description: `record and display ${normalizedName.toLowerCase()} status and history for authorized users`,
          priority: 'Medium',
        },
        normalizedName,
        index,
        1
      ),
    ],
  };
}

function normalizeFeature(feature = {}, index, projectName) {
  const normalizedName = titleCase(feature.feature_name || `Core Feature ${index + 1}`);
  const requirements = Array.isArray(feature.functional_requirements) ? feature.functional_requirements : [];

  return {
    feature_id: feature.feature_id || `FEAT-${String(index + 1).padStart(3, '0')}`,
    feature_name: normalizedName,
    description_and_priority: {
      description: String(feature.description_and_priority?.description || feature.description || `${projectName} shall support ${normalizedName.toLowerCase()}.`).trim(),
      priority: feature.description_and_priority?.priority || feature.priority || (index === 0 ? 'High' : 'Medium'),
    },
    functional_requirements: (requirements.length ? requirements : [{}, {}])
      .slice(0, 6)
      .map((requirement, requirementIndex) => normalizeRequirement(requirement, normalizedName, index, requirementIndex)),
  };
}

function buildUserClass(userClassName, index) {
  const normalizedName = titleCase(userClassName || `User Group ${index + 1}`);
  return {
    user_class_id: `UC-${String(index + 1).padStart(3, '0')}`,
    user_class_name: normalizedName,
    description: `${normalizedName} interacts with the platform to complete business tasks and review outcomes.`,
    technical_expertise: 'Low to Medium',
    security_or_privilege_level: index === 0 ? 'Standard' : 'Role-based',
    education_or_experience: 'Basic digital literacy',
    frequency_of_use: index === 0 ? 'Daily' : 'Weekly',
    importance_rank: index + 1,
    notes: '',
  };
}

function coerceObject(value, fallback = {}) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value;
  }

  return { ...fallback };
}

function ensureNestedObjects(srs) {
  srs.sections = coerceObject(srs.sections);
  srs.sections.introduction = coerceObject(
    srs.sections.introduction,
    typeof srs.sections.introduction === 'string'
      ? { purpose: srs.sections.introduction }
      : {}
  );
  srs.sections.introduction.product_scope = coerceObject(
    srs.sections.introduction.product_scope,
    typeof srs.sections.introduction.product_scope === 'string'
      ? { summary: srs.sections.introduction.product_scope }
      : {}
  );
  srs.sections.overall_description = coerceObject(
    srs.sections.overall_description,
    typeof srs.sections.overall_description === 'string'
      ? { product_perspective: { system_context: srs.sections.overall_description } }
      : {}
  );
  srs.sections.overall_description.product_perspective = coerceObject(
    srs.sections.overall_description.product_perspective,
    typeof srs.sections.overall_description.product_perspective === 'string'
      ? { system_context: srs.sections.overall_description.product_perspective }
      : {}
  );
  srs.sections.external_interface_requirements = coerceObject(srs.sections.external_interface_requirements);
  srs.sections.other_nonfunctional_requirements = coerceObject(srs.sections.other_nonfunctional_requirements);
  srs.sections.other_requirements = coerceObject(srs.sections.other_requirements);
  srs.appendices = coerceObject(srs.appendices);
  return srs;
}

function applyMetadataDefaults(srs, collectedInfo) {
  const today = new Date().toISOString().split('T')[0];
  srs.document_type ||= 'Software Requirements Specification';
  srs.standard ||= 'IEEE SRS';
  srs.metadata ||= {};
  srs.metadata.project_name ||= collectedInfo.project_name || 'My Application';
  srs.metadata.project_id ||= buildProjectId(srs.metadata.project_name);
  srs.metadata.domain ||= collectedInfo.domain || 'General';
  srs.metadata.application_type ||= 'Web';
  srs.metadata.version ||= '1.0';
  srs.metadata.status ||= 'draft';
  srs.metadata.author ||= 'AI';
  srs.metadata.organization ||= 'SRS Maker Agent';
  srs.metadata.date_created ||= today;
  srs.metadata.last_updated ||= today;
  srs.metadata.language ||= 'en';

  if (!Array.isArray(srs.revision_history) || !srs.revision_history.length) {
    srs.revision_history = [
      {
        revision_id: 'REV-001',
        name: srs.metadata.author,
        date: today,
        reason_for_changes: 'Initial generated draft',
        version: '0.1',
      },
    ];
  }

  return srs;
}

function applyHeuristicRepairs(srs, collectedInfo = {}) {
  ensureNestedObjects(srs);

  const projectName = collectedInfo.project_name || srs.metadata?.project_name || 'My Application';
  const targetUsers = toSentenceList(collectedInfo.target_users, ['General User', 'Administrator']);
  const coreFeatures = toSentenceList(collectedInfo.core_features, ['User management', 'Core workflow management', 'Notifications']);
  const integrations = toSentenceList(collectedInfo.integrations, ['REST API integration', 'Email delivery service']);
  const reports = toSentenceList(collectedInfo.reports_and_notifications, ['Email alerts', 'Dashboard summaries']);
  const compliance = toSentenceList(collectedInfo.compliance, ['Standard privacy controls']);

  const introduction = srs.sections.introduction;
  if (needsText(introduction.purpose)) {
    introduction.purpose = `This Software Requirements Specification defines the functional and non-functional requirements for ${projectName}.`;
  }
  if (needsText(introduction.product_scope.summary)) {
    introduction.product_scope.summary = String(collectedInfo.core_features || `${projectName} provides a browser-based workflow for its target users.`).trim();
  }
  if (!Array.isArray(introduction.product_scope.goals) || !introduction.product_scope.goals.length) {
    introduction.product_scope.goals = [
      `Deliver the primary ${projectName} user workflow through a web application.`,
      'Support scalable growth with modular MERN microservices.',
    ];
  }
  if (!Array.isArray(introduction.product_scope.business_objectives) || !introduction.product_scope.business_objectives.length) {
    introduction.product_scope.business_objectives = [
      'Improve operational visibility.',
      'Reduce manual effort in the primary business process.',
    ];
  }
  if (!Array.isArray(introduction.product_scope.benefits) || !introduction.product_scope.benefits.length) {
    introduction.product_scope.benefits = [
      'Faster user task completion.',
      'More reliable tracking and reporting.',
    ];
  }

  const overallDescription = srs.sections.overall_description;
  if (needsText(overallDescription.product_perspective.system_context)) {
    overallDescription.product_perspective.system_context = `${projectName} operates as a MERN web application with a React client, Node.js microservices, and a MongoDB data layer.`;
  }
  if (needsText(overallDescription.product_perspective.product_origin)) {
    overallDescription.product_perspective.product_origin = 'New system';
  }

  if (!Array.isArray(overallDescription.product_functions) || !overallDescription.product_functions.length) {
    overallDescription.product_functions = coreFeatures.slice(0, 5).map((featureName, index) => ({
      function_id: `PF-${String(index + 1).padStart(3, '0')}`,
      name: titleCase(featureName),
      description: `${projectName} shall support ${String(featureName).toLowerCase()} as a core business capability.`,
    }));
  }

  if (!Array.isArray(overallDescription.user_classes_and_characteristics) || !overallDescription.user_classes_and_characteristics.length) {
    overallDescription.user_classes_and_characteristics = targetUsers.slice(0, 4).map((userClassName, index) => buildUserClass(userClassName, index));
  }

  const interfaces = srs.sections.external_interface_requirements;
  if (!Array.isArray(interfaces.user_interfaces) || !interfaces.user_interfaces.length) {
    interfaces.user_interfaces = [
      {
        interface_id: 'UI-001',
        name: 'Responsive web application',
        description: 'A browser-based user interface optimized for desktop and mobile workflows.',
        type: 'Web UI',
      },
      {
        interface_id: 'UI-002',
        name: 'Administrative dashboard',
        description: 'A management interface for reporting, approvals, and operational monitoring.',
        type: 'Dashboard',
      },
    ];
  }
  if (!Array.isArray(interfaces.software_interfaces) || !interfaces.software_interfaces.length) {
    interfaces.software_interfaces = integrations.slice(0, 3).map((integrationName, index) => ({
      interface_id: `SI-${String(index + 1).padStart(3, '0')}`,
      name: titleCase(integrationName),
      description: `${projectName} exchanges data with ${integrationName.toLowerCase()} using secure service interfaces.`,
    }));
  }
  if (!Array.isArray(interfaces.communications_interfaces) || !interfaces.communications_interfaces.length) {
    interfaces.communications_interfaces = [
      {
        interface_id: 'CI-001',
        protocol: 'HTTPS',
        description: 'All client-to-service and service-to-service communication shall use encrypted HTTPS connections.',
      },
    ];
  }
  if (!Array.isArray(interfaces.hardware_interfaces)) {
    interfaces.hardware_interfaces = [];
  }

  const existingFeatures = Array.isArray(srs.sections.system_features) ? srs.sections.system_features : [];
  const normalizedFeatures = existingFeatures.map((feature, index) => normalizeFeature(feature, index, projectName));
  const desiredFeatureNames = [...new Set([...normalizedFeatures.map((feature) => feature.feature_name), ...coreFeatures.map((feature) => titleCase(feature))])];
  while (normalizedFeatures.length < 3) {
    const featureName = desiredFeatureNames[normalizedFeatures.length] || `Core Feature ${normalizedFeatures.length + 1}`;
    normalizedFeatures.push(buildFeature(featureName, normalizedFeatures.length, projectName));
  }
  srs.sections.system_features = normalizedFeatures.slice(0, 8);

  const nfr = srs.sections.other_nonfunctional_requirements;
  if (!Array.isArray(nfr.performance_requirements) || !nfr.performance_requirements.length) {
    nfr.performance_requirements = [
      {
        requirement_id: 'NFR-PERF-001',
        description: `The system shall respond to common ${projectName.toLowerCase()} requests within 2 seconds under normal load.`,
      },
    ];
  }
  if (!Array.isArray(nfr.security_requirements) || !nfr.security_requirements.length) {
    nfr.security_requirements = [
      {
        requirement_id: 'NFR-SEC-001',
        description: 'The system shall enforce authentication, authorization, and audit logging for protected operations.',
      },
    ];
  }
  if (!Array.isArray(nfr.software_quality_attributes) || !nfr.software_quality_attributes.length) {
    nfr.software_quality_attributes = [
      {
        attribute_id: 'QA-001',
        attribute_name: 'Reliability',
        description: 'The platform shall remain stable during normal daily operation and recover gracefully from failures.',
      },
      {
        attribute_id: 'QA-002',
        attribute_name: 'Maintainability',
        description: 'The solution shall use modular services and documented APIs so teams can safely enhance it over time.',
      },
    ];
  }
  if (!Array.isArray(nfr.business_rules) || !nfr.business_rules.length) {
    nfr.business_rules = reports.slice(0, 2).map((reportName, index) => ({
      rule_id: `BR-${String(index + 1).padStart(3, '0')}`,
      description: `${projectName} shall generate ${reportName.toLowerCase()} according to the configured business workflow.`,
    }));
  }
  if (!Array.isArray(nfr.safety_requirements)) {
    nfr.safety_requirements = [];
  }

  const otherRequirements = srs.sections.other_requirements;
  if (!Array.isArray(otherRequirements.database_requirements) || !otherRequirements.database_requirements.length) {
    otherRequirements.database_requirements = [
      {
        requirement_id: 'DB-001',
        description: 'The system shall persist operational, audit, and user data in MongoDB collections with timestamps and role-based access controls.',
      },
    ];
  }
  if (!Array.isArray(otherRequirements.legal_requirements) || !otherRequirements.legal_requirements.length) {
    otherRequirements.legal_requirements = compliance.slice(0, 3).map((ruleName, index) => ({
      requirement_id: `LEG-${String(index + 1).padStart(3, '0')}`,
      description: `${projectName} shall support ${ruleName} obligations through privacy, retention, and access-control policies.`,
    }));
  }
  if (!Array.isArray(otherRequirements.additional_requirements) || !otherRequirements.additional_requirements.length) {
    otherRequirements.additional_requirements = [
      {
        requirement_id: 'ADD-001',
        description: 'The delivered solution shall include deployment, API, and operational support documentation.',
      },
    ];
  }
  if (!Array.isArray(otherRequirements.internationalization_requirements)) {
    otherRequirements.internationalization_requirements = [];
  }
  if (!Array.isArray(otherRequirements.reuse_objectives)) {
    otherRequirements.reuse_objectives = [];
  }

  if (!Array.isArray(srs.appendices.glossary) || !srs.appendices.glossary.length) {
    srs.appendices.glossary = [
      { term: 'SRS', definition: 'Software Requirements Specification' },
      { term: 'MERN', definition: 'MongoDB, Express, React, and Node.js architecture' },
    ];
  }
  if (!Array.isArray(srs.appendices.analysis_models)) {
    srs.appendices.analysis_models = [];
  }
  if (!Array.isArray(srs.appendices.to_be_determined_list)) {
    srs.appendices.to_be_determined_list = [];
  }

  if (!Array.isArray(srs.services) || srs.services.length < 2) {
    const inferredServices = typeof deepSeekService._inferServices === 'function'
      ? deepSeekService._inferServices(srs, collectedInfo)
      : [];
    if (Array.isArray(inferredServices) && inferredServices.length) {
      srs.services = inferredServices;
    }
  }

  return srs;
}

function validateSrs(srs) {
  const issues = [];

  for (const check of REQUIRED_CHECKS) {
    const value = getValueAtPath(srs, check.path);

    if (check.type === 'string') {
      if (typeof value !== 'string' || !value.trim()) {
        issues.push({ path: check.path, message: 'Required text is missing', type: 'missing' });
      }
      continue;
    }

    if (check.type === 'array') {
      if (!Array.isArray(value) || value.length < (check.min || 0)) {
        issues.push({ path: check.path, message: `Expected at least ${check.min || 0} item(s)`, type: 'missing' });
      }
    }
  }

  const placeholderIssues = collectPlaceholderIssues(srs);
  const allIssues = [...issues, ...placeholderIssues];
  const passedChecks = Math.max(REQUIRED_CHECKS.length - issues.length, 0);
  const completenessScore = Number((passedChecks / REQUIRED_CHECKS.length).toFixed(2));

  return {
    issues: allIssues,
    completenessScore,
    isPass: !issues.length && !placeholderIssues.length,
  };
}

class SrsValidationService {
  async validateAndRepair({ srs, projectDescription, collectedInfo, sessionId, logFn = () => {} }) {
    let working = applyHeuristicRepairs(applyMetadataDefaults(clone(srs), collectedInfo), collectedInfo);
    let report = validateSrs(working);
    let repairAttempted = false;

    if (!report.isPass) {
      repairAttempted = true;
      logFn('Rechecking generated SRS against the IEEE template...', 'info');
      working = applyHeuristicRepairs(applyMetadataDefaults(await deepSeekService.repairSRS(working, {
        issues: report.issues,
        projectDescription,
        collectedInfo,
      }, logFn), collectedInfo), collectedInfo);
      report = validateSrs(working);
    }

    if (!report.isPass) {
      logFn('Applying local fallback repairs to remaining empty SRS sections...', 'warning');
      working = applyHeuristicRepairs(working, collectedInfo);
      report = validateSrs(working);
    }

    working.quality_check = {
      session_id: sessionId,
      checked_at: new Date().toISOString(),
      template_source: deepSeekService.getTemplateSummary(200),
      repair_attempted: repairAttempted,
      status: report.isPass ? (repairAttempted ? 'repaired' : 'passed') : 'warning',
      completeness_score: report.completenessScore,
      issue_count: report.issues.length,
      issues: report.issues,
      pdf_ready: report.isPass,
      json_ready: report.isPass,
    };

    return {
      srs: working,
      report: working.quality_check,
    };
  }
}

export default new SrsValidationService();
