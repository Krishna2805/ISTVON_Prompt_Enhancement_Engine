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
```

### Safety Broker Decisions
- **`BLOCK`**: Rejects harmful or unsafe inputs.
- **`NEEDS_FIX`**: Identifies risky or underspecified prompts, sanitizing inputs before enhancing.
- **`ALLOW`**: Passes safe inputs directly to the enhancement pipeline.

### COSTAR Gap Analysis
Evaluates prompt quality against key dimensions: **C**ontext, **O**bjective, **S**uccess criteria, **T**imeline, **A**udience, **R**esources.

---

## ⚙️ Installation & Setup

### 1. Clone & Setup Environment

```bash
git clone <your-repository-url>
cd ISTVON_Prompt_Enhancement_Engine

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Copy `.env.example` to `.env` (optional):

```bash
cp .env.example .env
```

Environment options:
```env
# Google Gemini API Key (Optional: system automatically falls back to rule-based mapping if omitted)
GEMINI_API_KEY=your_gemini_api_key_here

# PostgreSQL Database Configuration (Optional: for persistent telemetry logging)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=istvon_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

*Note: The engine is fully functional out of the box without any API keys or database connections.*

---

## 🚀 Usage & Deployment

### 1. Launch the Streamlit Web Application

```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 2. Run Test Suite

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run individual test modules
python -m pytest tests/test_broker.py -v
python -m pytest tests/test_llm_mapper.py -v
python -m pytest tests/test_rules.py -v
```

---

## 📂 Project Structure

```
ISTVON_Prompt_Enhancement_Engine/
├── README.md                  # Comprehensive documentation
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
