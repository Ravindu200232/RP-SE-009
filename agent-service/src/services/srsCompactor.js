/**
 * SRSCompactor — Codex-style automatic context compaction for SRS documents.
 *
 * Problem: Large IEEE SRS JSON documents (5,000–20,000 chars) sent raw to Ollama
 * overwhelm the 671B model context window → 10-minute timeouts.
 *
 * Solution (3-layer):
 *  Layer 1 — DIRECT EXTRACTION: If SRS already has services[] with endpoints defined,
 *             build the plan schema directly (NO AI needed → 0ms, no timeout possible).
 *  Layer 2 — COMPACT TEXT: Reduce verbose JSON to ~600 char summary for AI.
 *  Layer 3 — ULTRA-COMPACT: If still timing out, send only service names + route counts.
 *
 * Codex context compaction analogy:
 *  - Like Codex auto-summarising old context turns, we summarise the SRS
 *  - Only the "diff" (what AI actually needs) is kept
 *  - Structured info (services, routes, models) is extracted losslessly
 */

const PORT_START = 3001;

class SRSCompactor {
  /**
   * Main entry point.
   * @param {object|string} srs - Raw SRS (JSON object or string)
   * @returns {{ compact: string, canSkipAI: boolean, directPlan: object|null, tokenEstimate: number }}
   */
  compact(srs) {
    // Normalise to object
    if (typeof srs === 'string') {
      try { srs = JSON.parse(srs); } catch {
        // Plain text SRS — truncate to 2000 chars
        return { compact: srs.slice(0, 2000), canSkipAI: false, directPlan: null, tokenEstimate: 500 };
      }
    }

    // ── Layer 1: Can we skip AI entirely? ────────────────────────────────
    if (this._hasFullServiceDefinitions(srs)) {
      const directPlan = this._buildDirectPlan(srs);
      const compact = this._toCompactText(srs);
      return { compact, canSkipAI: true, directPlan, tokenEstimate: Math.ceil(compact.length / 4) };
    }

    // ── Layer 2: Compact text (send to AI with short prompt) ─────────────
    const compact = this._toCompactText(srs);
    return { compact, canSkipAI: false, directPlan: null, tokenEstimate: Math.ceil(compact.length / 4) };
  }

  /**
   * Even shorter version for timeout retry.
   * Just service names + route counts → ~150 chars.
   */
  ultraCompact(srs) {
    if (typeof srs === 'string') {
      try { srs = JSON.parse(srs); } catch { return srs.slice(0, 500); }
    }

    const name = srs.metadata?.project_name || srs.projectName || 'MyApp';
    const domain = srs.metadata?.domain || '';

    if (srs.services?.length) {
      const svcList = srs.services.map((s, i) =>
        `${this._toKebab(s.name)} port:${PORT_START + i} routes:${(s.endpoints || s.routes || []).length}`
      ).join(', ');
      return `Project: ${name} (${domain})\nServices: ${svcList}`;
    }

    const features = (srs.sections?.system_features || [])
      .map(f => f.feature_name).join(', ');
    return `Project: ${name} (${domain})\nFeatures: ${features}`;
  }

  // ── Layer 1 helpers ──────────────────────────────────────────────────────

  /**
   * Check if the SRS already has complete service+endpoint definitions.
   * If yes, we can build the plan directly without any AI call.
   */
  _hasFullServiceDefinitions(srs) {
    return (
      Array.isArray(srs.services) &&
      srs.services.length >= 1 &&
      srs.services.every(s =>
        s.name &&
        (Array.isArray(s.endpoints) || Array.isArray(s.routes)) &&
        (s.endpoints || s.routes).length > 0
      )
    );
  }

