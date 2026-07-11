"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Pencil, Sparkles, Zap } from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Answer, Question } from "@agentforge/shared";

type AnsweredItem = { question: Question; display: string };

export default function QuestionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [history, setHistory] = useState<AnsweredItem[]>([]);
  const [multi, setMulti] = useState<string[]>([]);
  const [otherText, setOtherText] = useState("");
  const [showOther, setShowOther] = useState(false);
  const [phase, setPhase] = useState<"loading" | "asking" | "generating">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getQuestions(id)
      .then((d) => {
        setQuestions(d.questions || []);
        setPhase("asking");
      })
      .catch((e) => setError((e as Error).message));
  }, [id]);

  const current = questions[index];
  const total = questions.length;

  function record(question: Question, value: Answer["value"], display: string, raw?: string) {
    setAnswers((prev) => [...prev, { question_id: question.id, value, raw_text: raw }]);
    setHistory((prev) => [...prev, { question, display }]);
    setMulti([]);
    setOtherText("");
    setShowOther(false);
    if (index + 1 < questions.length) {
      setIndex(index + 1);
    } else {
      finalize([...answers, { question_id: question.id, value, raw_text: raw }]);
    }
  }

  async function finalize(allAnswers: Answer[]) {
    setPhase("generating");
    try {
      const res = await api.submitAnswers(id, allAnswers);
      if (res.follow_up_questions && res.follow_up_questions.length > 0) {
        setQuestions((prev) => [...prev, ...res.follow_up_questions]);
        setIndex((i) => i + 1);
        setPhase("asking");
        return;
      }
      await api.generateSrs(id);
      router.push(`/projects/${id}/analyzer?tab=srs`);
    } catch (e) {
      setError((e as Error).message);
      setPhase("asking");
    }
  }

  const progressPct = useMemo(
    () => (total ? Math.round(((index) / total) * 100) : 0),
    [index, total],
  );

  if (phase === "generating") {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex flex-1 flex-col items-center justify-center gap-4">
          <div className="afs-spinner" />
          <p className="text-sm font-medium">Agent 1 is generating your SRS, diagrams & report…</p>
          <p className="text-xs text-muted-foreground">Validating JSON · building tables · rendering diagrams</p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex items-center justify-between border-b border-border bg-card px-5 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Agent 1 — Requirement Gathering
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {Math.min(index + 1, total)} / {total} questions
          </span>
          <div className="h-1.5 w-32 overflow-hidden rounded-full bg-secondary">
            <div className="h-full bg-primary transition-all" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </div>

      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-6">
        <Bubble>
          Great! I&apos;ve read your idea. I have {total} simple question{total === 1 ? "" : "s"} to make sure I build
          exactly what you want. No tech jargon — promise. Let&apos;s go!
        </Bubble>

        {history.map((h, i) => (
          <div key={i} className="mb-3 animate-fade-in">
            <Bubble small label={`Question ${i + 1}`}>
              {h.question.question}
            </Bubble>
            <div className="mt-1 flex justify-end">
              <span className="rounded-2xl rounded-tr-sm bg-primary px-3 py-1.5 text-sm text-primary-foreground">
                {h.display}
              </span>
            </div>
          </div>
        ))}

        {current && (
          <div className="animate-fade-in">
            <Bubble label={`Question ${index + 1} of ${total}`}>{current.question}</Bubble>
            {current.why_needed && (
              <p className="mb-2 ml-11 text-xs text-muted-foreground">Why: {current.why_needed}</p>
            )}
            <div className="ml-11 flex flex-wrap gap-2">
              <QuestionInput
                question={current}
                multi={multi}
                setMulti={setMulti}
                showOther={showOther}
                setShowOther={setShowOther}
                otherText={otherText}
                setOtherText={setOtherText}
                onAnswer={record}
              />
            </div>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      </main>
    </div>
  );
}

function Bubble({
  children,
  label,
  small,
}: {
  children: React.ReactNode;
  label?: string;
  small?: boolean;
}) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Zap className="h-4 w-4" />
      </div>
      <div className={`max-w-md rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-2.5 ${small ? "py-2" : ""}`}>
        {label && <div className="mb-0.5 text-[11px] font-medium text-muted-foreground">{label}</div>}
        <div className="text-sm">{children}</div>
      </div>
    </div>
  );
}

