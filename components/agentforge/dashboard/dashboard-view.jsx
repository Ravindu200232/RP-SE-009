import React from "react";
import { AF_DATA } from "../core/data";
import {
  DashboardHeader,
  DashboardKpiGrid,
  DashboardOverviewGrid,
  RecentBuildsTable,
  DashboardBottomRow,
  DashboardInspector,
} from "./dashboard-sections";

function DashboardView({ onNavigate }) {
  const { projects, pipeline, builds, activity } = AF_DATA;

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-5">
        <DashboardHeader onNavigate={onNavigate} />
        <DashboardKpiGrid />
        <DashboardOverviewGrid project={projects[0]} pipeline={pipeline} onNavigate={onNavigate} />
        <RecentBuildsTable builds={builds} onNavigate={onNavigate} />
        <DashboardBottomRow activity={activity} onNavigate={onNavigate} />
      </div>
      <DashboardInspector onNavigate={onNavigate} />
    </div>
  );
}

export default DashboardView;
