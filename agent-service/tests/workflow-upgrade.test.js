const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs-extra');
const os = require('os');
const path = require('path');

const dependencyClassifier = require('../src/services/dependencyClassifier');
const artifactValidator = require('../src/services/artifactValidator');
const contextCompactor = require('../src/services/contextCompactor');
const memoryStore = require('../src/services/memoryStore');
const DeveloperAgent = require('../src/services/developerAgent');
const WorkflowDeveloperService = require('../src/services/workflowDeveloperService');
const workflowSessionStore = require('../src/services/workflowSessionStore');

test('dependencyClassifier keeps internal services out of npm dependencies', () => {
  const plan = dependencyClassifier.classifyPlan({
    projectName: 'TaskFlow',
    services: [
      {
        name: 'user-service',
        port: 3001,
        entities: ['User'],
        routes: [{ method: 'GET', path: '/api/v1/users' }]
      },
      {
        name: 'task-service',
        port: 3002,
        entities: ['Task'],
        routes: [{ method: 'GET', path: '/api/v1/tasks' }],
        dependencies: ['express', 'user-service', 'axios'],
        packageDependencies: ['mongoose'],
        devDependencies: ['nodemon']
      }
    ],
    frontend: {}
  });

  const taskService = plan.services.find((service) => service.name === 'task-service');

  assert.deepEqual(taskService.packageDependencies.sort(), ['axios', 'express', 'mongoose']);
  assert.deepEqual(taskService.serviceDependencies, ['user-service']);
  assert.ok(taskService.envVars.includes('USER_SERVICE_URL'));
  assert.equal(taskService.packageDependencies.includes('user-service'), false);
  assert.ok(plan.frontend.serviceUrls.includes('VITE_USER_SERVICE_URL=http://localhost:3001'));
  assert.ok(plan.frontend.serviceUrls.includes('VITE_TASK_SERVICE_URL=http://localhost:3002'));
});

test('dependencyClassifier normalizes core required files from planner data', () => {
  const plan = dependencyClassifier.classifyPlan({
    projectName: 'AuthFlow',
    services: [
      {
        name: 'auth-service',
        port: 3001,
        entities: ['User'],
        routes: [
          { method: 'POST', path: '/api/v1/auth/login' },
          { method: 'POST', path: '/api/v1/auth/register' }
        ],
        requiredFiles: [
          'package.json',
          'Server.js',
          'DbConnection.js',
          '.env.example',
          'controllers/userController.js',
          'models/user.model.js',
          'services/user.service.js'
        ]
      }
    ]
  });

  const authService = plan.services[0];

  assert.ok(authService.requiredFiles.includes('models/user.model.js'));
  assert.ok(authService.requiredFiles.includes('services/user.service.js'));
  assert.ok(authService.requiredFiles.includes('controllers/auth.controller.js'));
  assert.equal(authService.requiredFiles.includes('controllers/userController.js'), false);
});

test('artifactValidator reports missing model, middleware, controller, and unresolved imports', () => {
  const service = {
    name: 'task-service',
    entities: ['Task'],
    requiredFiles: [
      'package.json',
      'Server.js',
      '.env.example',
      'models/task.model.js',
      'controllers/task.controller.js',
      'routes/tasks.routes.js'
    ]
  };

  const files = [
    {
      path: 'task-service/Server.js',
      content: `
        import express from "express";
        import taskRouter from "./routes/tasks.routes.js";
        const app = express();
        app.use("/api/v1/tasks", taskRouter);
      `,
      service: 'task-service'
    },
    {
      path: 'task-service/routes/tasks.routes.js',
      content: `
        import express from "express";
        import { getTasks } from "../controllers/task.controller.js";
        const router = express.Router();
        router.get("/", getTasks);
        export default router;
      `,
      service: 'task-service'
    },
    {
      path: 'task-service/.env.example',
      content: 'PORT=3002\nMONGO_URL=mongodb://localhost:27017/taskflow\nSEKRET_KEY=secret',
      service: 'task-service'
    }
  ];

  const result = artifactValidator.validateService(service, files, {
    dependencies: {
      express: '^4.18.2',
      'user-service': '^1.0.0'
    }
  });

  const codes = result.issues.map((issue) => issue.code);

  assert.equal(result.ok, false);
  assert.ok(codes.includes('missing-required-files'));
  assert.ok(codes.includes('missing-model-file'));
  assert.ok(codes.includes('missing-json-middleware'));
  assert.ok(codes.includes('internal-service-in-package-json'));
  assert.ok(codes.includes('unresolved-import'));
});