  /**
   * Build a complete plan object directly from the SRS services array.
   * Follows the team's ES module template pattern.
   */
  _buildDirectPlan(srs) {
    const meta = srs.metadata || {};
    const projectName = this._toKebab(meta.project_name || srs.projectName || 'myapp');
    const description = srs.sections?.introduction?.purpose ||
                        srs.description ||
                        meta.project_name || projectName;

    const sharedSecret = 'shared_secret_key_change_in_production';
    const mongoUrl = `mongodb://localhost:27017/${projectName}`;

    // Map SRS services → plan services with team conventions
    const services = srs.services.map((svc, i) => {
      const name = this._toKebab(svc.name);        // "Auth Service" → "auth-service"
      const port = PORT_START + i;                  // Always use 3001+ not SRS ports
      const endpoints = svc.endpoints || svc.routes || [];

      // Convert SRS endpoint format → plan route format
      const routes = endpoints.map(ep => ({
        method: ep.method,
        path: this._normaliseApiPath(ep.path, name),
        description: ep.description || ''
      }));

      // Extract entity names for models (will be fleshed out by AI in source gen)
      const entityNames = svc.entities || [];
      const models = entityNames.map(entityName => ({
        name: entityName,
        fields: this._inferFields(entityName, name, srs)
      }));

      // Inter-service calls from dependencies
      const interServiceCalls = (svc.dependencies || [])
        .map(dep => this._toKebab(dep))
        .filter(dep => dep !== name); // don't include self

      const deps = ['express', 'mongoose', 'cors', 'dotenv', 'helmet',
        'express-rate-limit', 'body-parser', 'jsonwebtoken', 'bcryptjs',
        'axios', 'swagger-jsdoc', 'swagger-ui-express'];

      return { name, description: svc.description || '', port, routes, models, dependencies: deps, interServiceCalls };
    });

    // Build frontend pages from SRS features
    const pages = this._inferPages(srs, services);
    const routeGroups = this._inferRouteGroups(pages);

    // Build frontend serviceUrls
    const serviceUrls = services.map(s => {
      const key = s.name.replace(/-service$/, '').replace(/-/g, '_').toUpperCase();
      return `VITE_${key}_SERVICE_URL=http://localhost:${s.port}`;
    });

    return {
      projectName,
      description,
      services,
      frontend: {
        port: 5173,
        pages,
        routeGroups,
        components: ['Header', 'Footer', 'Sidebar'],
        serviceUrls
      },
      gateway: {
        port: 8080,
        routes: services.map(s => ({
          prefix: `/api/v1/${s.name.replace(/-service$/, '')}`,
          target: `http://localhost:${s.port}`,
          service: s.name
        }))
      },
      sharedEnv: { SEKRET_KEY: sharedSecret, MONGO_URL: mongoUrl }
    };
  }

  // ── Layer 2 helper ───────────────────────────────────────────────────────

  /**
   * Convert verbose SRS JSON → compact human-readable text (~600 chars).
   * This is what gets sent to Ollama instead of the full JSON.
   */
  _toCompactText(srs) {
    const meta = srs.metadata || {};
    const name = meta.project_name || srs.projectName || 'Unknown';
    const domain = meta.domain || '';
    const purpose = (srs.sections?.introduction?.purpose || srs.description || '').slice(0, 150);

    let text = `PROJECT: ${name} (${domain})\nPURPOSE: ${purpose}\n\n`;

    // Pre-defined services (already structured)
    if (srs.services?.length) {
      text += 'SERVICES (pre-defined in SRS):\n';
      srs.services.forEach((s, i) => {
        const port = PORT_START + i;
        const endpoints = (s.endpoints || s.routes || [])
          .map(e => `${e.method} ${e.path}`)
          .join(', ');
        text += `  ${i + 1}. ${s.name} → port ${port}: ${endpoints}\n`;
      });
      text += '\n';
    }

    // Features / functional requirements (compact)
    const features = srs.sections?.system_features || [];
    if (features.length) {
      text += 'FEATURES:\n';
      features.slice(0, 8).forEach(f => {
        text += `  - ${f.feature_name}: ${(f.description_and_priority?.description || '').slice(0, 80)}\n`;
      });
      text += '\n';
    }

    // Entities
    const allEntities = (srs.services || []).flatMap(s => s.entities || []);
    if (allEntities.length) {
      text += `ENTITIES: ${[...new Set(allEntities)].join(', ')}\n`;
    }

    // Dependencies
    const deps = (srs.overall_description?.assumptions_and_dependencies?.dependencies || []);
    if (deps.length) {
      text += `EXTERNAL DEPS: ${deps.map(d => d.description).join('; ')}\n`;
    }

    return text.slice(0, 1500); // Hard cap at 1500 chars
  }

