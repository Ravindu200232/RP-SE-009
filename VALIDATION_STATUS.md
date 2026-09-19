# AgentForge validation status

What was actually executed on this machine for the Python conversion of the
builder and QA agents.

## Passing

- Python compile across every agent and the server runtime.
- Repository test suite: 183 tests, 0 failures (`python test/run_suite.py`).
  This includes 79 new tests for the builder engine and 36 for the QA agent.
- `server_runtime` assembles and every symbol the HTTP layer calls resolves.
- Backend boot: MongoDB started, and `/projects`, `/models`, `/mongo`,
  `/settings`, `/srs-status`, `/deploy-status` and `/qa/<project>` all answered.
- Studio bridge exercised against a real project directory: project listing,
  file read/save, undo snapshot and restore, route enumeration, QA read-back
  and delete.
- Studio production build (`next build`) compiled and prerendered.
- Studio UI contracts: 42/42.
- Native tool calling against a live model (`gpt-oss:20b-cloud`): the model
  returned a well-formed `readFile` call with coerced arguments.
- End-to-end engine probe against that model: the loop wrote a file, read it
  back, and the completion gate refused to accept a completion claim with no
  runtime evidence, ending as `unverified` rather than looping.

## Found and fixed during validation

- Event payloads carrying a `name` key collided with the bus's own parameter,
  which would have broken every file write.
- Tool-call arguments were serialised as a JSON string; Ollama parses that
  field as an object and rejected the second request of every run.
- The unit coverage floor gated runs that had unit tests switched off.
- The completion gate could loop forever when a model never produced evidence.
- A transient provider 5xx ended a healthy run; it is now retried.
- `docker` was a contract skill for the microservices stack, so "no docker"
  could not remove it.

## Not claimed as executed here

- A complete real generated application built end to end with its database,
  browser journeys and deployment. That needs a long live run against the
  user's own services.
- `npm ci` in a clean checkout, Electron packaging, and live AWS/Vercel
  sign-in.
