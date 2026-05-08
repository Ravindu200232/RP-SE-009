"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import MemoryView from "./memory-view";

export default function MemoryScreen() {
  return (
    <StudioFrame pageId="memory">
      <MemoryView />
    </StudioFrame>
  );
}
