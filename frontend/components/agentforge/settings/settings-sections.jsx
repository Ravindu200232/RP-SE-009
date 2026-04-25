import React from "react";
import { Icon, Btn, Card, Input, Select, PageHeader } from "../core/ui";

export function SettingsHeader() {
  return (
    <PageHeader
      title="Settings"
      subtitle="Configure models, workspace behavior, integrations, appearance, and export preferences."
      breadcrumb={["AgentForge Studio", "Settings"]}
    />
  );
}

export function SettingsSectionCard({ title, subtitle, children, onSave, saveLabel = "Save" }) {
  return (
    <Card className="p-5 mb-4">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm font-semibold text-[#e6edf3]">{title}</p>
          {subtitle && <p className="text-xs text-[#484f58] mt-0.5">{subtitle}</p>}
        </div>
        {onSave && (
          <Btn size="sm" icon="Save" variant="primary" onClick={onSave}>
            {saveLabel}
          </Btn>
        )}
      </div>
      {children}
    </Card>
  );
}

export function ModelSettingsSection({ settings, setValue, onSave, onTest }) {
  return (
    <div className="col-span-2">
      <SettingsSectionCard title="Model Settings" subtitle="Configure local LLM endpoints for each agent." onSave={onSave}>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Ollama Base URL" value={settings.ollamaUrl} onChange={(value) => setValue("ollamaUrl", value)} className="col-span-2" />
          <Input label="Agent 1 - Requirement Analyzer" value={settings.model1} onChange={(value) => setValue("model1", value)} />
          <Input label="Agent 2 - Build Studio" value={settings.model2} onChange={(value) => setValue("model2", value)} />
          <Input label="Agent 3 - QA Center" value={settings.model3} onChange={(value) => setValue("model3", value)} />
          <Input label="Agent 4 - DevOps Center" value={settings.model4} onChange={(value) => setValue("model4", value)} />
        </div>
        <div className="flex gap-2 mt-3">
          <Btn size="xs" icon="Zap" onClick={() => onTest("Ollama")}>Test Connection</Btn>
          <Btn size="xs" icon="List">List Local Models</Btn>
        </div>
        <div className="mt-3 p-2.5 bg-[#0a3d2e]/20 rounded-lg border border-[#3fb950]/20">
          <p className="text-[10px] text-[#3fb950]">Ollama running - 4 models available - Last checked 2 min ago</p>
        </div>
      </SettingsSectionCard>
    </div>
  );
}

export function WorkspaceSettingsSection({ settings, setValue, onSave }) {
  return (
    <SettingsSectionCard title="Workspace Settings" subtitle="File system paths and auto-save configuration." onSave={onSave}>
      <div className="space-y-3">
        <div>
          <p className="text-xs font-medium text-[#8b949e] mb-1.5">Workspace Path</p>
          <div className="flex gap-2">
            <input value={settings.workspacePath} onChange={(event) => setValue("workspacePath", event.target.value)} className="flex-1 bg-[#0d1117] border border-[#21262d] rounded-lg px-3 py-2 text-xs text-[#e6edf3] font-mono focus:outline-none focus:border-[#388bfd]" />
            <Btn size="sm" icon="FolderOpen">Browse</Btn>
          </div>
        </div>
        <div>
          <p className="text-xs font-medium text-[#8b949e] mb-1.5">Artifact Output Folder</p>
          <div className="flex gap-2">
            <input value={settings.artifactFolder} onChange={(event) => setValue("artifactFolder", event.target.value)} className="flex-1 bg-[#0d1117] border border-[#21262d] rounded-lg px-3 py-2 text-xs text-[#e6edf3] font-mono focus:outline-none focus:border-[#388bfd]" />
            <Btn size="sm" icon="FolderOpen">Browse</Btn>
          </div>
        </div>
        <Select label="Auto-save Interval" value={`${settings.autoSave}s`} onChange={(value) => setValue("autoSave", value.replace("s", ""))} options={["10s", "30s", "60s", "120s", "Manual"]} />
        <Select label="Log Retention" value={settings.logRetention} onChange={(value) => setValue("logRetention", value)} options={["7 days", "14 days", "30 days", "90 days", "Forever"]} />
      </div>
    </SettingsSectionCard>
  );
}

export function GithubSettingsSection({ settings, setValue, onSave, onTest }) {
  return (
    <SettingsSectionCard title="GitHub Integration" subtitle="Connect to your repository for CI/CD and artifact push." onSave={onSave}>
      <div className="space-y-3">
        <Input label="Repository Owner" value={settings.ghOwner} onChange={(value) => setValue("ghOwner", value)} />
        <Input label="Repository Name" value={settings.ghRepo} onChange={(value) => setValue("ghRepo", value)} />
        <Input label="Default Branch" value={settings.ghBranch} onChange={(value) => setValue("ghBranch", value)} />
        <div>
          <p className="text-xs font-medium text-[#8b949e] mb-1.5">Personal Access Token</p>
          <input type="password" value={settings.ghToken} onChange={(event) => setValue("ghToken", event.target.value)} className="w-full bg-[#0d1117] border border-[#21262d] rounded-lg px-3 py-2 text-xs text-[#e6edf3] font-mono focus:outline-none focus:border-[#388bfd]" />
        </div>
        <div className="p-2.5 bg-[#0a3d2e]/20 rounded-lg border border-[#3fb950]/20">
          <p className="text-[10px] text-[#3fb950]">Connected to stayease-demo/stayease-hotel-booking - Token valid</p>
        </div>
        <div className="flex gap-2">
          <Btn size="xs" icon="Github">Connect GitHub</Btn>
          <Btn size="xs" icon="ShieldCheck" onClick={() => onTest("GitHub")}>Validate Access</Btn>
        </div>
      </div>
    </SettingsSectionCard>
  );
}

export function AwsSettingsSection({ settings, setValue, onSave, onTest }) {
  return (
    <SettingsSectionCard title="AWS Integration" subtitle="Configure deployment target and credentials." onSave={onSave}>
      <div className="space-y-3">
        <Select label="AWS Region" value={settings.awsRegion} onChange={(value) => setValue("awsRegion", value)} options={["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"]} />
        <Select label="Deployment Target" value={settings.awsTarget} onChange={(value) => setValue("awsTarget", value)} options={["ECS Fargate", "EC2 + ALB", "Elastic Beanstalk", "Lambda + API Gateway"]} />
        <div>
          <p className="text-xs font-medium text-[#8b949e] mb-1.5">Credential Status</p>
          <div className="p-2.5 bg-[#0a3d2e]/20 rounded-lg border border-[#3fb950]/20">
            <p className="text-[10px] text-[#3fb950]">AWS CLI credentials configured - IAM role: ecsTaskExecutionRole</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Btn size="xs" icon="Cloud">Connect AWS</Btn>
          <Btn size="xs" icon="ShieldCheck" onClick={() => onTest("AWS")}>Test Deployment Access</Btn>
        </div>
      </div>
    </SettingsSectionCard>
  );
}

export function AppearanceSettingsSection({ settings, setValue, onSave }) {
  const accentColors = ["#1f6feb", "#7c3aed", "#d97706", "#059669", "#db2777", "#0891b2"];

  return (
    <SettingsSectionCard title="Appearance" subtitle="Theme, typography, and layout preferences." onSave={onSave}>
      <div className="space-y-3">
        <Select label="Theme" value={settings.theme} onChange={(value) => setValue("theme", value)} options={["Dark", "Light", "System"]} />
        <Select label="Font Family" value={settings.font} onChange={(value) => setValue("font", value)} options={["Geist", "Inter", "Manrope", "Poppins", "JetBrains Mono"]} />
        <Select label="Density Mode" value={settings.density} onChange={(value) => setValue("density", value)} options={["Compact", "Comfortable", "Spacious"]} />
        <Select label="Sidebar Style" value={settings.sidebar} onChange={(value) => setValue("sidebar", value)} options={["Icon Only", "Icon + Label", "Floating", "Fixed Workspace"]} />
        <div>
          <p className="text-xs font-medium text-[#8b949e] mb-2">Accent Color</p>
          <div className="flex gap-2">
            {accentColors.map((color) => (
              <button key={color} onClick={() => setValue("accent", color)} className={`w-7 h-7 rounded-full border-2 transition-all ${settings.accent === color ? "border-white scale-110" : "border-transparent hover:scale-105"}`} style={{ background: color }} />
            ))}
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Btn size="xs" icon="Paintbrush">Apply Theme</Btn>
          <Btn size="xs" icon="RotateCcw">Restore Defaults</Btn>
        </div>
      </div>
    </SettingsSectionCard>
  );
}

export function AboutSettingsCard() {
  return (
    <div className="col-span-2">
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#1f6feb] to-[#7c3aed] flex items-center justify-center">
              <Icon name="Zap" size={18} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-[#e6edf3]">AgentForge Studio</p>
              <p className="text-xs text-[#484f58]">From software idea to deployment through coordinated AI agents.</p>
              <p className="text-xs text-[#484f58] mt-0.5">Version 1.0.0-alpha - Research Demo Build</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Btn size="xs" icon="RefreshCw">Check for Updates</Btn>
            <Btn size="xs" icon="FileText">View Changelog</Btn>
            <Btn size="xs" icon="HelpCircle">Documentation</Btn>
          </div>
        </div>
      </Card>
    </div>
  );
}
