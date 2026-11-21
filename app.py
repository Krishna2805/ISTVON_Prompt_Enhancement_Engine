# app.py - Full ISTVON Prompt Enhancement Engine
import streamlit as st
import copy
import time
import json
from datetime import datetime

# Import our modules
from config import Config
from database import DatabaseManager
from engine.istvon_schema import ISTVONSchema
from engine.context_analyzers import ContextAnalyzer
from engine.completion_rules import ISTVONCompletionEngine
from engine.llm_mapper import LLMISTVONMapper
from engine.pattern_matchers import ISTVONPatternMatcher
from engine.broker import ISTVONBroker, SUPPORT_MESSAGE
from utils.helpers import ExamplePrompts
from utils.json_logger import RuleEngineLogger

# --- ISTVON Transformation Logger ---

ISTVON_LOG_FILE = "istvon_transformations_log.json"

def log_istvon_transformation(original_prompt: str, istvon_data: dict, 
                               verdict: str, reason: str, processing_time_ms: int,
                               llm_response: str = None):
    """Append a complete ISTVON transformation record to the local log file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "original_prompt": original_prompt,
        "verdict": verdict,
        "reason": reason,
        "processing_time_ms": processing_time_ms,
        "istvon_json": istvon_data,
    }
    if llm_response:
        entry["llm_response"] = llm_response

    try:
        with open(ISTVON_LOG_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"Warning: Could not write to ISTVON log: {e}")


class ISTVONEngine:
    """Main ISTVON processing engine"""
    
    def __init__(self):
        self.schema = ISTVONSchema()
        self.context_analyzer = ContextAnalyzer()
        self.pattern_matcher = ISTVONPatternMatcher()
        self.completion_engine = ISTVONCompletionEngine()
        self.llm_mapper = LLMISTVONMapper()
        self.broker = ISTVONBroker()
        self.db_manager = DatabaseManager()

    def _blocked(self, prompt: str, reason: str, start_time: float, **extra) -> dict:
        """Record a BLOCK in prompt_log and return the blocked result."""
        processing_time = int((time.time() - start_time) * 1000)
        self.db_manager.log_transformation(prompt, {}, False, processing_time=processing_time,
                                           verdict="BLOCK", reason=reason)
        return {"success": False, "error": reason, "processing_time": processing_time,
                "blocked": True, "verdict": "BLOCK", "reason": reason, **extra}

    def process_prompt(self, prompt: str) -> dict:
        """Process a natural language prompt into ISTVON JSON"""
        start_time = time.time()

        try:
            # Step 1: Safety check with broker (regex tier)
            broker_result = self.broker.process_with_broker(prompt)

            # Extract broker decision details
            verdict = broker_result.get("verdict", "UNKNOWN")
            reason = broker_result.get("reason", "No reason provided")
            analysis = broker_result.get("analysis", {})

            if not broker_result["success"]:
                return self._blocked(prompt, reason, start_time,
                                     recommendations=analysis.get("recommendations", []))

            # Step 2: LLM safety check (skipped, i.e. fails open, when no LLM answers)
            validation_result = self.llm_mapper.check_prompt_safety(prompt)

            if not validation_result.get("safe", True):
                block_reason = f"Blocked due to: {validation_result.get('reason', 'Judged unsafe by the LLM')}"
                RuleEngineLogger().log_decision(prompt, "BLOCK", block_reason)
                return self._blocked(prompt, block_reason, start_time, llm_validated=True)

            # Step 3: Analyze context. COSTAR gaps are passed on so the LLM can fill them.
            context = self.context_analyzer.analyze_prompt_context(prompt)
            context["costar_missing"] = analysis.get("costar_gaps", {}).get("missing_elements", [])

            # Step 4: Create preliminary mapping
            preliminary_map = self._create_preliminary_mapping(prompt, context)

            # Step 5: Enhance with LLM (if available). NEEDS_FIX prompts go to the LLM exactly as
            # typed; only the audit-log copy is redacted. This does not keep personal data away from
            # the provider. (Word-level redaction like "[REDACTED] interest" destroys the meaning.)
            enhanced_map = self.llm_mapper.enhance_mapping(prompt, preliminary_map, context)

            # Step 6: Apply completion rules
            final_map = self.completion_engine.apply_completion_rules(enhanced_map, context)

            # Step 7: Validate against schema
            validated_map = self.schema.validate_istvon(final_map)

            # Step 8: Log the transformation with broker details
            processing_time = int((time.time() - start_time) * 1000)
            # NEEDS_FIX only: the [REDACTED] audit copy (prompt_log column keeps its old name)
            sanitized_prompt = broker_result.get("sanitized_prompt")
            log_id = self.db_manager.log_transformation(
                prompt, validated_map, True,
                context.get('domain', 'auto'), processing_time,
                verdict, reason, sanitized_prompt
            )

            # Step 9: Log to local ISTVON transformations file
            log_istvon_transformation(
                prompt, validated_map, verdict, reason, processing_time
            )

            return {
                "success": True,
                "istvon": validated_map,
                "context": context,
                "processing_time": processing_time,
                "verdict": verdict,
                "reason": reason,
                "sanitized_prompt": sanitized_prompt,
                "recommendations": analysis.get("recommendations", []),
                "llm_checked": validation_result.get("llm_checked", False),
                "llm_check_note": validation_result.get("reason", ""),
                "log_id": log_id,
            }
            
        except Exception as e:
            # Log failed transformation
            processing_time = int((time.time() - start_time) * 1000)
            self.db_manager.log_transformation(
                prompt, {}, False, 
                "error", processing_time, "ERROR", str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
    
    def _create_preliminary_mapping(self, prompt: str, context: dict) -> dict:
        """Rule-based mapping: regex extraction from the prompt plus domain defaults.
        This is the whole result in offline mode, and the starting point the LLM refines."""
        extracted = self.pattern_matcher.extract_istvon_elements(prompt)
        mapping = {
            "I": extracted["I"],
            "O": {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements", "High quality output"],
                **extracted["O"],
            }
        }
        for key in ("S", "N"):
            if extracted[key]:
                mapping[key] = extracted[key]

        # deepcopy: later steps extend/update these in place; without the copy every
        # request mutated the process-global Config and leaked into the next one.
        domain = context.get('domain', 'general')
        domain_config = copy.deepcopy(Config.get_domain_config(domain)) if domain != 'general' else {}
        tools = extracted["T"] + domain_config.get('default_tools', [])
        if tools:
            mapping["T"] = list(dict.fromkeys(tools))
        variables = {**domain_config.get('default_variables', {}), **extracted["V"]}  # prompt wins
        if variables:
            mapping["V"] = variables

        return mapping
    
    def generate_response_with_istvon(self, original_prompt: str, istvon_data: dict) -> str:
        """Generate response using Gemini API with the full ISTVON spec as context."""
        try:
            if not self.llm_mapper.client:
                return "Error: No LLM configured. Set GEMINI_API_KEY + GEMINI_MODEL or GROQ_API_KEY + GROQ_MODEL in .env."
            
            # Build a rich prompt from the ISTVON spec
            istvon_context_parts = []
            
            instructions = istvon_data.get("I", [])
            if instructions:
                istvon_context_parts.append("**Instructions:**\n" + "\n".join(f"- {i}" for i in instructions))
            
            sources = istvon_data.get("S", {})
            if sources:
                istvon_context_parts.append("**Sources & References:**\n" + json.dumps(sources, indent=2))
            
            tools = istvon_data.get("T", [])
            if tools:
                istvon_context_parts.append("**Tools to use:**\n" + "\n".join(f"- {t}" for t in tools))
            
            variables = istvon_data.get("V", {})
            if variables:
                istvon_context_parts.append("**Constraints & Variables:**\n" + json.dumps(variables, indent=2))
            
            outcome = istvon_data.get("O", {})
            if outcome:
                istvon_context_parts.append("**Expected Outcome:**\n" + json.dumps(outcome, indent=2))
            
            istvon_block = "\n\n".join(istvon_context_parts)
            
            full_prompt = (
                f"PRIMARY USER REQUEST (Main Objective):\n"
                f"\"{original_prompt}\"\n\n"
                f"SUPPORTING ISTVON FRAMEWORK (Guidelines, Tools & Constraints):\n"
                f"Use the structured ISTVON specification below to refine, format, and enhance your response. "
                f"The primary user request above is your main objective; use the ISTVON specification to ensure completeness, correct formatting, and appropriate tooling.\n\n"
                f"{istvon_block}\n\n"
                f"Now produce a high-quality response that directly fulfills the primary request following all ISTVON guidelines."
            )
            
            response_text = self.llm_mapper.generate_response(full_prompt)

            return response_text or "No response generated"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"


@st.cache_resource
def get_engine():
    return ISTVONEngine()


def _clear_state():
    """Clear button callback: reset the prompt box and any shown results."""
    for key in ['istvon_result', 'original_prompt', 'generated_response']:
        st.session_state.pop(key, None)
    st.session_state["prompt_input"] = ""


def main():
    """Main application function"""
    
    # Set page config - MUST be first Streamlit command
    st.set_page_config(
        page_title=Config.PAGE_TITLE,
        page_icon=Config.PAGE_ICON,
        layout=Config.LAYOUT,
        initial_sidebar_state="expanded"
    )
    
    # Title and description
    st.title("🚀 ISTVON Prompt Enhancement Engine")
    st.markdown("Transform natural language prompts into structured ISTVON JSON")
    
    # Initialize the engine once per server process (not on every widget interaction)
    engine = get_engine()
    llm_status = (f"✅ {engine.llm_mapper.provider.title()} ({engine.llm_mapper.model_name})"
                  if engine.llm_mapper.client else "⚠️ Offline pattern fallback")
    if not engine.llm_mapper.client:
        st.warning(f"**Offline mode.** {Config.llm_setup_hint()} Without an LLM you get the basic "
                   "regex mapping only: no LLM safety check and no response generation.")
    conn = engine.db_manager.connection
    db_status = "✅ PostgreSQL" if conn and not conn.closed else "⚠️ Not connected (local JSON logs only)"

    # --- Sidebar (cleaned up) ---
    with st.sidebar:
        st.header("📚 Example Prompts")
        
        example_type = st.selectbox(
            "Choose an example:",
            ["Select...", "business_email", "technical_doc", "blog_post", "research_summary"]
        )
        
        if example_type != "Select...":
            example_prompt = ExamplePrompts.get_example(example_type)
            st.text_area("Example:", value=example_prompt, height=100, disabled=True)
        
        st.markdown("---")
        st.header("ℹ️ System Status")
        st.markdown(f"**LLM:** {llm_status}")
        st.markdown(f"**Database:** {db_status}")
    
    # --- Main input area ---
    st.subheader("📝 Enter Your Prompt")
    
    # Text area for prompt input
    prompt = st.text_area(
        "Natural language prompt:",
        placeholder="e.g., 'Write a professional email about product launch'",
        height=100,
        max_chars=Config.MAX_PROMPT_LENGTH,
        key="prompt_input"
    )
    
    # Character count
    if prompt:
        st.caption(f"Characters: {len(prompt)}/{Config.MAX_PROMPT_LENGTH}")
    
    # Process button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        process_btn = st.button("🔄 Enhance with ISTVON", type="primary")
    
    with col2:
        # on_click runs before the next script run, so no st.rerun() is needed
        # (st.rerun() inside `if st.button()` loops forever on Streamlit 1.28).
        st.button("🗑️ Clear", on_click=_clear_state)

    # Process the prompt
    if process_btn:
        if prompt.strip():
            with st.spinner("Processing your prompt..."):
                result = engine.process_prompt(prompt)
                
                if result["success"]:
                    # Store result in session state
                    st.session_state['istvon_result'] = result
                    st.session_state['original_prompt'] = prompt
                    # Clear any previous response when a new prompt is processed
                    st.session_state.pop('generated_response', None)
                
                else:
                    for key in ['istvon_result', 'original_prompt', 'generated_response']:
                        st.session_state.pop(key, None)

                    safe_error = str(result.get('error', 'Unknown error')).replace('`', "'")
                    safe_reason = str(result.get('reason', 'N/A')).replace('`', "'")

                    if result.get("blocked", False):
                        st.error("🛡️ **Content Blocked for Safety**")
                        st.error(f"❌ `{safe_error}`")
                        
                        # Show verdict and reason
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Verdict:** {result.get('verdict', 'N/A')}")
                        with col2:
                            st.info(f"**Reason:** `{safe_reason}`")
                        
                        # Show safety recommendations
                        if result.get("recommendations"):
                            st.warning("💡 **Safety Recommendations:**")
                            for rec in result["recommendations"]:
                                st.write(f"• {rec}")
                        
                        if SUPPORT_MESSAGE not in result.get("recommendations", []):
                            st.info("🔄 **Please rephrase your prompt with appropriate language**")
                    else:
                        st.error(f"❌ Processing failed: `{safe_error}`")
        else:
            st.warning("Please enter a prompt first.")
    
    # --- Display ISTVON result from session state ---
    if 'istvon_result' in st.session_state:
        result = st.session_state['istvon_result']
        
        st.markdown("---")
        st.success("✅ ISTVON Framework Generated Successfully!")
        
        # Display verdict and reason
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Verdict:** {result.get('verdict', 'N/A')}")
        with col2:
            st.info(f"**Reason:** {result.get('reason', 'N/A')}")
        with col3:
            st.info(f"**Processing Time:** {result['processing_time']} ms")

        if result.get('verdict') == 'NEEDS_FIX':
            sent = f" and sent unchanged to {engine.llm_mapper.provider.title()}" if engine.llm_mapper.client else ""
            st.warning("⚠️ **Sensitive or risky wording detected.** The prompt was still processed as written"
                       f"{sent}; nothing was removed from it. Only the copy stored in the audit log has the "
                       f"flagged terms replaced: `{str(result.get('sanitized_prompt', '')).replace('`', chr(39))}`")
        for rec in result.get("recommendations", []):
            if not rec.startswith("Safe to proceed"):
                st.caption(f"💡 {rec}")
        if not result.get("llm_checked"):
            st.caption(f"ℹ️ LLM safety check skipped ({result.get('llm_check_note') or 'no LLM answer'}); "
                       "only the regex safety rules checked this prompt.")

        # --- Tab 1: ISTVON JSON ---
        tab1, tab2 = st.tabs(["🎯 ISTVON Framework", "⏱️ Processing Info"])
        
        with tab1:
            st.subheader("Generated ISTVON JSON")
            st.json(result["istvon"])
            
            # Download ISTVON-only JSON
            json_str = json.dumps(result["istvon"], indent=2)
            st.download_button(
                label="📥 Download ISTVON JSON",
                data=json_str,
                file_name=f"istvon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_istvon_only"
            )
        
        with tab2:
            st.subheader("Processing Information")
            st.metric("Processing Time", f"{result['processing_time']} ms")
            st.metric("LLM", llm_status)
        
        # --- Response Generation Section (below tabs) ---
        st.markdown("---")
        st.subheader("🚀 Response Generation")
        st.markdown(
            "Would you like to send the **ISTVON JSON** and your **original prompt** "
            "to the LLM for response generation?"
        )
        
        generate_btn = st.button("✅ Yes, Generate Response", type="primary", key="generate_response_btn")
        
        if generate_btn:
            if not engine.llm_mapper.client:
                st.error("❌ No LLM configured. Set `GEMINI_API_KEY` + `GEMINI_MODEL` or `GROQ_API_KEY` + `GROQ_MODEL` in `.env` to use response generation.")
            else:
                with st.spinner("Generating response from LLM using ISTVON spec..."):
                    original_prompt = st.session_state.get('original_prompt', '')
                    response_text = engine.generate_response_with_istvon(
                        original_prompt, result["istvon"]
                    )
                    st.session_state['generated_response'] = response_text
                    engine.db_manager.log_response(result.get('log_id'), response_text)

                    # Log the response alongside the ISTVON spec
                    log_istvon_transformation(
                        original_prompt, result["istvon"],
                        result.get('verdict', 'ALLOW'),
                        result.get('reason', 'Response generated'),
                        result.get('processing_time', 0),
                        llm_response=response_text
                    )
        
        # Display generated response (persisted in session state)
        if 'generated_response' in st.session_state:
            st.markdown("---")
            st.subheader("📝 Generated Response")
            st.markdown(st.session_state['generated_response'])
            
            # Download ISTVON + Response combined JSON
            combined_data = {
                "timestamp": datetime.now().isoformat(),
                "original_prompt": st.session_state.get('original_prompt', ''),
                "istvon_json": result["istvon"],
                "llm_response": st.session_state['generated_response'],
                "verdict": result.get('verdict', 'N/A'),
                "reason": result.get('reason', 'N/A'),
                "processing_time_ms": result.get('processing_time', 0)
            }
            combined_json_str = json.dumps(combined_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download ISTVON + Response JSON",
                data=combined_json_str,
                file_name=f"istvon_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_istvon_response"
            )
    
    # Footer
    st.markdown("---")
    st.markdown("**ISTVON Framework**: Instructions, Sources, Tools, Variables, Outcome, Notifications")

if __name__ == "__main__":
    main()