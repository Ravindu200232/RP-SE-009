import React from "react";
import { Icon, Btn } from "../core/ui";

const HEADER_OPTIONS = [
  {
    id: "h1",
    label: "Header 1",
    desc: "Logo left - nav center - CTA right",
    preview: (active) => (
      <div className={`flex items-center justify-between px-4 py-2 border-b ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-t-lg`}>
        <div className="w-12 h-3 bg-gray-300 rounded" />
        <div className="flex gap-2">{[0, 1, 2].map((item) => <div key={item} className="w-8 h-2 bg-gray-200 rounded" />)}</div>
        <div className="w-10 h-5 bg-blue-500 rounded-md" />
      </div>
    ),
  },
  {
    id: "h2",
    label: "Header 2",
    desc: "Centered logo - full-width nav below",
    preview: (active) => (
      <div className={`border-b ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-t-lg`}>
        <div className="flex justify-center py-1.5"><div className="w-12 h-3 bg-gray-300 rounded" /></div>
        <div className="flex justify-center gap-3 py-1 border-t border-gray-100">
          {[0, 1, 2, 3].map((item) => <div key={item} className="w-8 h-2 bg-gray-200 rounded" />)}
        </div>
      </div>
    ),
  },
  {
    id: "h3",
    label: "Header 3",
    desc: "Minimal - logo + single CTA",
    preview: (active) => (
      <div className={`flex items-center justify-between px-4 py-2.5 border-b ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-t-lg`}>
        <div className="w-16 h-3 bg-gray-300 rounded" />
        <div className="w-12 h-5 bg-gray-900 rounded-md" />
      </div>
    ),
  },
  {
    id: "h4",
    label: "Header 4",
    desc: "Dashboard sticky - icon + search + avatar",
    preview: (active) => (
      <div className={`flex items-center justify-between px-3 py-2 border-b ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-t-lg`}>
        <div className="w-5 h-5 bg-blue-400 rounded" />
        <div className="w-20 h-4 bg-gray-100 rounded-full border border-gray-200" />
        <div className="w-5 h-5 rounded-full bg-gray-300" />
      </div>
    ),
  },
];

const FOOTER_OPTIONS = [
  {
    id: "f1",
    label: "Footer 1",
    desc: "4-column link grid + copyright",
    preview: (active) => (
      <div className={`px-4 py-3 border-t ${active ? "border-blue-400 bg-blue-50" : "border-gray-100 bg-gray-50"} rounded-b-lg`}>
        <div className="grid grid-cols-4 gap-2 mb-2">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="space-y-1">
              <div className="w-10 h-2 bg-gray-400 rounded" />
              {[0, 1, 2].map((subItem) => <div key={subItem} className="w-12 h-1.5 bg-gray-200 rounded" />)}
            </div>
          ))}
        </div>
        <div className="border-t border-gray-200 pt-1.5 flex justify-between">
          <div className="w-20 h-1.5 bg-gray-200 rounded" />
          <div className="w-16 h-1.5 bg-gray-200 rounded" />
        </div>
      </div>
    ),
  },
  {
    id: "f2",
    label: "Footer 2",
    desc: "Logo + social icons + tagline",
    preview: (active) => (
      <div className={`px-4 py-3 border-t ${active ? "border-blue-400 bg-blue-50" : "border-gray-100 bg-gray-800"} rounded-b-lg`}>
        <div className="flex items-center justify-between mb-2">
          <div className="w-14 h-3 bg-gray-400 rounded" />
          <div className="flex gap-1.5">{[0, 1, 2].map((item) => <div key={item} className="w-5 h-5 rounded-full bg-gray-600" />)}</div>
        </div>
        <div className="w-28 h-1.5 bg-gray-600 rounded" />
      </div>
    ),
  },
  {
    id: "f3",
    label: "Footer 3",
    desc: "Minimal - one-line copyright + links",
    preview: (active) => (
      <div className={`px-4 py-2 border-t ${active ? "border-blue-400 bg-blue-50" : "border-gray-100 bg-white"} rounded-b-lg flex items-center justify-between`}>
        <div className="w-20 h-1.5 bg-gray-200 rounded" />
        <div className="flex gap-2">{[0, 1, 2].map((item) => <div key={item} className="w-10 h-1.5 bg-gray-200 rounded" />)}</div>
      </div>
    ),
  },
  {
    id: "f4",
    label: "Footer 4",
    desc: "Newsletter + links + social",
    preview: (active) => (
      <div className={`px-4 py-3 border-t ${active ? "border-blue-400 bg-blue-50" : "border-gray-100 bg-gray-50"} rounded-b-lg`}>
        <div className="flex items-center gap-2 mb-2 p-1.5 bg-white border border-gray-200 rounded-lg">
          <div className="flex-1 h-2 bg-gray-100 rounded" />
          <div className="w-12 h-4 bg-blue-500 rounded" />
        </div>
        <div className="flex justify-between">
          <div className="flex gap-2">{[0, 1, 2].map((item) => <div key={item} className="w-8 h-1.5 bg-gray-200 rounded" />)}</div>
          <div className="w-12 h-1.5 bg-gray-200 rounded" />
        </div>
      </div>
    ),
  },
];

