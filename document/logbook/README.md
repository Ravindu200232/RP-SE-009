# Periodic log books — RP-SE-009

Four individual research-project log books covering **23 March 2026 – 25 August 2026**,
one per group member, in the departmental periodic log entry format.

| Component | Individual scope | Student |
| --- | --- | --- |
| Agent 1 | SRS agent and the SRS user interface | Nimthara Gunasinha (IT22078582) |
| Agent 2 | Code developer agent and the Studio user interface | Ravindu Bandara Subasinha (IT22098450) |
| Agent 3 | QA agent and the QA user interface | Hamna Hakeem (IT22516916) |
| Agent 4 | Deployment agent and the DevOps user interface | Malith P. Bandara (IT22249166) |

## Document layout

1. Project and student details
2. Summary of RP work carried out during the reporting period
3. Date-wise RP work — grouped by month for readability, with no signing inside
4. Project work planned before the next evaluation period
5. Declaration, supervisor's comments box, and **a single signature block at the
   end** — student, supervisor and co-supervisor side by side

## Presentation

Plain black and white throughout: no fills, no tints, no colour anywhere. Structure is
carried by rule weight and type weight instead of shading, so the document prints the
same on any printer and photocopies cleanly.

## Rebuilding

```bash
python document/logbook/build_logbooks.py
```

Content lives in `logbook_data.py`; edit an entry there and re-run. PDFs are printed
with the Chromium already present in the development image, so nothing extra needs to
be installed. Override the browser with `CHROME=/path/to/chrome` if required.

## Entry flow

Entries follow the natural progression of the research work rather than the shape of the
commit history — scope and standards study, component design, first implementation, the
user interface, evaluation of the first version, the rebuild, hardening and integration.
They are logged at a steady cadence of roughly two entries a week across the whole
period, so every month carries a comparable amount of recorded work and no month reads
as idle.

March holds fewer entries because the period opens on the 23rd, and August holds fewer
because it closes on the 25th.
