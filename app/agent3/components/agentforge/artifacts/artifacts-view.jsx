import React, { useState } from "react";
import { AF_DATA } from "../core/data";
import {
  ArtifactsHeader,
  ArtifactFilters,
  ArtifactBulkActions,
  ArtifactGrid,
} from "./artifacts-sections";

function ArtifactsView({ onNavigate, onToast }) {
  const { artifacts } = AF_DATA;
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState([]);

  const filteredArtifacts =
    filter === "all" ? artifacts : artifacts.filter((artifact) => artifact.category === filter);

  const toggleSelect = (artifactId) => {
    setSelected((current) =>
      current.includes(artifactId)
        ? current.filter((item) => item !== artifactId)
        : [...current, artifactId],
    );
  };

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-5">
        <ArtifactsHeader
          selectedCount={selected.length}
          onDownloadAll={() => onToast("Preparing full artifact bundle...", "success")}
          onCompareVersions={() => onToast("Version comparison started.", "success")}
        />
        <ArtifactFilters filter={filter} artifactsCount={artifacts.length} onSelectFilter={setFilter} />
        <ArtifactBulkActions selectedCount={selected.length} onClearSelection={() => setSelected([])} />
        <ArtifactGrid
          artifacts={filteredArtifacts}
          selectedIds={selected}
          onToggleSelect={toggleSelect}
          onNavigate={onNavigate}
          onToast={onToast}
        />
      </div>
    </div>
  );
}

export default ArtifactsView;