test('artifactValidator accepts common file naming variants for generated artifacts', () => {
  const service = {
    name: 'auth-service',
    entities: ['User'],
    requiredFiles: [
      'package.json',
      'Server.js',
      '.env.example',
      'models/user.model.js',
      'services/user.service.js',
      'controllers/auth.controller.js',
      'routes/auth.routes.js'
    ]
  };

  const files = [
    {
      path: 'auth-service/package.json',
      content: JSON.stringify({ name: 'auth-service', dependencies: { express: '^4.18.2' } }, null, 2),
      service: 'auth-service'
    },
    {
      path: 'auth-service/Server.js',
      content: `
        import express from "express";
        import bodyParser from "body-parser";
        import authRouter from "./routes/authRoutes.js";
        const app = express();
        app.use(bodyParser.json());
        app.use("/api/v1/auth", authRouter);
      `,
      service: 'auth-service'
    },
    {
      path: 'auth-service/.env.example',
      content: 'PORT=3001\nMONGO_URL=mongodb://localhost:27017/auth\nSEKRET_KEY=secret',
      service: 'auth-service'
    },
    {
      path: 'auth-service/models/User.js',
      content: `
        import mongoose from "mongoose";
        const schema = new mongoose.Schema({ email: String });
        export default mongoose.model("User", schema);
      `,
      service: 'auth-service'
    },
    {
      path: 'auth-service/services/userService.js',
      content: 'export async function createUser() { return null; }',
      service: 'auth-service'
    },
    {
      path: 'auth-service/controllers/authController.js',
      content: `
        export async function login(req, res) { return res.json({ ok: true }); }
        export async function register(req, res) { return res.json({ ok: true }); }
      `,
      service: 'auth-service'
    },
    {
      path: 'auth-service/routes/authRoutes.js',
      content: `
        import express from "express";
        import { login, register } from "../controllers/authController.js";
        const router = express.Router();
        router.post("/login", login);
        router.post("/register", register);
        export default router;
      `,
      service: 'auth-service'
    }
  ];

  const result = artifactValidator.validateService(service, files, {
    dependencies: { express: '^4.18.2' }
  });

  assert.equal(result.audit.missingFiles.length, 0);
  assert.equal(result.ok, true);
});

test('artifactValidator resolves local imports case-insensitively for generated files', () => {
  const service = {
    name: 'auth-service',
    entities: ['User'],
    requiredFiles: [
      'package.json',
      'Server.js',
      '.env.example',
      'models/user.model.js',
      'services/user.service.js'
    ]
  };

  const files = [
    {
      path: 'auth-service/package.json',
      content: JSON.stringify({ name: 'auth-service' }, null, 2),
      service: 'auth-service'
    },
    {
      path: 'auth-service/Server.js',
      content: 'import express from "express"; const app = express(); app.use(express.json());',
      service: 'auth-service'
    },
    {
      path: 'auth-service/.env.example',
      content: 'PORT=3001\nMONGO_URL=mongodb://localhost:27017/auth\nSEKRET_KEY=secret',
      service: 'auth-service'
    },
    {
      path: 'auth-service/models/User.js',
      content: 'export default {};',
      service: 'auth-service'
    },
    {
      path: 'auth-service/models/user.model.js',
      content: 'export { default } from "./User.js";',
      service: 'auth-service'
    },
    {
      path: 'auth-service/services/user.service.js',
      content: 'import User from "../models/user.js"; export async function listUsers() { return User.find(); }',
      service: 'auth-service'
    }
  ];

  const result = artifactValidator.validateService(service, files, {
    dependencies: { express: '^4.18.2' }
  });

  assert.equal(result.ok, true);
  assert.equal(result.issues.some((issue) => issue.code === 'unresolved-import'), false);
});

