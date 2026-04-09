---
name: ieee-srs-writer
description: Produce complete IEEE-style Software Requirements Specification content from collected project information. Use when the app needs to generate or repair an SRS so that the result reads like a formal human-written specification, aligns with IEEE headings, and exports well into a traditional light PDF document.
---

# IEEE SRS Writer

Write like a professional analyst preparing a formal specification for review.

## Rules

- Preserve IEEE-style section intent and business clarity.
- Prefer concrete, reviewable statements over placeholders.
- Keep section wording formal, neutral, and human-written.
- Use complete sentences for descriptions.
- Keep functional requirements specific and testable.
- Use "The system shall..." for requirement statements.
- Keep terminology consistent across metadata, sections, services, and appendices.
- Replace blanks with realistic assumptions when the user has not provided the detail.
- Make the document export cleanly to a traditional light PDF.

## Document Voice

- Formal
- Clear
- Concise
- Review-friendly

## Section Expectations

- Introduction: clear purpose, scope, audience, references.
- Overall Description: product context, users, functions, environment, constraints.
- External Interfaces: user, software, communications, and hardware interfaces when relevant.
- System Features: distinct named features with requirements.
- Nonfunctional Requirements: measurable performance, security, quality, and business rules.
- Other Requirements: legal, database, and additional operational constraints.
- Appendices: glossary, analysis notes, TBD list only when genuinely unresolved.

## Output Intent

- Read like a serious SRS prepared by a human analyst.
- Stay complete enough for PDF export, JSON storage, and review.
