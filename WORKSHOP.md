# Building Production-Ready Agentic Workflows

This file is the workshop. Every command and every prompt is a cell: open it in VS Code with the
[Runme](https://marketplace.visualstudio.com/items?itemName=stateful.runme) extension (VS Code offers it when you open
the folder; a Codespace has it preinstalled) and press ▶ on a cell to run it where it sits; the output stays under the
cell. Every cell also has a copy
button, and `runme run <name>` runs a named cell from a terminal. The cells are the real commands, not wrappers, so
you can read what each one does; the `Makefile` holds the same commands as targets (`make check-1`, `make vibe-1`, …)
for anyone working in a plain terminal.

Each step below says **what** the cell does, **why** we do it, and **what to look for** in its output. The cards in
`workshop/` hold the full requirements for each module; this file is the path through them.

## What the investigation agent is

**The situation.** An error lands in Sentry: `KeyError: 'UK'` in checkout, forty events in ten minutes. Someone on call
opens the issue, reads a stack trace, finds the file on GitHub at the commit that is actually deployed, works out which
assumption the input broke, and writes it up in the thread so the next person can act. Twenty to forty minutes, most
of it navigation, repeated for every alert.

**What the agent does.** You ask it a question in plain language, the way you would ask a colleague:

> Checkout is failing for some customers with KeyError: 'UK'. What's the root cause?

It investigates the way the colleague would, with two read-only tools:

1. **Sentry**: finds the matching issue, reads a representative event (exception type and message, the stack frames,
   first and last seen), and the tags the event carries: `release`, the commit SHA that was running, and `repository`,
   the GitHub `owner/repo` that holds the code.
2. **GitHub**: opens the responsible file *in that repository at that commit* (not the default branch, which may have
   moved on), reads the function around the failing line, and, if it needs to, the recent commits that touched it.
3. Then it explains the defect as a fact about the code, not a guess about the input.

**What it produces.** Not prose: an `InvestigationReport`, a typed object every turn must end with, so a test can
score it, a workflow can return it, and a chat message can be rendered from it:

```json
{
  "summary": "Checkout fails for United Kingdom orders because the shipping table has no 'UK' entry.",
  "exception": "KeyError: 'UK'",
  "file": "sample-app/shop/shipping.py",
  "symbol": "rate_for",
  "root_cause": "rate_for looks the legacy 'UK' country code up in RATES_CENTS, which only has the ISO code 'GB': `return RATES_CENTS[country]`.",
  "confidence": "high",
  "evidence": [
    {"source": "sentry", "reference": "https://sentry.io/.../issues/1", "proves": "KeyError: 'UK' raised in shop/shipping.py rate_for"},
    {"source": "github", "reference": "https://github.com/<you>/investigation-agent-workshop/blob/<sha>/sample-app/shop/shipping.py", "proves": "RATES_CENTS has GB, not UK"}
  ],
  "next_check": null
}
```

`confidence` and `next_check` are part of the contract: when the agent cannot see enough (module 1, before it has
connectors), the right answer is low confidence and a `next_check` that says what to look at, not an invented cause.

**What it never does.** It does not resolve the issue, comment on it, open a pull request or touch anything: its
connectors expose write tools, and module 2's policy denies every one of them. Investigation is read-only; the person
who reads the report decides.

**What it investigates today: the sample shop.** `sample-app/shop/` is a small Python checkout flow (pricing, shipping,
discounts, inventory, taxes, notifications) with six planted bugs, one per module, each a reasonable assumption that a
real order breaks:

| # | Exception | Where | The assumption that breaks |
|---|---|---|---|
| 1 | `ValueError` | `pricing.py :: parse_amount` | prices are whole dollars; a poster priced `"12.50"` reaches `int()` |
| 2 | `KeyError: 'UK'` | `shipping.py :: rate_for` | country codes are ISO; a legacy storefront still sends `UK`, the table has `GB` |
| 3 | `ZeroDivisionError` | `discounts.py :: average_item_price` | a cart has items; a member's cart was emptied in another tab |
| 4 | `TypeError` | `inventory.py :: reserve` | stock levels are numbers; the warehouse CSV exports text |
| 5 | `AttributeError` | `notifications.py :: confirmation_recipient` | every order has a customer; guest checkout has none |
| 6 | `IndexError` | `taxes.py :: rate_for_region` | region codes look like `CA-ON`; France is just `FR` |

In setup you run the six checkout scenarios and send their exceptions to *your* Sentry project, tagged with the commit
and your fork. From then on they are real production errors as far as the agent is concerned: it reads them through
the same connectors it would use at work, and in module 3 they double as the eval dataset, because for each one we
know the file, the symbol and the cause. Mistral's own engineering team runs the full-size version of this agent on its
production incidents; this is the trimmed one you can build in a day.

## How the day works

You start on `main`, which has **no agent code**: there is no `agent/` folder yet (module 1 creates it with
`agents init`), no `workflow/` either (module 4 creates it with `mistral init`), and `evals/` holds only the six eval
cases. What you have is the
specification: a requirements card per module, the prompt that hands it to your coding agent, and the acceptance tests
in `tests/` that stay red until the code exists. Nobody types code today. You hand requirements to a coding agent, read
the test results, and refine.

You work in **your own fork**. The GitHub connector reads the sample app from it, at the commit that sent each error,
so every module ends with a commit and a push.

Cells that open __Vibe__ are interactive: they run in the VS Code terminal panel (full size; the workspace settings
arrange that), Vibe builds while you watch and asks before risky actions, and `/quit` or `ctrl+c` hands control back.
They all have the shape `uv run --env-file .env vibe "$(cat workshop/prompts/<module>.md)"`: `uv run --env-file`
loads your `.env` into the environment (Vibe reads `MISTRAL_API_KEY` from there), and the prompt file is passed as
Vibe's first message. Prefer no UI? Add `--trust --auto-approve --output streaming -p` before the prompt to run it
headless with tool calls auto-approved. Cells that run checks print their output under the cell.