function QuestionInput({
  question,
  multi,
  setMulti,
  showOther,
  setShowOther,
  otherText,
  setOtherText,
  onAnswer,
}: {
  question: Question;
  multi: string[];
  setMulti: (v: string[]) => void;
  showOther: boolean;
  setShowOther: (v: boolean) => void;
  otherText: string;
  setOtherText: (v: string) => void;
  onAnswer: (q: Question, value: Answer["value"], display: string, raw?: string) => void;
}) {
  const t = question.answer_type;

  if (t === "free_text" || t === "number") {
    return (
      <FreeText
        type={t === "number" ? "number" : "text"}
        value={otherText}
        setValue={setOtherText}
        onSubmit={(v) => onAnswer(question, t === "number" ? Number(v) : v, v, v)}
      />
    );
  }

  const options = question.suggested_options.length
    ? question.suggested_options
    : t === "yes_no"
      ? ["Yes", "No"]
      : [];

  if (t === "multi_choice") {
    return (
      <>
        {options.map((opt) =>
          opt === "Other" ? (
            <OtherButton key={opt} active={showOther} onClick={() => setShowOther(!showOther)} />
          ) : (
            <button
              key={opt}
              onClick={() => setMulti(multi.includes(opt) ? multi.filter((m) => m !== opt) : [...multi, opt])}
              className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                multi.includes(opt)
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card hover:bg-secondary"
              }`}
            >
              {opt}
            </button>
          ),
        )}
        {showOther && <InlineOther value={otherText} setValue={setOtherText} onAdd={(v) => setMulti([...multi, v])} />}
        <Button
          size="sm"
          className="ml-1"
          disabled={multi.length === 0 && !otherText}
          onClick={() => {
            const all = otherText ? [...multi, otherText] : multi;
            onAnswer(question, all, all.join(", "), otherText || undefined);
          }}
        >
          Continue
        </Button>
      </>
    );
  }

  // single_choice / yes_no
  return (
    <>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onAnswer(question, opt, opt)}
          className="rounded-full border border-border bg-card px-3 py-1.5 text-sm transition-colors hover:border-primary hover:bg-primary/5"
        >
          {opt}
        </button>
      ))}
      {showOther ? (
        <InlineOther
          value={otherText}
          setValue={setOtherText}
          onAdd={(v) => onAnswer(question, v, v, v)}
        />
      ) : (
        <OtherButton active={false} onClick={() => setShowOther(true)} />
      )}
    </>
  );
}

function OtherButton({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full border border-dashed px-3 py-1.5 text-sm transition-colors ${
        active ? "border-primary text-primary" : "border-border text-muted-foreground hover:bg-secondary"
      }`}
    >
      <Pencil className="h-3 w-3" /> Other — type your answer
    </button>
  );
}

function InlineOther({
  value,
  setValue,
  onAdd,
}: {
  value: string;
  setValue: (v: string) => void;
  onAdd: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && value && onAdd(value)}
        placeholder="Type your answer…"
        className="h-8 w-48 rounded-full border border-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
    </div>
  );
}

function FreeText({
  type,
  value,
  setValue,
  onSubmit,
}: {
  type: string;
  value: string;
  setValue: (v: string) => void;
  onSubmit: (v: string) => void;
}) {
  return (
    <div className="flex w-full max-w-md items-center gap-2">
      <input
        autoFocus
        type={type}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && value.trim() && onSubmit(value.trim())}
        placeholder="Type your answer and press Enter…"
        className="h-9 flex-1 rounded-lg border border-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <Button size="sm" disabled={!value.trim()} onClick={() => onSubmit(value.trim())}>
        <Sparkles className="h-3.5 w-3.5" /> Send
      </Button>
    </div>
  );
}
