"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import DesignSelectorView from "./design-selector-view";

export default function DesignSelectorScreen() {
  return (
    <StudioFrame pageId="design-selector">
      <DesignSelectorView />
    </StudioFrame>
  );
}
