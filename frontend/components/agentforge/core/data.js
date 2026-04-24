// AgentForge Studio — Seed Data
export const AF_DATA = {
  projects: [
    {
      id: "proj-001",
      name: "StayEase Hotel Booking System",
      code: "STAY-001",
      domain: "Hospitality",
      type: "Full Stack SaaS",
      platform: ["Web", "Internal Admin"],
      stage: "Agent 3 QA Validation",
      frontendPreset: "Enterprise Dashboard",
      backendStack: "FastAPI + PostgreSQL",
      qaScore: 87,
      updatedAt: "12 min ago",
      status: "active",
      description: "A hotel booking platform with customer login, room browsing, booking management, payments, admin dashboard, and reporting.",
      features: [
        { id: "F-01", name: "Customer Authentication", priority: "Critical", role: "Guest", status: "done" },
        { id: "F-02", name: "Room Search & Filtering", priority: "High", role: "Guest", status: "done" },
        { id: "F-03", name: "Booking Management", priority: "Critical", role: "Guest", status: "done" },
        { id: "F-04", name: "Payment Processing", priority: "Critical", role: "Guest", status: "done" },
        { id: "F-05", name: "Admin Dashboard", priority: "High", role: "Admin", status: "done" },
        { id: "F-06", name: "Reporting & Analytics", priority: "Medium", role: "Admin", status: "in-progress" },
        { id: "F-07", name: "Notification System", priority: "Medium", role: "System", status: "in-progress" },
      ]
    },
    {
      id: "proj-002",
      name: "MediTrack Clinic Management Platform",
      code: "MEDI-002",
      domain: "Healthcare",
      type: "Web Application",
      platform: ["Web", "Internal Admin"],
      stage: "Agent 2 Building",
      frontendPreset: "Healthcare Portal",
      backendStack: "NestJS + PostgreSQL",
      qaScore: null,
      updatedAt: "2 hrs ago",
      status: "active",
      description: "Clinic management system covering patient records, appointment scheduling, prescriptions, billing and staff management.",
      features: []
    },
    {
      id: "proj-003",
      name: "LearnHub LMS Portal",
      code: "LEARN-003",
      domain: "Education",
      type: "Full Stack SaaS",
      platform: ["Web", "Android", "iOS"],
      stage: "Frontend Design Selection",
      frontendPreset: "Education Portal",
      backendStack: "Node.js Express + MongoDB",
      qaScore: null,
      updatedAt: "1 day ago",
      status: "active",
      description: "Learning management system with course creation, student enrollment, assessments, progress tracking, and certificate generation.",
      features: []
    }
  ],

  pipeline: [
    { id: "stage-1", label: "Idea Intake", status: "complete", pct: 100, lastAction: "Idea submitted via intake form", agent: null, note: "Project scope defined" },
    { id: "stage-2", label: "Agent 1 Analysis", status: "complete", pct: 100, lastAction: "SRS v1.2 generated", agent: "Agent 1", note: "14 functional requirements extracted" },
    { id: "stage-3", label: "Design Selection", status: "complete", pct: 100, lastAction: "Enterprise Dashboard preset approved", agent: null, note: "Frontend design approved. Backend generation aligned with selected UI architecture." },
    { id: "stage-4", label: "Agent 2 Build", status: "complete", pct: 94, lastAction: "6 backend services generated", agent: "Agent 2", note: "Fix loop applied, 1 iteration" },
    { id: "stage-5", label: "Agent 3 Testing", status: "active", pct: 67, lastAction: "Integration tests running", agent: "Agent 3", note: "2 integration mismatches flagged" },
    { id: "stage-6", label: "Agent 4 Deployment", status: "pending", pct: 0, lastAction: "Awaiting QA approval", agent: "Agent 4", note: "DevOps bundle ready to generate" },
    { id: "stage-7", label: "Release", status: "pending", pct: 0, lastAction: "Not started", agent: null, note: "Release gate locked" }
  ],

  builds: [
    { id: "BLD-0041", project: "StayEase", preset: "Enterprise Dashboard", stage: "QA Testing", qaScore: 87, deployStatus: "Pending", updatedAt: "12 min ago" },
    { id: "BLD-0039", project: "StayEase", preset: "Enterprise Dashboard", stage: "Build Complete", qaScore: 72, deployStatus: "Blocked", updatedAt: "3 hrs ago" },
    { id: "BLD-0036", project: "MediTrack", preset: "Healthcare Portal", stage: "Building", qaScore: null, deployStatus: "In Progress", updatedAt: "2 hrs ago" },
    { id: "BLD-0031", project: "LearnHub", preset: "Education Portal", stage: "Design Selected", qaScore: null, deployStatus: "Not Started", updatedAt: "1 day ago" },
    { id: "BLD-0028", project: "StayEase", preset: "SaaS Product", stage: "Released", qaScore: 91, deployStatus: "Live", updatedAt: "5 days ago" }
  ],

  activity: [
    { id: 1, time: "12 min ago", agent: "Agent 3", msg: "Flagged 2 integration mismatches in booking-service and payment-service" },
    { id: 2, time: "34 min ago", agent: "Agent 2", msg: "Static analysis complete — 3 warnings, 0 errors in backend services" },
    { id: 3, time: "1 hr ago", agent: "Agent 2", msg: "Generated 6 backend services: auth, user, booking, payment, notification, report" },
    { id: 4, time: "2 hrs ago", agent: "System", msg: "Frontend preset 'Enterprise Dashboard' approved and forwarded to Agent 2" },
    { id: 5, time: "3 hrs ago", agent: "Agent 1", msg: "SRS v1.2 generated — 14 functional, 6 non-functional requirements" },
    { id: 6, time: "5 hrs ago", agent: "Agent 4", msg: "GitHub Actions workflow YAML generated for MediTrack (previous build)" },
    { id: 7, time: "1 day ago", agent: "Agent 4", msg: "AWS deployment bundle created — ECS + RDS config for StayEase v0.1.0" },
  ],

  services: [
    { name: "auth-service", framework: "FastAPI", endpoints: 8, models: 3, health: "healthy", status: "generated" },
    { name: "user-service", framework: "FastAPI", endpoints: 12, models: 4, health: "healthy", status: "generated" },
    { name: "booking-service", framework: "FastAPI", endpoints: 15, models: 5, health: "warning", status: "fix-applied" },
    { name: "payment-service", framework: "FastAPI", endpoints: 10, models: 3, health: "warning", status: "fix-applied" },
    { name: "notification-service", framework: "FastAPI", endpoints: 6, models: 2, health: "healthy", status: "generated" },
    { name: "report-service", framework: "FastAPI", endpoints: 9, models: 4, health: "healthy", status: "generated" }
  ],

  pages: [
    { name: "Login Page", route: "/login", status: "generated", requirements: 2, layout: "Centered Auth", components: ["AuthForm", "Logo", "Link"] },
    { name: "Register Page", route: "/register", status: "generated", requirements: 3, layout: "Centered Auth", components: ["RegisterForm", "StepIndicator"] },
    { name: "Dashboard", route: "/dashboard", status: "generated", requirements: 6, layout: "Sidebar + Grid", components: ["KPICards", "BookingTable", "Charts"] },
    { name: "Room Listing", route: "/rooms", status: "generated", requirements: 4, layout: "Filter + Grid", components: ["FilterBar", "RoomCard", "Pagination"] },
    { name: "Room Detail", route: "/rooms/:id", status: "generated", requirements: 3, layout: "Split View", components: ["Gallery", "BookingPanel", "Reviews"] },
    { name: "Booking Form", route: "/bookings/new", status: "generated", requirements: 5, layout: "Multi-step Form", components: ["StepForm", "GuestInfo", "PaymentForm"] },
    { name: "My Bookings", route: "/bookings", status: "generated", requirements: 3, layout: "Table View", components: ["BookingTable", "StatusBadge", "Filters"] },
    { name: "Reports", route: "/admin/reports", status: "in-progress", requirements: 4, layout: "Dashboard Grid", components: ["Charts", "DataTable", "Export"] },
    { name: "Admin Panel", route: "/admin", status: "in-progress", requirements: 6, layout: "Admin Layout", components: ["UserTable", "MetricsRow", "Logs"] },
    { name: "Settings", route: "/settings", status: "generated", requirements: 2, layout: "Settings Layout", components: ["SettingsForm", "ProfileSection"] }
  ],

  bugs: [
    { id: "BUG-014", title: "Booking payload schema mismatch", severity: "High", module: "booking-service", rootCause: "API contract response field 'check_out' expected as 'checkout_date'", fix: "Update response model in BookingResponse schema", status: "pending", agent: "Agent 2" },
    { id: "BUG-013", title: "Payment callback missing idempotency key", severity: "Medium", module: "payment-service", rootCause: "Webhook handler does not validate idempotency_key header", fix: "Add idempotency key middleware to payment webhook route", status: "pending", agent: "Agent 2" },
    { id: "BUG-011", title: "JWT expiry not validated on refresh", severity: "Low", module: "auth-service", rootCause: "Refresh token endpoint does not check token expiry", fix: "Add exp claim validation in token refresh handler", status: "resolved", agent: "Agent 2" }
  ],

  artifacts: [
    { id: "ART-001", name: "SRS Document v1.2", category: "Requirements", agent: "Agent 1", version: "1.2", status: "approved", format: "PDF", updatedAt: "3 hrs ago" },
    { id: "ART-002", name: "Requirements JSON Spec", category: "Requirements", agent: "Agent 1", version: "1.2", status: "approved", format: "JSON", updatedAt: "3 hrs ago" },
    { id: "ART-003", name: "Architecture Diagrams", category: "Diagrams", agent: "Agent 1", version: "1.0", status: "approved", format: "PNG", updatedAt: "3 hrs ago" },
    { id: "ART-004", name: "Frontend Design Pack", category: "Design", agent: "System", version: "1.0", status: "approved", format: "ZIP", updatedAt: "2 hrs ago" },
    { id: "ART-005", name: "Source Code Bundle", category: "Code", agent: "Agent 2", version: "0.4", status: "in-progress", format: "ZIP", updatedAt: "12 min ago" },
    { id: "ART-006", name: "OpenAPI Documentation", category: "API", agent: "Agent 2", version: "0.4", status: "in-progress", format: "YAML", updatedAt: "1 hr ago" },
    { id: "ART-007", name: "QA Test Report", category: "Testing", agent: "Agent 3", version: "0.2", status: "in-progress", format: "PDF", updatedAt: "12 min ago" },
    { id: "ART-008", name: "Bug Report Bundle", category: "Testing", agent: "Agent 3", version: "0.2", status: "review", format: "JSON", updatedAt: "12 min ago" },
    { id: "ART-009", name: "Dockerfiles (all services)", category: "DevOps", agent: "Agent 4", version: "—", status: "pending", format: "DIR", updatedAt: "Not generated" },
    { id: "ART-010", name: "docker-compose.yml", category: "DevOps", agent: "Agent 4", version: "—", status: "pending", format: "YAML", updatedAt: "Not generated" },
    { id: "ART-011", name: "GitHub Actions Workflow", category: "CI/CD", agent: "Agent 4", version: "—", status: "pending", format: "YAML", updatedAt: "Not generated" },
    { id: "ART-012", name: "AWS Deployment Config", category: "Cloud", agent: "Agent 4", version: "—", status: "pending", format: "YAML", updatedAt: "Not generated" },
  ],

  versions: [
    { version: "v0.1.0", date: "5 days ago", summary: "Initial prototype release", preset: "SaaS Product", build: "Complete", qa: 91, deploy: "Live", notes: "First working prototype with auth, room listing and basic booking flow." },
    { version: "v0.2.0", date: "1 day ago", summary: "Design refresh + backend expansion", preset: "Enterprise Dashboard", build: "Complete", qa: 72, deploy: "Blocked", notes: "Switched to Enterprise Dashboard preset. Added 3 new backend services. QA blocked due to 2 contract mismatches." },
    { version: "v0.3.0-rc", date: "Now (in progress)", summary: "QA fix cycle + DevOps preparation", preset: "Enterprise Dashboard", build: "In Progress", qa: 87, deploy: "Pending", notes: "Fixing BUG-013 and BUG-014. DevOps bundle pending QA approval." }
  ],

  logLines: [
    "[12:01:04] [Agent3] Starting integration test suite — 7 modules, 34 test cases",
    "[12:01:06] [Agent3] ✓ auth-service: 8/8 unit tests passed",
    "[12:01:09] [Agent3] ✓ user-service: 12/12 unit tests passed",
    "[12:01:13] [Agent3] ✗ booking-service: schema mismatch on /bookings POST — field 'checkout_date' not found",
    "[12:01:14] [Agent3] ✗ payment-service: idempotency key missing in webhook handler",
    "[12:01:16] [Agent3] ✓ notification-service: 6/6 unit tests passed",
    "[12:01:18] [Agent3] ✓ report-service: 9/9 unit tests passed",
    "[12:01:20] [Agent3] Integration test run complete — 2 failures detected",
    "[12:01:20] [Agent3] Generating bug reports BUG-013, BUG-014",
    "[12:01:22] [System] Bug reports queued for Agent 2 review"
  ],

  srsRequirements: [
    { id: "REQ-001", text: "The system shall allow customers to search available rooms by date range, room type, and guest count.", type: "Functional", priority: "Critical", confidence: 98, deps: 0 },
    { id: "REQ-002", text: "The system shall provide a secure checkout flow supporting credit card and digital wallet payments.", type: "Functional", priority: "Critical", confidence: 95, deps: 2 },
    { id: "REQ-003", text: "The system shall send confirmation emails and SMS notifications upon successful booking.", type: "Functional", priority: "High", confidence: 92, deps: 1 },
    { id: "REQ-004", text: "The system shall load the room listing page in under 2 seconds under normal load conditions.", type: "Non-Functional", priority: "High", confidence: 78, deps: 0 },
    { id: "REQ-005", text: "Admin users shall be able to manage room inventory, pricing, and availability in real-time.", type: "Functional", priority: "High", confidence: 96, deps: 1 },
    { id: "REQ-006", text: "The system shall comply with PCI-DSS standards for payment data handling.", type: "Non-Functional", priority: "Critical", confidence: 88, deps: 2 },
    { id: "REQ-007", text: "The system shall support multi-language UI for English, Arabic, and French.", type: "Functional", priority: "Medium", confidence: 82, deps: 0 },
    { id: "REQ-008", text: "The system shall generate monthly occupancy and revenue reports for admin users.", type: "Functional", priority: "Medium", confidence: 90, deps: 1 }
  ],

  memoryPatterns: [
    { id: "MEM-001", issue: "Booking schema mismatch on nested date fields", projectType: "Hospitality SaaS", fix: "Normalize date fields to ISO 8601 in response models", confidence: 94, outcome: "Resolved in 1 iteration" },
    { id: "MEM-002", issue: "JWT refresh endpoint missing expiry check", projectType: "Auth Service", fix: "Add exp claim validation in token refresh handler", confidence: 97, outcome: "Resolved immediately" },
    { id: "MEM-003", issue: "Missing idempotency on payment webhooks", projectType: "Payment Integration", fix: "Add idempotency_key middleware to webhook routes", confidence: 91, outcome: "Resolved in 1 iteration" },
    { id: "MEM-004", issue: "Microservices startup order dependency", projectType: "FastAPI Microservices", fix: "Add depends_on with healthcheck in docker-compose", confidence: 89, outcome: "Resolved via docker-compose update" },
  ]
};
