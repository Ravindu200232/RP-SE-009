---
url: /guide/cli.md
---

# Command Line Interface

## Commands

### `vitest`

Start Vitest in the current directory. Will enter the watch mode in development environment and run mode in CI (or non-interactive terminal) automatically.

You can pass an additional argument as the filter of the test files to run. For example:

```bash
vitest foobar
```

Will run only the test file that contains `foobar` in their paths. This filter only checks inclusion and doesn't support regexp or glob patterns (unless your terminal processes it before Vitest receives the filter).

Since Vitest 3, you can also specify the test by filename and line number:

```bash
$ vitest basic/foo.test.ts:10
```

::: warning
Note that Vitest requires the full filename for this feature to work. It can be relative to the current working directory or an absolute file path.

```bash
$ vitest basic/foo.js:10 # ✅
$ vitest ./basic/foo.js:10 # ✅
$ vitest /users/project/basic/foo.js:10 # ✅
$ vitest foo:10 # ❌
$ vitest ./basic/foo:10 # ❌
```

At the moment Vitest also doesn't support ranges:

```bash
$ vitest basic/foo.test.ts:10, basic/foo.test.ts:25 # ✅
$ vitest basic/foo.test.ts:10-25 # ❌
```

:::

### `vitest run`

Perform a single run without watch mode.

### `vitest watch`

Run all test suites but watch for changes and rerun tests when they change. Same as calling `vitest` without an argument. Will fallback to `vitest run` in CI or when stdin is not a TTY (non-interactive environment).

### `vitest dev`

Alias to `vitest watch`.

### `vitest related`

Run only tests that cover a list of source files. Works with static imports (e.g., `import('./index.js')` or `import index from './index.js`), but not the dynamic ones (e.g., `import(filepath)`). All files should be relative to root folder.