const NAV_OPTIONS = [
  {
    id: "n1",
    label: "Nav 1",
    desc: "Horizontal top nav with dropdown",
    preview: (active) => (
      <div className={`flex gap-3 px-3 py-2 border-b ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-t-lg`}>
        {["Home", "Rooms", "About", "Contact"].map((item) => (
          <div key={item} className="text-[8px] text-gray-500">
            {item}
          </div>
        ))}
      </div>
    ),
  },
  {
    id: "n2",
    label: "Nav 2",
    desc: "Left sidebar navigation",
    preview: (active) => (
      <div className={`flex h-12 border ${active ? "border-blue-400" : "border-gray-200"} rounded-lg overflow-hidden`}>
        <div className={`w-10 ${active ? "bg-blue-50" : "bg-gray-50"} border-r border-gray-200 flex flex-col items-center py-1 gap-1`}>
          {[0, 1, 2].map((item) => <div key={item} className="w-4 h-3 bg-gray-200 rounded" />)}
        </div>
        <div className="flex-1 bg-white p-1.5">
          <div className="h-2 w-full bg-gray-100 rounded mb-1" />
          <div className="grid grid-cols-2 gap-1">{[0, 1].map((item) => <div key={item} className="h-3 bg-gray-100 rounded" />)}</div>
        </div>
      </div>
    ),
  },
  {
    id: "n3",
    label: "Nav 3",
    desc: "Tab bar (mobile-inspired)",
    preview: (active) => (
      <div className={`flex items-center justify-around py-1.5 border-t ${active ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"} rounded-b-lg`}>
        {["A", "B", "C", "D"].map((item) => (
          <div key={item} className="text-[10px] text-gray-400">
            {item}
          </div>
        ))}
      </div>
    ),
  },
  {
    id: "n4",
    label: "Nav 4",
    desc: "Breadcrumb trail",
    preview: (active) => (
      <div className={`flex items-center gap-1 px-3 py-1.5 ${active ? "bg-blue-50" : "bg-gray-50"} rounded-lg border ${active ? "border-blue-200" : "border-gray-200"}`}>
        {["Home", "Rooms", "Detail"].map((item, index) => (
          <div key={item} className="flex items-center gap-1">
            <span className="text-[9px] text-gray-500">{item}</span>
            {index < 2 && <span className="text-[8px] text-gray-300">/</span>}
          </div>
        ))}
      </div>
    ),
  },
];

const CARD_OPTIONS = [
  {
    id: "c1",
    label: "Card 1",
    desc: "Filled white with shadow",
    preview: (active) => (
      <div className={`p-2 bg-white rounded-xl shadow-sm border ${active ? "border-blue-300" : "border-gray-100"}`}>
        <div className="h-8 bg-gray-100 rounded-lg mb-2" />
        <div className="h-2 w-3/4 bg-gray-200 rounded mb-1" />
        <div className="h-1.5 w-1/2 bg-gray-100 rounded" />
      </div>
    ),
  },
  {
    id: "c2",
    label: "Card 2",
    desc: "Outlined border only",
    preview: (active) => (
      <div className={`p-2 bg-white rounded-xl border-2 ${active ? "border-blue-400" : "border-gray-200"}`}>
        <div className="h-8 bg-gray-50 rounded-lg mb-2 border border-gray-100" />
        <div className="h-2 w-3/4 bg-gray-200 rounded mb-1" />
        <div className="h-1.5 w-1/2 bg-gray-100 rounded" />
      </div>
    ),
  },
  {
    id: "c3",
    label: "Card 3",
    desc: "Colored top accent",
    preview: (active) => (
      <div className={`p-2 bg-white rounded-xl border ${active ? "border-blue-300" : "border-gray-100"} border-t-4 ${active ? "border-t-blue-500" : "border-t-blue-400"}`}>
        <div className="h-8 bg-gray-100 rounded-lg mb-2" />
        <div className="h-2 w-3/4 bg-gray-200 rounded mb-1" />
        <div className="h-1.5 w-1/2 bg-gray-100 rounded" />
      </div>
    ),
  },
  {
    id: "c4",
    label: "Card 4",
    desc: "Hover glass / soft gradient",
    preview: (active) => (
      <div className={`p-2 rounded-xl border ${active ? "border-blue-300 bg-blue-50" : "border-gray-100 bg-gradient-to-br from-gray-50 to-white"}`}>
        <div className="h-8 bg-white rounded-lg mb-2 shadow-sm" />
        <div className="h-2 w-3/4 bg-gray-200 rounded mb-1" />
        <div className="h-1.5 w-1/2 bg-gray-100 rounded" />
      </div>
    ),
  },
];

