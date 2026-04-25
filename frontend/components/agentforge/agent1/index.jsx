"use client";

import React from "react";
import StudioFrame from "../layout/studio-frame";
import Agent1View from "./agent1-view";

export default function Agent1Screen() {
  return (
    <StudioFrame pageId="agent1">
      <Agent1View />
    </StudioFrame>
  );
}
