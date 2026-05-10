"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import VersionsView from "./versions-view";

export default function VersionsScreen() {
  return (
    <StudioFrame pageId="versions">
      <VersionsView />
    </StudioFrame>
  );
}
