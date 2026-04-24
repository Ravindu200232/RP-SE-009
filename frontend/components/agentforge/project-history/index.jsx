"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import ProjectHistoryView from "./project-history-view";

export default function ProjectHistoryScreen() {
  return (
    <StudioFrame pageId="project-history">
      <ProjectHistoryView />
    </StudioFrame>
  );
}
