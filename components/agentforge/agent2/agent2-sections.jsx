import React from "react";
import { Icon, Btn, Badge } from "../core/ui";

export const BUILD_STEPS = [
  { label: "Analyzing approved requirements", desc: "Parsing SRS + design preset constraints" },
  { label: "Designing microservice architecture", desc: "Mapping 6 services across bounded domains" },
  { label: "Scaffolding frontend structure", desc: "React + Tailwind project scaffold" },
  { label: "Generating page components", desc: "10 pages from Enterprise Dashboard preset" },
  { label: "Creating auth-service", desc: "FastAPI - 8 endpoints - JWT + OAuth2" },
  { label: "Creating booking-service", desc: "FastAPI - 15 endpoints - room + booking logic" },
  { label: "Creating payment-service", desc: "FastAPI - 10 endpoints - Stripe integration" },
  { label: "Creating notification-service", desc: "FastAPI - 6 endpoints - email + SMS dispatch" },
  { label: "Creating report-service", desc: "FastAPI - 9 endpoints - analytics + exports" },
  { label: "Integrating services and APIs", desc: "Service-to-service contracts finalized" },
  { label: "Final quality checks", desc: "Linting - type checks - dependency scan" },
  { label: "Build complete", desc: "All modules generated and validated" },
];

export const CODE_LOGS = [
  "-> Reading SRS v1.2 and design preset...",
  "-> Architecture: Microservices (6 services)",
  "-> Scaffolding /frontend/src/...",
  "-> Generating LoginPage.tsx",
  "-> Generating DashboardPage.tsx",
  "-> Generating RoomListPage.tsx",
  "-> Generating BookingForm.tsx",
  "-> Generating AdminPanel.tsx",
  "-> /backend/auth-service/main.py",
  "-> auth: POST /auth/login",
  "-> auth: POST /auth/register",
  "-> auth: POST /auth/refresh",
  "-> /backend/booking-service/main.py",
  "-> booking: POST /bookings",
  "-> booking: GET /bookings/:id",
  "-> booking: PATCH /bookings/:id/cancel",
  "-> /backend/payment-service/main.py",
  "-> payment: POST /payments/checkout",
  "-> payment: POST /payments/webhook",
  "-> /backend/notification-service/main.py",
  "-> /backend/report-service/main.py",
  "-> Running linter... 0 errors, 3 warnings",
  "-> Type checks passed",
  "-> All 12 build steps complete",
  "-> Build package ready for QA",
];

export const BUILDER_TABS = [
  { id: "timeline", label: "Build Timeline" },
  { id: "frontend", label: "Frontend Pages" },
  { id: "backend", label: "Backend Services" },
  { id: "coder", label: "Coder" },
];

