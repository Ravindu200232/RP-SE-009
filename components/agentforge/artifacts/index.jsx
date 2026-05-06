"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import ArtifactsView from "./artifacts-view";

export default function ArtifactsScreen() {
  return (
    <StudioFrame pageId="artifacts">
      <ArtifactsView />
    </StudioFrame>
  );
}
