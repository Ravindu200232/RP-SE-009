import React, { useState } from "react";
import { AF_DATA } from "../core/data";
import {
  VersionsHeader,
  ReleaseTimeline,
  VersionComparisonCard,
  ReleaseNotesCard,
} from "./versions-sections";

function VersionsView({ onToast }) {
  const { versions } = AF_DATA;
  const [selected, setSelected] = useState([]);

  const toggleSelect = (versionId) => {
    setSelected((current) =>
      current.includes(versionId) ? current.filter((item) => item !== versionId) : [...current, versionId],
    );
  };

  return (
    <div className="flex h-full overflow-y-auto p-5 flex-col bg-white">
      <VersionsHeader
        selectedCount={selected.length}
        onCreateRelease={() => onToast("New release created: v1.0.0", "success")}
      />
      <ReleaseTimeline versions={versions} selectedIds={selected} onToggleSelect={toggleSelect} />
      <VersionComparisonCard versions={versions} />
      <ReleaseNotesCard />
    </div>
  );
}

export default VersionsView;
