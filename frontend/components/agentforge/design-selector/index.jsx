"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import SandboxStudio from "./sandbox-studio";

export default function DesignSelectorScreen() {
  return (
    <StudioFrame pageId="design-selector">
      <SandboxStudio />
    </StudioFrame>
  );
}