  // ── Field inference ──────────────────────────────────────────────────────

  /**
   * Infer sensible default fields for known entity types.
   * The source code generator will add more when it writes the actual model.
   */
  _inferFields(entityName, serviceName, srs) {
    const e = entityName.toLowerCase();

    // Common patterns
    const timestamped = { name: 'timestamps', type: 'Boolean', virtual: true }; // signals {timestamps:true}

    if (e === 'user') return [
      { name: 'firstName', type: 'String', required: true },
      { name: 'lastName', type: 'String', required: true },
      { name: 'email', type: 'String', required: true, unique: true },
      { name: 'passwordHash', type: 'String', required: true },
      { name: 'role', type: 'String', enum: ['student', 'instructor', 'admin'], default: 'student' },
      { name: 'avatar', type: 'String' },
      { name: 'bio', type: 'String' }
    ];

    if (e === 'course') return [
      { name: 'title', type: 'String', required: true },
      { name: 'description', type: 'String' },
      { name: 'price', type: 'Number', default: 0 },
      { name: 'thumbnail', type: 'String' },
      { name: 'instructorId', type: 'String', required: true },
      { name: 'isPublished', type: 'Boolean', default: false },
      { name: 'category', type: 'String' }
    ];

    if (e === 'enrollment') return [
      { name: 'studentId', type: 'String', required: true },
      { name: 'courseId', type: 'String', required: true },
      { name: 'enrolledAt', type: 'Date', default: 'Date.now' },
      { name: 'paymentStatus', type: 'String', enum: ['pending', 'paid', 'free'], default: 'pending' }
    ];

    if (e === 'lesson') return [
      { name: 'courseId', type: 'String', required: true },
      { name: 'title', type: 'String', required: true },
      { name: 'videoUrl', type: 'String' },
      { name: 'order', type: 'Number', default: 0 },
      { name: 'duration', type: 'Number' }
    ];

    if (e === 'lessonprogress' || e === 'progress') return [
      { name: 'studentId', type: 'String', required: true },
      { name: 'lessonId', type: 'String', required: true },
      { name: 'courseId', type: 'String', required: true },
      { name: 'completed', type: 'Boolean', default: false },
      { name: 'completedAt', type: 'Date' }
    ];

    if (e === 'quiz') return [
      { name: 'courseId', type: 'String', required: true },
      { name: 'title', type: 'String', required: true },
      { name: 'questions', type: 'Array' },
      { name: 'passingScore', type: 'Number', default: 70 }
    ];

    if (e === 'quizattempt' || e === 'attempt') return [
      { name: 'quizId', type: 'String', required: true },
      { name: 'studentId', type: 'String', required: true },
      { name: 'answers', type: 'Array' },
      { name: 'score', type: 'Number' },
      { name: 'passed', type: 'Boolean', default: false }
    ];

    if (e === 'order' || e === 'payment') return [
      { name: 'userId', type: 'String', required: true },
      { name: 'items', type: 'Array' },
      { name: 'totalAmount', type: 'Number', required: true },
      { name: 'status', type: 'String', enum: ['pending', 'paid', 'failed'], default: 'pending' },
      { name: 'paymentId', type: 'String' }
    ];

    if (e === 'product' || e === 'item') return [
      { name: 'name', type: 'String', required: true },
      { name: 'description', type: 'String' },
      { name: 'price', type: 'Number', required: true },
      { name: 'stock', type: 'Number', default: 0 },
      { name: 'category', type: 'String' },
      { name: 'imageUrl', type: 'String' }
    ];

    if (e === 'task') return [
      { name: 'title', type: 'String', required: true },
      { name: 'description', type: 'String' },
      { name: 'status', type: 'String', enum: ['todo', 'in-progress', 'done'], default: 'todo' },
      { name: 'userId', type: 'String', required: true },
      { name: 'dueDate', type: 'Date' }
    ];

    // Generic entity fallback
    return [
      { name: 'name', type: 'String', required: true },
      { name: 'description', type: 'String' },
      { name: 'createdBy', type: 'String' },
      { name: 'isActive', type: 'Boolean', default: true }
    ];
  }

