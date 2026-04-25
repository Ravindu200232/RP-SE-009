"use client";

import React from "react";
import AuthView from "./auth-view";

export default function AuthScreen({ initialMode = "login" }) {
  return <AuthView initialMode={initialMode} />;
}
