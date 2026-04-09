const srsCompactor = require('./srsCompactor');
const dependencyClassifier = require('./dependencyClassifier');

const SYSTEM_PROMPT = `You are an expert software architect specializing in MERN stack microservices.
Analyze product requirements and return ONLY valid JSON.

Requirements:
- Backend services use ES modules, Server.js, DbConnection.js, MONGO_URL, SEKRET_KEY.
- Generated apps use Vite + React on port 5173 and a gateway on port 8080.
- Internal service names must NEVER appear in packageDependencies.
- Every service must define entities, requiredFiles, packageDependencies, devDependencies, serviceDependencies, controllers, routes, envVars, and serviceCalls.

Return JSON only with this shape:
{
  "projectName": "string",
  "description": "string",
  "services": [
    {
      "name": "task-service",
      "description": "string",
      "port": 3002,
      "entities": ["Task"],
      "controllers": ["taskController"],
      "routes": [{ "method": "GET", "path": "/api/v1/tasks", "description": "List tasks" }],
      "models": [{ "name": "Task", "fields": [{ "name": "title", "type": "String", "required": true }] }],
      "requiredFiles": ["package.json", "Server.js", "DbConnection.js", ".env.example", "controllers/authController.js", "models/task.model.js", "services/task.service.js", "controllers/task.controller.js", "routes/task.routes.js"],
      "packageDependencies": ["express", "mongoose", "cors", "dotenv", "helmet", "express-rate-limit", "body-parser", "jsonwebtoken", "bcryptjs", "axios", "swagger-jsdoc", "swagger-ui-express"],
      "devDependencies": ["nodemon"],
      "serviceDependencies": ["user-service"],
      "envVars": ["PORT", "MONGO_URL", "SEKRET_KEY", "SERVER_URL", "USER_SERVICE_URL"],
      "serviceCalls": [{ "service": "user-service", "envVar": "USER_SERVICE_URL", "purpose": "validate user identity" }]
    }
  ],
  "frontend": {
    "port": 5173,
    "pages": [{ "name": "Home", "route": "/", "description": "Landing page", "group": "HomePage" }],
    "routeGroups": ["HomePage"],
    "components": ["Header", "Footer"],
    "serviceUrls": ["VITE_TASK_SERVICE_URL=http://localhost:3002"]
  },
  "gateway": {
    "port": 8080,
    "routes": [{ "prefix": "/api/v1/tasks", "target": "http://localhost:3002", "service": "task-service" }]
  },
  "sharedEnv": {
    "SEKRET_KEY": "shared_secret_key_change_in_production",
    "MONGO_URL": "mongodb://localhost:27017/{projectName}"
  }
}`;

class WorkflowPlanner {
  constructor(ollamaService, io) {
    this.ollama = ollamaService;
    this.io = io;
  }

  async plan(jobId, srs, context = {}, onToken) {
    const compacted = srsCompactor.compact(srs || {});
    if (compacted.canSkipAI && compacted.directPlan) {
      return this.normalizePlan(compacted.directPlan, context);
    }

    const prompt = `Analyze this project summary and create a detailed MERN microservice plan.

Summary:
${compacted.compact}

${this.buildContextPrompt(context)}

Return ONLY valid JSON.`;

    const response = await this.ollama.generate(
      jobId,
      prompt,
      SYSTEM_PROMPT,
      'planner',
      'plan',
      onToken,
      context.messageContext
    );

    return this.normalizePlan(this.parse(response), context);
  }

  async planContinuation(jobId, task, currentPlan, context = {}, onToken) {
    const prompt = `Update this existing MERN microservice plan for a follow-up task.

Task:
${task}

Current plan:
${JSON.stringify(currentPlan, null, 2)}

${this.buildContextPrompt(context)}

Return the FULL updated plan as valid JSON. Preserve unchanged services and ports when possible.`;

    const response = await this.ollama.generate(
      jobId,
      prompt,
      SYSTEM_PROMPT,
      'planner',
      'plan_follow_up',
      onToken,
      context.messageContext
    );

    return this.normalizePlan(this.parse(response), context);
  }

  buildContextPrompt(context = {}) {
    const parts = [];
    if (context.compactedContext?.plannerPrompt) {
      parts.push(`Compacted workflow context:\n${context.compactedContext.plannerPrompt}`);
    }
    if (context.instructions?.mergedText) {
      parts.push(`Instruction chain:\n${context.instructions.mergedText}`);
    }
    if (context.memory?.files?.['PROJECT_STATE.md']) {
      parts.push(`Current project state:\n${context.memory.files['PROJECT_STATE.md']}`);
    }
    if (context.task) {
      parts.push(`Current task:\n${context.task}`);
    }
    return parts.join('\n\n');
  }

  parse(response) {
    try {
      const fenced = response.match(/```json\s*([\s\S]*?)\s*```/) ||
        response.match(/```\s*([\s\S]*?)\s*```/);
      return JSON.parse((fenced ? fenced[1] : response).trim());
    } catch {
      const start = response.indexOf('{');
      const end = response.lastIndexOf('}') + 1;
      if (start === -1 || end <= start) {
        throw new Error(`Planner returned invalid JSON: ${response.slice(0, 200)}`);
      }
      return JSON.parse(response.slice(start, end));
    }
  }

  normalizePlan(plan, context = {}) {
    const normalized = {
      ...plan,
      projectName: plan.projectName || context.projectName || 'generated-app',
      description: plan.description || context.description || '',
      frontend: {
        port: 5173,
        pages: plan.frontend?.pages || [],
        routeGroups: plan.frontend?.routeGroups || ['HomePage'],
        components: plan.frontend?.components || ['Header', 'Footer'],
        serviceUrls: plan.frontend?.serviceUrls || []
      },
      gateway: {
        port: 8080,
        routes: plan.gateway?.routes || []
      },
      sharedEnv: {
        SEKRET_KEY: plan.sharedEnv?.SEKRET_KEY || 'shared_secret_key_change_in_production',
        MONGO_URL: (plan.sharedEnv?.MONGO_URL || 'mongodb://localhost:27017/{projectName}')
          .replace('{projectName}', plan.projectName || context.projectName || 'generated-app')
          .replace('{project}', plan.projectName || context.projectName || 'generated-app')
      }
    };

    const classified = dependencyClassifier.classifyPlan(normalized);
    classified.services = (classified.services || []).map((service, index) => ({
      ...service,
      port: service.port || (3001 + index),
      description: service.description || `${service.name} service`
    }));

    if (!classified.gateway.routes || classified.gateway.routes.length === 0) {
      classified.gateway.routes = classified.services.map((service) => ({
        prefix: `/api/v1/${service.name.replace(/-service$/, '')}`,
        target: `http://localhost:${service.port}`,
        service: service.name
      }));
    }

    return classified;
  }
}

module.exports = WorkflowPlanner;
