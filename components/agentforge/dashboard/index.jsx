"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import DashboardView from "./dashboard-view";

export default function DashboardScreen() {
  return (
    <StudioFrame pageId="dashboard">
      <DashboardView />
    </StudioFrame>
  );
}