```ini
question ──> investigate workflow ──> agent session ──> Sentry connector (read-only)
                 (module 4)           (modules 1-2)   └─> GitHub connector (read-only)
                                            │
                                            └──> InvestigationReport ──> evals: score + judge + gate (module 3)
```

## 0 · Setup

Everything in this section is accounts and wiring, not building, so do it before the day. All of it is free: Mistral
Studio, Sentry's Developer plan, GitHub Free. Nothing needs a credit card.

### 0.1 What runs where, and why

- **Mistral Studio** runs the model, holds the **connectors** (your Sentry and GitHub logins, so the agent never sees a
   token), traces every session in **Observability**, and in module 4 orchestrates the **workflow**.
- **Sentry** receives six planted errors from the sample shop. They are the dataset: the agent investigates them, the
   evals score the answers.
- **GitHub** holds your fork. The agent reads the shop's code from it at the exact commit that sent each error, which
   is how it can quote the offending line.
- **Your machine** (or, as a fallback, a Codespace) runs the coding agent, the tests, the evals, and the two local
   workers in module 4.

### 0.2 Fork the repository and open it

Fork this repository to your GitHub account (public is fine). Then pick **one** of the two ways to work, A or B. A is
the one to use; B is the fallback for a machine you cannot install tools on.

#### A · On your machine (preferred)

Clone your fork, open the folder in VS Code, and accept the recommended extensions (Runme, Python, Ruff). Then install
the three command-line tools the day needs. Each is one cell; press ▶, or copy it into a terminal.

