import React, { useEffect, useRef, useState } from "react";
import {
  Icon,
  Badge,
  Card,
  KPICard,
  Table,
  InspectorPanel,
  InspectorSection,
  InspectorRow,
  ProgressBar,
} from "../core/ui";

export const TEST_STEPS = [
  { label: "Setting up test environment", desc: "Initializing pytest + coverage" },
  { label: "Running auth-service unit tests", desc: "8 test cases" },
  { label: "Running user-service unit tests", desc: "12 test cases" },
  { label: "Running booking-service unit tests", desc: "15 test cases" },
  { label: "Running payment-service unit tests", desc: "10 test cases" },
  { label: "Running integration: registration -> login", desc: "End-to-end flow" },
  { label: "Running integration: booking -> payment", desc: "Full booking flow" },
  { label: "Running API contract validation", desc: "Checking response schemas" },
  { label: "Calculating coverage report", desc: "Line + function coverage" },
  { label: "Generating QA report", desc: "Compiling results" },
];

export const BUGS_PER_ROUND = [
  [
    {
      id: "BUG-014",
      title: "Booking schema mismatch",
      severity: "High",
      module: "booking-service",
      desc: "Field 'checkout_date' missing in response",
      fix: "Rename field in BookingResponse schema",
    },
    {
      id: "BUG-013",
      title: "Payment idempotency key missing",
      severity: "Medium",
      module: "payment-service",
      desc: "Webhook handler does not validate idempotency_key",
      fix: "Add idempotency middleware to webhook route",
    },
    {
      id: "BUG-012",
      title: "Auth token expiry not checked",
      severity: "Low",
      module: "auth-service",
      desc: "Refresh endpoint skips exp claim check",
      fix: "Add exp validation in token refresh handler",
    },
  ],
  [
    {
      id: "BUG-013",
      title: "Payment idempotency key missing",
      severity: "Medium",
      module: "payment-service",
      desc: "Partially fixed - still failing on retry",
      fix: "Ensure middleware runs before handler",
    },
    {
      id: "BUG-015",
      title: "Coverage below threshold on report-service",
      severity: "Low",
      module: "report-service",
      desc: "Line coverage 68% (threshold 80%)",
      fix: "Add 3 missing unit tests for aggregation logic",
    },
  ],
  [],
];

export const QA_SCORES = [72, 85, 94];

const CODE_LOG_TEMPLATES = [
  [
    "-> Agent 2 received BUG-014, BUG-013, BUG-012",
    "-> Opening booking-service/models.py...",
    "-> Patching BookingResponse schema...",
    "  - Adding checkout_date field",
    "  - Updating response serializer",
    "-> Running unit tests...",
    "  - test_booking_response_schema passed",
    "-> BookingResponse.checkout_date fixed",
    "-> Opening payment-service/webhooks.py...",
    "-> Adding idempotency middleware...",
    "  - Importing idempotency validator",
    "  - Adding middleware to webhook route",
    "-> Running payment tests...",
    "  - test_payment_webhook_idempotent passed",
    "-> Payment idempotency middleware fixed",
    "-> Opening auth-service/token_refresh.py...",
    "-> Fixing auth refresh handler...",
    "  - Adding exp claim validation",
    "-> Running auth tests...",
    "  - test_token_refresh_exp_validation passed",
    "-> All 3 fixes applied",
    "-> Running full test suite...",
    "  - 47 tests passed",
    "-> Sending back to Agent 3",
  ],
  [
    "-> Agent 2 received BUG-013, BUG-015",
    "-> Opening payment-service/webhooks.py...",
    "-> Re-patching payment webhook handler...",
    "  - Reordering middleware execution",
    "  - Moving idempotency check before handler",
    "-> Running payment tests...",
    "  - test_payment_webhook_idempotent passed",
    "  - test_retry_scenario passed",
    "-> Middleware order corrected",
    "-> Opening report-service/test_coverage.py...",
    "-> Adding missing report-service tests...",
    "  - test_aggregation_monthly",
    "  - test_aggregation_by_room_type",
    "  - test_aggregation_empty_dataset",
    "-> Running coverage analysis...",
    "  Coverage: 68% -> 82%",
    "  - Above threshold (80%)",
    "-> Coverage improved",
    "-> All 2 fixes applied",
    "-> Running full test suite...",
    "  - 49 tests passed",
    "-> Sending back to Agent 3",
  ],
];

export const QA_TABS = [
  { id: "timeline", label: "Test Timeline" },
  { id: "fixlog", label: "Fix Log" },
  { id: "overview", label: "Overview" },
  { id: "unit", label: "Unit Testing" },
  { id: "integration", label: "Integration" },
  { id: "api", label: "API Contracts" },
  { id: "bugs", label: "Bug Reports" },
];

