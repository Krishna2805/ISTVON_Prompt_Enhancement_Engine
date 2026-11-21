# ISTVON Prompt Enhancement Engine

A Streamlit app that turns natural language prompts into structured **ISTVON** JSON. A two-phase safety check runs first (regex rules, then an LLM check), plus COSTAR gap analysis. The mapping uses Gemini or Groq when a key is configured and a basic offline pattern-matcher mode otherwise.

---

## 💡 What is ISTVON?

**ISTVON** is a framework for structuring AI prompts so the model gets clear, complete instructions:

| Component | Description | Example |
|-----------|-------------|---------|
| **I** - Instructions | Clear, actionable execution steps | `["Write a professional email", "Include call to action"]` |
| **S** - Sources | Reference materials, documents, or data | `{"documents": ["user_guide.pdf"]}` |
| **T** - Tools | Hardware/software utilities required | `["Email templates", "Grammar checker"]` |
| **V** - Variables | Constraints, parameters & style guidelines | `{"tone": "professional", "length": "200 words"}` |
| **O** - Outcome | Expected formatting & success criteria | `{"format": "Email", "success_criteria": [...]}` |
| **N** - Notifications | Milestone tracking & progress logs | `{"milestones": ["Draft complete"]}` |

---

## 🔄 System Architecture & Flow

```
User Natural Language Prompt
            │
            ▼
 ┌──────────────────────┐
 │ Safety Broker (regex)│ ────────► BLOCK  (harmful-intent phrase; logged, shown with advice)
 │ + COSTAR gap analysis│ ────────► NEEDS_FIX (sensitive/ambiguous term; continues with a warning)
 └──────────┬───────────┘
            │ ALLOW / NEEDS_FIX
            ▼
 ┌──────────────────────┐
 │ LLM safety check     │ ────────► BLOCK  (e.g. social engineering behind "research" framing)
 └──────────┬───────────┘           (skipped when no LLM is configured)
            ▼
 ┌──────────────────────┐
 │ Context + pattern    │ (domain, complexity; regex extraction of tone, length, audience, format…)
 │ extraction           │
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │    ISTVON Mapper     │ (Gemini or Groq refines the draft; offline: draft + domain defaults)
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │ Completion rules +   │ (fills missing keys; hand-rolled required-key / type check)
 │ schema check         │
 └──────────┬───────────┘
            ▼
   Structured ISTVON JSON ──► JSON logs + PostgreSQL prompt_log (if configured)
            │
            ▼
 ┌──────────────────────┐
 │ Response Generation  │ (Optional, needs an LLM: sends prompt + I-S-T-V-O spec; response stored)
 └──────────────────────┘
```