test('workflowDeveloperService synthesizes config env module for unresolved imports', () => {
  const developer = new WorkflowDeveloperService({}, { to: () => ({ emit: () => {} }) });
  const service = {
    name: 'dashboard-service',
    port: 3006,
    entities: ['DashboardStat'],
    envVars: ['PORT', 'MONGO_URL', 'SEKRET_KEY'],
    routes: [{ method: 'GET', path: '/api/v1/dashboard/stats' }]
  };
  const plan = {
    projectName: 'TaskFlow',
    sharedEnv: {
      MONGO_URL: 'mongodb://localhost:27017/taskflow',
      SEKRET_KEY: 'secret'
    }
  };
  const files = [
    {
      path: 'controllers/dashboard.controller.js',
      content: 'import env from "../config/env"; export function getDashboard(req, res) { return res.json(env); }',
      service: 'dashboard-service'
    }
  ];
  const validation = {
    audit: { missingFiles: [] },
    issues: [
      {
        code: 'unresolved-import',
        message: 'Import "../config/env" in controllers/dashboard.controller.js does not resolve to a generated file.'
      }
    ]
  };

  const repairs = developer.buildRepairArtifacts(service, plan, files, validation);

  assert.equal(repairs.some((file) => file.path === 'config/env.js'), true);
  assert.match(repairs.find((file) => file.path === 'config/env.js').content, /dotenv\.config\(\)/);
});

