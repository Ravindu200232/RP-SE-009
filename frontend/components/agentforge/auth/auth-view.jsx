"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthFormCard, AuthHeroCopy, AUTH_VISUALS, AuthVisualShowcase } from "./auth-sections";
import {
  loadActiveSession,
  loadStoredCredentials,
  saveActiveSession,
  saveStoredCredentials,
} from "../core/auth-storage";

const DEFAULT_FORMS = {
  login: {
    email: "",
    password: "",
  },
  signup: {
    email: "",
    password: "",
  },
};

function AuthView({ initialMode = "login" }) {
  const router = useRouter();
  const [mode, setMode] = useState(initialMode);
  const [formState, setFormState] = useState(DEFAULT_FORMS);
  const [activeVisualId, setActiveVisualId] = useState(initialMode === "login" ? "business" : "hello");
  const [savedAccountEmail, setSavedAccountEmail] = useState("");
  const [feedback, setFeedback] = useState({ type: "", message: "" });

  const activeForm = useMemo(() => formState[mode] || DEFAULT_FORMS[mode], [formState, mode]);

  useEffect(() => {
    const storedCredentials = loadStoredCredentials();
    const activeSession = loadActiveSession();

    if (storedCredentials?.email) {
      setSavedAccountEmail(storedCredentials.email);
      setFormState((current) => ({
        ...current,
        login: {
          ...current.login,
          email: storedCredentials.email,
        },
        signup: {
          ...current.signup,
          email: storedCredentials.email,
        },
      }));
    }

    if (activeSession?.email) {
      setSavedAccountEmail(activeSession.email);
      setFeedback({
        type: "success",
        message: `Last signed in as ${activeSession.email}. Login again to continue to your dashboard.`,
      });
    }
  }, []);

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    setActiveVisualId(nextMode === "login" ? "business" : "hello");
    setFeedback({ type: "", message: "" });
  };

  const handleFieldChange = (field, value) => {
    setFormState((current) => ({
      ...current,
      [mode]: {
        ...current[mode],
        [field]: value,
      },
    }));
    setFeedback({ type: "", message: "" });
  };

  const isValidGmail = (email) => {
    return /^[^\s@]+@gmail\.com$/i.test(email);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const email = activeForm.email.trim().toLowerCase();
    const password = activeForm.password.trim();

    if (!isValidGmail(email)) {
      setFeedback({ type: "error", message: "Please use a valid Gmail address." });
      return;
    }

    if (!password) {
      setFeedback({ type: "error", message: "Please enter a password." });
      return;
    }

    if (mode === "signup") {
      saveStoredCredentials({ email, password });
      setSavedAccountEmail(email);
      setFormState((current) => ({
        ...current,
        login: {
          email,
          password,
        },
        signup: {
          email,
          password,
        },
      }));
      setMode("login");
      setActiveVisualId("business");
      setFeedback({
        type: "success",
        message: "Account created locally. Use the Login tab to enter the dashboard.",
      });
      return;
    }

    const storedCredentials = loadStoredCredentials();

    if (!storedCredentials?.email) {
      setFeedback({ type: "error", message: "Create an account first using the Sign Up tab." });
      return;
    }

    if (storedCredentials.email !== email || storedCredentials.password !== password) {
      setFeedback({ type: "error", message: "Email or password does not match the saved local account." });
      return;
    }

    saveActiveSession({ email });
    setSavedAccountEmail(email);
    router.push("/dashboard");
  };

  const handleDemo = () => {
    saveActiveSession({ email: savedAccountEmail || "demo@gmail.com" });
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-white">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(17,17,17,0.04)_1px,transparent_1px)] bg-[length:18rem_100%]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.78),transparent_34%),radial-gradient(circle_at_82%_14%,rgba(246,222,115,0.14),transparent_18%)]" />

      <div className="relative z-10 mx-auto grid min-h-screen max-w-[1600px] items-start gap-10 px-6 py-8 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:items-center lg:px-10 lg:py-10 xl:px-14 xl:py-12">
        <div className="flex flex-col justify-center">
          <div className="mb-7 inline-flex items-center gap-3">
            <img src="/logo.png" alt="AgentForge Studio logo" className="h-10 w-auto object-contain" />
            <div>
              <p className="text-lg font-black leading-none text-black">AgentForge Studio</p>
              <p className="mt-1 text-xs font-semibold uppercase tracking-[0.26em] text-black/38">
                AI Agent Workspace
              </p>
            </div>
          </div>

          <AuthHeroCopy />

          <AuthFormCard
            mode={mode}
            form={activeForm}
            onModeChange={handleModeChange}
            onFieldChange={handleFieldChange}
            onSubmit={handleSubmit}
            onDemo={handleDemo}
            savedAccountEmail={savedAccountEmail}
            feedback={feedback}
          />
        </div>

        <div className="flex w-full items-start justify-center pb-2 lg:items-center lg:justify-end">
          <AuthVisualShowcase
            visuals={AUTH_VISUALS}
            activeVisualId={activeVisualId}
            onSelectVisual={setActiveVisualId}
          />
        </div>
      </div>
    </div>
  );
}

export default AuthView;