  // ── Page inference ───────────────────────────────────────────────────────

  /**
   * Infer frontend pages from SRS features and services.
   * Produces the pages[] array for the plan's frontend section.
   */
  _inferPages(srs, services) {
    const pages = [
      { name: 'Home', route: '/', description: 'Landing / home page', group: 'HomePage' },
      { name: 'Login', route: '/login', description: 'Login form', group: 'HomePage' },
      { name: 'Register', route: '/register', description: 'Registration form', group: 'HomePage' }
    ];

    // Check if there's an auth/user service → always need login/register
    const hasAuth = services.some(s => s.name.includes('auth') || s.name.includes('user'));

    // Infer dashboard pages from features
    const features = srs.sections?.system_features || [];
    const featureNames = features.map(f => (f.feature_name || '').toLowerCase());

    // Check what kind of dashboard pages are needed
    const hasCourses = featureNames.some(f => f.includes('course') || f.includes('learn'));
    const hasAdmin = featureNames.some(f => f.includes('admin') || f.includes('manage'));
    const hasInstructor = featureNames.some(f => f.includes('instructor') || f.includes('teach'));
    const hasQuiz = featureNames.some(f => f.includes('quiz') || f.includes('assess'));
    const hasEnroll = featureNames.some(f => f.includes('enroll'));
    const hasTask = featureNames.some(f => f.includes('task'));
    const hasOrder = featureNames.some(f => f.includes('order') || f.includes('payment'));

    // Dashboard pages per domain
    if (hasCourses) {
      pages.push({ name: 'Courses', route: '/courses', description: 'Browse all courses', group: 'HomePage' });
      pages.push({ name: 'CourseDetail', route: '/courses/:id', description: 'Course detail and enrollment', group: 'HomePage' });
      pages.push({ name: 'MyLearning', route: '/my-learning', description: 'Enrolled courses for student', group: 'StudentPage' });
    }

    if (hasInstructor || hasCourses) {
      pages.push({ name: 'InstructorDashboard', route: '/instructor/dashboard', description: 'Instructor dashboard', group: 'InstructorPage' });
      pages.push({ name: 'CreateCourse', route: '/instructor/courses/create', description: 'Create new course', group: 'InstructorPage' });
      if (hasCourses) pages.push({ name: 'ManageCourses', route: '/instructor/courses', description: 'Manage my courses', group: 'InstructorPage' });
      if (hasQuiz) pages.push({ name: 'CreateQuiz', route: '/instructor/quiz/create', description: 'Create quiz', group: 'InstructorPage' });
    }

    if (hasAdmin || hasTask) {
      pages.push({ name: 'AdminDashboard', route: '/admin/dashboard', description: 'Admin dashboard', group: 'AdminPage' });
    }

    if (hasTask) {
      pages.push({ name: 'Tasks', route: '/tasks', description: 'My tasks list', group: 'AdminPage' });
    }

    if (hasOrder) {
      pages.push({ name: 'Orders', route: '/orders', description: 'My orders', group: 'AdminPage' });
    }

    return pages;
  }

  _inferRouteGroups(pages) {
    const groups = [...new Set(pages.map(p => p.group))];
    // Always ensure HomePage is first
    return ['HomePage', ...groups.filter(g => g !== 'HomePage')];
  }

  // ── Utilities ────────────────────────────────────────────────────────────

  _toKebab(name) {
    return name
      .toLowerCase()
      .replace(/\s+service$/i, '-service')
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '');
  }

  /**
   * Normalise SRS API path to team convention /api/v1/{resource}/...
   * SRS might use /api/auth/register → normalise to /api/v1/auth/register
   */
  _normaliseApiPath(path, serviceName) {
    if (!path) return '/';

    // Already in v1 format
    if (path.includes('/api/v1/')) return path;

    // Has /api/ prefix but no v1
    if (path.startsWith('/api/')) {
      return path.replace('/api/', '/api/v1/');
    }

    // No /api prefix at all — add service resource prefix
    const resource = serviceName.replace(/-service$/, '');
    return `/api/v1/${resource}${path}`;
  }
}

module.exports = new SRSCompactor();
