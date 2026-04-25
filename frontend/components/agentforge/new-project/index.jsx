"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import NewProjectView from "./new-project-view";

export default function NewProjectScreen() {
  return (
    <StudioFrame pageId="new-project">
      <NewProjectView />
    </StudioFrame>
  );
}