**What.** [uv](https://docs.astral.sh/uv/) installs Python and every dependency, and runs everything in this file.

```sh {"interactive":"false","name":"install-uv"}
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**What.** [Vibe](https://docs.mistral.ai/vibe/code/cli/install-setup), the coding agent you build with. The installer
runs `uv tool install mistral-vibe` for you: Vibe lives outside the project environment, on your PATH as `vibe`.

```sh {"interactive":"false","name":"install-vibe"}
curl -LsSf https://mistral.ai/vibe/install.sh | bash
```

__What.__ The [Mistral CLI](https://docs.mistral.ai/studio/mistral-cli/quickstart), which scaffolds, runs and deploys
the workflow in modules 4 and 5. `MISTRAL_INSTALL_BUN=1` lets the installer bring the Bun runtime it needs.

```sh {"interactive":"false","name":"install-cli"}
curl -fsSL https://mistral.ai/cli/install.sh | MISTRAL_INSTALL_BUN=1 bash
```

**What.** Proves all three are reachable. The installers add `~/.local/bin` and `~/.mistral/bin` to the PATH of *new*
terminals; this cell adds them for itself, so it works right away. If a later cell says `command not found`, open a
new terminal (or reload the VS Code window) once.

```sh {"interactive":"false","name":"install-check"}
export PATH="$HOME/.local/bin:$HOME/.mistral/bin:$PATH" && uv --version && vibe --version && mistral --version
```

**Look for:** three version lines, uv 0.8 or later. Git and a GitHub login that can push to your fork are assumed.

#### B · GitHub Codespaces (fallback)

Nothing to install, but it is a remote machine: slower to start, and Vibe runs over the browser's terminal. On your
fork, _Code → Codespaces → Create codespace on main_. The container runs the same three installs as A, installs the
dependencies (0.8) and opens this file as a notebook. If you add the four values below as Codespaces secrets first
(_GitHub → Settings → Codespaces → Secrets_: `MISTRAL_API_KEY`, `SENTRY_CONNECTOR_NAME`, `GITHUB_CONNECTOR_NAME`,
`SENTRY_DSN`), they land in `.env` automatically; otherwise you fill `.env` by hand as you go through 0.3 to 0.7.
Skip the cells of A.

#### Create `.env` (both ways)

**What.** Copies `.env.example` to `.env`, the file every value from 0.3 to 0.7 goes into. Blank values stay blank for
you to fill in; any value already in the environment (Codespaces secrets arrive that way) is filled in. It never
overwrites an existing `.env`, so running it twice is harmless.

```sh {"interactive":"false","name":"setup-env"}
sh scripts/bootstrap-env.sh
```

**Look for:** `Wrote .env (0 values filled from the environment)` on your machine. Open `.env` now and keep it open:
the next four steps each produce one value for it. `.env` is gitignored, so nothing in it reaches GitHub, an image, or
a prompt.

### 0.3 Mistral Studio: an API key

**What.** One key, used by the agent, the evals, the judge and the workflow worker.

1. Sign in at [console.mistral.ai](https://console.mistral.ai) and pick the workspace you will use all day.
   If the workshop comes with credits, redeem them first: the facilitator shows a link and a QR code that opens
   **admin.mistral.ai → Subscription → Redeem** with the code filled in. The credits land in the organization you are
   signed in to, so redeem before you create the key, in the same organization.
2. Open **API keys → Create new key**. If the key dialog offers a connectors scope, choose the one that includes
   **private and shared connectors**: the default *shared connectors only* cannot use a connector you connected
   privately.
3. Copy the key: it goes in `.env` as `MISTRAL_API_KEY`.

**Why one workspace.** Connectors are connected by a Studio user; the agent calls them as the user whose key it runs
with. Key, connectors and (in module 4) the workflow deployment must all be in the same workspace, or a session fails
with *connector … is not connected*.

### 0.4 Sentry: a project and its DSN

**What.** A Sentry project that receives the six errors. The DSN is the address the sample shop sends them to.

1. Sign up at [sentry.io](https://sentry.io) (Developer plan). Create an organization if asked.
2. **Projects → Create Project**. Platform **Python**; under *Set your alert frequency* anything is fine; select only
   **Error Monitoring**; name it `workshop-shop`.
3. The next screen shows a setup snippet with `dsn="https://…@…ingest.sentry.io/…"`. Copy the DSN. Later you find it
   under **Settings → Projects → workshop-shop → Client Keys (DSN)**.
4. It goes in `.env` as `SENTRY_DSN`. The DSN can only _send_ events; it cannot read anything, which is why it is safe
   in a local `.env` and useless to the agent.

### 0.5 Connect Sentry to Studio

**What.** The Sentry connector from Studio's marketplace, authorized with your Sentry login. It gives the agent read
access to your Sentry organization.

__Why a connector instead of a token in `.env`.__ The agent never holds a Sentry credential. Studio keeps the OAuth
grant; the agent calls `search_issues` as _you_, every call is traced, and in module 2 a policy decides which of the
connector's tools it may call at all.

1. In Studio, open **Connectors** ([console.mistral.ai/connectors](https://console.mistral.ai/connectors)) and click
   **New connector → Browse marketplace**.
2. Search for **Sentry**, select it, and add it.
3. Click __Connect__. Sentry opens: sign in, pick your organization, and approve the access. Back in Studio the
   connector shows as connected and lists its tools: `find_organizations`, `find_projects`, `search_issues`,
   `search_events`, `get_sentry_resource`, and more (including write tools the agent will never be allowed to call).
4. Copy the connector's __name__ exactly as Studio shows it, suffix included if it has one (for example `sentry_d183`).
   It goes in `.env` as `SENTRY_CONNECTOR_NAME`. The SDK names the tools `connector_<name>.<tool>`, which is what
   module 2's policy matches.

### 0.6 Connect GitHub to Studio

**What.** The GitHub connector from the same marketplace, installed on your fork, so the agent can read files at a
given commit.

1. In **Connectors**, click **New connector → Browse marketplace**, search for **GitHub**, select it, and add it.
2. Click **Connect**. GitHub opens. Authorize the **MistralAI** GitHub App for the account that owns your fork. When it
   asks for repository access, **Only select repositories → your fork** is the minimum; *All repositories* also works.
3. Back in Studio, the connector lists its tools (`get_file_contents`, `list_commits`, `search_code`, …, plus write
   tools the policy will deny). Copy its __name__ as Studio shows it (for example `github`). It goes in `.env` as
   `GITHUB_CONNECTOR_NAME`.

If your Studio organization already connected GitHub at the organization level (*Admin → Connectors → App
Connections*), the connector is connected for you; make sure the app can see your fork.

### 0.7 Complete `.env`

__What.__ A check that the file you created in 0.2 now has every value; `INVESTIGATION_AGENT_NAME` is the one you
choose yourself.

| Variable | Where it comes from | Who reads it |
|---|---|---|
| `MISTRAL_API_KEY` | Studio → API keys (0.3) | the agent, the evals, the judge, the workflow worker |
| `SENTRY_CONNECTOR_NAME` | Studio → Connectors, the Sentry connector's name (0.5) | `agent/config.py`, to build the policy and the connector list |
| `GITHUB_CONNECTOR_NAME` | Studio → Connectors, the GitHub connector's name (0.6) | same |
| `SENTRY_DSN` | Sentry → project → Client Keys (0.4) | `sample-app/send_error.py` only |
| `INVESTIGATION_AGENT_NAME` | you: `investigation-agent-<your-name>` | `agents serve` (module 4): the name your agent worker runs under, and the name the workflow's activity opens sessions on. Unique, or two workers claim each other's sessions |

No blank values left: every later cell runs through `uv run --env-file .env`, which is how the key and the names reach
the code.

### 0.8 Install and prove the toolchain

**What.** `uv sync` reads the root `pyproject.toml` and installs Python 3.12 and everything it declares into one
`.venv` at the repository root; `--all-groups` adds the dev group (pytest, ruff). The Mistral packages it installs:

| Package | What it is | Used from |
|---|---|---|
| `mistralai-agents[bashkit]==1.1.3` | the **Agents SDK**: `Agent`, sessions, connectors, policies, hooks, skills, the `agents` CLI; `bashkit` is the in-process sandbox that holds skill files | modules 1, 2, 4 |
| `mistralai-workflows` | the **Workflows SDK**: `@workflows.activity`, `@workflows.workflow.define`, the worker | module 4 |
| `mistralai` | the **Mistral client**: plain chat completions, used by the eval judge | module 3 |

The Agents SDK is pinned to the exact release the reference code and tests were verified against, so everyone in the
room runs the same API. This root environment is for the day: tests, evals, the sample shop. The two deployable units
carry their own dependency lists, because that is what their images build from in module 5: `agents init` writes
`agent/pyproject.toml` in module 1 and `mistral init` writes the workflow's in module 4. Vibe and the Mistral CLI are not
in here: they are command-line tools, installed once in 0.2.

```sh {"interactive":"false","name":"setup"}
uv sync --all-groups
```

**What.** Lists the Mistral packages that landed in `.venv`, with their versions.

```sh {"interactive":"false","name":"setup-packages"}
uv pip list | grep -i mistral
```

**Look for:** `mistralai 3.7.x`, `mistralai-agents 1.1.3`, `mistralai-workflows 3.19.x`, plus the pieces they pull in
(`mistralai-otel-observability`, which traces sessions into Studio; `mistralai-vibe-harness` and `mistralai-vibe-sdk`,
the runtime the Agents SDK is built on; `mistralai-workflows-plugins-mistralai`). If `mistralai-agents` shows another
version, something else installed the SDK into this `.venv`: run `uv sync --all-groups` again.

**What.** Runs the sample shop's own tests: they assert that each of the six bugs raises the expected exception, which
proves the tooling works and the dataset is intact.

```sh {"interactive":"false","name":"setup-check"}
uv run pytest tests/test_sample_app.py -q
```

**Look for:** `8 passed`. Anything else is a setup problem to fix before the day.

__What.__ Vibe reads `MISTRAL_API_KEY` from the environment, and `uv run --env-file .env` puts it there, so there is
no sign-in step. This cell runs one tiny headless turn (`-p` is headless mode, `--max-turns 1` stops after one
exchange, `--trust` skips the folder-trust prompt) to prove Vibe reaches Mistral with your key.

```sh {"interactive":"false","name":"setup-vibe"}
uv run --env-file .env vibe --trust --max-turns 1 --output text -p "Reply with exactly one word: ready"
```

**Look for:** a one-word answer, `ready`. A `401` means the key; a network error means the proxy or Wi-Fi.

**What.** Opens Vibe once, interactively, so you can set its thinking level before the day. Vibe starts Mistral Large 4
at *high* (the footer reads `Mistral Large 4[high]`); high spends several times longer per step than the cards need.
In the Vibe window type `/thinking`, pick **medium**, and let the picker save it (not "session only"), then `/exit`.
Every `vibe-N` cell from now on runs at medium; the footer will say so.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"setup-vibe-thinking"}
uv run --env-file .env vibe
```

**Look for:** `Mistral Large 4[medium]` in the footer before you `/exit`.

__What.__ Signs the __Mistral CLI__ in with the API key you already have. Module 4 uses the CLI to scaffold the
workflow (`mistral init`) and run its worker (`mistral dev`); module 5 deploys with it. `mistral login --api-key -`
reads the key from stdin, so the cell pipes `MISTRAL_API_KEY` out of `.env` and the key is never typed, echoed or left
in a shell history; it works the same on your machine and in a Codespace. (Plain `mistral login` signs in through the
browser instead; device-code sign-in is not available yet.) The CLI was installed in 0.2.

```sh {"interactive":"false","name":"setup-cli"}
uv run --env-file .env sh -c 'printf %s "$MISTRAL_API_KEY" | mistral login --api-key -' && mistral whoami
```

**Look for:** a confirmation that the key was saved, then your account, organization and workspace from `whoami`.
The CLI now acts in the workspace that key belongs to, which is the workspace the connectors (0.5, 0.6) live in.

### 0.9 Send the six errors to Sentry

**What.** Runs each of the six checkout scenarios, lets it crash, and sends the exception to your Sentry project. Every
event is tagged with the scenario number, your fork's `owner/repo`, and the current commit as the **release**.

**Why commit and push first.** The agent will read the code *at that commit on your fork*. If the commit is not on
GitHub, the GitHub connector cannot open it.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"setup-sentry"}
git add -A && (git diff --cached --quiet || git commit -qm "Workshop setup") && git push
cd sample-app && uv run --env-file ../.env python send_error.py all
```

**Look for:** six lines `Scenario n (…) sent to Sentry as event …`. Then open your Sentry project: within a minute,
six issues in the `demo` environment: `ValueError`, `KeyError`, `ZeroDivisionError`, `TypeError`, `AttributeError`,
`IndexError`, each with `scenario`, `repository` and `release` tags. That is the dataset the agent will be evaluated on
in module 3. Send them before the day, not in the room: Sentry's free tier can take a while to index.

## 1 · A testable agent

Card: [workshop/01-agent-skeleton.md](workshop/01-agent-skeleton.md).

**What you build.** An agent project scaffolded by `agents init`, then an agent whose every turn ends in a validated
`InvestigationReport` (file, symbol, root cause, confidence, evidence), plus `investigate()`, one function that runs a
turn and returns the outcome as data, and `ask.py` to print it. No connectors yet.

**Why this first.** Everything later consumes the report: the evals score it, the workflow returns it. Nailing the
output contract first makes every later module testable, and it sets the habit of the day: `instructions.md` is a
requirements document for the model, and the report model is its acceptance test. The tests drive the agent with a
scripted model, offline, so this module needs no network at all.

**What.** `agents init` is the SDK's scaffolder: it creates a project that `agents deploy` can ship in one step. The
name argument is the folder; `--no-git` because your fork already is a repository. It also writes an empty
`agent/.env`, which the cell removes: this workshop keeps one `.env` at the root and passes it with `--env-file ../.env`.

```sh {"interactive":"false","name":"init-agent"}
uv run agents init agent --no-git && rm agent/.env
```

**What.** Lists what `agents init` wrote into `agent/`, then prints the two files worth reading: `pyproject.toml`
(the agent's own dependency list, with the Agents SDK pinned to the version you installed; `agents deploy` builds
its image from this file in module 5) and `main.py` (a hello-world agent with one tool, the file your coding agent
replaces). The rest (`Dockerfile`, `.python-version`, `uv.lock`, `.gitignore`, `README.md`) stays as generated.

```sh {"interactive":"false","name":"scaffold"}
ls -A agent && echo ---- && cat agent/pyproject.toml && echo ---- && cat agent/main.py
```

**Look for:** `pyproject.toml` pins the SDK to the version you just installed and declares `agent/` a uv workspace of
its own, so it locks its dependencies separately (`uv.lock`; commit it, the Dockerfile builds with `--frozen`).
`Dockerfile` is what `agents deploy` builds in module 5: uv, the project, `agents run-worker`, as a non-root user. It
is yours to edit. `main.py` is a hello-world agent with a weather tool, the file module 1 replaces. `.gitignore`,
`.python-version` and `README.md` are what you would expect. The `agents` CLI finds the agent at `main:agent` by
convention.

**What.** The CLI loading the scaffold, before anything of yours exists: one friendly weather agent, no sandbox, one
tool. Compare with the same command at the end of the module.

```sh {"interactive":"false","name":"info-0"}
cd agent && uv run --env-file ../.env agents info .
```

**What.** Opens Vibe with the card's prompt as its first message. The prompt (`workshop/prompts/01-agent-skeleton.md`)
tells it to read `AGENTS.md`, `docs/sdk-cheatsheet.md`, the card and the tests before writing anything, to build on
the scaffold rather than replace it, and to stop as soon as `make check-1` and `make lint` pass: everything after that
(`info-1`, `ask-1`) is yours to run, so you see the result rather than read about it.

**Before you press Enter on the prompt:** the footer should read `Mistral Large 4[medium]`, the level you saved in 0.8.
If it says `[high]`, type `/thinking`, pick medium, save, and carry on. Expect the build to take a few minutes: the
coding agent reads the files, writes the five files, runs the tests and fixes what fails. Watch what it does rather
than waiting: the tool calls it makes are the point of the exercise, and the facilitator keeps presenting meanwhile.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"vibe-1"}
uv run --env-file .env vibe "$(cat workshop/prompts/01-agent-skeleton.md)"
```

