"""Drama JSON Viewer - Streamlit debugging interface

Usage:
    streamlit run viewer/app.py
"""
import streamlit as st
from utils import get_client
from components.character_view import render_characters_section
from components.episode_view import render_episodes_section
from components.asset_view import render_asset_gallery, render_jobs_section

# Page config
st.set_page_config(
    page_title="Drama JSON Viewer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
    .drama-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 8px;
        color: white;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


def render_drama_header(drama: dict):
    """Render drama header with key info"""
    st.markdown(f"""
    <div class="drama-header">
        <h1>🎬 {drama.get('title', 'Untitled Drama')}</h1>
        <p><strong>Genre:</strong> {drama.get('genre', 'N/A')} | <strong>ID:</strong> {drama.get('id', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)


def render_drama_overview(drama: dict):
    """Render drama overview section"""
    st.header("Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Episodes", len(drama.get("episodes", [])))
    with col2:
        st.metric("Characters", len(drama.get("characters", [])))
    with col3:
        total_scenes = sum(len(ep.get("scenes", [])) for ep in drama.get("episodes", []))
        st.metric("Total Scenes", total_scenes)
    with col4:
        if drama.get("targetAudience"):
            st.metric("Target Audience", drama["targetAudience"])

    # Premise
    if drama.get("premise"):
        with st.expander("Premise", expanded=True):
            st.write(drama["premise"])

    # Themes
    if drama.get("themes"):
        st.write("**Themes:**", ", ".join(drama["themes"]))

    # Cover photo
    if drama.get("coverPhotoUrl"):
        st.image(drama["coverPhotoUrl"], caption="Cover Photo", use_container_width=True)


def render_actions_sidebar(drama: dict, client):
    """Render action buttons in sidebar"""
    st.sidebar.header("Actions")

    # Generate full drama
    if st.sidebar.button("🎬 Generate Full Drama", use_container_width=True):
        with st.spinner("Starting full drama generation..."):
            try:
                result = client.generate_full_drama(drama["id"])
                st.sidebar.success(f"Job created: {result.get('jobId')}")
                st.sidebar.info(f"Poll status: GET /dramas/{drama['id']}/jobs/{result.get('jobId')}")
            except Exception as e:
                st.sidebar.error(f"Failed: {str(e)}")

    # Improve drama
    with st.sidebar.expander("💡 Improve Drama"):
        feedback = st.text_area("Feedback", placeholder="Enter improvement suggestions...")
        if st.button("Submit Improvement", use_container_width=True):
            if feedback:
                with st.spinner("Improving drama..."):
                    try:
                        result = client.improve_drama(drama["id"], feedback)
                        st.success(f"Job created: {result.get('jobId')}")
                    except Exception as e:
                        st.error(f"Failed: {str(e)}")
            else:
                st.warning("Please enter feedback")

    # Critique drama
    if st.sidebar.button("📝 Get AI Critique", use_container_width=True):
        with st.spinner("Getting critique..."):
            try:
                result = client.critique_drama(drama["id"])
                st.sidebar.success(f"Job created: {result.get('jobId')}")
            except Exception as e:
                st.sidebar.error(f"Failed: {str(e)}")

    # Delete drama
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚠️ Danger Zone"):
        st.warning("This will delete the drama and all associated assets")
        if st.button("Delete Drama", type="secondary", use_container_width=True):
            try:
                client.delete_drama(drama["id"])
                st.success("Drama deleted successfully")
                st.session_state.pop("drama_id", None)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete: {str(e)}")


def main():
    """Main application"""
    st.title("🎬 Drama JSON Viewer")

    # Initialize API client
    try:
        client = get_client()
    except Exception as e:
        st.error(f"Failed to initialize API client: {str(e)}")
        st.info("Make sure the API server is running at http://localhost:8000")
        return

    # Sidebar - Drama selection
    st.sidebar.header("Select Drama")

    # Drama ID input
    drama_id = st.sidebar.text_input(
        "Drama ID",
        value=st.session_state.get("drama_id", ""),
        placeholder="Enter drama ID..."
    )

    # Or browse dramas
    with st.sidebar.expander("Browse Dramas"):
        try:
            dramas = client.list_dramas(skip=0, limit=20)
            if dramas:
                drama_options = {f"{d.get('title', 'Untitled')} ({d.get('id', 'N/A')[:12]}...)": d.get('id') for d in dramas}
                selected = st.selectbox("Select from list", options=list(drama_options.keys()))
                if st.button("Load Selected", use_container_width=True):
                    drama_id = drama_options[selected]
                    st.session_state["drama_id"] = drama_id
                    st.rerun()
            else:
                st.info("No dramas found")
        except Exception as e:
            st.error(f"Failed to load dramas: {str(e)}")

    # Load drama
    if not drama_id:
        st.info("👈 Enter a Drama ID in the sidebar to get started")
        st.markdown("---")
        st.markdown("### Quick Start")
        st.markdown("1. Make sure the API server is running: `python main.py`")
        st.markdown("2. Enter a drama ID in the sidebar")
        st.markdown("3. Or create a new drama: `POST /dramas` with a premise")
        return

    # Save drama ID to session
    st.session_state["drama_id"] = drama_id

    # Fetch drama
    try:
        with st.spinner("Loading drama..."):
            drama = client.get_drama(drama_id)
    except Exception as e:
        st.error(f"Failed to load drama: {str(e)}")
        st.info("Make sure the drama ID is correct and the API server is running")
        return

    # Render drama header
    render_drama_header(drama)

    # Render action buttons in sidebar
    render_actions_sidebar(drama, client)

    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Overview",
        "👥 Characters",
        "🎞️ Episodes",
        "🖼️ Assets",
        "⚙️ Jobs"
    ])

    with tab1:
        render_drama_overview(drama)

        # Raw JSON
        with st.expander("Raw Drama JSON"):
            st.json(drama)

    with tab2:
        render_characters_section(drama, client)

    with tab3:
        render_episodes_section(drama)

    with tab4:
        render_asset_gallery(drama, client)

    with tab5:
        render_jobs_section(drama, client)

    # Auto-refresh option
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)")
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
