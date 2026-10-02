"""
Streamlit Chat Frontend for MediBuddy Weather-Advisory Support Bot.
Provides an interactive multi-turn chat interface backed by LangGraph.
"""

import streamlit as st
import uuid
import sys
import os

# Ensure local imports work reliably
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.graph_agent import WeatherAdvisoryGraph

# Page configuration
st.set_page_config(
    page_title="MediBuddy Weather-Advisory Support Bot",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styles for clean, professional look
st.markdown("""
<style>
    .reportview-container {
        background: #fdfdfd;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    }
    .badge-critical { color: #dc2626; font-weight: bold; }
    .badge-high { color: #ea580c; font-weight: bold; }
    .badge-medium { color: #d97706; font-weight: bold; }
    .badge-low { color: #16a34a; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize bot in session state
if "bot" not in st.session_state:
    st.session_state.bot = WeatherAdvisoryGraph()

if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am the **MediBuddy Weather-Advisory Assistant**.\n\n"
                "I provide verified safety recommendations for outdoor activities (cycling, running, picnics, family outings, commutes) "
                "strictly grounded in **live Open-Meteo weather data** and our authorized clinical **Standard Operating Procedures (SOPs)**.\n\n"
                "Ask me about any activity and location (e.g. *'Is it safe to cycle in Bhopal today?'* or *'Should I take my kids to the park in Delhi?'*)."
            ),
            "state_info": None
        }
    ]

# Sidebar controls & information
with st.sidebar:
    st.title("🌦️ Weather Advisory")
    st.caption("MediBuddy Clinical SOP Safety Bot")

    st.markdown("---")
    st.subheader("Session Controls")
    st.write(f"**Session ID:** `{st.session_state.session_id}`")
    
    if st.button("🔄 Reset Conversation / New Session", use_container_width=True):
        st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Conversation reset. What activity and location would you like me to check?",
                "state_info": None
            }
        ]
        st.rerun()

    st.markdown("---")
    st.subheader("Quick Test Prompts")
    quick_prompts = [
        "Is it safe to cycle in Bhopal today?",
        "What about this evening instead?",
        "Is today good for a family picnic in Delhi?",
        "Taking my scooty across the open bridge in Mumbai",
        "Can my friends and I play chess indoors in Bangalore?",
        "Is it safe to go for a run in AbcDefGhi999Z?"
    ]

    for qp in quick_prompts:
        if st.button(qp, key=f"btn_{qp}", use_container_width=True):
            st.session_state.selected_prompt = qp
            st.rerun()

    st.markdown("---")
    st.subheader("Architecture Highlights")
    st.markdown("""
    - **LangGraph State Graph** with 8 nodes & 3 conditional branches
    - **Live Open-Meteo API** (No API key needed)
    - **Session Memory**: Context carries over across turns
    - **Zero Hallucination**: Only authorized SOPs cited
    - **Live Extensibility**: Add 11th rule to `data/sops.json` on the spot
    """)

# Display Chat History
st.title("MediBuddy Weather Safety Advisory")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display policy inspector expander if metadata exists
        state_info = msg.get("state_info")
        if state_info and state_info.get("selected_sop"):
            sop = state_info["selected_sop"]
            weather = state_info.get("weather_data", {})
            metrics = weather.get("metrics", {})
            
            with st.expander(f"🔍 Policy Inspector: [{sop['id']}] {sop['title']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Category:**", sop.get("category"))
                    st.write("**Severity:**", sop.get("severity"))
                    st.write("**Matched Rationale:**", sop.get("rationale"))
                with col2:
                    st.write("**Conflict Resolution Strategy:**", state_info.get("resolution_rationale"))
                    if state_info.get("secondary_sops"):
                        st.write(f"**Secondary SOPs ({len(state_info['secondary_sops'])}):**")
                        for s in state_info["secondary_sops"]:
                            st.write(f"- `{s['id']}`: {s['title']}")

# User Input Handling
prompt_to_process = None
if "selected_prompt" in st.session_state and st.session_state.selected_prompt:
    prompt_to_process = st.session_state.selected_prompt
    st.session_state.selected_prompt = None
else:
    user_input = st.chat_input("Ask about an outdoor activity and location (e.g. 'Is it safe to cycle in Bhopal?')...")
    if user_input:
        prompt_to_process = user_input

if prompt_to_process:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt_to_process, "state_info": None})
    with st.chat_message("user"):
        st.markdown(prompt_to_process)

    # Process through LangGraph agent
    with st.chat_message("assistant"):
        with st.spinner("Fetching live weather and evaluating clinical safety SOPs..."):
            agent_result = st.session_state.bot.process_message(
                user_query=prompt_to_process,
                session_id=st.session_state.session_id
            )
            response_text = agent_result.get("final_response", "No response generated.")
            st.markdown(response_text)

            # Record state info for auditability
            state_record = {
                "selected_sop": agent_result.get("selected_sop"),
                "secondary_sops": agent_result.get("secondary_sops", []),
                "weather_data": agent_result.get("weather_data"),
                "resolution_rationale": agent_result.get("resolution_rationale"),
                "status": agent_result.get("status")
            }

            if agent_result.get("selected_sop"):
                sop = agent_result["selected_sop"]
                with st.expander(f"🔍 Policy Inspector: [{sop['id']}] {sop['title']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Category:**", sop.get("category"))
                        st.write("**Severity:**", sop.get("severity"))
                        st.write("**Matched Rationale:**", sop.get("rationale"))
                    with col2:
                        st.write("**Conflict Resolution Strategy:**", agent_result.get("resolution_rationale"))
                        if agent_result.get("secondary_sops"):
                            st.write(f"**Secondary SOPs ({len(agent_result['secondary_sops'])}):**")
                            for s in agent_result["secondary_sops"]:
                                st.write(f"- `{s['id']}`: {s['title']}")

    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "state_info": state_record
    })
    st.rerun()