export function CodeLogAnimation({ round, onDone }) {
  const [visibleLogs, setVisibleLogs] = useState([]);
  const ref = useRef(null);
  const logs = CODE_LOG_TEMPLATES[Math.min(round, CODE_LOG_TEMPLATES.length - 1)] || [];

  useEffect(() => {
    setVisibleLogs([]);
    let index = 0;

    const interval = setInterval(() => {
      if (index < logs.length) {
        setVisibleLogs((current) => [...current, logs[index]]);
        index += 1;
        return;
      }

      clearInterval(interval);
      if (onDone) {
        setTimeout(onDone, 1500);
      }
    }, 400);

    return () => clearInterval(interval);
  }, [logs, onDone, round]);

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [visibleLogs]);

  return (
    <div ref={ref} className="bg-gray-900 rounded-xl border border-gray-700 p-4 font-mono h-64 overflow-y-auto shadow-inner">
      {visibleLogs.map((log, index) => (
        <p
          key={`${log}-${index}`}
          className={`text-[11px] leading-6 ${
            log.includes("passed") || log.includes("improved")
              ? "text-[#53C062]"
              : log.startsWith("->")
                ? "text-blue-400"
                : log.startsWith("  -")
                  ? "text-gray-400"
                  : "text-gray-500"
          }`}
          style={{ animation: "fadeIn 0.3s ease forwards" }}
        >
          {log}
        </p>
      ))}
    </div>
  );
}

