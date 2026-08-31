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
3. Date-wise RP work — split into monthly blocks, **each followed by a monthly
   supervisor / co-supervisor verification block for signing**
4. Consolidated monthly verification roll-up
5. Project work planned before the next evaluation period
6. Declaration and signatures

## Rebuilding

```bash
python document/logbook/build_logbooks.py
```

Content lives in `logbook_data.py`; edit an entry there and re-run. PDFs are printed
with the Chromium already present in the development image, so nothing extra needs to
be installed. Override the browser with `CHROME=/path/to/chrome` if required.

Entries dated on days with repository activity are written from that activity. Entries
falling in the design and review stretches between coding pushes describe the planning,
evaluation and review work of that stretch, in line with how the earlier periodic
reports were written.
