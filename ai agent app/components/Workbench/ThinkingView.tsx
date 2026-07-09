'use client';

import { useEffect, useMemo, useRef } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { Brain, Loader2 } from 'lucide-react';
import { useBuilder, type UiMessage } from '@/lib/store';

const THINKING_ANIMATION =
  'https://lottie.host/af95532e-18fc-4d89-8702-b84150f2c19c/kdwcLkO5Zr.lottie';

function latestAssistantThinking(messages: UiMessage[]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.role === 'assistant' && message.thinking?.trim()) {
      return message.thinking;
    }
  }
  return '';
}

export function useThinkingViewActive() {
  const messages = useBuilder((s) => s.messages);
  const isStreaming = useBuilder((s) => s.isStreaming);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const isBuilding = useBuilder((s) => s.isBuilding);
  const planningThinking = useBuilder((s) => s.planningThinking);
  const streamingPath = useBuilder((s) => s.streamingPath);
  const chatThinking = useMemo(() => latestAssistantThinking(messages), [messages]);

  return (
    !isBuilding &&
    !streamingPath &&
    ((isPlanning && planningThinking) || (isStreaming && Boolean(chatThinking.trim())))
  );
}

export function ThinkingView() {
  const messages = useBuilder((s) => s.messages);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const planningStage = useBuilder((s) => s.planningStage);
  const planningThinkingText = useBuilder((s) => s.planningThinkingText);
  const textRef = useRef<HTMLPreElement>(null);

  const chatThinking = useMemo(() => latestAssistantThinking(messages), [messages]);
  const thinkingText = planningThinkingText.trim() || chatThinking.trim();
  const subLabel = isPlanning
    ? planningStage
      ? `Planning ${planningStage}`
      : 'Planning the app'
    : 'deepseek-r1 is reasoning';

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const el = textRef.current;
      el?.scrollTo({ top: el.scrollHeight });
    });
    return () => cancelAnimationFrame(frame);
  }, [thinkingText]);

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center bg-bg px-6 py-8">
      <div className="flex w-full max-w-2xl flex-col items-center text-center">
        <div className="mb-3 flex items-center gap-2 rounded-full border border-sky-100 bg-sky-50 px-3 py-1.5 text-xs text-slate-500">
          <Loader2 size={13} className="animate-spin text-sky-500" />
          <span>{subLabel}</span>
        </div>

        <div className="h-32 w-32">
          <DotLottieReact src={THINKING_ANIMATION} loop autoplay />
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 text-sky-600">
            <Brain size={16} />
          </span>
          <h2 className="thinking-tone text-lg font-semibold">Thinking</h2>
        </div>

        <p className="mt-1 max-w-md text-sm text-text-muted">
          deepseek-r1 is working through the request before writing files.
        </p>

        <pre
          ref={textRef}
          className="mt-5 max-h-[42vh] w-full overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-bg-soft px-4 py-3 text-left font-mono text-[11px] leading-relaxed text-text-muted"
        >
          {thinkingText || 'deepseek-r1 is thinking through the next step...'}
        </pre>
      </div>
    </div>
  );
}