**Look for:** Vibe reading the tests before it writes code. Approve its file edits; refuse anything that touches
`tests/`, `evals/cases.jsonl` or `sample-app/shop/`, and anything that rewrites `agent/pyproject.toml`, `Dockerfile`
or `uv.lock` (a new dependency goes in with `cd agent && uv add <package>`).

**When it says it is done, it does not exit:** Vibe is a chat, and it sits waiting for your next message. Type `/exit`
(or press Ctrl+D) to close it and get the terminal back, then run the next cell. Do this before `fix-1` too: that cell
reopens the *same* session with `vibe -c`, and Vibe refuses to open a session that another Vibe process still holds.
The same goes for every `vibe-N` and `fix-N` cell below.

**What.** Runs the acceptance tests for module 1 (and the sample-app guard). The tests *are* the specification: they
build the agent with `connectors=False`, drive it with a scripted model, and check the report, the error handling and
the CLI.

```sh {"interactive":"false","name":"check-1"}
uv run pytest tests/test_sample_app.py tests/m1
```

**Look for:** the last line. `14 passed` (the 8 sample-app guards plus module 1's 6) means nothing to fix: go on to
`info-1`. A failure shows as `FAILED tests/m1/...` lines above a `N failed, M passed` last line, and failing on the
first try is normal: that is what `fix-1` is for. (The notebook prints pytest without its colours, so read the words,
not the colour.) The `check-N` cells grow by one test folder per module (14, 41, 65, 76 tests), so a later module
cannot break an earlier one unnoticed.

**Only if `check-1` reported failures; skip it when the last line was `14 passed`.** `vibe -c` continues the last Vibe session in this
folder; its message is the fix prompt (`workshop/prompts/fix.md`) followed by the last 80 lines of the failing test
run. Read the failure yourself first: turning a failing test into a precise follow-up is the skill of the day. Run it
again after each round until `check-1` ends in `14 passed` (two or three rounds is normal); `/exit` between rounds.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"fix-1"}
uv run --env-file .env vibe -c "$(cat workshop/prompts/fix.md; uv run pytest tests/test_sample_app.py tests/m1 2>&1 | tail -n 80)"
```

Run `check-1` again. Two or three rounds is typical.

**What.** `agents info` again, now on your agent: model, instructions, output type, and (from module 2) connectors,
skills, hooks and the policy. The first `uv run` inside `agent/` creates the project's own `.venv` from its lockfile.

```sh {"interactive":"false","name":"info-1"}
cd agent && uv run --env-file ../.env agents info .
```

__What.__ One live question against the real model, in-process: `ask.py` is the small CLI you just built around
`investigate()`. __This agent has no connectors yet.__ Module 2 adds them; `build_agent(connectors=True)` does nothing
until then. So the only honest answer it can give is "I cannot see Sentry", and that is what this cell is for: it
proves the path question → session → validated report, and it shows a model admitting what it cannot know instead of
inventing a cause.

```sh {"interactive":"false","name":"ask-1"}
cd agent && uv run --env-file ../.env python ask.py "What's causing the latest ValueError in Sentry, and which code is responsible?"
```

**Look for:** a report with `Confidence: low`, a summary that says no Sentry or GitHub connectors are available, a
`Next check` asking for access, and a `Tool calls` list holding only `self.sleep` (the SDK's one built-in; the model
waited, found nothing, and said so). **That is the correct module 1 answer, not a bug.** Keep this output: `ask-2`
answers the same question with the file and the line.

**What.** Commits whatever module 1 produced and pushes it to your fork, so the GitHub connector can read it in
module 2. Nothing to commit (your coding agent, or you, already did) is fine: the cell skips the commit and still
pushes.

```sh {"interactive":"false","name":"commit-1"}
git add -A && (git diff --cached --quiet || git commit -qm "Module 1: a testable agent") && git push && git log --oneline -1
```

Behind? `git checkout module-1 -- agent` brings in the reference for this module; `git diff module-1 -- agent` shows
how yours differs.

## 2 · Eyes, with guardrails

Card: [workshop/02-connectors-and-policy.md](workshop/02-connectors-and-policy.md).

**What you build.** The two connectors from setup, attached to the agent; a **permission policy** that denies every
tool by default and allows a reviewed read-only list; an **audit hook** that logs every tool call; and two **skills**,
one per system, that carry the long "how to query it" procedure so `instructions.md` stays short.

**Why guardrails before capability.** A connector exposes every tool its server has, writes included: Sentry's server
can resolve issues, GitHub's can comment and merge. The policy ships in the same commit as the connectors, as data the
tests can check, and `agents info` prints it. The hook is the other half: a record of what the agent asked for, even
when the policy said no.

**What.** Opens Vibe with module 2's prompt (`workshop/prompts/02-connectors-and-policy.md`): read the card and the
tests, then write `config.py` (connector names from `.env`, the read-only allowlists, the policy), `hooks.py` (the
audit trail), the two `SKILL.md` files, and wire them into `main.py`. Same rules as module 1: it stops when the tests
pass; `/exit` when it reports.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"vibe-2"}
uv run --env-file .env vibe "$(cat workshop/prompts/02-connectors-and-policy.md)"
```

