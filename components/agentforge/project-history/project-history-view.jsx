import React, { useState } from "react";
import {
  getFilteredProjects,
  ProjectHistoryHeader,
  ProjectStatsGrid,
  ProjectHistoryFilters,
  ProjectCards,
} from "./project-history-sections";

function ProjectHistoryView({ onNavigate, onToast }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  const filteredProjects = getFilteredProjects(filter, search);

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      <div className="flex-1 overflow-y-auto p-5">
        <ProjectHistoryHeader onNewProject={() => onNavigate("new-project")} />
        <ProjectStatsGrid />
        <ProjectHistoryFilters
          search={search}
          filter={filter}
          onSearchChange={setSearch}
          onFilterChange={setFilter}
        />
        <ProjectCards
          projects={filteredProjects}
          selectedId={selected}
          onSelectProject={setSelected}
          onNavigate={onNavigate}
          onArchive={(message) => onToast(message, "success")}
        />
      </div>
    </div>
  );
}

export default ProjectHistoryView;