test('workflowDeveloperService synthesizes missing canonical model files from entity names', () => {
  const developer = new WorkflowDeveloperService({}, { to: () => ({ emit: () => {} }) });
  const service = {
    name: 'task-service',
    entities: ['Task'],
    requiredFiles: ['models/task.model.js']
  };
  const validation = {
    audit: { missingFiles: ['models/task.model.js'] },
    issues: [{ code: 'missing-model-file', message: 'Entity-bearing services must generate at least one model file.' }]
  };

  const repairs = developer.buildRepairArtifacts(service, { projectName: 'TaskFlow' }, [], validation);
  const modelFile = repairs.find((file) => file.path === 'models/task.model.js');

  assert.ok(modelFile);
  assert.match(modelFile.content, /mongoose\.Schema/);
  assert.match(modelFile.content, /model\("Task"/);
});

test('contextCompactor builds compact workflow summaries for planner and developer prompts', () => {
  const compacted = contextCompactor.build({
    workspace: { name: 'TaskFlow' },
    thread: { title: 'Create task service' },
    task: 'Create task-service with CRUD',
    instructions: {
      mergedText: '# Rules\n- Use Route -> Controller -> Service -> Model\n- Never install internal services with npm\n'
    },
    memory: {
      files: {
        'PROJECT_STATE.md': '# PROJECT_STATE\nTask app with auth and tasks'
      },
      parsed: {
        'SERVICE_MAP.json': {
          'task-service': {
            port: 3002,
            entities: ['Task'],
            routes: [{ method: 'GET', path: '/api/v1/tasks' }],
            serviceDependencies: ['user-service']
          }
        },
        'FAILURE_PATTERNS.json': [
          { code: 'unresolved-import', message: 'Import "../models/task.js" failed', service: 'task-service' }
        ]
      }
    },
    index: {
      services: {
        'task-service': { fileCount: 4, kinds: { model: 1, route: 1, controller: 1, service: 1 } }
      }
    }
  });

  assert.match(compacted.plannerPrompt, /Route -> Controller -> Service -> Model/);
  assert.match(compacted.developerPrompt, /task-service: port 3002/);
  assert.match(compacted.repairPrompt, /unresolved-import/);
  assert.equal(compacted.stats.hasFailures, true);
});

test('workflowSessionStore persists stageful session state in AI_MEMORY', async (t) => {
  const workspaceDir = await fs.mkdtemp(path.join(os.tmpdir(), 'agent2-session-'));
  t.after(async () => {
    await fs.remove(workspaceDir);
  });

  const first = await workflowSessionStore.update(workspaceDir, {
    status: 'running',
    currentStage: 'planning',
    currentAgent: 'Planner',
    task: 'Create task-service',
    workspaceId: 'w1',
    threadId: 't1',
    targetServices: ['task-service'],
    attempts: { 'task-service': 1 }
  });

  const second = await workflowSessionStore.update(workspaceDir, {
    currentStage: 'generation',
    currentAgent: 'Developer',
    currentService: 'task-service',
    attempts: { 'task-service': 2 }
  });

  assert.equal(first.currentStage, 'planning');
  assert.equal(second.currentStage, 'generation');
  assert.equal(second.currentService, 'task-service');
  assert.equal(second.attempts['task-service'], 2);

  const saved = await workflowSessionStore.read(workspaceDir);
  assert.equal(saved.workspaceId, 'w1');
  assert.equal(saved.threadId, 't1');
  assert.deepEqual(saved.targetServices, ['task-service']);
});

test('memoryStore writes and merges AI_MEMORY files across runs', async (t) => {
  const workspaceDir = await fs.mkdtemp(path.join(os.tmpdir(), 'agent2-memory-'));
  t.after(async () => {
    await fs.remove(workspaceDir);
  });

  const workspace = { appDir: workspaceDir };
  const plan = dependencyClassifier.classifyPlan({
    projectName: 'TaskFlow',
    description: 'Task workflow app',
    services: [
      {
        name: 'task-service',
        port: 3002,
        entities: ['Task'],
        routes: [{ method: 'GET', path: '/api/v1/tasks' }],
        packageDependencies: ['express', 'mongoose'],
        serviceDependencies: ['user-service']
      },
      {
        name: 'user-service',
        port: 3001,
        entities: ['User'],
        routes: [{ method: 'GET', path: '/api/v1/users' }],
        packageDependencies: ['express', 'mongoose']
      }
    ]
  });

  await memoryStore.updateWorkspaceMemory({
    workspace,
    plan,
    index: {
      files: [
        {
          path: 'task-service/Server.js',
          kind: 'server',
          service: 'task-service',
          imports: ['./routes/tasks.routes.js']
        }
      ]
    },
    audit: {
      services: {
        'task-service': {
          missingFiles: ['models/task.model.js']
        }
      }
    },
    generation: { task: 'Initial generation', status: 'running' },
    thread: { title: 'Main thread' },
    failurePatterns: [{ code: 'missing-model-file', message: 'Task model missing' }]
  });

  await memoryStore.updateWorkspaceMemory({
    workspace,
    plan,
    index: {
      files: [
        {
          path: 'task-service/Server.js',
          kind: 'server',
          service: 'task-service',
          imports: ['./routes/tasks.routes.js']
        },
        {
          path: 'task-service/models/task.model.js',
          kind: 'model',
          service: 'task-service',
          imports: ['mongoose']
        }
      ]
    },
    audit: {
      services: {
        'task-service': {
          missingFiles: []
        }
      }
    },
    generation: { task: 'Fix model', status: 'completed' },
    thread: { title: 'Main thread' },
    failurePatterns: [
      { code: 'missing-model-file', message: 'Task model missing' },
      { code: 'unresolved-import', message: 'Controller import invalid' }
    ]
  });

  const memory = await memoryStore.read(workspaceDir);

  assert.equal(memory.summary.hasProjectState, true);
  assert.ok(memory.files['PROJECT_STATE.md'].includes('Task: Fix model'));
  assert.equal(memory.summary.indexedFiles, 2);
  assert.equal(memory.summary.servicesTracked, 2);
  assert.equal(memory.summary.failurePatterns, 2);

  const dependencyRules = memory.parsed['DEPENDENCY_RULES.json'];
  assert.deepEqual(dependencyRules['task-service'].forbiddenPackages, ['user-service']);

  const serviceMap = memory.parsed['SERVICE_MAP.json'];
  assert.ok(serviceMap['task-service'].envVars.includes('USER_SERVICE_URL'));
});

test('developerAgent.extractFiles recovers partial file blocks and ignores trailing junk', () => {
  const developerAgent = new DeveloperAgent(
    {},
    {
      to() {
        return { emit() {} };
      }
    }
  );

  const response = `
===FILE: file_0.js===
import mongoose from "mongoose";
const schema = new mongoose.Schema({ title: String }, { timestamps: true });
export default mongoose.model("Task", schema);
===END===
===FILE: routes/tasks.routes.js===
import express from "express";
import { getTasks } from "../controllers/task.controller.js";
const router = express.Router();
router.get("/", getTasks);
export default router;
===END===
Would Would you you like like to to continue
`;

  const files = developerAgent.extractFiles(response, 'task-service');

  assert.equal(files.length, 2);
  assert.ok(files.some((file) => file.path === 'models/Task.js'));
  assert.ok(files.some((file) => file.path === 'routes/tasks.routes.js'));
});

test('workflowDeveloperService strips fences and rewrites broken local imports to real files', () => {
  const service = new WorkflowDeveloperService(
    {},
    {
      to() {
        return { emit() {} };
      }
    }
  );

  const normalized = service.ensureDeterministicArtifacts(
    {
      name: 'task-service',
      port: 3002,
      entities: ['Task'],
      routes: [{ method: 'GET', path: '/api/v1/tasks' }],
      serviceDependencies: []
    },
    {
      projectName: 'task-manager',
      sharedEnv: {
        MONGO_URL: 'mongodb://localhost:27017/task-manager',
        SEKRET_KEY: 'secret'
      },
      services: []
    },
    [
      {
        path: 'models/Task.js',
        content: '```js\nexport default {};\n```',
        service: 'task-service'
      },
      {
        path: 'services/task.service.js',
        content: '```javascript\nimport TaskModel from "../models/Task.model";\nexport async function getTasks() { return TaskModel.find(); }\n```',
        service: 'task-service'
      },
      {
        path: 'controllers/taskController.js',
        content: '```js\nexport async function getTasks(req, res) { return res.json([]); }\n```',
        service: 'task-service'
      },
      {
        path: 'routes/taskRoutes.js',
        content: '```js\nexport default {};\n```',
        service: 'task-service'
      },
      {
        path: 'Server.js',
        content: '```js\nimport express from "express";\nconst app = express();\napp.use(express.json());\n```',
        service: 'task-service'
      }
    ]
  );

  const taskServiceFile = normalized.find((file) => file.path === 'services/task.service.js');
  const canonicalModelAlias = normalized.find((file) => file.path === 'models/task.model.js');

  assert.ok(taskServiceFile);
  assert.equal(taskServiceFile.content.includes('```'), false);
  assert.ok(taskServiceFile.content.includes('../models/Task.js'));
  assert.ok(canonicalModelAlias);
  assert.ok(canonicalModelAlias.content.includes("export { default } from \"./Task.js\";"));
});

test('workflowDeveloperService synthesizes nested route aliases, service scaffolds, and config env module', () => {
  const service = new WorkflowDeveloperService(
    {},
    {
      to() {
        return { emit() {} };
      }
    }
  );

  const normalized = service.ensureDeterministicArtifacts(
    {
      name: 'dashboard-service',
      port: 3003,
      entities: ['DashboardStats'],
      routes: [{ method: 'GET', path: '/api/v1/dashboard/stats' }],
      envVars: ['PORT', 'MONGO_URL', 'SEKRET_KEY', 'SERVER_URL', 'TASK_SERVICE_URL'],
      serviceDependencies: ['task-service'],
      requiredFiles: [
        'package.json',
        'Server.js',
        'DbConnection.js',
        '.env.example',
        'controllers/authController.js',
        'models/dashboard-stats.model.js',
        'services/dashboard-stats.service.js',
        'controllers/dashboard.controller.js',
        'routes/dashboard.routes.js'
      ]
    },
    {
      projectName: 'task-manager',
      sharedEnv: {
        MONGO_URL: 'mongodb://localhost:27017/task-manager',
        SEKRET_KEY: 'secret'
      },
      services: [{ name: 'task-service', port: 3002 }]
    },
    [
      {
        path: 'models/DashboardStats.js',
        content: 'export default {};',
        service: 'dashboard-service'
      },
      {
        path: 'controllers/statsController.js',
        content: 'export async function getDashboardStats(req, res) { return res.json({ ok: true }); }',
        service: 'dashboard-service'
      },
      {
        path: 'controllers/dashboard.controller.js',
        content: 'import { DASHBOARD_SERVICE_URL } from "../config/env"; export async function getDashboardStats(req, res) { return res.json({ url: DASHBOARD_SERVICE_URL }); }',
        service: 'dashboard-service'
      },
      {
        path: 'routes/stats.js',
        content: 'const statsRouter = {}; export { statsRouter }; export default statsRouter;',
        service: 'dashboard-service'
      },
      {
        path: 'Server.js',
        content: 'import express from "express"; const app = express(); app.use(express.json());',
        service: 'dashboard-service'
      }
    ]
  );

  const envModule = normalized.find((file) => file.path === 'config/env.js');
  const routeAlias = normalized.find((file) => file.path === 'routes/dashboard.routes.js');
  const serviceScaffold = normalized.find((file) => file.path === 'services/dashboard-stats.service.js');
  const controller = normalized.find((file) => file.path === 'controllers/dashboard.controller.js');

  assert.ok(envModule);
  assert.ok(envModule.content.includes('export const TASK_SERVICE_URL = process.env.TASK_SERVICE_URL;'));
  assert.ok(routeAlias);
  assert.ok(routeAlias.content.includes('export { default } from "./stats.js";'));
  assert.ok(serviceScaffold);
  assert.ok(serviceScaffold.content.includes('import DashboardStats'));
  assert.ok(serviceScaffold.content.includes('createDashboardStats'));
  assert.ok(controller);
  assert.ok(controller.content.includes('../config/env.js'));
});
