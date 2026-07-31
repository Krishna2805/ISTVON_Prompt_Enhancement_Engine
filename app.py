# app.py - Full ISTVON Prompt Enhancement Engine
import streamlit as st
import sys
import os
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
from engine.broker import ISTVONBroker, BrokerDecision
from utils.helpers import HelperFunctions, ExamplePrompts
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
        self.completion_engine = ISTVONCompletionEngine()
        self.llm_mapper = LLMISTVONMapper()
        self.broker = ISTVONBroker()
        self.db_manager = DatabaseManager()
    
    def process_prompt(self, prompt: str) -> dict:
        """Process a natural language prompt into ISTVON JSON"""
        start_time = time.time()
        
        try:
            # Step 1: Safety check with broker
            broker_result = self.broker.process_with_broker(prompt)
            
            # Extract broker decision details
            verdict = broker_result.get("verdict", "UNKNOWN")
            reason = broker_result.get("reason", "No reason provided")
            
            if not broker_result["success"]:
                # Content was blocked by broker
                processing_time = int((time.time() - start_time) * 1000)
                return {
                    "success": False,
                    "error": reason,
                    "processing_time": processing_time,
                    "blocked": True,
                    "verdict": verdict,
                    "reason": reason,
                    "recommendations": broker_result.get("analysis", {}).get("recommendations", [])
                }
            
            # Step 2: LLM Validation - Check if prompt is sanitizable
            validation_result = self.llm_mapper.validate_sanitizability(prompt)
            
            if not validation_result.get("sanitizable", True):
                # Prompt cannot be sanitized, block it
                processing_time = int((time.time() - start_time) * 1000)
                block_reason = f"Blocked due to: {validation_result.get('reason', 'Cannot be sanitized')}"
                
                # Log the block decision to JSON file
                json_logger = RuleEngineLogger()
                json_logger.log_decision(prompt, "BLOCK", block_reason)
                
                return {
                    "success": False,
                    "error": block_reason,
                    "processing_time": processing_time,
                    "blocked": True,
                    "verdict": "BLOCK",
                    "reason": block_reason,
                    "llm_validated": True
                }
            
            # Step 3: Analyze context
            context = self.context_analyzer.analyze_prompt_context(prompt)
            
            # Step 4: Create preliminary mapping
            preliminary_map = self._create_preliminary_mapping(prompt, context)
            
            # Step 5: Enhance with LLM (if available)
            enhanced_map = self.llm_mapper.enhance_mapping(prompt, preliminary_map, context)
            
            # Step 6: Apply completion rules
            final_map = self.completion_engine.apply_completion_rules(enhanced_map, context)
            
            # Step 7: Validate against schema
            validated_map = self.schema.validate_istvon(final_map)
            
            # Step 8: Log the transformation with broker details
            processing_time = int((time.time() - start_time) * 1000)
            sanitized_prompt = broker_result.get("sanitized_prompt")
            self.db_manager.log_transformation(
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
                "sanitized_prompt": sanitized_prompt
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
        """Create a preliminary ISTVON mapping based on rules"""
        mapping = {
            "I": [f"Execute the requested task: {prompt[:100]}..."],
            "O": {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements", "High quality output"]
            }
        }
        
        # Add domain-specific elements
        domain = context.get('domain', 'general')
        if domain != 'general':
            domain_config = Config.get_domain_config(domain)
            if domain_config.get('default_tools'):
                mapping["T"] = domain_config['default_tools']
            if domain_config.get('default_variables'):
                mapping["V"] = domain_config['default_variables']
        
        return mapping
    
    def generate_response_with_istvon(self, original_prompt: str, istvon_data: dict) -> str:
        """Generate response using Gemini API with the full ISTVON spec as context."""
        try:
            import google.generativeai as genai
            from config import Config
            
            if not Config.GEMINI_API_KEY:
                return "Error: No Gemini API key configured. Please add GEMINI_API_KEY to your .env file."
            
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
            
            # Configure Gemini
            genai.configure(api_key=Config.GEMINI_API_KEY)
            model = genai.GenerativeModel(Config.DEFAULT_MODEL)
            
            # Generate response
            response = model.generate_content(full_prompt)
            
            if response and response.text:
                return response.text
            else:
                return "No response generated"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"


def setup_environment():
    """Setup environment with error handling"""
    try:
        from database import DatabaseManager
        from config import Config
        from engine.istvon_schema import ISTVONSchema
        from engine.context_analyzers import ContextAnalyzer
        from engine.completion_rules import ISTVONCompletionEngine
        from engine.llm_mapper import LLMISTVONMapper
        return True
    except ImportError as e:
        st.error(f"Import error: {e}")
        return False

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
    
    # Check if environment is setup correctly
    with st.spinner("Checking environment..."):
        if not setup_environment():
            st.error("❌ Environment setup failed. Please check the error above.")
            return
    
    st.success("✅ Environment loaded successfully!")
    
    # Initialize the engine
    engine = ISTVONEngine()
    
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
        st.metric("API Status", "✅ Configured" if Config.is_api_configured() else "⚠️ Rule-based fallback")
    
    # --- Main input area ---
    st.subheader("📝 Enter Your Prompt")
    
    # Text area for prompt input
    prompt = st.text_area(
        "Natural language prompt:",
        placeholder="e.g., 'Write a professional email about product launch'",
        height=100,
        max_chars=Config.MAX_PROMPT_LENGTH
    )
    
    # Character count
    if prompt:
        st.caption(f"Characters: {len(prompt)}/{Config.MAX_PROMPT_LENGTH}")
    
    # Process button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        process_btn = st.button("🔄 Enhance with ISTVON", type="primary")
    
    with col2:
        clear_btn = st.button("🗑️ Clear")
    
    if clear_btn:
        # Clear session state explicitly before rerun
        for key in ['istvon_result', 'original_prompt', 'generated_response']:
            st.session_state.pop(key, None)
        st.rerun()
    
    # Process the prompt
    if process_btn:
        if prompt:
            with st.spinner("Processing your prompt..."):
                result = engine.process_prompt(prompt)
                
                if result["success"]:
                    # Store result in session state
                    st.session_state['istvon_result'] = result
                    st.session_state['original_prompt'] = prompt
                    # Clear any previous response when a new prompt is processed
                    st.session_state.pop('generated_response', None)
                
                else:
                    if result.get("blocked", False):
                        st.error("🛡️ **Content Blocked for Safety**")
                        st.error(f"❌ {result['error']}")
                        
                        # Show verdict and reason
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Verdict:** {result.get('verdict', 'N/A')}")
                        with col2:
                            st.info(f"**Reason:** {result.get('reason', 'N/A')}")
                        
                        # Show safety recommendations
                        if result.get("recommendations"):
                            st.warning("💡 **Safety Recommendations:**")
                            for rec in result["recommendations"]:
                                st.write(f"• {rec}")
                        
                        st.info("🔄 **Please rephrase your prompt with appropriate language**")
                    else:
                        st.error(f"❌ Processing failed: {result['error']}")
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
            st.metric("API Status", "✅ Configured" if Config.is_api_configured() else "⚠️ Using fallback")
        
        # --- Response Generation Section (below tabs) ---
        st.markdown("---")
        st.subheader("🚀 Response Generation")
        st.markdown(
            "Would you like to send the **ISTVON JSON** and your **original prompt** "
            "to the LLM for response generation?"
        )
        
        generate_btn = st.button("✅ Yes, Generate Response", type="primary", key="generate_response_btn")
        
        if generate_btn:
            if not Config.is_api_configured():
                st.error("❌ No Gemini API key configured. Add `GEMINI_API_KEY` to your `.env` file to use response generation.")
            else:
                with st.spinner("Generating response from LLM using ISTVON spec..."):
                    original_prompt = st.session_state.get('original_prompt', '')
                    response_text = engine.generate_response_with_istvon(
                        original_prompt, result["istvon"]
                    )
                    st.session_state['generated_response'] = response_text
                    
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