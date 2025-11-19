"""Asset gallery viewer component"""
import streamlit as st
from typing import Dict, Any, List


def render_asset_card(asset: Dict[str, Any]):
    """Render a single asset card"""
    with st.container():
        # Asset preview
        if asset.get("public_url"):
            asset_type = asset.get("asset_type", "").lower()
            if asset_type == "image":
                st.image(asset["public_url"], use_container_width=True)
            elif asset_type == "video":
                st.video(asset["public_url"])
            else:
                st.write(f"[Download]({asset['public_url']})")

        # Metadata
        st.caption(f"**{asset.get('tag', 'unknown')}** - {asset.get('filename', 'N/A')}")
        st.caption(f"Size: {asset.get('size_bytes', 0) / 1024:.1f} KB")
        if asset.get("created_at"):
            st.caption(f"Created: {asset['created_at'][:19]}")

        # Show details
        with st.expander("Details"):
            st.json(asset)


def render_asset_gallery(drama: Dict[str, Any], client):
    """Render asset gallery for a drama"""
    st.header("Asset Gallery")

    try:
        # Fetch assets from asset library
        assets = client.list_assets(
            user_id="10000",
            project_name=drama["id"]
        )

        if not assets:
            st.info("No assets generated yet for this drama")
            return

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            asset_types = ["All"] + list(set(a.get("asset_type", "unknown") for a in assets))
            selected_type = st.selectbox("Filter by Type", asset_types)

        with col2:
            tags = ["All"] + list(set(a.get("tag", "unknown") for a in assets))
            selected_tag = st.selectbox("Filter by Tag", tags)

        # Filter assets
        filtered_assets = assets
        if selected_type != "All":
            filtered_assets = [a for a in filtered_assets if a.get("asset_type") == selected_type]
        if selected_tag != "All":
            filtered_assets = [a for a in filtered_assets if a.get("tag") == selected_tag]

        st.write(f"Showing {len(filtered_assets)} of {len(assets)} assets")

        # Display assets in grid
        cols_per_row = 3
        for i in range(0, len(filtered_assets), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(filtered_assets):
                    with col:
                        render_asset_card(filtered_assets[idx])

    except Exception as e:
        st.error(f"Failed to load assets: {str(e)}")


def render_jobs_section(drama: Dict[str, Any], client):
    """Render jobs/generation history"""
    st.header("Generation Jobs")

    try:
        jobs = client.list_jobs(drama["id"])

        if not jobs:
            st.info("No generation jobs found for this drama")
            return

        # Filter by status
        statuses = ["All"] + list(set(j.get("status", "unknown") for j in jobs))
        selected_status = st.selectbox("Filter by Status", statuses, key="job_status_filter")

        filtered_jobs = jobs
        if selected_status != "All":
            filtered_jobs = [j for j in jobs if j.get("status") == selected_status]

        st.write(f"Showing {len(filtered_jobs)} of {len(jobs)} jobs")

        # Display jobs
        for job in filtered_jobs:
            with st.expander(
                f"{job.get('job_type', 'unknown').upper()} - {job.get('status', 'unknown')} - {job.get('job_id', 'N/A')[:12]}...",
                expanded=False
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Job ID:** {job.get('job_id', 'N/A')}")
                    st.write(f"**Type:** {job.get('job_type', 'N/A')}")
                    st.write(f"**Status:** {job.get('status', 'N/A')}")
                    if job.get("asset_id"):
                        st.write(f"**Asset ID:** {job['asset_id']}")

                with col2:
                    if job.get("created_at"):
                        st.write(f"**Created:** {job['created_at'][:19]}")
                    if job.get("completed_at"):
                        st.write(f"**Completed:** {job['completed_at'][:19]}")
                    if job.get("error"):
                        st.error(f"Error: {job['error']}")

                # Show result
                if job.get("r2_url"):
                    st.write(f"**Result URL:** {job['r2_url']}")
                    asset_type = job.get("job_type", "").lower()
                    if asset_type == "image":
                        st.image(job["r2_url"], use_container_width=True)
                    elif asset_type == "video":
                        st.video(job["r2_url"])

                # Show child jobs if parent
                if job.get("total_child_jobs", 0) > 0:
                    st.write(f"**Child Jobs:** {job.get('completed_child_jobs', 0)}/{job.get('total_child_jobs', 0)} completed")

                # Prompt
                if job.get("prompt"):
                    with st.expander("Prompt"):
                        st.text(job["prompt"])

                # Raw JSON
                with st.expander("Raw Job JSON"):
                    st.json(job)

    except Exception as e:
        st.error(f"Failed to load jobs: {str(e)}")
