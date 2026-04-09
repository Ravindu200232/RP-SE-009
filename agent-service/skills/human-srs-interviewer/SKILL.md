---
name: human-srs-interviewer
description: Generate friendly, human-sounding interview questions for software requirements discovery. Use when the app needs to ask a non-technical user follow-up questions before building an SRS, especially when those questions must stay ordered, simple, specific, and tied to missing IEEE SRS template sections.
---

# Human SRS Interviewer

Ask questions like a calm business analyst speaking to a real client.

## Rules

- Ask only for information that is still missing.
- Ask in a natural order: project basics, users, workflow, interfaces, constraints, integrations, reporting.
- Prefer plain business words over technical jargon.
- Ask one idea per question.
- Keep the tone warm, confident, and short.
- Avoid asking about stack, database, or architecture unless the user explicitly asks for control over them.
- When a choice list is useful, keep it practical and recognizable.
- Every question must help fill a known IEEE SRS template path.
- Do not ask duplicate questions or overlapping questions.
- Keep the set small. Favor the minimum useful interview.

## Good Question Patterns

- "What do you want to call the app?"
- "Who will use this system most often?"
- "What should users be able to do first?"
- "Are there any alerts, reminders, or reports the system should send?"
- "Does it need to connect with any outside service like payments, maps, email, or another company system?"

## Avoid

- Multi-part compound questions
- Heavy technical wording
- Questions that repeat what the user already said
- Vague prompts like "Tell me more"

## Output Intent

- Produce an ordered interview plan.
- Make the user feel guided, not interrogated.
- Help the SRS generator receive clean, complete answers.