Useful to run with [`lint-staged`](https://github.com/okonet/lint-staged) or with your CI setup.

```bash
vitest related /src/index.ts /src/hello-world.js
```

::: tip
Don't forget that Vitest runs with enabled watch mode by default. If you are using tools like `lint-staged`, you  should also pass `--run` option, so that command can exit normally.

```js [.lintstagedrc.js]
export default {
  '*.{js,ts}': 'vitest related --run',
}
```

:::

### `vitest bench`

Run only [benchmark](/guide/features.html#benchmarking) tests, which compare performance results.

### `vitest init`

`vitest init <name>` can be used to setup project configuration. At the moment, it only supports [`browser`](/guide/browser/) value:

```bash
vitest init browser
```

### `vitest list`

`vitest list` command inherits all `vitest` options to print the list of all matching tests. This command ignores `reporters` option. By default, it will print the names of all tests that matched the file filter and name pattern:

```shell
vitest list filename.spec.ts -t="some-test"
```

```txt
describe > some-test
describe > some-test > test 1
describe > some-test > test 2
```

You can pass down `--json` flag to print tests in JSON format or save it in a separate file:

```bash
vitest list filename.spec.ts -t="some-test" --json=./file.json
```

If `--json` flag doesn't receive a value, it will output the JSON into stdout.

You also can pass down `--filesOnly` flag to print the test files only:

```bash
vitest list --filesOnly
```

```txt
tests/test1.test.ts
tests/test2.test.ts
```

Since Vitest 5, `vitest list` [parses test files](/api/advanced/vitest#parsespecifications) statically instead of running them to collect tests. Pass `--no-static-parse` to run the files instead. Vitest parses test files with limited concurrency, defaulting to `os.availableParallelism()`. You can change it via the `--static-parse-concurrency` option.

### `vitest doctor`

`vitest doctor` measures how much faster the test suite would run under alternative configurations by running it under each of them. The candidates are picked based on the current config:

```bash
vitest doctor
```

```
Results (min of 3 runs each)

  baseline (pool: forks · isolate: true)  4.08s
  pool: 'threads'                         3.64s (-11%)
  pool: 'vmThreads'                       1.33s (-67%)
  isolate: false                          1.28s (-69%)

Recommendation: pool: 'vmThreads' (-67%)

  // vitest.config.ts
  import { defineConfig } from 'vitest/config'

  export default defineConfig({
    test: {
      pool: 'vmThreads', // measured -67% on this suite
    },
  })
```

The `isolate: false` candidate is additionally validated by running the suite twice with a shuffled file order: if any test depends on isolation, the candidate is reported as failed instead of recommended. When several candidates are close to the fastest, doctor prefers the one that keeps per-file isolation.

Doctor also probes lower [`maxWorkers`](/config/maxworkers) values on top of the winning configuration: every worker funnels its transform requests through the single main-thread Vite server, so past a certain count more workers make the run slower, not faster. Starting from half the current worker count, doctor keeps halving while the suite gets at least 5% faster, and includes the winning value in the recommendation.

Suites running a DOM environment are measured under both vm pools, `vmThreads` and `vmForks`: they amortize the environment creation cost by keeping one environment per worker while every file still gets a fresh VM context. `vmForks` uses child processes instead of worker threads: each child gets its own heap and garbage collector, so either pool can come out faster depending on the suite, and `vmForks` is the vm option for suites that cannot run in worker threads.

Projects running `jsdom` are also measured under `environment: 'happy-dom'` when the package is installed. The swap is applied per project; projects on other environments keep them. happy-dom implements the DOM differently than jsdom, so tests that depend on layout or navigation should be verified before adopting the swap. When the [fs module cache](/config/fsmodulecache) is off, doctor measures `fsModuleCache: true` after an untimed priming run that populates the cache, so the reported time is what repeated runs pay.

Every measurement runs the full suite, including browser projects: `isolate: false` also affects browser mode. Candidates that cannot affect browser projects (`pool`, `environment`, the fs module cache) are picked based on the node-side projects only.

Failing candidates are reported with an excerpt of their errors. If the suite fails under the current configuration, doctor aborts and shows the errors: it needs a passing baseline to compare against.

Short suites are measured multiple times and the best time is reported, so the comparison reflects a warm steady state. Doctor runs the full suite several times, so it takes a multiple of a normal run's time. See [Improving Performance](/guide/improving-performance) for the trade-offs behind every candidate.

Doctor measures and reports the baseline even when there are no candidates to compare. Configurations on a `vm` pool are additionally compared against `pool: 'threads'` with `isolate: false`, which also reuses workers but shares module state between files; a configuration already on one vm pool is still measured under the other.

## Shell Autocompletions

Vitest provides shell autocompletions for commands, options, and option values powered by [`@bomb.sh/tab`](https://github.com/bombshell-dev/tab).

### Setup

For permanent setup in zsh, add this to your `~/.zshrc`:

```bash
# Add to ~/.zshrc for permanent autocompletions (same can be done for other shells)
source <(vitest complete zsh)
```

### Package Manager Integration

`@bomb.sh/tab` integrates with [package managers](https://github.com/bombshell-dev/tab?tab=readme-ov-file#package-manager-completions). Autocompletions work when running vitest directly:

::: code-group

```bash [npm]
npm vitest <Tab>
```

```bash [npm]
npm exec vitest <Tab>
```

```bash [pnpm]
pnpm vitest <Tab>
```

```bash [yarn]
yarn vitest <Tab>
```

```bash [bun]
bun vitest <Tab>
```

:::

For package manager autocompletions, you should install [tab's package manager completions](https://github.com/bombshell-dev/tab?tab=readme-ov-file#package-manager-completions) separately.

## Options

::: tip
Vitest supports both camel case and kebab case for [CLI arguments](https://github.com/cacjs/cac#dot-nested-options). For example, `--passWithNoTests` and `--pass-with-no-tests` will both work (`--no-color` and `--inspect-brk` are the exceptions).

Vitest also supports different ways of specifying the value: `--reporter dot` and `--reporter=dot` are both valid.

If option supports an array of values, you need to pass the option multiple times:

```
vitest --reporter=dot --reporter=default
```

Boolean options can be negated with `no-` prefix. Specifying the value as `false` also works:

```
vitest --no-api
vitest --api=false
```

:::

### root

* **CLI:** `-r, --root <path>`
* **Config:** [root](/config/root)

Root path

### config

* **CLI:** `-c, --config <path>`

Path to config file

### update

* **CLI:** `-u, --update [type]`
* **Config:** [update](/config/update)

Update snapshot (accepts boolean, "new", "all" or "none")

### watch

* **CLI:** `-w, --watch`
* **Config:** [watch](/config/watch)

Enable watch mode

### testNamePattern

* **CLI:** `-t, --testNamePattern <pattern>`
* **Config:** [testNamePattern](/config/testnamepattern)

Run tests with full names matching the specified regexp pattern

### dir

* **CLI:** `--dir <path>`
* **Config:** [dir](/config/dir)

Base directory to scan for the test files

### ui

* **CLI:** `--ui`

Enable UI

### open

* **CLI:** `--open`
* **Config:** [open](/config/open)

Open UI automatically (default: `!process.env.CI`)

### api.port

* **CLI:** `--api.port [port]`

Specify server port. Note if the port is already being used, Vite will automatically try the next available port so this may not be the actual port the server ends up listening on. If true will be set to `51204`

### api.host

* **CLI:** `--api.host [host]`

Specify which IP addresses the server should listen on. Set this to `0.0.0.0` or `true` to listen on all addresses, including LAN and public addresses

### api.strictPort

* **CLI:** `--api.strictPort`

Set to true to exit if port is already in use, instead of automatically trying the next available port

### api.allowExec

* **CLI:** `--api.allowExec`
* **Config:** [api.allowExec](/config/api#api-allowexec)

Allow API to execute code. (Be careful when enabling this option in untrusted environments)

### api.allowWrite

* **CLI:** `--api.allowWrite`
* **Config:** [api.allowWrite](/config/api#api-allowwrite)

Allow API to edit files. (Be careful when enabling this option in untrusted environments)

### silent

* **CLI:** `--silent [value]`
* **Config:** [silent](/config/silent)

Silent console output from tests. Use `'passed-only'` to see logs from failing tests only.

### hideSkippedTests

* **CLI:** `--hideSkippedTests`

Hide logs for skipped tests

### reporters

* **CLI:** `--reporter <name>`
* **Config:** [reporters](/config/reporters)

Specify reporters (default, agent, minimal, blob, verbose, dot, json, tap, tap-flat, junit, tree, hanging-process, github-actions)

### outputFile

* **CLI:** `--outputFile <filename/-s>`
* **Config:** [outputFile](/config/outputfile)

Write test results to a file when supporter reporter is also specified, use cac's dot notation for individual outputs of multiple reporters (example: `--outputFile.tap=./tap.txt`)

### coverage.provider

* **CLI:** `--coverage.provider <name>`
* **Config:** [coverage.provider](/config/coverage#coverage-provider)

Select the tool for coverage collection, available values are: "v8", "istanbul" and "custom"

### coverage.enabled

* **CLI:** `--coverage.enabled`
* **Config:** [coverage.enabled](/config/coverage#coverage-enabled)

Enables coverage collection. Can be overridden using the `--coverage` CLI option (default: `false`)

### coverage.include

* **CLI:** `--coverage.include <pattern>`
* **Config:** [coverage.include](/config/coverage#coverage-include)

Files included in coverage as glob patterns. May be specified more than once when using multiple patterns. By default only files covered by tests are included.

### coverage.exclude

* **CLI:** `--coverage.exclude <pattern>`
* **Config:** [coverage.exclude](/config/coverage#coverage-exclude)

Files to be excluded in coverage. May be specified more than once when using multiple extensions.

### coverage.clean

* **CLI:** `--coverage.clean`
* **Config:** [coverage.clean](/config/coverage#coverage-clean)

Clean coverage results before running tests (default: true)

### coverage.cleanOnRerun

* **CLI:** `--coverage.cleanOnRerun`
* **Config:** [coverage.cleanOnRerun](/config/coverage#coverage-cleanonrerun)

Clean coverage report on watch rerun (default: true)

### coverage.reportsDirectory

* **CLI:** `--coverage.reportsDirectory <path>`
* **Config:** [coverage.reportsDirectory](/config/coverage#coverage-reportsdirectory)

Directory to write coverage report to (default: ./coverage)

### coverage.reporter

* **CLI:** `--coverage.reporter <name>`
* **Config:** [coverage.reporter](/config/coverage#coverage-reporter)

Coverage reporters to use. Visit [`coverage.reporter`](/config/coverage#coverage-reporter) for more information (default: `["text", "html", "clover", "json"]`)

### coverage.reportOnFailure

* **CLI:** `--coverage.reportOnFailure`
* **Config:** [coverage.reportOnFailure](/config/coverage#coverage-reportonfailure)

Generate coverage report even when tests fail (default: `false`)

### coverage.allowExternal

* **CLI:** `--coverage.allowExternal`
* **Config:** [coverage.allowExternal](/config/coverage#coverage-allowexternal)

Collect coverage of files outside the project root (default: `false`)

### coverage.skipFull

* **CLI:** `--coverage.skipFull`
* **Config:** [coverage.skipFull](/config/coverage#coverage-skipfull)

Do not show files with 100% statement, branch, and function coverage (default: `false`)

### coverage.thresholds.100

* **CLI:** `--coverage.thresholds.100`
* **Config:** [coverage.thresholds.100](/config/coverage#coverage-thresholds-100)

Shortcut to set all coverage thresholds to 100 (default: `false`)

### coverage.thresholds.perFile

* **CLI:** `--coverage.thresholds.perFile <boolean>`
* **Config:** [coverage.thresholds.perFile](/config/coverage#coverage-thresholds-perfile)

Check thresholds per file. See `--coverage.thresholds.lines`, `--coverage.thresholds.functions`, `--coverage.thresholds.branches` and `--coverage.thresholds.statements` for the actual thresholds (default: `false`). Object form is available in config files only.

### coverage.thresholds.autoUpdate

* **CLI:** `--coverage.thresholds.autoUpdate <boolean|function>`
* **Config:** [coverage.thresholds.autoUpdate](/config/coverage#coverage-thresholds-autoupdate)

Update threshold values: "lines", "functions", "branches" and "statements" to configuration file when current coverage is above the configured thresholds (default: `false`)

### coverage.thresholds.lines

* **CLI:** `--coverage.thresholds.lines <number>`

Threshold for lines. Visit [istanbuljs](https://github.com/istanbuljs/nyc#coverage-thresholds) for more information. This option is not available for custom providers

### coverage.thresholds.functions

* **CLI:** `--coverage.thresholds.functions <number>`

Threshold for functions. Visit [istanbuljs](https://github.com/istanbuljs/nyc#coverage-thresholds) for more information. This option is not available for custom providers

### coverage.thresholds.branches

* **CLI:** `--coverage.thresholds.branches <number>`

Threshold for branches. Visit [istanbuljs](https://github.com/istanbuljs/nyc#coverage-thresholds) for more information. This option is not available for custom providers

### coverage.thresholds.statements

* **CLI:** `--coverage.thresholds.statements <number>`

Threshold for statements. Visit [istanbuljs](https://github.com/istanbuljs/nyc#coverage-thresholds) for more information. This option is not available for custom providers

### coverage.ignoreClassMethods

* **CLI:** `--coverage.ignoreClassMethods <name>`
* **Config:** [coverage.ignoreClassMethods](/config/coverage#coverage-ignoreclassmethods)

Array of class method names to ignore for coverage. Visit [istanbuljs](https://github.com/istanbuljs/nyc#ignoring-methods) for more information. This option is only available for the istanbul providers (default: `[]`)

### coverage.processingConcurrency

* **CLI:** `--coverage.processingConcurrency <number>`
* **Config:** [coverage.processingConcurrency](/config/coverage#coverage-processingconcurrency)

Concurrency limit used when processing the coverage results. (default min between 20 and the number of CPUs)

### coverage.customProviderModule

* **CLI:** `--coverage.customProviderModule <path>`
* **Config:** [coverage.customProviderModule](/config/coverage#coverage-customprovidermodule)

Specifies the module name or path for the custom coverage provider module. Visit [Custom Coverage Provider](/guide/coverage#custom-coverage-provider) for more information. This option is only available for custom providers

### coverage.watermarks.statements

* **CLI:** `--coverage.watermarks.statements <watermarks>`

High and low watermarks for statements in the format of `<high>,<low>`

### coverage.watermarks.lines

* **CLI:** `--coverage.watermarks.lines <watermarks>`

High and low watermarks for lines in the format of `<high>,<low>`

### coverage.watermarks.branches

* **CLI:** `--coverage.watermarks.branches <watermarks>`

High and low watermarks for branches in the format of `<high>,<low>`

### coverage.watermarks.functions

* **CLI:** `--coverage.watermarks.functions <watermarks>`

High and low watermarks for functions in the format of `<high>,<low>`

### coverage.changed

* **CLI:** `--coverage.changed <commit/branch>`
* **Config:** [coverage.changed](/config/coverage#coverage-changed)

Collect coverage only for files changed since a specified commit or branch (e.g., `origin/main` or `HEAD~1`). Inherits value from `--changed` by default.

### coverage.excludeAfterRemap

* **CLI:** `--coverage.excludeAfterRemap`
* **Config:** [coverage.excludeAfterRemap](/config/coverage#coverage-excludeafterremap)

Apply exclusions again after coverage has been remapped to original sources. (default: false)

### coverage.htmlDir

* **CLI:** `--coverage.htmlDir <path>`
* **Config:** [coverage.htmlDir](/config/coverage#coverage-htmldir)

Directory of HTML coverage output to be served in UI mode and HTML reporter.

### coverage.autoAttachSubprocess

* **CLI:** `--coverage.autoAttachSubprocess`
* **Config:** [coverage.autoAttachSubprocess](/config/coverage#coverage-autoattachsubprocess)

Track coverage of the `node:child_process` and `node:worker_threads` spawned during test run. Supported only by `v8` provider. (default: false)

### mode

* **CLI:** `--mode <name>`
* **Config:** [mode](/config/mode)

Override Vite mode (default: `test`)

### isolate

* **CLI:** `--isolate`
* **Config:** [isolate](/config/isolate)

Run every test file in isolation. To disable isolation, use `--no-isolate` (default: `true`)

### globals

* **CLI:** `--globals`
* **Config:** [globals](/config/globals)

Inject apis globally

### injectCjsGlobals

* **CLI:** `--injectCjsGlobals`
* **Config:** [injectCjsGlobals](/config/injectcjsglobals)

Inject CommonJS variables (`module`, `exports`, `require`, `__filename`, `__dirname`) into every test module. To disable, use `--no-inject-cjs-globals` (default: `true`)

### dom

* **CLI:** `--dom`

Mock browser API with happy-dom

### browser.enabled

* **CLI:** `--browser.enabled`
* **Config:** [browser.enabled](/config/browser/enabled)

Run tests in the browser. Equivalent to `--browser.enabled` (default: `false`)

### browser.name

* **CLI:** `--browser.name <name>`

Run all tests in a specific browser. Some browsers are only available for specific providers (see `--browser.provider`).

### browser.headless

* **CLI:** `--browser.headless`
* **Config:** [browser.headless](/config/browser/headless)

Run the browser in headless mode (i.e. without opening the GUI (Graphical User Interface)). If you are running Vitest in CI, it will be enabled by default (default: `process.env.CI`)

### browser.ui

* **CLI:** `--browser.ui`
* **Config:** [browser.ui](/config/browser/ui)

Show Vitest UI when running tests (default: `!process.env.CI`)

### browser.detailsPanelPosition

* **CLI:** `--browser.detailsPanelPosition <position>`
* **Config:** [browser.detailsPanelPosition](/config/browser/detailspanelposition)

Default position for the details panel in browser mode. Either `right` (horizontal split) or `bottom` (vertical split) (default: `right`)

### browser.connectTimeout

* **CLI:** `--browser.connectTimeout <timeout>`
* **Config:** [browser.connectTimeout](/config/browser/connecttimeout)

If connection to the browser takes longer, the test suite will fail (default: `60_000`)

### browser.dependencySourcemaps

* **CLI:** `--browser.dependencySourcemaps`
* **Config:** [browser.dependencySourcemaps](/config/browser/dependencysourcemaps)

Serve sourcemaps of dependencies to the browser in headless runs, used by devtools when debugging into `node_modules`. Reported test errors are source-mapped either way. Use `--browser.dependencySourcemaps=false` to speed up test runs if you don't step into dependency code (default: `true`)

### browser.trackUnhandledErrors

* **CLI:** `--browser.trackUnhandledErrors`
* **Config:** [browser.trackUnhandledErrors](/config/browser/trackunhandlederrors)

Control if Vitest catches uncaught exceptions so they can be reported (default: `true`)

### browser.trace

* **CLI:** `--browser.trace <mode>`
* **Config:** [browser.trace](/config/browser/trace)

Enable trace view mode. Supported: "on", "off", "on-first-retry", "on-all-retries", "retain-on-failure".

### browser.traceView.enabled

* **CLI:** `--browser.traceView.enabled`
* **Config:** [browser.traceView.enabled](/config/browser/traceview#traceview-enabled)

Enable Vitest trace-view collection for browser tests (default: `false`)

### browser.traceView.recordCanvas

* **CLI:** `--browser.traceView.recordCanvas`
* **Config:** [browser.traceView.recordCanvas](/config/browser/traceview#traceview-recordcanvas)

Capture canvas pixels in trace-view snapshots (default: `false`)

### browser.traceView.inlineImages

* **CLI:** `--browser.traceView.inlineImages`
* **Config:** [browser.traceView.inlineImages](/config/browser/traceview#traceview-inlineimages)

Inline loaded image pixels in trace-view snapshots (default: `false`)

### browser.locators.exact

* **CLI:** `--browser.locators.exact`
* **Config:** [browser.locators.exact](/config/browser/locators#locators-exact)

Should locators match the text exactly by default (default: `true`)

### pool

* **CLI:** `--pool <pool>`
* **Config:** [pool](/config/pool)

Specify pool, if not running in the browser (default: `forks`)

### execArgv

* **CLI:** `--execArgv <option>`
* **Config:** [execArgv](/config/execargv)

Pass additional arguments to `node` process when spawning `worker_threads` or `child_process`.

### vmMemoryLimit

* **CLI:** `--vmMemoryLimit <limit>`
* **Config:** [vmMemoryLimit](/config/vmmemorylimit)

Memory limit for VM pools. If you see memory leaks, try to tinker this value.

### fileParallelism

* **CLI:** `--fileParallelism`
* **Config:** [fileParallelism](/config/fileparallelism)

Should all test files run in parallel. Use `--no-file-parallelism` to disable (default: `true`)

### maxWorkers

* **CLI:** `--maxWorkers <workers>`
* **Config:** [maxWorkers](/config/maxworkers)

Maximum number or percentage of workers to run tests in

### environment

* **CLI:** `--environment <name>`
* **Config:** [environment](/config/environment)

Specify runner environment, if not running in the browser (default: `node`)

### passWithNoTests

* **CLI:** `--passWithNoTests`
* **Config:** [passWithNoTests](/config/passwithnotests)

Pass when no tests are found

### logHeapUsage

* **CLI:** `--logHeapUsage`
* **Config:** [logHeapUsage](/config/logheapusage)

Show the size of heap for each test when running in node

### detectAsyncLeaks

* **CLI:** `--detectAsyncLeaks`
* **Config:** [detectAsyncLeaks](/config/detectasyncleaks)

Detect asynchronous resources leaking from the test file (default: `false`)

### allowOnly

* **CLI:** `--allowOnly`
* **Config:** [allowOnly](/config/allowonly)

Allow tests and suites that are marked as only (default: `!process.env.CI`)

### dangerouslyIgnoreUnhandledErrors

* **CLI:** `--dangerouslyIgnoreUnhandledErrors`
* **Config:** [dangerouslyIgnoreUnhandledErrors](/config/dangerouslyignoreunhandlederrors)

Ignore any unhandled errors that occur

### changed

* **CLI:** `--changed [since]`
* **Config:** [changed](/config/changed)

Run tests that are affected by the changed files (default: `false`)

### sequence.shuffle.files

* **CLI:** `--sequence.shuffle.files`
* **Config:** [sequence.shuffle.files](/config/sequence#sequence-shuffle-files)

Run files in a random order. Long running tests will not start earlier if you enable this option. (default: `false`)

### sequence.shuffle.tests

* **CLI:** `--sequence.shuffle.tests`
* **Config:** [sequence.shuffle.tests](/config/sequence#sequence-shuffle-tests)

Run tests in a random order (default: `false`)

### sequence.concurrent

* **CLI:** `--sequence.concurrent`
* **Config:** [sequence.concurrent](/config/sequence#sequence-concurrent)

Make tests run in parallel (default: `false`)

### sequence.seed

* **CLI:** `--sequence.seed <seed>`
* **Config:** [sequence.seed](/config/sequence#sequence-seed)

Set the randomization seed. This option will have no effect if `--sequence.shuffle` is falsy. Visit ["Random Seed" page](https://en.wikipedia.org/wiki/Random_seed) for more information

### sequence.hooks

* **CLI:** `--sequence.hooks <order>`
* **Config:** [sequence.hooks](/config/sequence#sequence-hooks)

Changes the order in which hooks are executed. Accepted values are: "stack", "list" and "parallel". Visit [`sequence.hooks`](/config/sequence#sequence-hooks) for more information (default: `"parallel"`)

### sequence.setupFiles

* **CLI:** `--sequence.setupFiles <order>`
* **Config:** [sequence.setupFiles](/config/sequence#sequence-setupfiles)

Changes the order in which setup files are executed. Accepted values are: "list" and "parallel". If set to "list", will run setup files in the order they are defined. If set to "parallel", will run setup files in parallel (default: `"parallel"`)

### inspect

* **CLI:** `--inspect [[host:]port]`

Enable Node.js inspector (default: `127.0.0.1:9229`)

### inspectBrk

* **CLI:** `--inspectBrk [[host:]port]`

Enable Node.js inspector and break before the test starts

### testTimeout

* **CLI:** `--testTimeout <timeout>`
* **Config:** [testTimeout](/config/testtimeout)

Default timeout of a test in milliseconds (default: `5000`). Use `0` to disable timeout completely.

### hookTimeout

* **CLI:** `--hookTimeout <timeout>`
* **Config:** [hookTimeout](/config/hooktimeout)

Default hook timeout in milliseconds (default: `10000`). Use `0` to disable timeout completely.

### bail

* **CLI:** `--bail <number>`
* **Config:** [bail](/config/bail)

Stop test execution when given number of tests have failed (default: `0`)

### retry.count

* **CLI:** `--retry.count <times>`
* **Config:** [retry.count](/config/retry#retry-count)

Number of times to retry a test if it fails (default: `0`)

### retry.delay

* **CLI:** `--retry.delay <ms>`
* **Config:** [retry.delay](/config/retry#retry-delay)

Delay in milliseconds between retry attempts (default: `0`)

### retry.condition

* **CLI:** `--retry.condition <pattern>`
* **Config:** [retry.condition](/config/retry#retry-condition)

Regex pattern to match error messages that should trigger a retry. Only errors matching this pattern will cause a retry (default: retry on all errors)

### repeats

* **CLI:** `--repeats <number>`
* **Config:** [repeats](/config/repeats)

Repeat every test a specific number of times regardless of the result (default: `0`)

### diff.aAnnotation

* **CLI:** `--diff.aAnnotation <annotation>`
* **Config:** [diff.aAnnotation](/config/diff#diff-aannotation)

Annotation for expected lines (default: `Expected`)

### diff.aIndicator

* **CLI:** `--diff.aIndicator <indicator>`
* **Config:** [diff.aIndicator](/config/diff#diff-aindicator)

Indicator for expected lines (default: `-`)

### diff.bAnnotation

* **CLI:** `--diff.bAnnotation <annotation>`
* **Config:** [diff.bAnnotation](/config/diff#diff-bannotation)

Annotation for received lines (default: `Received`)

### diff.bIndicator

* **CLI:** `--diff.bIndicator <indicator>`
* **Config:** [diff.bIndicator](/config/diff#diff-bindicator)

Indicator for received lines (default: `+`)

### diff.commonIndicator

* **CLI:** `--diff.commonIndicator <indicator>`
* **Config:** [diff.commonIndicator](/config/diff#diff-commonindicator)

Indicator for common lines (default: ` `)

### diff.contextLines

* **CLI:** `--diff.contextLines <lines>`
* **Config:** [diff.contextLines](/config/diff#diff-contextlines)

Number of lines of context to show around each change (default: `5`)

### diff.emptyFirstOrLastLinePlaceholder

* **CLI:** `--diff.emptyFirstOrLastLinePlaceholder <placeholder>`
* **Config:** [diff.emptyFirstOrLastLinePlaceholder](/config/diff#diff-emptyfirstorlastlineplaceholder)

Placeholder for an empty first or last line (default: `""`)

### diff.expand

* **CLI:** `--diff.expand`
* **Config:** [diff.expand](/config/diff#diff-expand)

Expand all common lines (default: `true`)

### diff.includeChangeCounts

* **CLI:** `--diff.includeChangeCounts`
* **Config:** [diff.includeChangeCounts](/config/diff#diff-includechangecounts)

Include comparison counts in diff output (default: `false`)

### diff.omitAnnotationLines

* **CLI:** `--diff.omitAnnotationLines`
* **Config:** [diff.omitAnnotationLines](/config/diff#diff-omitannotationlines)

Omit annotation lines from the output (default: `false`)

### diff.printBasicPrototype

* **CLI:** `--diff.printBasicPrototype`
* **Config:** [diff.printBasicPrototype](/config/diff#diff-printbasicprototype)

Print basic prototype Object and Array (default: `true`)

### diff.maxDepth

* **CLI:** `--diff.maxDepth <maxDepth>`
* **Config:** [diff.maxDepth](/config/diff#diff-maxdepth)

Limit the depth to recurse when printing nested objects (default: `20`)

### diff.truncateThreshold

* **CLI:** `--diff.truncateThreshold <threshold>`
* **Config:** [diff.truncateThreshold](/config/diff#diff-truncatethreshold)

Number of lines to show before and after each change (default: `0`)

### diff.truncateAnnotation

* **CLI:** `--diff.truncateAnnotation <annotation>`
* **Config:** [diff.truncateAnnotation](/config/diff#diff-truncateannotation)

Annotation for truncated lines (default: `... Diff result is truncated`)

### exclude

* **CLI:** `--exclude <glob>`
* **Config:** [exclude](/config/exclude)

Additional file globs to be excluded from test

### expandSnapshotDiff

* **CLI:** `--expandSnapshotDiff`
* **Config:** [expandSnapshotDiff](/config/expandsnapshotdiff)

Show full diff when snapshot fails

### disableConsoleIntercept

* **CLI:** `--disableConsoleIntercept`
* **Config:** [disableConsoleIntercept](/config/disableconsoleintercept)

Disable automatic interception of console logging (default: `false`)

### typecheck.enabled

* **CLI:** `--typecheck.enabled`
* **Config:** [typecheck.enabled](/config/typecheck#typecheck-enabled)

Enable typechecking alongside tests (default: `false`)

### typecheck.only

* **CLI:** `--typecheck.only`
* **Config:** [typecheck.only](/config/typecheck#typecheck-only)

Run only typecheck tests. This automatically enables typecheck (default: `false`)

### typecheck.checker

* **CLI:** `--typecheck.checker <name>`
* **Config:** [typecheck.checker](/config/typecheck#typecheck-checker)

Specify the typechecker to use. Available values are: "tsc" and "vue-tsc" and a path to an executable (default: `"tsc"`)

### typecheck.allowJs

* **CLI:** `--typecheck.allowJs`
* **Config:** [typecheck.allowJs](/config/typecheck#typecheck-allowjs)

Allow JavaScript files to be typechecked. By default takes the value from tsconfig.json

### typecheck.ignoreSourceErrors

* **CLI:** `--typecheck.ignoreSourceErrors`
* **Config:** [typecheck.ignoreSourceErrors](/config/typecheck#typecheck-ignoresourceerrors)

Ignore type errors from source files

### typecheck.build

* **CLI:** `--typecheck.build`
* **Config:** [typecheck.build](/config/typecheck#typecheck-build)

Use TypeScript build mode

### typecheck.tsconfig

* **CLI:** `--typecheck.tsconfig <path>`
* **Config:** [typecheck.tsconfig](/config/typecheck#typecheck-tsconfig)

Path to a custom tsconfig file

### typecheck.spawnTimeout

* **CLI:** `--typecheck.spawnTimeout <time>`
* **Config:** [typecheck.spawnTimeout](/config/typecheck#typecheck-spawntimeout)

Minimum time in milliseconds it takes to spawn the typechecker

### project

* **CLI:** `-p, --project <name>`

The name of the project to run if you are using Vitest workspace feature. This can be repeated for multiple projects: `--project=1 --project=2`. You can also filter projects using wildcards like `--project=packages*`, and exclude projects with `--project=!pattern`. A project runs if it matches no negated pattern and, when regular patterns are also given, matches at least one of them.

### slowTestThreshold

* **CLI:** `--slowTestThreshold <threshold>`
* **Config:** [slowTestThreshold](/config/slowtestthreshold)

Threshold in milliseconds for a test or suite to be considered slow (default: `300`)

### teardownTimeout

* **CLI:** `--teardownTimeout <timeout>`
* **Config:** [teardownTimeout](/config/teardowntimeout)

Default timeout of a teardown function in milliseconds (default: `10000`)

### maxConcurrency

* **CLI:** `--maxConcurrency <number>`
* **Config:** [maxConcurrency](/config/maxconcurrency)

Maximum number of concurrent tests and suites during test file execution (default: `5`)

### fsModuleCache

* **CLI:** `--fsModuleCache`
* **Config:** [fsModuleCache](/config/fsmodulecache)

Cache transformed modules on the file system and reuse them between reruns (default: `false`)

### fsModuleCachePath

* **CLI:** `--fsModuleCachePath <path>`
* **Config:** [fsModuleCachePath](/config/fsmodulecachepath)

Directory where the `fsModuleCache` is stored (default: `node_modules/.vitest-cache`)

### expect.requireAssertions

* **CLI:** `--expect.requireAssertions`
* **Config:** [expect.requireAssertions](/config/expect#expect-requireassertions)

Require that all tests have at least one assertion

### expect.poll.interval

* **CLI:** `--expect.poll.interval <interval>`
* **Config:** [expect.poll.interval](/config/expect#expect-poll-interval)

Poll interval in milliseconds for `expect.poll()` assertions (default: `50`)

### expect.poll.timeout

* **CLI:** `--expect.poll.timeout <timeout>`
* **Config:** [expect.poll.timeout](/config/expect#expect-poll-timeout)

Poll timeout in milliseconds for `expect.poll()` assertions (default: `1000`)

### printConsoleTrace

* **CLI:** `--printConsoleTrace`
* **Config:** [printConsoleTrace](/config/printconsoletrace)

Always print console stack traces

### includeTaskLocation

* **CLI:** `--includeTaskLocation`
* **Config:** [includeTaskLocation](/config/includetasklocation)

Collect test and suite locations in the `location` property

### attachmentsDir

* **CLI:** `--attachmentsDir <dir>`
* **Config:** [attachmentsDir](/config/attachmentsdir)

The directory where attachments from `context.annotate` are stored in (default: `.vitest/attachments`)

### run

* **CLI:** `--run`

Disable watch mode

### color

* **CLI:** `--no-color`

Removes colors from the console output

### clearScreen

* **CLI:** `--clearScreen`

Clear terminal screen when re-running tests during watch mode (default: `true`)

### configLoader

* **CLI:** `--configLoader <loader>`

Use `bundle` to bundle the config with esbuild or `runner` (experimental) to process it on the fly. This is only available in vite version 6.1.0 and above. (default: `bundle`)

### standalone

* **CLI:** `--standalone`

Start Vitest without running tests. Tests will be running only on change. If browser mode is enabled, the UI will be opened automatically. This option is ignored when CLI file filters are passed. (default: `false`)

### listTags

* **CLI:** `--listTags [type]`

List all available tags instead of running tests. `--list-tags=json` will output tags in JSON format, unless there are no tags.

### clearCache

* **CLI:** `--clearCache`

Delete all Vitest caches, including the `fsModuleCache`, without running any tests. This will reduce the performance in the subsequent test run.

### tagsFilter

* **CLI:** `--tagsFilter <expression>`

Run only tests with the specified tags. You can use logical operators `&&` (and), `||` (or) and `!` (not) to create complex expressions, see [Test Tags](/guide/test-tags#syntax) for more information.

### strictTags

* **CLI:** `--strictTags`
* **Config:** [strictTags](/config/stricttags)

Should Vitest throw an error if test has a tag that is not defined in the config. (default: `true`)

### sharedViteServer

* **CLI:** `--sharedViteServer`
* **Config:** [sharedViteServer](/config/sharedviteserver)

Let inline projects that don't modify the Vite config reuse the Vite server of the config that declares them. (default: `true`)

### experimental.importDurations.print

* **CLI:** `--experimental.importDurations.print <boolean|on-warn>`
* **Config:** [experimental.importDurations.print](/config/experimental#experimental-importdurations-print)

When to print import breakdown to CLI terminal. Use `true` to always print, `false` to never print, or `on-warn` to print only when imports exceed the warn threshold (default: false).

### experimental.importDurations.limit

* **CLI:** `--experimental.importDurations.limit <number>`
* **Config:** [experimental.importDurations.limit](/config/experimental#experimental-importdurations-limit)

Maximum number of imports to collect and display (default: 0, or 10 if print or UI is enabled).

### experimental.importDurations.failOnDanger

* **CLI:** `--experimental.importDurations.failOnDanger`
* **Config:** [experimental.importDurations.failOnDanger](/config/experimental#experimental-importdurations-failondanger)

Fail the test run if any import exceeds the danger threshold (default: false).

### experimental.importDurations.thresholds.warn

* **CLI:** `--experimental.importDurations.thresholds.warn <number>`
* **Config:** [experimental.importDurations.thresholds.warn](/config/experimental#experimental-importdurations-thresholds-warn)

Warning threshold - imports exceeding this are shown in yellow/orange (default: 100).

### experimental.importDurations.thresholds.danger

* **CLI:** `--experimental.importDurations.thresholds.danger <number>`
* **Config:** [experimental.importDurations.thresholds.danger](/config/experimental#experimental-importdurations-thresholds-danger)

Danger threshold - imports exceeding this are shown in red (default: 500).

### experimental.viteModuleRunner

* **CLI:** `--experimental.viteModuleRunner`
* **Config:** [experimental.viteModuleRunner](/config/experimental#experimental-vitemodulerunner)

Control whether Vitest uses Vite's module runner to run the code or fallback to the native `import`. (default: `true`)

### experimental.nodeLoader

* **CLI:** `--experimental.nodeLoader`
* **Config:** [experimental.nodeLoader](/config/experimental#experimental-nodeloader)

Controls whether Vitest will use Node.js Loader API to process in-source or mocked files. This has no effect if `viteModuleRunner` is enabled. Disabling this can increase performance. (default: `true`)

### experimental.vcsProvider

* **CLI:** `--experimental.vcsProvider <path>`
* **Config:** [experimental.vcsProvider](/config/experimental#experimental-vcsprovider)

Custom provider for detecting changed files. (default: `git`)

### experimental.preParse

* **CLI:** `--experimental.preParse`
* **Config:** [experimental.preParse](/config/experimental#experimental-preparse)

Parse test specifications before running them. This will apply `.only` flag and test name pattern across all files without running them. (default: `false`)

### experimental.diagnostics.isolate

* **CLI:** `--experimental.diagnostics.isolate`
* **Config:** [experimental.diagnostics.isolate](/config/experimental#experimental-diagnostics-isolate)

Print a hint estimating how much time `isolate: false` would save when `isolate: true` spends a significant amount of time spawning a worker per test file. (default: `true`)

### experimental.diagnostics.environment

* **CLI:** `--experimental.diagnostics.environment`
* **Config:** [experimental.diagnostics.environment](/config/experimental#experimental-diagnostics-environment)

Print a hint when re-creating a DOM environment for every test file dominates the run and a `vm` pool would set it up once per worker. (default: `true`)

### experimental.diagnostics.import

* **CLI:** `--experimental.diagnostics.import`
* **Config:** [experimental.diagnostics.import](/config/experimental#experimental-diagnostics-import)

Print a hint when test files repeatedly evaluate the same module graph (typical for barrel-file imports) and `isolate: false` would evaluate it once per worker. (default: `true`)

### experimental.diagnostics.transform

* **CLI:** `--experimental.diagnostics.transform`
* **Config:** [experimental.diagnostics.transform](/config/experimental#experimental-diagnostics-transform)

Print a hint when transforming modules dominates the run and `fsModuleCache` would persist the results across runs. (default: `true`)

### shard

* **Type:** `string`
* **Default:** disabled

Test suite shard to execute in a format of `<index>`/`<count>`, where

* `count` is a positive integer, count of divided parts
* `index` is a positive integer, index of divided part

This command will divide all tests into `count` equal parts, and will run only those that happen to be in an `index` part. For example, to split your tests suite into three parts, use this:

```sh
vitest run --shard=1/3
vitest run --shard=2/3
vitest run --shard=3/3
```

:::warning
You cannot use this option with `--watch` enabled (enabled in dev by default).
:::

::: tip
If `--reporter=blob` is used without an output file, the default path will include the current shard config and blob label from `VITEST_BLOB_LABEL` or the blob reporter `label` option to avoid collisions with other Vitest processes.
:::

### merge-reports

* **Type:** `boolean | string`

Merges every blob report located in the specified folder (`.vitest/blob/` by default). You can use any reporters with this command (except [`blob`](/guide/reporters#blob-reporter)):

```sh
vitest --merge-reports --reporter=junit
```
