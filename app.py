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
                # Note: Rule engine decision is already logged to JSON file by broker
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
                from utils.json_logger import RuleEngineLogger
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
    
    def generate_response(self, prompt: str) -> str:
        """Generate response using Gemini API"""
        try:
            import google.generativeai as genai
            from config import Config
            
            # Configure Gemini
            genai.configure(api_key=Config.GEMINI_API_KEY)
            model = genai.GenerativeModel(Config.DEFAULT_MODEL)
            
            # Generate response
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text
            else:
                return "No response generated"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def export_response_to_json(self, response_data: dict, filename: str = None) -> str:
        """Export response data to JSON file and return the file path"""
        try:
            from datetime import datetime
            import os
            
            # Create exports directory if it doesn't exist
            exports_dir = "exports"
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"response_export_{timestamp}.json"
            
            # Ensure filename has .json extension
            if not filename.endswith('.json'):
                filename += '.json'
            
            filepath = os.path.join(exports_dir, filename)
            
            # Write JSON data to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            return filepath
            
        except Exception as e:
            print(f"Error exporting to JSON: {str(e)}")
            return None
    
    def create_complete_response_data(self, original_prompt: str, istvon_data: dict, 
                                    context: dict, response: str, processing_time: int,
                                    verdict: str, reason: str, sanitized_prompt: str = None) -> dict:
        """Create a complete response data structure for JSON export matching PostgreSQL schema"""
        from datetime import datetime
        
        # Get the selected instruction from ISTVON as sanitized_prompt
        selected_instruction = None
        if istvon_data and 'I' in istvon_data and istvon_data['I']:
            selected_instruction = istvon_data['I'][0] if isinstance(istvon_data['I'], list) else str(istvon_data['I'])
        
        return {
            "id": None,  # Will be set by database auto-increment
            "timestamp": datetime.now().isoformat(),
            "original_prompt": original_prompt,
            "verdict": verdict,
            "reason": reason,
            "sanitized_prompt": sanitized_prompt or selected_instruction,
            "final_response": response,
            "istvon_map_json": istvon_data,
            "metadata": {
                "processing_time_ms": processing_time,
                "export_version": "2.0",
                "context_analysis": context,
                "database_logged": True
            }
        }
    
    def process_and_export_response(self, original_prompt: str, istvon_data: dict, 
                                  context: dict, response: str, processing_time: int,
                                  verdict: str, reason: str, sanitized_prompt: str = None) -> dict:
        """Complete workflow: create response data, export to JSON, and log to database"""
        try:
            # Create complete response data
            complete_response_data = self.create_complete_response_data(
                original_prompt, istvon_data, context, response, 
                processing_time, verdict, reason, sanitized_prompt
            )
            
            # Export to JSON file
            json_filepath = self.export_response_to_json(complete_response_data)
            
            # Log to database
            self.db_manager.log_transformation(
                original_prompt, istvon_data, True,
                context.get('domain', 'auto'), processing_time,
                verdict, reason, sanitized_prompt, response
            )
            
            return {
                "success": True,
                "json_filepath": json_filepath,
                "response_data": complete_response_data,
                "database_logged": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "json_filepath": None,
                "database_logged": False
            }
    
    def import_json_to_database(self, json_filepath: str) -> bool:
        """Import a JSON file back into the database"""
        return self.db_manager.import_from_json_file(json_filepath)