export function QaHeader({ qaScore, round, showFixing, allDone, tab, onChangeTab, bugCount }) {
  return (
    <div className="px-5 pt-4 pb-3 border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
            <span>AgentForge</span>
            <Icon name="ChevronRight" size={10} />
            <span>QA Center</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">QA Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Validate the generated system through structured testing and quality scoring.
          </p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <div className="text-right">
            <p className="text-xs text-gray-400">QA Score</p>
            <p className={`text-2xl font-bold ${qaScore >= 90 ? "text-[#53C062]" : qaScore >= 80 ? "text-amber-600" : "text-red-600"}`}>
              {qaScore}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-400">Round</p>
            <p className="text-2xl font-bold text-gray-900">{round + 1}/3</p>
          </div>
          {showFixing && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1f6feb]/10 rounded-lg border border-[#1f6feb]/30">
              <Icon name="Loader2" size={36} />
              <span className="text-xs font-medium text-[#1f6feb]">Agent 2 Fixing...</span>
            </div>
          )}
          {allDone && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-[#53C062]/10 text-[#53C062] text-xs font-medium rounded-lg border border-[#53C062]/30">
              <Icon name="CheckCircle2" size={13} /> QA Passed
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-1 mt-3 border-b border-gray-200 -mb-3">
        {QA_TABS.map((item) => {
          const count =
            item.id === "fixlog" ? (showFixing ? 1 : 0) : item.id === "bugs" ? bugCount : 0;

          return (
            <button
              key={item.id}
              onClick={() => onChangeTab(item.id)}
              className={`px-3 py-2 text-xs font-medium transition-all border-b-2 -mb-px ${
                tab === item.id ? "border-[#1f6feb] text-[#1f6feb]" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {item.label}
              {count > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-[#1f6feb] text-white">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function RoundHistory({ roundHistory }) {
  if (!roundHistory.length) {
    return null;
  }

  return (
    <div className="mb-5 space-y-2">
      {roundHistory.map((item) => (
        <div
          key={`round-${item.round}`}
          className={`flex items-center gap-3 p-3 rounded-xl border text-xs ${item.bugs > 0 ? "bg-amber-50 border-amber-200" : "bg-[#53C062]/10 border-[#53C062]/20"}`}
        >
          <Icon
            name={item.bugs > 0 ? "AlertTriangle" : "CheckCircle2"}
            size={14}
            className={item.bugs > 0 ? "text-amber-600" : "text-[#53C062]"}
          />
          <span className={`font-medium ${item.bugs > 0 ? "text-amber-700" : "text-[#53C062]"}`}>
            Round {item.round + 1}
          </span>
          <span className="text-gray-500">Score: {item.score}%</span>
          <span className="text-gray-500">
            {item.bugs > 0 ? `${item.bugs} bugs -> sent to Agent 2` : "All tests passed"}
          </span>
        </div>
      ))}
    </div>
  );
}

export function TimelinePane({ round, testStep, testDone, showFixing, fixingRound, roundHistory, bugs, qaScore, allDone, onFixDone }) {
  return (
    <div className="max-w-2xl">
      <RoundHistory roundHistory={roundHistory} />

      {!showFixing && !allDone && (
        <div className="flex items-center gap-2 mb-4">
          <span className="w-2 h-2 rounded-full bg-[#1f6feb] animate-pulse" />
          <p className="text-xs font-semibold text-gray-700">Round {round + 1} - Testing Cycle</p>
        </div>
      )}

      {showFixing && (
        <div className="mb-5">
          <div className="flex items-center gap-3 mb-3 p-3 bg-[#1f6feb]/5 rounded-xl border border-[#1f6feb]/20">
            <div className="flex items-center justify-center flex-shrink-0 min-w-[72px]">
              <Icon name="Loader2" size={72} />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-800">Agent 2 - Bug Fix Round {fixingRound + 1}</p>
              <p className="text-xs text-gray-500">Applying patches and re-validating in Builder Studio...</p>
            </div>
          </div>
          <CodeLogAnimation round={fixingRound} onDone={onFixDone} />
        </div>
      )}

      {!showFixing && (
        <div className="space-y-1">
          {TEST_STEPS.map((step, index) => {
            const done = index <= testStep;
            const active = index === testStep && !testDone;

            return (
              <div key={step.label} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center border-2 flex-shrink-0 transition-all duration-500 ${
                      done ? "border-[#53C062] bg-[#53C062]/10" : active ? "border-[#1f6feb] bg-white" : "border-gray-200 bg-white"
                    }`}
                  >
                    {done ? (
                      <Icon name="Check" size={13} className="text-[#53C062]" />
                    ) : active ? (
                      <Icon name="Loader2" size={13} className="text-[#1f6feb] animate-spin" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-gray-200" />
                    )}
                  </div>
                  {index < TEST_STEPS.length - 1 && (
                    <div className={`w-px flex-1 my-0.5 ${done ? "bg-[#53C062]/30" : "bg-gray-100"}`} style={{ minHeight: 16 }} />
                  )}
                </div>
                <div className="pb-3 flex-1">
                  <p className={`text-xs font-semibold ${done ? "text-gray-900" : active ? "text-[#1f6feb]" : "text-gray-300"}`}>
                    {step.label}
                  </p>
                  <p className={`text-xs mt-0.5 ${done ? "text-gray-500" : "text-gray-300"}`}>{step.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {testDone && bugs.length === 0 && !showFixing && (
        <div className="mt-4 p-4 bg-[#53C062]/10 rounded-xl border border-[#53C062]/20 flex items-center gap-3">
          <Icon name="CheckCircle2" size={18} className="text-[#53C062]" />
          <div>
            <p className="text-sm font-semibold text-gray-800">All tests passed! QA Score: {qaScore}%</p>
            <p className="text-xs text-gray-500 mt-0.5">Auto-navigating to DevOps Center...</p>
          </div>
        </div>
      )}
    </div>
  );
}

export function FixLogPane({ fixingRound }) {
  return (
    <div className="max-w-2xl">
      <p className="text-xs text-gray-500 mb-3">Detailed fix log from Agent 2 Builder Studio</p>
      <CodeLogAnimation round={fixingRound} />
    </div>
  );
}

export function OverviewPane() {
  return (
    <div>
      <div className="grid grid-cols-4 gap-3 mb-5">
        <KPICard label="QA Score" value="94%" color="green" icon="Star" />
        <KPICard label="Unit Pass Rate" value="100%" color="green" icon="CheckCircle2" />
        <KPICard label="Integration Pass Rate" value="100%" color="green" icon="Link2" />
        <KPICard label="Open Bugs" value="0" color="green" icon="Bug" />
      </div>
      <Card className="p-4">
        <p className="text-xs font-semibold text-gray-900 mb-3">Test Matrix</p>
        <Table
          cols={["Module", "Unit", "Integration", "API", "Status"]}
          rows={[
            ["Authentication", "Pass", "Pass", "Pass", <Badge key="auth" color="green">Passing</Badge>],
            ["User Management", "Pass", "Pass", "Pass", <Badge key="user" color="green">Passing</Badge>],
            ["Booking Flow", "Pass", "Pass", "Pass", <Badge key="booking" color="green">Passing</Badge>],
            ["Payment Flow", "Pass", "Pass", "Pass", <Badge key="payment" color="green">Passing</Badge>],
            ["Notifications", "Pass", "Pass", "Pass", <Badge key="notification" color="green">Passing</Badge>],
            ["Reporting", "Pass", "Pass", "Pass", <Badge key="reporting" color="green">Passing</Badge>],
          ]}
        />
      </Card>
    </div>
  );
}

export function BugReportsPane({ bugs, showFixing }) {
  if (!bugs.length && !showFixing) {
    return (
      <div className="text-center py-12">
        <Icon name="CheckCircle2" size={36} className="text-[#53C062] mx-auto mb-3" />
        <p className="text-sm font-medium text-gray-600">No open bugs - all resolved</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-w-2xl">
      {bugs.map((bug) => (
        <Card key={bug.id} className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-xs font-bold text-red-600">{bug.id}</span>
                <Badge color={bug.severity === "High" ? "red" : bug.severity === "Medium" ? "amber" : "default"}>
                  {bug.severity}
                </Badge>
              </div>
              <p className="text-xs font-semibold text-gray-900">{bug.title}</p>
              <p className="text-xs text-gray-500 mt-0.5">{bug.desc}</p>
              <p className="text-xs text-[#1f6feb] mt-1">Fix: {bug.fix}</p>
            </div>
            {showFixing ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#1f6feb]/10 text-[#1f6feb]">
                <Icon name="Loader2" size={28} />
                Fixing
              </span>
            ) : (
              <Badge color="red">Open</Badge>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

export function ApiContractsPane() {
  return (
    <div className="max-w-3xl">
      <p className="text-xs text-gray-500 mb-3">All API contracts validated successfully after fix rounds.</p>
      <Table
        cols={["Method", "Route", "Service", "Status"]}
        rows={[
          [<span key="login-method" className="text-[#53C062] font-bold font-mono">POST</span>, "/auth/login", "auth-service", <Badge key="login-badge" color="green">Valid</Badge>],
          [<span key="register-method" className="text-[#53C062] font-bold font-mono">POST</span>, "/auth/register", "auth-service", <Badge key="register-badge" color="green">Valid</Badge>],
          [<span key="rooms-method" className="text-[#1f6feb] font-bold font-mono">GET</span>, "/rooms", "room-service", <Badge key="rooms-badge" color="green">Valid</Badge>],
          [<span key="bookings-method" className="text-[#53C062] font-bold font-mono">POST</span>, "/bookings", "booking-service", <Badge key="bookings-badge" color="green">Valid</Badge>],
          [<span key="payments-method" className="text-[#53C062] font-bold font-mono">POST</span>, "/payments/checkout", "payment-service", <Badge key="payments-badge" color="green">Valid</Badge>],
        ]}
      />
    </div>
  );
}

export function UnitTestingPane() {
  const tests = [
    "test_user_login_success",
    "test_duplicate_email_rejected",
    "test_room_search_by_type",
    "test_booking_creation",
    "test_booking_schema_valid",
    "test_payment_checkout",
    "test_payment_webhook_idempotent",
    "test_notification_dispatch",
  ];

  return (
    <div className="space-y-2 max-w-2xl">
      {tests.map((testName) => (
        <Card key={testName} className="p-3 border-l-2 border-l-[#53C062]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-gray-700">{testName}</span>
            <Badge color="green">Pass</Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function IntegrationPane() {
  const flows = [
    {
      name: "User registration -> login -> token",
      steps: ["POST /register", "POST /login", "JWT received"],
    },
    {
      name: "Browse rooms -> book -> payment",
      steps: ["GET /rooms", "POST /bookings", "POST /payments/checkout"],
    },
    {
      name: "Admin action -> notification",
      steps: ["PATCH /admin/rooms", "POST /notifications"],
    },
  ];

  return (
    <div className="space-y-3 max-w-2xl">
      {flows.map((flow) => (
        <Card key={flow.name} className="p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-900">{flow.name}</p>
            <Badge color="green">Pass</Badge>
          </div>
          <div className="flex items-center gap-2">
            {flow.steps.map((step, index) => (
              <div key={step} className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#53C062]/10 border border-[#53C062]/20 text-[10px] font-mono text-[#53C062]">
                  {step}
                </div>
                {index < flow.steps.length - 1 && <Icon name="ArrowRight" size={11} className="text-gray-300" />}
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

export function QaInspector({ round, qaScore, bugs, showFixing, roundHistory }) {
  return (
    <InspectorPanel title="QA Inspector">
      <InspectorSection title="Current Round">
        <InspectorRow label="Round" value={`${round + 1} / 3`} />
        <InspectorRow label="QA Score" value={`${qaScore}%`} />
        <InspectorRow label="Open Bugs" value={showFixing ? "Fixing..." : bugs.length} />
        <ProgressBar value={qaScore} color={qaScore >= 90 ? "green" : qaScore >= 80 ? "amber" : "blue"} className="mt-2" />
      </InspectorSection>
      {roundHistory.length > 0 && (
        <InspectorSection title="Fix Rounds">
          {roundHistory.map((item) => (
            <InspectorRow
              key={`inspector-round-${item.round}`}
              label={`Round ${item.round + 1}`}
              value={item.bugs > 0 ? `${item.bugs} bugs fixed` : "Passed"}
            />
          ))}
        </InspectorSection>
      )}
      {showFixing && (
        <InspectorSection title="Agent 2 Status">
          <div className="flex items-center gap-2 text-xs text-[#1f6feb]">
            <Icon name="Loader2" size={28} />
            Fixing bugs...
          </div>
        </InspectorSection>
      )}
    </InspectorPanel>
  );
}
