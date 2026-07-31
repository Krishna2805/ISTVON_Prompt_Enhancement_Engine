# ISTVON Prompt Enhancement Engine

A robust framework for converting natural language prompts into structured, validated **ISTVON** schema format with built-in safety broker checks, COSTAR gap analysis, and dual Gemini LLM / offline rule-based fallback execution.

---

## 💡 What is ISTVON?

**ISTVON** is a standardized framework for structuring AI prompts to guarantee deterministic, high-quality responses:

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
 │    Safety Broker     │ ────────► BLOCK (Rejects harmful content)
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │  COSTAR Gap Analysis │ ────────► NEEDS_FIX (Sanitizes & flags missing elements)
 └──────────┬───────────┘                │
            │                            ▼
            │                   Sanitize & Enhance
            ▼                            │
 ┌──────────────────────┐                ▼
 │   Context Detection  │           ┌─────────┐
 └──────────┬───────────┘           │  ALLOW  │
            │                       └─────────┘
            ▼
 ┌──────────────────────┐
 │    ISTVON Mapper     │ (Gemini API or Rule-Engine Fallback)
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │  Schema Validation   │ (Dataclass / Pydantic Verification)
 └──────────┬───────────┘
            │
            ▼
   Structured ISTVON JSON
            │
            ▼
 ┌──────────────────────┐
 │ Response Generation  │ (Optional: Sends Prompt + ISTVON I-S-T-V-O spec to LLM)
 └──────────────────────┘
```

### Safety Broker Decisions
- **`BLOCK`**: Rejects harmful or unsafe inputs.
- **`NEEDS_FIX`**: Identifies risky or underspecified prompts, sanitizing inputs before enhancing.
- **`ALLOW`**: Passes safe inputs directly to the enhancement pipeline.

### COSTAR Gap Analysis
Evaluates prompt quality against key dimensions: **C**ontext, **O**bjective, **S**uccess criteria, **T**imeline, **A**udience, **R**esources.

---

## 📋 Prerequisites & Things to Know Before Running

- **Python Version**: Python 3.9+ installed on your system.
- **No Mandatory API Keys**: The app runs 100% out of the box using built-in rule-based pattern matchers. Providing a `GEMINI_API_KEY` enables Google Gemini LLM enhancements and response generation, but is entirely optional.
- **No Mandatory Database**: PostgreSQL integration is optional for enterprise telemetry logging. If PostgreSQL is not configured, the system seamlessly logs transformations locally to JSON (`istvon_transformations_log.json` & `rule_engine_logs.json`).
- **Flexible JSON Exports**: Download standalone ISTVON framework specifications or combined ISTVON + LLM generated response payloads.

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

Copy `.env.example` to `.env` if you wish to configure optional credentials:

```bash
cp .env.example .env
```

Environment settings template:
```env
# Optional: Google Gemini API Key for LLM-powered prompt transformation
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: PostgreSQL Database connection for telemetry
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=istvon_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

## 🚀 Usage & Deployment

### 1. Launch the Web Dashboard (Streamlit)

```bash
streamlit run app.py
```
- Default URL: **`http://localhost:8501`**
- Custom Port (if 8501 is in use): `streamlit run app.py --server.port 8502`

### 2. Run Standalone CLI Demo

```bash
python demo.py
```

### 3. Run Test Suite

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run individual test modules
python -m pytest tests/test_broker.py -v
python -m pytest tests/test_llm_mapper.py -v
python -m pytest tests/test_rules.py -v
```

---

## 🛠️ Helpful Tips & Troubleshooting

| Scenario | Detail / Solution |
|----------|-------------------|
| **Default Web Port** | `http://localhost:8501` |
| **Port Already in Use** | Run `streamlit run app.py --server.port 8502` |
| **Running Without API Key** | App automatically uses rule-based pattern matching (no API key needed) |
| **Running Without Database** | App logs decisions locally to JSON (no database setup required) |
| **Execution Policy Error (Windows)** | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` before activating venv |

---

## 📂 Project Structure

```
ISTVON_Prompt_Enhancement_Engine/
├── README.md                  # Comprehensive project documentation
├── app.py                     # Main Streamlit web application
├── config.py                  # Environment & schema configuration
├── database.py                # PostgreSQL telemetry & audit logger
├── demo.py                    # Standalone engine demonstration script
├── requirements.txt           # Project dependencies
├── engine/                    # Core processing engine
│   ├── broker.py              # Safety broker (ALLOW / NEEDS_FIX / BLOCK)
│   ├── completion_rules.py    # Rule-based completion fallback engine
│   ├── context_analyzers.py   # Technical, business & creative context detector
│   ├── istvon_schema.py       # ISTVON dataclass & JSON schema validator
│   ├── llm_mapper.py          # Gemini AI prompt transformer
│   └── pattern_matchers.py    # RegEx extractor for instructions & variables
├── utils/                     # Utility modules
│   ├── helpers.py             # String & dict formatting helpers
│   ├── json_logger.py         # JSON decision logging
│   ├── json_parser.py         # Robust JSON extractor & parser
│   ├── logger.py              # Application logging utility
│   └── validators.py          # Schema validation helper
└── tests/                     # Test suite
    ├── test_broker.py
    ├── test_llm_mapper.py
    └── test_rules.py
```
