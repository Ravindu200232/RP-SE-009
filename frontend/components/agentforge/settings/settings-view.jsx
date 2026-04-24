import React, { useState } from "react";
import {
  SettingsHeader,
  ModelSettingsSection,
  WorkspaceSettingsSection,
  GithubSettingsSection,
  AwsSettingsSection,
  AppearanceSettingsSection,
  AboutSettingsCard,
} from "./settings-sections";

function SettingsView({ onToast }) {
  const [settings, setSettings] = useState({
    ollamaUrl: "http://localhost:11434",
    model1: "llama3:70b",
    model2: "codellama:34b",
    model3: "llama3:8b",
    model4: "mistral:7b",
    workspacePath: "/Users/dev/agentforge/workspaces",
    autoSave: "30",
    logRetention: "30 days",
    artifactFolder: "/Users/dev/agentforge/artifacts",
    ghOwner: "stayease-demo",
    ghRepo: "stayease-hotel-booking",
    ghBranch: "main",
    ghToken: "ghp_***masked***",
    awsRegion: "us-east-1",
    awsTarget: "ECS Fargate",
    theme: "Dark",
    accent: "#1f6feb",
    font: "Geist",
    density: "Comfortable",
    sidebar: "Icon + Label",
  });

  const setValue = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const save = (section) => onToast(`${section} settings saved successfully.`, "success");
  const test = (label) => onToast(`Testing ${label} connection...`, "success");

  return (
    <div className="flex h-full overflow-y-auto p-5 flex-col">
      <SettingsHeader />
      <div className="grid grid-cols-2 gap-5 max-w-5xl">
        <ModelSettingsSection settings={settings} setValue={setValue} onSave={() => save("Model")} onTest={test} />
        <WorkspaceSettingsSection settings={settings} setValue={setValue} onSave={() => save("Workspace")} />
        <GithubSettingsSection settings={settings} setValue={setValue} onSave={() => save("GitHub")} onTest={test} />
        <AwsSettingsSection settings={settings} setValue={setValue} onSave={() => save("AWS")} onTest={test} />
        <AppearanceSettingsSection settings={settings} setValue={setValue} onSave={() => save("Appearance")} />
        <AboutSettingsCard />
      </div>
    </div>
  );
}

export default SettingsView;