const PAGE_TEMPLATES = [
  {
    id: "pt1",
    name: "Dashboard",
    category: "App",
    preview: () => (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
          <div className="w-14 h-2.5 bg-gray-300 rounded" />
          <div className="flex gap-1"><div className="w-6 h-5 bg-blue-500 rounded" /></div>
        </div>
        <div className="flex" style={{ height: 100 }}>
          <div className="w-12 bg-gray-50 border-r border-gray-200 p-1 space-y-1">
            {[0, 1, 2, 3].map((item) => <div key={item} className={`w-full h-4 rounded ${item === 0 ? "bg-blue-100" : "bg-gray-100"}`} />)}
          </div>
          <div className="flex-1 p-2">
            <div className="grid grid-cols-3 gap-1 mb-2">{[0, 1, 2].map((item) => <div key={item} className="h-8 bg-gray-100 rounded-lg border border-gray-200" />)}</div>
            <div className="h-12 bg-gray-50 rounded-lg border border-gray-200" />
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "pt2",
    name: "Login Page",
    category: "Auth",
    preview: () => (
      <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden" style={{ height: 120 }}>
        <div className="flex items-center justify-center h-full">
          <div className="w-28 bg-white border border-gray-200 rounded-xl p-3 shadow-sm">
            <div className="w-6 h-6 bg-blue-100 rounded-lg mx-auto mb-2" />
            <div className="h-2 w-full bg-gray-200 rounded mb-2" />
            <div className="space-y-1.5 mb-2">
              <div className="h-4 bg-gray-100 rounded border border-gray-200" />
              <div className="h-4 bg-gray-100 rounded border border-gray-200" />
            </div>
            <div className="h-5 bg-blue-500 rounded-lg" />
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "pt3",
    name: "Landing Page",
    category: "Marketing",
    preview: () => (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" style={{ height: 120 }}>
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
          <div className="w-12 h-2.5 bg-gray-300 rounded" />
          <div className="flex gap-1.5">
            {[0, 1].map((item) => <div key={item} className="w-10 h-2 bg-gray-200 rounded" />)}
            <div className="w-10 h-4 bg-blue-500 rounded" />
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-4 px-3">
          <div className="w-32 h-3 bg-gray-200 rounded mb-1.5" />
          <div className="w-24 h-2 bg-gray-100 rounded mb-3" />
          <div className="flex gap-1.5">
            <div className="w-14 h-5 bg-blue-500 rounded-lg" />
            <div className="w-14 h-5 bg-gray-200 rounded-lg" />
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "pt4",
    name: "Table / List",
    category: "App",
    preview: () => (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" style={{ height: 120 }}>
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
          <div className="w-14 h-2.5 bg-gray-300 rounded" />
          <div className="w-14 h-5 bg-blue-500 rounded-lg" />
        </div>
        <div className="p-2">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="flex items-center gap-2 py-1 border-b border-gray-100 last:border-0">
              {[20, 32, 16, 14].map((width, widthIndex) => (
                <div key={widthIndex} className="h-2 bg-gray-100 rounded" style={{ width: `${width * 2}px` }} />
              ))}
            </div>
          ))}
        </div>
      </div>
    ),
  },
];

export const COMPONENT_CATEGORIES = [
  { id: "header", label: "Header", options: HEADER_OPTIONS },
  { id: "footer", label: "Footer", options: FOOTER_OPTIONS },
  { id: "nav", label: "Navigation", options: NAV_OPTIONS },
  { id: "card", label: "Cards", options: CARD_OPTIONS },
];

