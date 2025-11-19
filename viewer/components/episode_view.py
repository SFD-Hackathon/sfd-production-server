"""Episode and scene viewer components"""
import streamlit as st
from typing import Dict, Any, List


def render_scene(scene: Dict[str, Any], episode_id: str, drama_id: str):
    """Render a single scene"""
    with st.container():
        st.markdown(f"### Scene {scene.get('sceneNumber', 'N/A')}")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Scene details
            if scene.get("location"):
                st.write(f"**Location:** {scene['location']}")
            if scene.get("timeOfDay"):
                st.write(f"**Time:** {scene['timeOfDay']}")
            if scene.get("description"):
                st.write(f"**Description:** {scene['description']}")

            # Characters in scene
            if scene.get("characters"):
                char_names = ", ".join(scene["characters"])
                st.write(f"**Characters:** {char_names}")

            # Dialogue
            if scene.get("dialogue"):
                with st.expander("Dialogue"):
                    for line in scene["dialogue"]:
                        character = line.get("character", "Unknown")
                        text = line.get("text", "")
                        st.markdown(f"**{character}:** {text}")

        with col2:
            # Storyboard
            if scene.get("storyboardUrl"):
                st.image(scene["storyboardUrl"], caption="Storyboard", use_container_width=True)

            # Video clip
            if scene.get("videoClipUrl"):
                st.video(scene["videoClipUrl"])

        # Assets
        if scene.get("assets"):
            with st.expander(f"Assets ({len(scene['assets'])})"):
                for asset in scene["assets"]:
                    render_asset(asset)

        # Raw JSON
        with st.expander("Raw Scene JSON"):
            st.json(scene)


def render_asset(asset: Dict[str, Any]):
    """Render a single asset"""
    st.markdown(f"**{asset.get('type', 'Unknown Type')}** - {asset.get('description', 'No description')}")
    if asset.get("url"):
        asset_type = asset.get("type", "").lower()
        if "image" in asset_type or "storyboard" in asset_type:
            st.image(asset["url"], use_container_width=True)
        elif "video" in asset_type or "clip" in asset_type:
            st.video(asset["url"])
        else:
            st.write(f"[Download Asset]({asset['url']})")


def render_episode(episode: Dict[str, Any], drama_id: str):
    """Render a single episode"""
    # Get episode number - could be in episodeNumber or episode_number
    ep_num = episode.get('episodeNumber') or episode.get('episode_number') or 'N/A'
    with st.expander(f"Episode {ep_num}: {episode.get('title', 'Untitled')}", expanded=False):
        # Episode metadata
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Episode ID:** {episode.get('id', 'N/A')}")
            st.write(f"**Title:** {episode.get('title', 'Untitled')}")
        with col2:
            if episode.get("duration"):
                st.write(f"**Duration:** {episode['duration']}")
            scenes_count = len(episode.get("scenes", []))
            st.write(f"**Scenes:** {scenes_count}")

        # Description/Synopsis (check both fields)
        description = episode.get("description") or episode.get("synopsis")
        if description:
            st.markdown("**Description:**")
            st.write(description)
            st.markdown("---")

        # Scenes
        scenes = episode.get("scenes", [])
        if scenes:
            st.markdown("---")
            st.markdown("#### Scenes")
            for scene in scenes:
                st.markdown("---")
                render_scene(scene, episode["id"], drama_id)
        else:
            st.info("No scenes in this episode")

        # Raw JSON
        with st.expander("Raw Episode JSON"):
            st.json(episode)


def render_episodes_section(drama: Dict[str, Any]):
    """Render all episodes section"""
    st.header("Episodes")

    episodes = drama.get("episodes", [])

    if not episodes:
        st.warning("No episodes found in this drama")
        return

    st.write(f"Total episodes: {len(episodes)}")

    # Display episodes
    for episode in episodes:
        render_episode(episode, drama["id"])