__What.__ Module 2's tests pin the policy to the SDK's own rules: a write tool is denied, a read tool on the allowed
list passes, the skill tool is allowed (forget `skill.*` and the model silently cannot load skills), and a scripted
call to a forbidden tool shows up in `tool_calls` but never runs.

```sh {"interactive":"false","name":"check-2"}
uv run pytest tests/test_sample_app.py tests/m1 tests/m2
```

**Look for:** `41 passed` (module 2 adds 27 tests). Otherwise `fix-2`.

**Only if `check-2` reported failures; skip it when the last line was `41 passed`.** Same loop as module 1: the failing output goes back to
the same Vibe session; re-run `check-2` after each round, `/exit` between rounds.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"fix-2"}
uv run --env-file .env vibe -c "$(cat workshop/prompts/fix.md; uv run pytest tests/test_sample_app.py tests/m1 tests/m2 2>&1 | tail -n 80)"
```

**What.** `agents info` again, on the module 2 agent. The CLI loads `main:agent` exactly the way `agents serve` and
`agents deploy` will, and prints what it found: the model, the instructions, the two connectors, the two skills, the
`AuditTrail` hook and the whole permission policy, rule by rule. It is the fastest way to see whether the wiring in
`main.py` is what the card asked for, without spending a model call.

```sh {"interactive":"false","name":"info-2"}
cd agent && uv run --env-file ../.env agents info .
```

**Look for:** two connectors, two skills, one hook, and a policy that ends with *anything else: deny*.

**What.** The same question as `ask-1`, to the same `ask.py`, but the agent now has the connectors, the skills and
the policy. This is the first time it can actually look: load the Sentry skill, find the latest `ValueError`, read its
stack and release, open the file at that commit on your fork, and name the line. One real session, a minute or so.

```sh {"interactive":"false","name":"ask-2"}
cd agent && uv run --env-file ../.env python ask.py "What's causing the latest ValueError in Sentry, and which code is responsible?"
```

__Look for:__ `file: sample-app/shop/pricing.py`, `symbol: parse_amount`, `confidence: high`, evidence pointing at a
Sentry event and a GitHub file at the release commit. Read the tool-calls line: `skill.read` first, then
`connector_<sentry>.search_issues`, then `connector_<github>.get_file_contents`. If a call was denied it still appears
in the list; it just did not run. Open __Studio → Observability__ and find the same session: that trace is what you
will read in module 3 when a case fails.

**What.** Commits and pushes module 2 (skips the commit if there is nothing new). Module 3's eval runs against this
agent, so what you push now is the baseline you will measure.

```sh {"interactive":"false","name":"commit-2"}
git add -A && (git diff --cached --quiet || git commit -qm "Module 2: connectors behind a deny-by-default policy") && git push && git log --oneline -1
```

## 3 · The eval loop

Card: [workshop/03-eval-loop.md](workshop/03-eval-loop.md).

**The problem this module solves.** After module 2 the agent works, and you know that because you read one report and
it looked right. Now change one sentence in `instructions.md`. Is the agent better or worse? You cannot tell from one
report: the model is not deterministic, one question is one sample, and "looks right" is your opinion. The tests in
`tests/` cannot answer it either: they drive the agent with a scripted model and check the code around it, not the
model's behaviour. Everything that decides how well the agent *investigates* lives in natural language (the
instructions and the two skills), and the only test for natural language is to run it against questions whose answers
you already know and score the result. That is an eval.

**What one run does.** For each of the six planted bugs there is a case in `evals/cases.jsonl`: the question an
engineer would ask, plus what a correct investigation must find (the exception type, the file, the function, a few
words any correct root cause mentions, and the planted bug explained by the person who planted it). The runner asks
the module 2 agent each question in its own session, takes the `InvestigationReport` it returns, and scores it twice:

- __Four deterministic scorers__ check the facts: is `file` the expected file, `symbol` the expected function,
   `exception` the expected type, and does `root_cause` mention at least two of the cause keywords? Each is right or
   wrong, no model involved, so the same report always scores the same.
- **One LLM judge** grades what the scorers cannot: did the explanation name the real defect, quote the line, cite
   evidence, and avoid claims it has no evidence for? It gives 1 to 5 against the reference cause. It never sees Sentry
   or GitHub, only the case and the report, so it cannot be fooled by the same wrong file the agent read.

Across the six cases that gives an accuracy per scorer (how many of six were right) and a mean judge score. The
**gate** turns the numbers into a decision: every scorer at 0.80 or above and the judge at 3.5 or above, or the run
fails. Each run is saved under `evals/results/`, and the next run prints a delta against it: that delta is the
answer to "better or worse".

__What you build.__ `evals/scoring.py` (the scorers, the summary, the gate), `evals/judge.py` (the rubric and the
judge call), `evals/run_evals.py` (run the cases, print the table, save the run, print the delta), with the dataset
given. The `check-3` tests prove the _machinery_ works, with scripted reports and no model: a run of the eval is what
proves the _agent_ works. Studio's hosted Evaluations do this same shape (dataset → task → evaluators → gate) for
enterprise workspaces; you build it by hand today so every part of it is yours.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"vibe-3"}
uv run --env-file .env vibe "$(cat workshop/prompts/03-eval-loop.md)"
```

