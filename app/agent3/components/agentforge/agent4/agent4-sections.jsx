import React, { useState } from "react";
import { AF_DATA } from "../core/data";
import { Icon, Btn, Badge, Card, CodeBlock } from "../core/ui";

export const DEPLOY_STEPS = [
  { label: "Project intake", desc: "Validate source path and enumerate files." },
  { label: "Agent 3 report parsing", desc: "Link previous QA/gate context if provided." },
  { label: "Service discovery", desc: "Discover frontend, services, workflows, and AWS templates." },
  { label: "Docker audit", desc: "Inspect Dockerfiles and container hardening." },
  { label: "Docker generation", desc: "Generate improved Docker assets." },
  { label: "Compose validation/generation", desc: "Generate compose repair artifacts." },
  { label: "Workflow generation", desc: "Generate or repair GitHub Actions workflows." },
  { label: "Env template generation", desc: "Assemble env requirement manifests." },
  { label: "AWS template generation", desc: "Generate or repair task definitions." },
  { label: "Deployment gate evaluation", desc: "Compute blockers, warnings, and readiness." },
  { label: "Docs generation", desc: "Write human-readable docs and reports." },
  { label: "Final packaging", desc: "Store generated artifacts and reports." },
];

export const DEPLOY_TABS = [
  { id: "timeline", label: "Deployment Pipeline" },
  { id: "containers", label: "Containers" },
  { id: "cicd", label: "CI/CD" },
  { id: "cloud", label: "Cloud Config" },
  { id: "releases", label: "Releases" },
];

const WIZARD_STEPS = ["Deploy?", "GitHub", "AWS", "Vercel", "Deploying"];

const DOCKER_COMPOSE = `version: "3.9"
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [auth-service]
  auth-service:
    build: ./services/auth
    ports: ["8001:8000"]
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
  booking-service:
    build: ./services/booking
    ports: ["8002:8000"]
  payment-service:
    build: ./services/payment
    ports: ["8003:8000"]
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: stayease
      POSTGRES_USER: \${DB_USER}
      POSTGRES_PASSWORD: \${DB_PASS}
    healthcheck:
      test: ["CMD-SHELL","pg_isready"]
      interval: 5s
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:`;

const GH_WORKFLOW = `name: StayEase CI/CD
on:
  push:
    branches: [main]
jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest --cov=.
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: \${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: \${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Push to ECR & Deploy ECS
        run: |
          aws ecr get-login-password | docker login ...
          docker build -t stayease-api .
          docker push \${{ secrets.ECR_REGISTRY }}/stayease-api
          aws ecs update-service --cluster stayease-prod \
            --service stayease-api --force-new-deployment`;

