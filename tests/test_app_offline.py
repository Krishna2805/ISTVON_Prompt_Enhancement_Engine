# tests/test_app_offline.py - the Streamlit app with no LLM key and no database
import os

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import database
from config import Config

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


class NoDatabase:
    """Stands in for DatabaseManager when PostgreSQL is absent."""
    connection = None

    def log_transformation(self, *args, **kwargs):
        return None

    def log_response(self, *args, **kwargs):
        return False


def _no_keys(monkeypatch, provider=""):
    for name, value in (("GEMINI_API_KEY", None), ("DEFAULT_MODEL", ""), ("GROQ_API_KEY", None),
                        ("GROQ_MODEL", ""), ("LLM_PROVIDER", provider)):
        monkeypatch.setattr(Config, name, value)


@pytest.fixture
def offline_app(monkeypatch):
    _no_keys(monkeypatch)
    monkeypatch.setattr(database, "DatabaseManager", NoDatabase)
    st.cache_resource.clear()  # the engine is cached per process; build it with this config
    yield AppTest.from_file(APP, default_timeout=60)
    st.cache_resource.clear()


def test_no_keys_app_runs_offline_end_to_end(offline_app):
    at = offline_app.run()
    assert not at.exception
    banner = " ".join(w.value for w in at.warning)
    assert "Offline mode" in banner and "GEMINI_API_KEY" in banner and "GROQ_MODEL" in banner
    assert any("Not connected" in m.value for m in at.sidebar.markdown)

    at.text_area(key="prompt_input").input("Write a business email under 200 words to clients").run()
    next(b for b in at.button if "Enhance" in b.label).click().run()
    assert not at.exception
    assert at.json, "ISTVON JSON not rendered"
    assert any("LLM safety check skipped" in c.value for c in at.caption)

    next(b for b in at.button if "Generate Response" in b.label).click().run()
    assert not at.exception
    assert any("No LLM configured" in e.value for e in at.error)


def test_setup_hint_names_what_is_missing(monkeypatch):
    _no_keys(monkeypatch)
    assert Config.llm_settings() == (None, None, None)
    assert "GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL" in Config.llm_setup_hint()

    # LLM_PROVIDER=groq with a Groq key but no GROQ_MODEL: offline, even if Gemini is configured
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "unit-check-value-gemini")
    monkeypatch.setattr(Config, "DEFAULT_MODEL", "gemini-model")
    monkeypatch.setattr(Config, "GROQ_API_KEY", "unit-check-value-groq")
    monkeypatch.setattr(Config, "LLM_PROVIDER", "groq")
    assert Config.llm_settings() == (None, None, None)
    hint = Config.llm_setup_hint()
    assert "LLM_PROVIDER=groq" in hint and "GROQ_MODEL" in hint and "GROQ_API_KEY" not in hint.split(".")[0]
