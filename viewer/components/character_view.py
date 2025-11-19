"""Character viewer component"""
import streamlit as st
from typing import Dict, Any


def render_character(character: Dict[str, Any], drama_id: str, client):
    """Render a single character card"""
    with st.container():
        col1, col2 = st.columns([1, 2])

        with col1:
            # Display portrait if available (check both 'url' and 'portraitUrl' fields)
            portrait_url = character.get("url") or character.get("portraitUrl")
            if portrait_url:
                st.image(portrait_url, use_container_width=True)
            else:
                st.info("No portrait generated yet")

                # Add generate button
                if st.button(f"Generate Portrait", key=f"gen_char_{character['id']}"):
                    with st.spinner("Generating portrait..."):
                        try:
                            result = client.generate_character(drama_id, character["id"])
                            st.success(f"Job created: {result.get('jobId')}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to generate: {str(e)}")

        with col2:
            st.subheader(character.get("name", "Unnamed Character"))

            # Description (show prominently)
            if character.get("description"):
                st.write(character["description"])
                st.markdown("---")

            # Character details
            if character.get("gender"):
                st.write(f"**Gender:** {character['gender'].title()}")
            if character.get("age"):
                st.write(f"**Age:** {character['age']}")
            if character.get("occupation"):
                st.write(f"**Occupation:** {character['occupation']}")
            if character.get("personality"):
                st.write(f"**Personality:** {character['personality']}")
            if character.get("voice_description"):
                with st.expander("Voice Description"):
                    st.write(character["voice_description"])

            # Show raw JSON
            with st.expander("Raw JSON"):
                st.json(character)


def render_characters_section(drama: Dict[str, Any], client):
    """Render all characters section"""
    st.header("Characters")

    characters = drama.get("characters", [])

    if not characters:
        st.warning("No characters found in this drama")
        return

    st.write(f"Total characters: {len(characters)}")

    # Display characters
    for idx, character in enumerate(characters):
        st.markdown("---")
        render_character(character, drama["id"], client)