export function DeployWizard({ onStart, onCancel }) {
  const [step, setStep] = useState(0);
  const [githubRepo, setGithubRepo] = useState("stayease-demo/stayease-hotel-booking");
  const [githubBranch, setGithubBranch] = useState("main");
  const [awsRegion, setAwsRegion] = useState("us-east-1");
  const [awsTarget, setAwsTarget] = useState("ECS Fargate");
  const [vercelProject, setVercelProject] = useState("stayease-frontend");

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-2xl overflow-hidden w-[480px]" style={{ animation: "slideInUp 0.4s ease forwards" }}>
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-bold text-gray-900">Deploy to Production</p>
            {step > 0 && (
              <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
                <Icon name="X" size={14} />
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {WIZARD_STEPS.slice(1).map((wizardStep, index) => (
              <div key={wizardStep} className="flex items-center gap-2">
                <div
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium border ${
                    index + 1 === step
                      ? "bg-blue-600 text-white border-blue-600"
                      : index + 1 < step
                        ? "bg-green-50 text-green-700 border-green-300"
                        : "bg-white text-gray-400 border-gray-200"
                  }`}
                >
                  {index + 1 < step ? <Icon name="Check" size={10} /> : null}
                  {wizardStep}
                </div>
                {index < WIZARD_STEPS.length - 2 && (
                  <div className={`h-px w-4 ${index + 1 < step ? "bg-green-300" : "bg-gray-200"}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="p-6">
          {step === 0 && (
            <div className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
                <Icon name="Rocket" size={28} className="text-green-600" />
              </div>
              <h2 className="text-lg font-bold text-gray-900 mb-2">QA Passed! Ready to Deploy?</h2>
              <p className="text-sm text-gray-500 mb-6">
                Agent 3 completed all tests with a <strong className="text-green-600">94% QA score</strong>. Agent 4 will now generate Docker, CI/CD, and AWS deployment assets.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 py-3 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                >
                  <Icon name="Rocket" size={16} /> Yes, Deploy Now
                </button>
                <button
                  onClick={onCancel}
                  className="px-5 py-3 rounded-xl bg-gray-100 text-gray-600 text-sm font-medium hover:bg-gray-200 transition-colors"
                >
                  Not Yet
                </button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gray-900 flex items-center justify-center">
                  <Icon name="Github" size={20} className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-900">Connect GitHub Repository</p>
                  <p className="text-xs text-gray-500">Workflow YAML will be pushed to this repo</p>
                </div>
              </div>
              <div className="space-y-3 mb-5">
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Repository</p>
                  <input value={githubRepo} onChange={(event) => setGithubRepo(event.target.value)} className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none focus:border-blue-400" />
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Branch</p>
                  <input value={githubBranch} onChange={(event) => setGithubBranch(event.target.value)} className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none focus:border-blue-400" />
                </div>
                <div className="flex items-center gap-2 p-2.5 bg-green-50 rounded-lg border border-green-200">
                  <Icon name="CheckCircle2" size={13} className="text-green-600" />
                  <span className="text-xs text-green-700">Connected - Token valid</span>
                </div>
              </div>
              <button
                onClick={() => setStep(2)}
                className="w-full py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
              >
                Next - Connect AWS <Icon name="ArrowRight" size={14} />
              </button>
            </div>
          )}

          {step === 2 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center">
                  <Icon name="Cloud" size={20} className="text-orange-600" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-900">Connect AWS Account</p>
                  <p className="text-xs text-gray-500">Containers will be deployed to ECS Fargate</p>
                </div>
              </div>
              <div className="space-y-3 mb-5">
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Region</p>
                  <select value={awsRegion} onChange={(event) => setAwsRegion(event.target.value)} className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none">
                    {["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"].map((region) => (
                      <option key={region}>{region}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Deployment Target</p>
                  <select value={awsTarget} onChange={(event) => setAwsTarget(event.target.value)} className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none">
                    {["ECS Fargate", "EC2 + ALB", "Elastic Beanstalk"].map((target) => (
                      <option key={target}>{target}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2 p-2.5 bg-green-50 rounded-lg border border-green-200">
                  <Icon name="CheckCircle2" size={13} className="text-green-600" />
                  <span className="text-xs text-green-700">IAM role configured - Credentials valid</span>
                </div>
              </div>
              <button
                onClick={() => setStep(3)}
                className="w-full py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
              >
                Next - Connect Vercel <Icon name="ArrowRight" size={14} />
              </button>
            </div>
          )}

          {step === 3 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-black flex items-center justify-center">
                  <Icon name="Globe" size={20} className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-900">Connect Vercel (Optional)</p>
                  <p className="text-xs text-gray-500">Deploy static frontend to Vercel CDN</p>
                </div>
              </div>
              <div className="space-y-3 mb-5">
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Vercel Project Name</p>
                  <input value={vercelProject} onChange={(event) => setVercelProject(event.target.value)} className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none focus:border-blue-400" />
                </div>
                <div className="flex items-center gap-2 p-2.5 bg-green-50 rounded-lg border border-green-200">
                  <Icon name="CheckCircle2" size={13} className="text-green-600" />
                  <span className="text-xs text-green-700">Vercel linked - Auto-deploy on push</span>
                </div>
              </div>
              <button
                onClick={() => {
                  setStep(4);
                  onStart();
                }}
                className="w-full py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
              >
                <Icon name="Rocket" size={16} /> Start Deployment Pipeline
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function DevOpsHeader({ deployDone, tab, onChangeTab }) {
  return (
    <div className="px-5 pt-4 pb-3 border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
            <span>AgentForge</span>
            <Icon name="ChevronRight" size={10} />
            <span>DevOps Center</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">DevOps Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">Package, automate, version, and deploy to GitHub and AWS.</p>
        </div>
        {deployDone && (
          <div className="flex items-center gap-2 pt-1">
            <span className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 text-xs font-semibold rounded-lg border border-green-200 animate-pulse">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              v1.0.0 Live
            </span>
          </div>
        )}
      </div>
      <div className="flex gap-1 mt-3 border-b border-gray-200 -mb-3">
        {DEPLOY_TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => deployDone && onChangeTab(item.id)}
            className={`px-3 py-2 text-xs font-medium transition-all border-b-2 -mb-px ${
              tab === item.id
                ? "border-green-500 text-green-700"
                : deployDone
                  ? "border-transparent text-gray-500 hover:text-gray-700"
                  : item.id === "timeline"
                    ? "border-transparent text-gray-700"
                    : "border-transparent text-gray-300 cursor-not-allowed"
            }`}
          >
            {item.label}
            {!deployDone && item.id !== "timeline" && (
              <Icon name="Lock" size={9} className="inline ml-1 text-gray-300" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DeploymentTimelinePane({ showWizard, deployStep, deployDone }) {
  if (showWizard) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Icon name="Rocket" size={36} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm">Waiting for deployment configuration...</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-2 mb-5">
        {deployDone ? (
          <span className="flex items-center gap-2 text-sm font-semibold text-green-700">
            <Icon name="CheckCircle2" size={16} className="text-green-600" /> Deployment complete - v1.0.0 is live
          </span>
        ) : (
          <span className="flex items-center gap-2 text-sm font-semibold text-blue-700">
            <Icon name="Loader2" size={36} /> Deployment pipeline running...
          </span>
        )}
      </div>
      <div className="space-y-1">
        {DEPLOY_STEPS.map((step, index) => {
          const done = index <= deployStep;
          const active = index === deployStep && !deployDone;

          return (
            <div key={step.label} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center border-2 flex-shrink-0 transition-all duration-500 ${done ? "border-green-500 bg-green-50" : active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"}`}>
                  {done ? (
                    <Icon name="Check" size={13} className="text-green-600" />
                  ) : active ? (
                    <Icon name="Loader2" size={13} className="text-blue-500 animate-spin" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-gray-200" />
                  )}
                </div>
                {index < DEPLOY_STEPS.length - 1 && <div className={`w-px flex-1 my-0.5 ${done ? "bg-green-200" : "bg-gray-100"}`} style={{ minHeight: 16 }} />}
              </div>
              <div className="pb-3 flex-1">
                <p className={`text-xs font-semibold ${done ? "text-gray-900" : active ? "text-blue-600" : "text-gray-300"}`}>{step.label}</p>
                <p className={`text-xs mt-0.5 ${done ? "text-gray-500" : "text-gray-300"}`}>{step.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ContainersPane() {
  return (
    <div className="max-w-2xl">
      <div className="flex gap-2 mb-4">
        <Btn size="xs" icon="Download">Download All</Btn>
        <Btn size="xs" icon="Copy">Copy compose.yml</Btn>
      </div>
      <CodeBlock code={DOCKER_COMPOSE} lang="yaml" />
    </div>
  );
}

export function CicdPane() {
  return (
    <div className="max-w-2xl">
      <div className="flex gap-2 mb-4">
        <Btn size="xs" icon="Download">Download YAML</Btn>
        <Btn size="xs" icon="Copy">Copy</Btn>
      </div>
      <CodeBlock code={GH_WORKFLOW} lang="yaml" />
    </div>
  );
}

export function CloudConfigPane() {
  const cards = [
    ["ECS Fargate", "Backend services deployed", "Server", "green"],
    ["S3 + CloudFront", "Frontend static site", "Globe", "blue"],
    ["RDS PostgreSQL", "Managed database", "Database", "violet"],
    ["Secrets Manager", "Credentials secured", "Lock", "amber"],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 max-w-2xl">
      {cards.map(([title, description, icon, color]) => (
        <Card key={title} className="p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color === "green" ? "bg-green-100" : color === "blue" ? "bg-blue-100" : color === "violet" ? "bg-violet-100" : "bg-amber-100"}`}>
              <Icon name={icon} size={15} className={color === "green" ? "text-green-600" : color === "blue" ? "text-blue-600" : color === "violet" ? "text-violet-600" : "text-amber-600"} />
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-900">{title}</p>
              <Badge color={color}>Active</Badge>
            </div>
          </div>
          <p className="text-xs text-gray-500">{description}</p>
        </Card>
      ))}
    </div>
  );
}

export function ReleasesPane() {
  return (
    <div className="max-w-lg space-y-3">
      {AF_DATA.versions.map((version, index) => (
        <Card key={version.version} className="p-4">
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-bold text-gray-900">{version.version}</span>
            {index === AF_DATA.versions.length - 1 ? <Badge color="green" dot>Live</Badge> : <Badge color="default">Archive</Badge>}
          </div>
          <p className="text-xs text-gray-500 mt-1">{version.summary}</p>
          <p className="text-xs text-gray-400 mt-1">{version.date}</p>
        </Card>
      ))}
    </div>
  );
}