**What.** The acceptance tests for module 3, on top of modules 1 and 2. They feed the scorers hand-written reports
(right file, wrong file, a GitHub URL instead of a path, a bare file name) and check every verdict; they build the
judge's prompt and check it carries the rubric, the reference cause and the report; they run the runner with a
scripted agent, including one case that raises, and check the table, the saved file and the gate. No model is called.

```sh {"interactive":"false","name":"check-3"}
uv run pytest tests/test_sample_app.py tests/m1 tests/m2 tests/m3
```

**Look for:** `65 passed` (module 3 adds 24). Otherwise `fix-3`.

**Only if `check-3` reported failures; skip it when the last line was `65 passed`.** Same loop: the failing output goes back to the same Vibe
session; re-run `check-3` after each round.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"fix-3"}
uv run --env-file .env vibe -c "$(cat workshop/prompts/fix.md; uv run pytest tests/test_sample_app.py tests/m1 tests/m2 tests/m3 2>&1 | tail -n 80)"
```

**What.** A short first run of the eval, before the real one: only cases 1 and 2 (`--cases 1,2`), and without the
LLM judge (`--no-judge`). Its job is to prove that the runner you just built works end to end: it starts a session,
gets a report back, scores it and prints the table. Each case is a complete investigation by the agent (a session that
reads Sentry and GitHub and returns a report), so even two cases take a minute or two; that is why you try two before
spending the time on six. The judge is one more model call per case, to grade the explanation; you do not need that
to see whether the runner works, so this run skips it.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"eval-smoke"}
uv run --env-file .env python evals/run_evals.py --no-judge --cases 1,2
```