### Safety Broker Decisions
The regex tier uses the **single worst match**, not a sum of scores:
- **`BLOCK`**: a harmful-intent phrase, such as "hack into…", "write ransomware", "steal passwords", "build a bomb", "how to make meth", self-harm methods, or sexual content involving minors. The UI shows the reason and recommendations.
- **`NEEDS_FIX`**: a sensitive or ambiguous term, such as "phishing", "SQL injection", "personal data", "illegal", or an SSN/card-number-shaped value. The tool **warns and proceeds**: the raw prompt is processed as written and **is sent to the LLM unchanged**. Only the copy stored in the audit log has the matched terms replaced with `[REDACTED]`. This is not PII protection (see [Design choices and limitations](#-design-choices-and-limitations)).
- **`ALLOW`**: no rule matched. Topic words alone ("bank", "financial", "medical", "attack the bottleneck") do not trigger anything.

Defensive or test framing near a cyber term ("protect my account from someone trying to hack into it", "bypass authentication in Cypress tests") downgrades BLOCK to NEEDS_FIX. When an LLM is configured, it then runs a second safety check that can still BLOCK.

### COSTAR Gap Analysis
Scores the prompt against **C**ontext, **O**bjective, **S**uccess criteria, **T**imeline, **A**udience and **R**esources. Missing elements are shown as suggestions and passed to the LLM so it can fill sensible defaults. They never block a prompt.

---

## 📋 Prerequisites & Things to Know Before Running

- **Python**: tested on 3.11. Python 3.13+ will not install the pinned `numpy<2` (no wheels for it); use 3.11 or 3.12.
- **LLM is optional, but it is what makes the output good.** Set `GEMINI_API_KEY` + `GEMINI_MODEL`, or `GROQ_API_KEY` + `GROQ_MODEL`. See [LLM providers](#-llm-providers-gemini-or-groq) for the exact rules.
- **Offline mode** (no usable key) is a basic fallback. The app says so in a banner that names the missing settings. Regex extraction picks up the main instruction, tone, length ("under 200 words"), audience, output format, URLs and frameworks, then adds domain-template tools, variables and success criteria. There is no LLM safety check and no response generation.
- **PostgreSQL is optional.** If configured, every decision (ALLOW, NEEDS_FIX and BLOCK) goes into the `prompt_log` table, and generated responses are stored on the same row. Local JSON-lines logs (`istvon_transformations_log.json`, `rule_engine_logs.json`) are written on every request either way. Without a reachable server the sidebar shows "Database: Not connected"; the app tries once at startup and then at most once a minute.
- **Downloads**: the UI offers the ISTVON JSON and a combined ISTVON + response JSON as browser downloads.

---

## 🔌 LLM providers (Gemini or Groq)

**Groq support** is a recent addition. Groq serves open models through an OpenAI-compatible chat-completions API. The app calls it with Python's standard library (`urllib`), so it needs no extra package. It was tested with `openai/gpt-oss-120b`; other Groq chat models that support JSON mode should work but were not tested. Gemini goes through the `google-genai` SDK (tested with `gemini-3.1-flash-lite`).

To enable one, put a key **and** a model in `.env` (copy `.env.example`) and restart the app:

| Provider | Settings | Where to get a key |
|---|---|---|
| Gemini | `GEMINI_API_KEY` + `GEMINI_MODEL` | https://aistudio.google.com/app/apikey |
| Groq | `GROQ_API_KEY` + `GROQ_MODEL` (e.g. `openai/gpt-oss-120b`) | https://console.groq.com/keys |

Selection rules (`Config.llm_settings()`):
1. A provider counts only when both its key and its model are set and neither is a placeholder (`your_...`, `xxx`, etc.).
2. With no `LLM_PROVIDER`, Gemini is used if it is complete, otherwise Groq.
3. `LLM_PROVIDER=gemini` or `LLM_PROVIDER=groq` forces that provider. If it is incomplete, the app runs **offline**, even when the other provider is configured. It does not silently fall back.
4. Offline, a banner names the missing variables, e.g. `LLM_PROVIDER=groq forces that provider, but it is missing (not set or a placeholder): GROQ_MODEL`.

Tested combinations (fresh clone, no `.env`, no PostgreSQL, settings passed as environment variables, 2026-11-21):

| Settings | Result |
|---|---|
| No keys at all | Offline. Banner lists all four variables. The prompt is processed, the "LLM safety check skipped" notice shows, and Generate Response says "No LLM configured". No crash, no traceback. Also covered by `tests/test_app_offline.py`. |
| `GEMINI_API_KEY` only (no model) | Offline. Banner names `GEMINI_MODEL`. |
| Gemini key + model only | Gemini, live calls OK, LLM safety check ran |
| Groq key + model only | Groq (`openai/gpt-oss-120b`), live calls OK, LLM safety check ran |
| Both complete, no `LLM_PROVIDER` | Gemini |
| `LLM_PROVIDER=groq` + Groq key, no `GROQ_MODEL` (Gemini complete) | Offline. Banner names `GROQ_MODEL`. |
| `LLM_PROVIDER=groq` + Groq key, no `GROQ_MODEL`, nothing else | Offline. Banner names `GROQ_MODEL`. |

---

## ⚙️ Installation & Setup

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Krishna2805/ISTVON_Prompt_Enhancement_Engine.git
cd ISTVON_Prompt_Enhancement_Engine

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env` - Optional)

Copy `.env.example` to `.env` and fill in what you want to use:

```bash
cp .env.example .env
```

```env
# LLM: Gemini (used first if configured)...
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=your_gemini_model_here
# ...or Groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=your_groq_model_here        # e.g. openai/gpt-oss-120b
# LLM_PROVIDER=groq                    # force one provider when both are set

# Optional: PostgreSQL audit log
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=istvon_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
# or: DATABASE_URL=postgresql://user:password@host:5432/istvon_db
```

---

## 🚀 Usage

### 1. Launch the Web App (Streamlit)

```bash
streamlit run app.py
```
- Default URL: **`http://localhost:8501`**
- Another port: `streamlit run app.py --server.port 8700`

### 2. Check the Database Connection

```bash
python demo.py
```
Creates the `prompt_log` table if needed and inserts one sample row, or prints a note if PostgreSQL is not installed or not configured. It does not run the prompt engine.

### 3. Run Test Suite

```bash
# Run all tests (104)
python -m pytest tests/ -v

# Individual modules
python -m pytest tests/test_pipeline.py -v      # end-to-end process_prompt, LLM + DB mocked
python -m pytest tests/test_app_offline.py -v   # the Streamlit app with no LLM key and no database
python -m pytest tests/test_broker_rules.py -v  # safety verdicts on realistic prompts
python -m pytest tests/test_broker.py -v
python -m pytest tests/test_llm_mapper.py -v
python -m pytest tests/test_rules.py -v
```
Tests run in a temporary directory, so they never touch your JSON logs or the database.

---

## 🛠️ Helpful Tips & Troubleshooting

| Scenario | Detail / Solution |
|----------|-------------------|
| **Default Web Port** | `http://localhost:8501` |
| **Port in use, or `WinError 10013` on Windows** | The port is taken or in a Windows-reserved range (`netsh int ipv4 show excludedportrange protocol=tcp`). Use another, e.g. `--server.port 8700` |
| **Running Without API Key** | Offline pattern-matcher mode; a banner at the top names the missing settings |
| **Key set but the app still says offline** | Read the banner: usually `GEMINI_MODEL` / `GROQ_MODEL` is missing or still a placeholder, or `LLM_PROVIDER` forces an incomplete provider |
| **Running Without Database** | Nothing to set up; decisions are still logged to the local JSON files. Startup is a few seconds slower while the connect attempt fails |
| **Execution Policy Error (Windows)** | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` before activating venv |

---

## 📂 Project Structure

```
ISTVON_Prompt_Enhancement_Engine/
├── README.md
├── docs/
│   └── ARCHITECTURE.md        # Detailed architecture & design decisions
├── app.py                     # Streamlit app + ISTVONEngine pipeline
├── config.py                  # .env loading, provider selection, domain defaults
├── database.py                # PostgreSQL prompt_log audit logger
├── demo.py                    # Database connection check (inserts one sample row)
├── requirements.txt
├── engine/
│   ├── broker.py              # Regex safety rules (ALLOW / NEEDS_FIX / BLOCK) + COSTAR gaps
│   ├── completion_rules.py    # Fills missing ISTVON keys with domain defaults
│   ├── context_analyzers.py   # Domain, complexity & specificity detection
│   ├── istvon_schema.py       # Hand-rolled required-key / type check for ISTVON dicts
│   ├── llm_mapper.py          # Gemini (google-genai) / Groq (HTTP) mapping, safety check, response
│   └── pattern_matchers.py    # Regex extraction of instructions, tone, length, audience, format
├── utils/
│   ├── helpers.py             # Example prompts for the sidebar
│   ├── json_logger.py         # JSON-lines decision log (rule_engine_logs.json)
│   ├── json_parser.py         # Extracts JSON from LLM output
│   └── logger.py              # Application logging utility
├── examples/                  # Sample prompts and outputs
└── tests/                     # pytest suite (conftest.py isolates log files)
```
Downloads (ISTVON JSON, ISTVON + response JSON) are served by the browser; the app writes no export files.

---

## ⚖️ Design choices and limitations

- **NEEDS_FIX warns and proceeds; it does not protect personal data.** On NEEDS_FIX the raw prompt is sent to the LLM provider (Google or Groq) exactly as typed. The redaction only affects one audit copy: the `prompt_log.sanitized_prompt` column (the name is historical). Even that copy only replaces what a rule matched, and the raw prompt is stored next to it in `prompt_log.original_prompt` and in both JSON log files. Don't type real personal data into the app if it must not leave your machine. Redacting before sending was rejected because word-level redaction breaks the request ("Explain how [REDACTED] interest works").
- **The regex broker judges the worst single match.** Harmful-intent phrases block; bare topic words only flag for review. Regexes miss paraphrases, so the LLM safety check is the second line, and that only runs when an LLM is configured.
- **The LLM safety check fails open.** With no LLM, or if the call fails or returns something unparseable, the prompt continues with only the regex verdict. The UI says "LLM safety check skipped" and why (e.g. "LLM call failed: ServerError"). This happened during testing: a Gemini 503 "high demand" error let an OTP-phishing prompt through on the regex verdict alone, though the same prompt is blocked when Gemini answers. Fail-closed would make the app unusable offline; this is the trade-off.
- **Self-harm support message.** When a self-harm rule matches, the prompt is blocked and the only recommendation shown is: "If you are in immediate danger, call your local emergency number. To find a free, confidential helpline in your country, visit https://findahelpline.com." It is region-neutral on purpose: Find A Helpline (run by ThroughLine; the directory the International Association for Suicide Prevention points to) covers many countries, and hard-coded numbers would be wrong for most users. **This tool is not a crisis service.**
- **Offline mode is basic.** Regex extraction plus domain templates; no LLM safety check, no response generation.
- **One LLM provider at a time.** `LLM_PROVIDER` forces one and never falls back to the other (see [LLM providers](#-llm-providers-gemini-or-groq)).
- **PostgreSQL is best-effort.** Failures are printed to the console and never stop a request. After a failed connect the app waits a minute before retrying, so a database outage costs at most one slow request per minute.
- **Local logs keep raw prompts.** `istvon_transformations_log.json` and `rule_engine_logs.json` are written on every request and are git-ignored; delete them if they hold anything sensitive.
