"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import SettingsView from "./settings-view";

export default function SettingsScreen() {
  return (
    <StudioFrame pageId="settings">
      <SettingsView />
    </StudioFrame>
  );
}
