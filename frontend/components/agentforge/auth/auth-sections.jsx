"use client";

import React from "react";
import { Icon } from "../core/ui";

export const AUTH_VISUALS = [
  {
    id: "hello",
    title: "Welcome Agent",
    subtitle: "Instant onboarding for new builders and founders.",
    src: "/3D%20Hello%20GIF%20by%20L3S%20Research%20Center.gif",
  },
  {
    id: "business",
    title: "Business Agent",
    subtitle: "Production-ready automation for teams and operators.",
    src: "/3D%20Business%20GIF%20by%20L3S%20Research%20Center.gif",
  },
  {
    id: "robot",
    title: "Creative Agent",
    subtitle: "Guided building for specs, prompts, and releases.",
    src: "/3D%20Robot%20GIF%20by%20L3S%20Research%20Center.gif",
  },
  {
    id: "presenter",
    title: "Demo Agent",
    subtitle: "Present, test, and share agent workflows with clarity.",
    src: "/3D%20Robot%20GIF%20by%20L3S%20Research%20Center%20(1).gif",
  },
];

const FORM_FIELDS = {
  login: [
    { id: "email", label: "Gmail Address", type: "email", placeholder: "you@gmail.com" },
    { id: "password", label: "Password", type: "password", placeholder: "Enter your password" },
  ],
  signup: [
    { id: "email", label: "Gmail Address", type: "email", placeholder: "you@gmail.com" },
    { id: "password", label: "Create Password", type: "password", placeholder: "Create a secure password" },
  ],
};

function AuthModeTabs({ mode, onModeChange }) {
  return (
    <div className="inline-flex flex-wrap gap-2">
      {[
        { id: "signup", label: "Sign Up" },
        { id: "login", label: "Login" },
      ].map((tab) => {
        const active = tab.id === mode;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onModeChange(tab.id)}
            className={`min-w-[104px] rounded-full px-4 py-2 text-sm font-semibold transition-all ${
              active
                ? "bg-black text-white"
                : "bg-transparent text-black/68 hover:text-black"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function AuthField({ field, value, onChange }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-black/45">
        {field.label}
      </span>
      <input
        type={field.type}
        value={value}
        onChange={(event) => onChange(field.id, event.target.value)}
        placeholder={field.placeholder}
        className="h-12 w-full border-0 border-b border-black/18 bg-transparent px-0 text-sm text-black outline-none transition placeholder:text-black/35 focus:border-black"
      />
    </label>
  );
}

export function AuthHeroCopy() {
  return (
    <div className="max-w-[34rem]">
      <div className="space-y-1 text-black">
        <h1 className="text-[2.9rem] font-black leading-[0.94] tracking-[-0.05em] sm:text-[3.6rem] lg:text-[4.35rem]">
          <span className="block">AI Agents</span>
          <span className="block">Creation With</span>
          <span className="block">In Seconds</span>
        </h1>
      </div>

      <p className="mt-5 max-w-xl text-[15px] leading-7 text-black/62 sm:text-base">
        Crafting smart solutions in moments, therefore revolutionizing efficiency and innovation.
        Deploy intelligent agents that work for you around the clock.
      </p>
    </div>
  );
}

export function AuthFormCard({
  mode,
  form,
  onModeChange,
  onFieldChange,
  onSubmit,
  onDemo,
  savedAccountEmail,
  feedback,
}) {
  const isLogin = mode === "login";
  const fields = FORM_FIELDS[mode];

  return (
    <div className="mt-8 max-w-[33rem]">
      <div className="flex flex-wrap items-center gap-4">
        <AuthModeTabs mode={mode} onModeChange={onModeChange} />
      </div>

      <div className="mt-6">
        <p className="text-[1.75rem] font-bold text-black">
          {isLogin ? "Welcome back to AgentForge Studio" : "Create your AgentForge Studio workspace"}
        </p>
        <p className="mt-2 text-sm leading-6 text-black/56">
          {isLogin
            ? "Log in to continue building, testing, and deploying agents from one studio."
            : "Start a new workspace, invite your team, and generate your first AI agent in minutes."}
        </p>
      </div>

      {savedAccountEmail && (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-black/40">Saved Account</p>
          <p className="mt-1 text-sm font-medium text-black">{savedAccountEmail}</p>
          <p className="mt-1 text-xs text-black/54">Stored locally in this browser for quick login to the demo dashboard.</p>
        </div>
      )}

      {feedback?.message && (
        <div
          className={`mt-4 text-sm font-medium ${
            feedback.type === "error" ? "text-red-600" : "text-[#2d960c]"
          }`}
        >
          {feedback.message}
        </div>
      )}

      <form className="mt-6 space-y-3.5" onSubmit={onSubmit}>
        {fields.map((field) => (
          <AuthField
            key={field.id}
            field={field}
            value={form[field.id] || ""}
            onChange={onFieldChange}
          />
        ))}

        {isLogin && (
          <div className="flex items-center justify-between gap-4 px-1 text-sm">
            <label className="flex items-center gap-2 text-black/58">
              <input type="checkbox" defaultChecked className="h-4 w-4 rounded border-black/20 accent-black" />
              Keep me signed in
            </label>
            <button type="button" className="font-semibold text-black underline underline-offset-4">
              Forgot password?
            </button>
          </div>
        )}

        {!isLogin && <p className="text-sm leading-6 text-black/58">Use a Gmail address and password. We store it locally in this browser so you can log in and continue to the dashboard.</p>}

        <div className="grid gap-3 pt-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <button
            type="submit"
            className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-black px-5 text-sm font-semibold text-white transition hover:bg-black/88"
          >
            <Icon name={isLogin ? "ArrowRight" : "Sparkles"} size={16} />
            {isLogin ? "Login to Dashboard" : "Create Local Account"}
          </button>

          <button
            type="button"
            onClick={onDemo}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-black/14 bg-transparent px-5 text-sm font-semibold text-black transition hover:border-black/28 hover:bg-black/[0.03]"
          >
            <Icon name="Play" size={14} />
            Continue Demo
          </button>
        </div>
      </form>
    </div>
  );
}

function VisualThumb({ visual, active, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(visual.id)}
      className="h-full px-2 py-2 text-left transition-opacity hover:opacity-100"
    >
      <div className={`flex h-full flex-col ${active ? "opacity-100" : "opacity-88"}`}>
        <div className="mb-4 flex min-h-[10rem] items-center justify-center overflow-visible">
          <img src={visual.src} alt={visual.title} className="h-[11.5rem] w-full scale-[1.08] object-contain" />
        </div>
        <div className="flex-1">
          <p className="text-lg font-semibold text-black">{visual.title}</p>
          <p className="mt-1.5 text-sm leading-6 text-black/55">{visual.subtitle}</p>
        </div>
      </div>
    </button>
  );
}

export function AuthVisualShowcase({ visuals, activeVisualId, onSelectVisual }) {
  return (
    <div className="w-full">
      <div className="grid gap-6 sm:grid-cols-2">
        {visuals.map((visual) => (
          <VisualThumb
            key={visual.id}
            visual={visual}
            active={visual.id === activeVisualId}
            onSelect={onSelectVisual}
          />
        ))}
      </div>
    </div>
  );
}