const FOLDER_TREE = [
  { name: "stayease/", type: "dir", level: 0 },
  { name: "frontend/", type: "dir", level: 1 },
  { name: "src/", type: "dir", level: 2 },
  { name: "pages/", type: "dir", level: 3 },
  { name: "LoginPage.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "DashboardPage.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "RoomListPage.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "BookingForm.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "AdminPanel.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "components/", type: "dir", level: 3 },
  { name: "RoomCard.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "BookingTable.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "PaymentForm.tsx", type: "file", level: 4, lang: "tsx" },
  { name: "auth-service/", type: "dir", level: 1 },
  { name: "main.py", type: "file", level: 2, lang: "py" },
  { name: "routes.py", type: "file", level: 2, lang: "py" },
  { name: "models.py", type: "file", level: 2, lang: "py" },
  { name: "requirements.txt", type: "file", level: 2, lang: "txt" },
  { name: "booking-service/", type: "dir", level: 1 },
  { name: "main.py", type: "file", level: 2, lang: "py" },
  { name: "routes.py", type: "file", level: 2, lang: "py" },
  { name: "models.py", type: "file", level: 2, lang: "py" },
  { name: "payment-service/", type: "dir", level: 1 },
  { name: "main.py", type: "file", level: 2, lang: "py" },
  { name: "stripe_handler.py", type: "file", level: 2, lang: "py" },
  { name: "notification-service/", type: "dir", level: 1 },
  { name: "main.py", type: "file", level: 2, lang: "py" },
  { name: "report-service/", type: "dir", level: 1 },
  { name: "main.py", type: "file", level: 2, lang: "py" },
  { name: "docker-compose.yml", type: "file", level: 0, lang: "yaml" },
  { name: ".env.example", type: "file", level: 0, lang: "env" },
];

const FILE_CONTENTS = {
  "LoginPage.tsx": `import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/auth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    const token = await authService.login(email, password);
    if (token) navigate('/dashboard');
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-96 bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold mb-6">Welcome to StayEase</h1>
        <form onSubmit={handleLogin} className="space-y-4">
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full border rounded-lg px-4 py-2" />
          <input type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border rounded-lg px-4 py-2" />
          <button type="submit"
            className="w-full bg-blue-600 text-white rounded-lg py-2 font-medium">
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}`,
  "routes.py": `from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from .models import UserCreate, UserLogin, TokenResponse
from .auth import create_token, verify_password, get_password_hash
from .database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db=Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_token(user.id), "token_type": "bearer"}`,
  "models.py": `from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from .database import Base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default="guest")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    bookings = relationship("Booking", back_populates="user")`,
};

export function BuilderHeader({ buildDone, buildStep, tab, onChangeTab }) {
  return (
    <div className="px-5 pt-4 pb-3 border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
            <span>AgentForge</span>
            <Icon name="ChevronRight" size={10} />
            <span>Builder Studio</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">Builder Studio</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Generate aligned frontend and backend systems based on approved requirements.
          </p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          {buildDone ? (
            <span className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 text-xs font-medium rounded-lg border border-green-200">
              <Icon name="CheckCircle2" size={13} /> Build Complete
            </span>
          ) : (
            <span className="flex items-center gap-2 px-3 py-1.5 bg-violet-50 text-violet-700 text-xs font-medium rounded-lg border border-violet-200">
              <Icon name="Loader2" size={36} />
              Building... {buildStep >= 0 ? `${buildStep + 1}/${BUILD_STEPS.length}` : ""}
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-1 mt-3 border-b border-gray-200 -mb-3">
        {BUILDER_TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => buildDone && onChangeTab(item.id)}
            className={`px-3 py-2 text-xs font-medium transition-all border-b-2 -mb-px ${
              tab === item.id
                ? "border-blue-500 text-blue-600"
                : buildDone
                  ? "border-transparent text-gray-500 hover:text-gray-700 cursor-pointer"
                  : item.id === "timeline"
                    ? "border-transparent text-gray-700"
                    : "border-transparent text-gray-300 cursor-not-allowed"
            }`}
          >
            {item.label}
            {!buildDone && item.id !== "timeline" && (
              <Icon name="Lock" size={9} className="inline ml-1 text-gray-300" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

export function BuildTimelinePane({ buildStep }) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="max-w-lg space-y-1">
        {BUILD_STEPS.map((step, index) => {
          const done = index <= buildStep;
          const active = index === buildStep + 1;

          return (
            <div key={step.label} className="flex gap-3" style={{ animation: done ? "fadeIn 0.4s ease forwards" : "none" }}>
              <div className="flex flex-col items-center">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center border-2 flex-shrink-0 transition-all duration-500 ${
                    done
                      ? "border-green-500 bg-green-50"
                      : active
                        ? "border-blue-400 bg-blue-50"
                        : "border-gray-200 bg-white"
                  }`}
                >
                  {done ? (
                    <Icon name="Check" size={13} className="text-green-600" />
                  ) : active ? (
                    <Icon name="Loader2" size={13} className="text-blue-500 animate-spin" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-gray-200" />
                  )}
                </div>
                {index < BUILD_STEPS.length - 1 && (
                  <div
                    className={`w-px flex-1 my-0.5 transition-all duration-500 ${done ? "bg-green-200" : "bg-gray-100"}`}
                    style={{ minHeight: 16 }}
                  />
                )}
              </div>
              <div className="pb-3 flex-1">
                <p
                  className={`text-xs font-semibold transition-colors duration-300 ${
                    done ? "text-gray-900" : active ? "text-blue-600" : "text-gray-300"
                  }`}
                >
                  {step.label}
                </p>
                <p className={`text-xs mt-0.5 transition-colors duration-300 ${done ? "text-gray-500" : "text-gray-300"}`}>
                  {step.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function CodeLogPane({ buildDone, codeLogs, codeLogRef }) {
  return (
    <div className="w-80 border-l border-gray-200 flex flex-col bg-gray-950">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-800">
        <Icon name="Terminal" size={12} className="text-green-400" />
        <span className="text-xs text-gray-400 font-mono">Code Log</span>
        <span className="ml-auto flex gap-1">
          {[0, 1, 2].map((dot) => (
            <span
              key={dot}
              className="w-1.5 h-1.5 rounded-full bg-green-400"
              style={{
                animation: `typingDot 1.2s ${dot * 0.2}s ease-in-out infinite`,
                display: buildDone ? "none" : "block",
              }}
            />
          ))}
        </span>
      </div>
      <div ref={codeLogRef} className="flex-1 overflow-y-auto p-3 font-mono space-y-0.5">
        {codeLogs.map((log, index) => (
          <p
            key={`${log}-${index}`}
            className={`text-[10px] leading-5 ${
              log.includes("complete") || log.includes("passed")
                ? "text-green-400"
                : log.startsWith("->")
                  ? "text-gray-300"
                  : "text-gray-500"
            }`}
            style={{ animation: "fadeIn 0.3s ease forwards" }}
          >
            {log}
          </p>
        ))}
        {!buildDone && <span className="text-green-400 text-[10px]">|</span>}
      </div>
    </div>
  );
}

export function LivePreviewModal({ page, onClose }) {
  if (!page) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl overflow-hidden"
        style={{ width: 900, height: 600 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 border-b border-gray-200">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-400" />
            <div className="w-3 h-3 rounded-full bg-yellow-400" />
            <div className="w-3 h-3 rounded-full bg-green-400" />
          </div>
          <div className="flex-1 mx-4 bg-white rounded-lg px-3 py-1 text-xs text-gray-500 font-mono border border-gray-200">
            stayease.app{page.route}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <Icon name="X" size={14} />
          </button>
        </div>
        <div className="flex h-full">
          {page.layout?.includes("Sidebar") && (
            <div className="w-48 bg-gray-50 border-r border-gray-200 p-3">
              <div className="w-20 h-6 bg-blue-100 rounded mb-4" />
              {[0, 1, 2, 3, 4].map((item) => (
                <div
                  key={item}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded mb-1 ${item === 0 ? "bg-blue-50" : ""}`}
                >
                  <div className={`w-3 h-3 rounded ${item === 0 ? "bg-blue-400" : "bg-gray-300"}`} />
                  <div className={`h-2 rounded flex-1 ${item === 0 ? "bg-blue-200" : "bg-gray-200"}`} />
                </div>
              ))}
            </div>
          )}
          <div className="flex-1 bg-white p-5 overflow-hidden">
            {page.name === "Login Page" ? (
              <div className="flex items-center justify-center h-full">
                <div className="w-72 border border-gray-200 rounded-2xl p-6 shadow-sm">
                  <div className="w-10 h-10 bg-blue-100 rounded-xl mx-auto mb-3" />
                  <div className="h-4 bg-gray-200 rounded w-3/4 mx-auto mb-4" />
                  <div className="space-y-2 mb-3">
                    <div className="h-8 bg-gray-100 rounded-lg border border-gray-200" />
                    <div className="h-8 bg-gray-100 rounded-lg border border-gray-200" />
                  </div>
                  <div className="h-8 bg-blue-500 rounded-lg" />
                </div>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="h-5 w-32 bg-gray-200 rounded" />
                  <div className="h-7 w-24 bg-blue-500 rounded-lg" />
                </div>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {[0, 1, 2].map((item) => (
                    <div key={item} className="border border-gray-200 rounded-xl p-3">
                      <div className="h-2 w-16 bg-gray-200 rounded mb-2" />
                      <div className="h-5 w-12 bg-gray-800 rounded" />
                    </div>
                  ))}
                </div>
                <div className="border border-gray-200 rounded-xl overflow-hidden">
                  {[0, 1, 2, 3].map((row) => (
                    <div
                      key={row}
                      className={`flex items-center gap-3 px-4 py-2.5 text-xs border-b border-gray-100 ${row === 0 ? "bg-gray-50 text-gray-500" : ""}`}
                    >
                      {row === 0
                        ? ["ID", "Name", "Status", "Date"].map((header) => (
                            <span key={header} className="flex-1 font-medium">
                              {header}
                            </span>
                          ))
                        : ["#10" + row, "Sample Item", "Active", "Apr 23"].map((value, valueIndex) => (
                            <span key={valueIndex} className={`flex-1 ${valueIndex === 2 ? "text-green-600" : "text-gray-600"}`}>
                              {value}
                            </span>
                          ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function FrontendPagesPane({ pages, onOpenPreview }) {
  return (
    <div className="overflow-y-auto p-5">
      <p className="text-xs text-gray-500 mb-4">
        All pages generated from <span className="text-violet-600 font-medium">Enterprise Dashboard</span> design preset.
      </p>
      <div className="grid grid-cols-3 gap-3">
        {pages.map((page) => (
          <div key={page.name} className="bg-white border border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-all hover:shadow-sm">
            <div className="aspect-video bg-gray-50 rounded-lg border border-gray-100 mb-3 overflow-hidden flex">
              {page.layout?.includes("Sidebar") && <div className="w-6 bg-gray-200 border-r border-gray-200" />}
              <div className="flex-1 p-1.5">
                <div className="h-1.5 w-12 bg-gray-300 rounded mb-1.5" />
                <div className="grid grid-cols-2 gap-1">{[0, 1, 2, 3].map((item) => <div key={item} className="h-3 bg-gray-200 rounded" />)}</div>
              </div>
            </div>
            <p className="text-xs font-semibold text-gray-900 mb-1">{page.name}</p>
            <p className="font-mono text-[10px] text-gray-400 mb-2">{page.route}</p>
            <div className="flex flex-wrap gap-1 mb-3">
              {page.components.slice(0, 2).map((component) => (
                <span key={component} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                  {component}
                </span>
              ))}
            </div>
            <button
              onClick={() => onOpenPreview(page)}
              className="w-full py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-1.5"
            >
              <Icon name="Globe" size={11} /> Live Preview
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function BackendServicesPane({ services }) {
  return (
    <div className="overflow-y-auto p-5">
      <p className="text-xs text-gray-500 mb-4">Microservice architecture - FastAPI - PostgreSQL - Docker-ready</p>
      <div className="grid grid-cols-2 gap-3">
        {services.map((service) => (
          <div key={service.name} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm font-bold text-violet-600">{service.name}</span>
              <Badge color="green">Generated</Badge>
            </div>
            <div className="bg-gray-950 rounded-lg p-3 font-mono text-[10px] space-y-0.5">
              <p className="text-yellow-400">folder {service.name}/</p>
              {["main.py", "routes.py", "models.py", "schemas.py", "requirements.txt"].map((file) => (
                <p key={file} className="text-gray-300 pl-3">
                  |- {file}
                </p>
              ))}
              <p className="text-gray-600 pl-3">|- Dockerfile</p>
            </div>
            <div className="flex gap-2 mt-3 text-[10px] text-gray-500">
              <span>{service.endpoints} endpoints</span>
              <span>-</span>
              <span>{service.models} models</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CoderPane({ selectedFile, onSelectFile }) {
  return (
    <div className="flex h-full">
      <div className="w-56 border-r border-gray-200 overflow-y-auto bg-gray-50 p-2">
        <p className="text-[10px] text-gray-400 uppercase tracking-wider px-2 mb-2">Project Files</p>
        {FOLDER_TREE.map((item, index) => (
          <button
            key={`${item.name}-${index}`}
            onClick={() => item.type === "file" && onSelectFile(item.name)}
            className={`w-full flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors text-left ${
              item.type === "dir"
                ? "text-gray-500 font-medium cursor-default"
                : selectedFile === item.name
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100 cursor-pointer"
            }`}
            style={{ paddingLeft: `${8 + item.level * 14}px` }}
          >
            <span>{item.type === "dir" ? "folder" : item.lang === "tsx" ? "tsx" : item.lang === "py" ? "py" : "file"}</span>
            <span className="truncate">{item.name}</span>
          </button>
        ))}
      </div>
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800">
          <Icon name="FileCode" size={12} className="text-blue-400" />
          <span className="text-xs text-gray-300 font-mono">{selectedFile}</span>
        </div>
        <div className="flex-1 overflow-y-auto p-4 font-mono">
          <pre className="text-[11px] text-gray-300 leading-6 whitespace-pre-wrap">
            {FILE_CONTENTS[selectedFile] ||
              `// ${selectedFile}\n// Generated by AgentForge Builder Studio\n// Architecture: Microservices - FastAPI\n`}
          </pre>
        </div>
      </div>
    </div>
  );
}