def setup_environment():
    """Setup environment with error handling"""
    try:
        # Test imports
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
    
    # Sidebar with examples and analytics
    with st.sidebar:
        st.header("📚 Example Prompts")
        
        example_type = st.selectbox(
            "Choose an example:",
            ["Select...", "business_email", "technical_doc", "blog_post", "research_summary"]
        )
        
        if example_type != "Select...":
            example_prompt = ExamplePrompts.get_example(example_type)
            st.text_area("Example:", value=example_prompt, height=100, disabled=True)
        
        st.header("📊 Analytics")
        try:
            analytics = engine.db_manager.get_analytics()
            st.metric("Total Transformations", analytics.get('total_transformations', 0))
            st.metric("Success Rate", f"{analytics.get('success_rate', 0):.1f}%")
            st.metric("Avg Prompt Length", f"{analytics.get('avg_prompt_length', 0):.0f} chars")
        except Exception as e:
            # Database might not be connected - this is expected in many cases
            st.info("No analytics data yet")
        
        st.header("🔧 Recent Sanitized Prompts")
        try:
            sanitized_prompts = engine.db_manager.get_sanitized_prompts(5)
            if sanitized_prompts:
                for i, prompt_data in enumerate(sanitized_prompts, 1):
                    with st.expander(f"Prompt {i} - {prompt_data['verdict']}"):
                        st.write("**Original:**", prompt_data['original_prompt'][:100] + "...")
                        st.write("**Sanitized:**", prompt_data['sanitized_prompt'][:100] + "...")
                        st.write("**Time:**", prompt_data['timestamp'])
            else:
                st.info("No sanitized prompts yet")
        except Exception as e:
            # Database might not be connected - this is expected in many cases
            st.info("No sanitized prompts data yet")
        
        st.header("📁 JSON Import/Export")
        st.write("Import JSON files back into database:")
        
        # File uploader for JSON import
        uploaded_file = st.file_uploader(
            "Choose a JSON file to import",
            type=['json'],
            key="json_importer"
        )
        
        if uploaded_file is not None:
            try:
                # Save uploaded file temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_filepath = tmp_file.name
                
                # Import to database
                if engine.import_json_to_database(tmp_filepath):
                    st.success("✅ JSON file imported successfully to database!")
                else:
                    st.error("❌ Failed to import JSON file to database")
                
                # Clean up temp file
                import os
                os.unlink(tmp_filepath)
                
            except Exception as e:
                st.error(f"❌ Error importing file: {str(e)}")
        
        # Show recent exports
        st.write("**Recent Exports:**")
        try:
            import os
            exports_dir = "exports"
            if os.path.exists(exports_dir):
                export_files = [f for f in os.listdir(exports_dir) if f.endswith('.json')]
                if export_files:
                    # Sort by modification time (newest first)
                    export_files.sort(key=lambda x: os.path.getmtime(os.path.join(exports_dir, x)), reverse=True)
                    for i, filename in enumerate(export_files[:3], 1):
                        st.write(f"{i}. `{filename}`")
                else:
                    st.info("No export files yet")
            else:
                st.info("No exports directory yet")
        except Exception as e:
            # File system issues - this is expected if exports directory doesn't exist
            st.info("No export files available")
    
    # Main input area
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
        st.rerun()
    
    # Process the prompt
    if process_btn:
        if prompt:
            with st.spinner("Processing your prompt..."):
                result = engine.process_prompt(prompt)
                
                if result["success"]:
                    # Store result in session state to avoid re-processing
                    st.session_state['istvon_result'] = result
                    st.session_state['original_prompt'] = prompt
                    st.success("✅ Prompt processed successfully!")
                    
                    # Display verdict and reason
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Verdict:** {result.get('verdict', 'N/A')}")
                    with col2:
                        st.info(f"**Reason:** {result.get('reason', 'N/A')}")
                    
                    # Just show success message - detailed results will be shown in session state section below
                
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
    
    # Display ISTVON result from session state (if exists)
    if 'istvon_result' in st.session_state:
        result = st.session_state['istvon_result']
        
        st.markdown("---")
        st.success("✅ ISTVON Framework Generated Successfully!")
        
        # Display verdict and reason
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Verdict:** {result.get('verdict', 'N/A')}")
        with col2:
            st.info(f"**Reason:** {result.get('reason', 'N/A')}")
        
        # Display results in tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 ISTVON JSON", "📊 Context Analysis", "🔧 Generate Response", "⏱️ Processing Info"])
        
        with tab1:
            st.subheader("Generated ISTVON JSON")
            st.json(result["istvon"])
            
            # Download button
            json_str = json.dumps(result["istvon"], indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"istvon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with tab2:
            st.subheader("Context Analysis")
            context = result["context"]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Domain", context.get('domain', 'general'))
            with col2:
                st.metric("Complexity", context.get('complexity', 'medium'))
            with col3:
                st.metric("Specificity", context.get('specificity', 'medium'))
            
            if context.get('domain_specific_rules'):
                st.subheader("Domain Rules Applied")
                st.json(context['domain_specific_rules'])
        
        with tab3:
            st.subheader("🚀 Generate Response")
            
            # Get instructions from ISTVON "I" section
            istvon_instructions = result["istvon"].get("I", [])
            
            if istvon_instructions:
                st.write("**Select a prompt from ISTVON Instructions:**")
                
                # Create dropdown with ISTVON instructions
                selected_instruction = st.selectbox(
                    "Choose an instruction prompt:",
                    istvon_instructions,
                    key="instruction_selector"
                )
                
                # Generate response button
                col1, col2 = st.columns([1, 3])
                with col1:
                    generate_response_btn = st.button("🚀 Generate Response", type="primary", key="generate_response_from_istvon")
                
                # Generate response if button clicked
                if generate_response_btn and selected_instruction:
                    with st.spinner("Generating response..."):
                        response = engine.generate_response(selected_instruction)
                        
                        # Process and export response (JSON + Database)
                        export_result = engine.process_and_export_response(
                            original_prompt=st.session_state.get('original_prompt', ''),
                            istvon_data=result["istvon"],
                            context=result["context"],
                            response=response,
                            processing_time=result.get('processing_time', 0),
                            verdict=result.get('verdict', 'ALLOW'),
                            reason=result.get('reason', 'ISTVON instruction'),
                            sanitized_prompt=result.get('sanitized_prompt')
                        )
                        
                        st.success("✅ Response generated successfully!")
                        st.text_area("Generated Response:", value=response, height=200, key="response_output")
                        
                        # Show export results
                        if export_result["success"]:
                            st.success(f"📄 Response exported to JSON: `{export_result['json_filepath']}`")
                            st.info("💾 Data has been logged to the database")
                        else:
                            st.error(f"❌ Export failed: {export_result.get('error', 'Unknown error')}")
                            st.warning("⚠️ Response was generated but export failed")
            else:
                st.warning("No instructions found in ISTVON framework.")
        
        with tab4:
            st.subheader("Processing Information")
            st.metric("Processing Time", f"{result['processing_time']} ms")
            st.metric("API Status", "✅ Configured" if Config.is_api_configured() else "⚠️ Using fallback")
            
            # Show recent transformations
            st.subheader("Recent Transformations")
            try:
                recent = engine.db_manager.get_recent_transformations(3)
                for item in recent:
                    status_icon = "✅" if item['success'] else "❌"
                    st.text(f"{status_icon} {item['prompt']} ({item['timestamp']})")
            except Exception as e:
                # Database might not be connected - this is expected in many cases
                st.info("No recent transformations")
    
    # Footer
    st.markdown("---")
    st.markdown("**ISTVON Framework**: Instructions, Sources, Tools, Variables, Outcome, Notifications")

if __name__ == "__main__":
    main()