**Look for:** a two-row table, `judge -` in both rows (skipped), and an aggregates line. An error in a row's note column
is a problem in the runner or the agent to fix now, before the full run; `gate: FAIL` on two cases means nothing yet.

**What.** The real first measurement, the **baseline**: all six cases, the four scorers and the judge, the gate, saved
under `evals/results/` so later runs can be compared with it. The runner keeps three sessions in flight, so expect
about five minutes.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"eval-baseline"}
uv run --env-file .env python evals/run_evals.py --label baseline
```

**Look for:** a table with one row per case (`yes`/`no` per scorer, the judge's 1-5, the number of tool calls, and
the judge's rationale or the error as a note), then one line of aggregates: `completed 6/6`, `file`, `symbol`,
`exception`, `cause` as fractions of the six cases, `judge` as a mean, and `gate: PASS` or `gate: FAIL` with the
scorers below threshold. Read it as a diagnosis, not a grade: a run where `exception` is 1.00 but
`symbol` is 0.50 says the agent finds the right error and then reads the wrong function. Which scorer fails most, and
on which cases?

__Now the loop the agent lives in.__ This is the part of the module that matters; the build was the setup for it. Pick
a failing case, open its session in __Studio → Observability__ (the session ID is in the saved results file)
and read what the model actually did: which tools it called in what order, the file it opened, the branch it read, the
frame it chose. Form one hypothesis about _why_ it went wrong, change _one thing_ in `agent/instructions.md` or a
`SKILL.md` (never code: the code did not change between runs, the words did), and rerun. Typical findings: it reports
the caller's frame (`checkout.py`) instead of the defect because no rule says "the frame whose code you read, not the
caller"; it reads the file on `main` instead of the release commit because the skill never says the release is a SHA;
it never quotes the line because `root_cause` does not ask for one.

**What.** The second measurement, after your one change. `--label "instructions v2"` is just the name stored in the
results file, so you can tell runs apart later; everything else is the baseline command again, all six cases with the
judge. When it finishes, the runner compares the summary with the most recent saved run (the baseline) and prints the
delta line.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"eval-v2"}
uv run --env-file .env python evals/run_evals.py --label "instructions v2"
```

**Look for:** the delta line against the previous run, `file 0.83 -> 1.00 (+0.17)` and so on per scorer. A one-case
move (0.83 → 1.00 is one case out of six) is within the noise of a non-deterministic model; a move across several scorers or several cases is a
real effect. Keep the change if the delta is positive, revert it if not, and go again with the next hypothesis: that
is the whole method, applied to a prompt. Two things it protects you from later: a model update (rerun the baseline,
read the delta) and a well-meant edit that quietly makes the agent worse. Never put the reference causes from
`cases.jsonl` into the instructions: that is teaching to the test, and the gate would pass while the agent learned
nothing.

**What.** Commits and pushes module 3: the eval code, the two saved runs under `evals/results/`, and the improved
instructions. The results files are worth keeping in git; they are the evidence that the change helped.

```sh {"interactive":"false","name":"commit-3"}
git add -A && (git diff --cached --quiet || git commit -qm "Module 3: the eval loop") && git push && git log --oneline -1
```

## 4 · Make it durable

Card: [workshop/04-workflow.md](workshop/04-workflow.md).

**What you build.** A workflow project scaffolded by the Mistral CLI, then a Workflow with one activity that runs one
investigation: started from Studio with a question, recorded step by step, resumable after a crash, returning the
report. The agent itself runs as a durable worker under `agents serve`.

**Why a workflow around an agent.** A turn is minutes of tool calls. Whatever starts it needs something that survives a
restart, retries only what is safe, records what happened, and can wait for a person. The agent stays an agent; the
workflow owns the lifecycle. The execution ID doubles as the idempotency key, so a replayed activity joins the running
turn instead of starting a second investigation.

__What.__ `mistral init` with the workflow preset scaffolds a worker app: a uv workspace of its own under `workflow/`,
the worker in `apps/worker/` (an entrypoint that discovers every workflow in the `worker.workflows` package and serves
it, plus a hot-reload entrypoint for `mistral dev`), a Dockerfile under `deploy/docker/`, `mistral.json` describing the
app, and, in `.agents/skills/`, a skill that teaches your coding agent the Workflows SDK. `--no-git` because your fork
already is a repository; `--yes` accepts the defaults. It also writes `workflow/.env` with a `DEPLOYMENT_NAME` derived
from your login, which is the queue your worker will register on.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"init-workflow"}
mistral init workflow --preset workflow --no-git --yes
```

**What.** The files worth reading: the app manifest, the worker's project file, the entrypoint that does the
discovery, and the first lines of the skill your coding agent will read.

```sh {"interactive":"false","name":"scaffold-workflow"}
ls -A workflow workflow/apps/worker/src/worker workflow/apps/worker/src/worker/workflows && echo ---- && cat workflow/mistral.json && echo ---- && cat workflow/apps/worker/pyproject.toml && echo ---- && sed -n 1,20p workflow/apps/worker/src/worker/entrypoints/worker.py && echo ---- && sed -n 1,12p workflow/.agents/skills/capability-workflows/SKILL.md
```

__Look for:__ `workflows/` is empty apart from `__init__.py`: that is where the module you build goes, and the worker
finds it by convention. `mistral.json` names the module, its Dockerfile and the `mistral dev` command. The skill's
description is the SDK's own rules for the coding agent: determinism, where I/O belongs, timeouts and retries.

__What.__ The worker reads `workflow/.env`, not the root one. This copies your `MISTRAL_API_KEY` and
`INVESTIGATION_AGENT_NAME` into it, next to the `DEPLOYMENT_NAME` the scaffold chose.

```sh {"interactive":"false","name":"workflow-env"}
sh scripts/workflow-env.sh
```

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"vibe-4"}
uv run --env-file .env vibe "$(cat workshop/prompts/04-workflow.md)"
```

