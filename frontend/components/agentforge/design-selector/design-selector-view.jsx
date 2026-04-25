import React, { useState } from "react";
import {
  DesignSelectorHeader,
  ComponentCategorySidebar,
  ComponentOptionsGrid,
  DesignTemplateGrid,
  ApprovalSummaryPanel,
} from "./design-selector-sections";

function DesignSelectorView({ onNavigate, onToast }) {
  const [view, setView] = useState("components");
  const [activeCategory, setActiveCategory] = useState("header");
  const [selections, setSelections] = useState({
    header: "h1",
    footer: "f1",
    nav: "n1",
    card: "c1",
  });
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  const approve = () => {
    onToast("Design approved. Frontend layout decisions will guide Agent 2 generation.", "success");
    setTimeout(() => onNavigate("agent2"), 800);
  };

  const mainView =
    view === "components" ? (
      <div className="flex flex-1 overflow-hidden">
        <ComponentCategorySidebar
          activeCategory={activeCategory}
          selections={selections}
          onSelectCategory={setActiveCategory}
        />
        <ComponentOptionsGrid
          activeCategory={activeCategory}
          selections={selections}
          onSelectOption={(category, optionId) =>
            setSelections((current) => ({ ...current, [category]: optionId }))
          }
        />
      </div>
    ) : (
      <DesignTemplateGrid selectedTemplate={selectedTemplate} onSelectTemplate={setSelectedTemplate} />
    );

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <DesignSelectorHeader
          view={view}
          onChangeView={setView}
          onApprove={approve}
          onNavigate={onNavigate}
        />
        {mainView}
      </div>
      <ApprovalSummaryPanel
        selections={selections}
        selectedTemplate={selectedTemplate}
        onApprove={approve}
        onNavigate={onNavigate}
      />
    </div>
  );
}

export default DesignSelectorView;