export function DesignSelectorHeader({ view, onChangeView, onApprove, onNavigate }) {
  return (
    <div className="px-5 pt-4 pb-3 border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
            <span>AgentForge</span>
            <Icon name="ChevronRight" size={10} />
            <span>Design Selector</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">Frontend Design Selector</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Choose the visual direction before Agent 2 generates the application.
          </p>
        </div>
        <div className="flex gap-2 pt-1">
          <Btn icon="Save">Save Preset</Btn>
          <Btn icon="CheckCircle2" variant="success" onClick={onApprove}>
            Approve Design
          </Btn>
          <Btn icon="ArrowRight" variant="primary" onClick={onApprove}>
            Send to Agent 2
          </Btn>
        </div>
      </div>
      <div className="flex gap-1 mt-3">
        <button
          onClick={() => onChangeView("components")}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${view === "components" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
        >
          Page Components
        </button>
        <button
          onClick={() => onChangeView("design")}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${view === "design" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
        >
          Page Design
        </button>
      </div>
    </div>
  );
}

export function ComponentCategorySidebar({ activeCategory, selections, onSelectCategory }) {
  return (
    <div className="w-40 border-r border-gray-200 bg-gray-50 p-3 space-y-1 flex-shrink-0">
      <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-2 px-1">Component Type</p>
      {COMPONENT_CATEGORIES.map((category) => (
        <button
          key={category.id}
          onClick={() => onSelectCategory(category.id)}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${activeCategory === category.id ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
        >
          {category.label}
          {selections[category.id] && (
            <Icon
              name="Check"
              size={11}
              className={activeCategory === category.id ? "text-white" : "text-green-500"}
            />
          )}
        </button>
      ))}
    </div>
  );
}

export function ComponentOptionsGrid({ activeCategory, selections, onSelectOption }) {
  const category = COMPONENT_CATEGORIES.find((item) => item.id === activeCategory);

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <p className="text-xs text-gray-500 mb-4">
        Select a <strong className="text-gray-900">{category?.label}</strong> design for your application:
      </p>
      <div className="grid grid-cols-2 gap-4">
        {category?.options.map((option) => (
          <button
            key={option.id}
            onClick={() => onSelectOption(activeCategory, option.id)}
            className={`text-left p-4 rounded-2xl border-2 transition-all ${selections[activeCategory] === option.id ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-blue-300"}`}
          >
            <div className="mb-3 border border-gray-100 rounded-xl overflow-hidden">
              {option.preview(selections[activeCategory] === option.id)}
              <div className="h-8 bg-white border-t border-gray-100 flex items-center px-3 gap-2">
                <div className="w-full h-1.5 bg-gray-100 rounded" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-gray-900">{option.label}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{option.desc}</p>
              </div>
              {selections[activeCategory] === option.id && (
                <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                  <Icon name="Check" size={11} className="text-white" />
                </div>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function DesignTemplateGrid({ selectedTemplate, onSelectTemplate }) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <p className="text-xs text-gray-500 mb-4">Select page templates that will be generated for your application:</p>
      <div className="grid grid-cols-4 gap-4">
        {PAGE_TEMPLATES.map((template) => (
          <button
            key={template.id}
            onClick={() => onSelectTemplate(selectedTemplate === template.id ? null : template.id)}
            className={`text-left rounded-2xl border-2 overflow-hidden transition-all ${selectedTemplate === template.id ? "border-blue-500" : "border-gray-200 hover:border-blue-300"}`}
          >
            <div className="p-3">{template.preview()}</div>
            <div className={`px-3 pb-3 ${selectedTemplate === template.id ? "bg-blue-50" : "bg-white"}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-gray-900">{template.name}</p>
                  <span className="text-[10px] text-gray-400">{template.category}</span>
                </div>
                {selectedTemplate === template.id && (
                  <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                    <Icon name="Check" size={11} className="text-white" />
                  </div>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function ApprovalSummaryPanel({ selections, selectedTemplate, onApprove, onNavigate }) {
  return (
    <div className="w-52 border-l border-gray-200 bg-gray-50 flex flex-col overflow-y-auto flex-shrink-0">
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-700">Approval Summary</p>
      </div>
      <div className="p-4 space-y-3 flex-1">
        {COMPONENT_CATEGORIES.map((category) => {
          const option = category.options.find((item) => item.id === selections[category.id]);
          return (
            <div key={category.id}>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">{category.label}</p>
              <p className="text-xs font-medium text-gray-700">{option?.label}</p>
              <p className="text-[10px] text-gray-500">{option?.desc}</p>
            </div>
          );
        })}
        {selectedTemplate && (
          <div>
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Page Focused</p>
            <p className="text-xs font-medium text-gray-700">
              {PAGE_TEMPLATES.find((template) => template.id === selectedTemplate)?.name}
            </p>
          </div>
        )}
      </div>
      <div className="p-4 border-t border-gray-200 space-y-2">
        <Btn size="xs" variant="primary" icon="CheckCircle2" onClick={onApprove} className="w-full justify-center">
          Approve Design
        </Btn>
        <Btn size="xs" icon="ArrowRight" onClick={onApprove} className="w-full justify-center">
          Send to Agent 2
        </Btn>
        <Btn size="xs" icon="ArrowLeft" onClick={() => onNavigate("agent1")} className="w-full justify-center">
          Back to Analyzer
        </Btn>
      </div>
    </div>
  );
}
