"use client";

import React, { cloneElement, isValidElement, useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import StudioShell from "./studio-shell";
import { PAGE_ROUTES } from "../core/page-config";

export default function StudioFrame({ pageId, children }) {
  const router = useRouter();
  const [toasts, setToasts] = useState([]);

  const onNavigate = useCallback((nextPage) => {
    router.push(PAGE_ROUTES[nextPage] || PAGE_ROUTES.dashboard);
  }, [router]);

  const onToast = useCallback((msg, type = "info") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, msg, type }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 4500);
  }, []);

  const content = useMemo(() => {
    if (!isValidElement(children)) return children;
    return cloneElement(children, { onNavigate, onToast });
  }, [children, onNavigate, onToast]);

  return (
    <StudioShell currentPage={pageId} onNavigate={onNavigate} toasts={toasts}>
      <div key={pageId} className="h-full page-enter">
        {content}
      </div>
    </StudioShell>
  );
}
