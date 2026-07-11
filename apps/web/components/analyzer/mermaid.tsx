"use client";

import { useEffect, useId, useRef, useState } from "react";

let initialized = false;

export function MermaidDiagram({ source }: { source: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId().replace(/[:]/g, "_");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        if (!initialized) {
          mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
          initialized = true;
        }
        const { svg } = await mermaid.render(`m_${id}`, source);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source, id]);

  if (error) {
    return (
      <pre className="overflow-auto rounded bg-secondary p-2 text-[10px] text-muted-foreground">{source}</pre>
    );
  }
  return <div ref={ref} className="flex justify-center [&_svg]:max-w-full" />;
}