**Look for:** Vibe adding the Agents SDK through the scaffold's wrapper (`bash tools/uv.sh add --package
workflows-app …`), then writing one file, `workflow/apps/worker/src/worker/workflows/investigate.py`. Refuse edits to
the entrypoints, `mistral.json` or the Dockerfile.

**What.** The acceptance tests for module 4, on top of the first three. They import your workflow module, check the
input and result models, run the activity against a scripted agent (so no network), check that it is not retried and
that the execution ID is the idempotency key, and check that the worker's discovery finds the workflow by convention.
Nothing here starts a worker or talks to Studio; the cells after do that.

```sh {"interactive":"false","name":"check-4"}
uv run pytest tests/test_sample_app.py tests/m1 tests/m2 tests/m3 tests/m4
```

**Look for:** `76 passed` (module 4 adds 11). Otherwise `fix-4`.

**Only if `check-4` reported failures; skip it when the last line was `76 passed`.** Same loop: the failing output goes back to the same Vibe
session; re-run `check-4` after each round.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"fix-4"}
uv run --env-file .env vibe -c "$(cat workshop/prompts/fix.md; uv run pytest tests/test_sample_app.py tests/m1 tests/m2 tests/m3 tests/m4 2>&1 | tail -n 80)"
```

__What.__ Two long-running processes, as background cells: they keep running while you move on, and you stop them from
the cell's terminal. `agents serve` runs your agent as a worker under `INVESTIGATION_AGENT_NAME`; sessions now live on
Mistral and survive a restart. `mistral dev` runs the workflow worker from the scaffold: it reads `workflow/.env`,
registers on its `DEPLOYMENT_NAME`, serves every workflow it discovers, and restarts itself when you edit the code. The
first run downloads the Python the scaffold pins (3.14) and builds `workflow/.venv`. Both need Workflows enabled on your
workspace.

```sh {"background":"true","excludeFromRunAll":"true","name":"serve"}
cd agent && uv run --env-file ../.env sh -c 'exec agents serve . --name "$INVESTIGATION_AGENT_NAME"'
```

```sh {"background":"true","excludeFromRunAll":"true","name":"worker"}
cd workflow && mistral dev
```

**Look for:** `serve` printing the agent name it registered; `mistral dev` logging `workflow discovery complete` with
`investigate` and the deployment it registered on. Then, in **Studio → Workflows → investigate → Start Workflow**,
paste:

```json
{"question": "Checkout is failing with KeyError: 'UK'. What's the root cause?"}
```

Open __Executions__ and watch it run: the activity starts, the agent session appears in Observability, the result
carries the report. __Then break it on purpose:__ stop the `worker` cell mid-execution, start it again, and watch the
execution resume from the activity instead of starting over. Stop the `serve` cell and start an execution: read the
failure your `read_report` wrote; restart `serve` and run it again.

**What.** Commits and pushes module 4: the workflow scaffold and your `investigate.py`. Stop the two background cells
first if you are done with them (the trash icon on the cell, or Ctrl+C in its terminal); the commit does not need
them, but the next module's deploy cells do not want a local worker claiming the same deployment name.

```sh {"interactive":"false","name":"commit-4"}
git add -A && (git diff --cached --quiet || git commit -qm "Module 4: the investigate workflow") && git push && git log --oneline -1
```

## 5 · Deploy it, trigger it, schedule it

Card: [workshop/05-stretch.md](workshop/05-stretch.md). This module depends on organization feature flags and the
Mistral GitHub App on your repository; follow along if your workspace has them, otherwise watch the demo and take the
steps home.

__What.__ `agents deploy` builds a managed worker from your pushed commit. The connector names arrive as workspace
secrets (__Studio → Secrets__, `sentry_connector_name` and `github_connector_name`) bound to environment variables, so
the image never contains them.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"deploy-agent"}
git push
cd agent && uv run --env-file ../.env agents deploy . --name "$(grep '^INVESTIGATION_AGENT_NAME=' ../.env | cut -d= -f2)" \
  --secret-binding SENTRY_CONNECTOR_NAME=secret:workspace:sentry_connector_name \
  --secret-binding GITHUB_CONNECTOR_NAME=secret:workspace:github_connector_name
```

**What.** The same eval with `--served`, against the deployed agent instead of the in-process one: proof that nothing
changed between your laptop and the managed worker.

```sh {"excludeFromRunAll":"true","interactive":"false","name":"eval-served"}
uv run --env-file .env python evals/run_evals.py --served --cases 2 --no-judge
```

**What.** The workflow, deployed the way it was scaffolded to be: `mistral deploy` builds the worker's Dockerfile from
the pushed commit and runs it on Mistral under a name you choose. Stop the `worker` cell first: two workers on one
deployment both take executions.

```sh {"closeTerminalOnSuccess":"false","excludeFromRunAll":"true","interactive":"true","name":"deploy-workflow"}
cd workflow && mistral deploy --name "investigate-$(whoami)" --yes
```

The Slack webhook and trigger, and the schedule, are click paths and a few lines; the card has them.

## Wrap

A requirement has four parts: outcome, interfaces, constraints, and the test that says it is done. Guardrails are
requirements too. An eval you can re-run is the evidence. Which module changed how you will write your next prompt?
