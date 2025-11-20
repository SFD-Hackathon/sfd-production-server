"""
Tests for repository classes with Supabase integration.
"""

import pytest
import uuid
from datetime import datetime
from app.dal import get_supabase_client, DramaRepository, JobRepository, UserRepository
from app.models import Drama, Character, Episode, Scene

# Test user UUID (matches demo user in local Supabase)
TEST_USER_ID = "a1111111-1111-1111-1111-111111111111"


@pytest.fixture
def supabase_client():
    """Get Supabase client for tests."""
    return get_supabase_client()


@pytest.fixture
def drama_repo(supabase_client):
    """Get DramaRepository instance."""
    return DramaRepository(supabase_client)


@pytest.fixture
def job_repo(supabase_client):
    """Get JobRepository instance."""
    return JobRepository(supabase_client)


@pytest.fixture
def user_repo(supabase_client):
    """Get UserRepository instance."""
    return UserRepository(supabase_client)


@pytest.fixture
async def test_drama_id():
    """Generate unique test drama ID."""
    return f"test_drama_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def cleanup_test_dramas(drama_repo):
    """Clean up test dramas after tests."""
    created_drama_ids = []

    yield created_drama_ids

    # Cleanup
    for drama_id in created_drama_ids:
        try:
            await drama_repo.delete_drama_complete(drama_id)
        except Exception as e:
            print(f"Cleanup warning for {drama_id}: {e}")


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_get_user(self, user_repo):
        """Test getting user by ID."""
        user = await user_repo.get_user(TEST_USER_ID)
        assert user is not None
        assert user["id"] == TEST_USER_ID
        assert user["email"] == "demo@shortformdramas.com"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_repo):
        """Test getting non-existent user returns None."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        user = await user_repo.get_user(fake_uuid)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, user_repo):
        """Test getting user by email."""
        user = await user_repo.get_user_by_email("demo@shortformdramas.com")
        assert user is not None
        assert user["id"] == TEST_USER_ID
        assert user["email"] == "demo@shortformdramas.com"


class TestJobRepository:
    """Tests for JobRepository."""

    @pytest.mark.asyncio
    async def test_create_job(self, job_repo, drama_repo, test_drama_id):
        """Test creating a job."""
        # First create a drama (required by foreign key constraint)
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama for Job",
            description="Test description",
            premise="Test premise"
        )

        job_id = str(uuid.uuid4())
        job = await job_repo.create_job(
            user_id=TEST_USER_ID,
            drama_id=test_drama_id,
            job_id=job_id,
            job_type="generate_image",
            prompt="Test image generation"
        )

        assert job is not None
        assert job["job_id"] == job_id
        assert job["user_id"] == TEST_USER_ID
        assert job["drama_id"] == test_drama_id
        assert job["job_type"] == "generate_image"
        assert job["status"] == "pending"

        # Cleanup
        await job_repo.delete("job_id", job_id)
        await drama_repo.delete_drama_complete(test_drama_id)

    @pytest.mark.asyncio
    async def test_get_job_by_job_id(self, job_repo, drama_repo, test_drama_id):
        """Test getting job by job_id."""
        # Create drama first
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama",
            description="Test",
            premise="Test"
        )

        job_id = str(uuid.uuid4())

        # Create job
        created_job = await job_repo.create_job(
            user_id=TEST_USER_ID,
            drama_id=test_drama_id,
            job_id=job_id,
            job_type="generate_video"
        )

        # Get job
        job = await job_repo.get_job_by_job_id(job_id)
        assert job is not None
        assert job["job_id"] == job_id

        # Cleanup
        await job_repo.delete("job_id", job_id)
        await drama_repo.delete_drama_complete(test_drama_id)

    @pytest.mark.asyncio
    async def test_update_job_status(self, job_repo, drama_repo, test_drama_id):
        """Test updating job status."""
        # Create drama first
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama",
            description="Test",
            premise="Test"
        )

        job_id = str(uuid.uuid4())

        # Create job
        await job_repo.create_job(
            user_id=TEST_USER_ID,
            drama_id=test_drama_id,
            job_id=job_id,
            job_type="generate_image"
        )

        # Update status to processing
        updated_job = await job_repo.update_job_status(job_id, "processing")
        assert updated_job is not None
        assert updated_job["status"] == "processing"

        # Update status to completed
        updated_job = await job_repo.update_job_status(
            job_id,
            "completed",
            r2_url="https://example.com/result.png"
        )
        assert updated_job is not None
        assert updated_job["status"] == "completed"
        assert updated_job["r2_url"] == "https://example.com/result.png"

        # Cleanup
        await job_repo.delete("job_id", job_id)
        await drama_repo.delete_drama_complete(test_drama_id)

    @pytest.mark.asyncio
    async def test_hierarchical_job_creation(self, job_repo, drama_repo, test_drama_id):
        """Test creating parent and child jobs."""
        # Create drama first
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama",
            description="Test",
            premise="Test"
        )

        # Use actual UUIDs for job_ids
        parent_job_id = str(uuid.uuid4())
        child_job_id = str(uuid.uuid4())

        # Create parent job
        parent_job = await job_repo.create_job(
            user_id=TEST_USER_ID,
            drama_id=test_drama_id,
            job_id=parent_job_id,
            job_type="generate_drama",
            total_jobs=1
        )
        assert parent_job is not None

        # Create child job - parent_job_id references the UUID 'id' column, not 'job_id'
        child_job = await job_repo.create_job(
            user_id=TEST_USER_ID,
            drama_id=test_drama_id,
            job_id=child_job_id,
            job_type="generate_image",
            parent_job_id=parent_job["id"]  # Use the UUID id, not job_id
        )
        assert child_job is not None
        assert child_job["parent_job_id"] == parent_job["id"]

        # Get child jobs - uses the parent's UUID id
        children = await job_repo.get_child_jobs(parent_job["id"])
        assert len(children) >= 1
        assert any(j["job_id"] == child_job_id for j in children)

        # Cleanup
        await job_repo.delete("job_id", child_job_id)
        await job_repo.delete("job_id", parent_job_id)
        await drama_repo.delete_drama_complete(test_drama_id)


class TestDramaRepository:
    """Tests for DramaRepository."""

    @pytest.mark.asyncio
    async def test_create_drama(self, drama_repo, test_drama_id, cleanup_test_dramas):
        """Test creating a drama."""
        drama = await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama",
            description="A test drama for unit testing",
            premise="Test premise"
        )

        assert drama is not None
        assert drama["id"] == test_drama_id
        assert drama["title"] == "Test Drama"
        assert drama["user_id"] == TEST_USER_ID

        cleanup_test_dramas.append(test_drama_id)

    @pytest.mark.asyncio
    async def test_get_drama(self, drama_repo, test_drama_id, cleanup_test_dramas):
        """Test getting drama by ID."""
        # Create drama
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Test Drama",
            description="Test description",
            premise="Test premise"
        )
        cleanup_test_dramas.append(test_drama_id)

        # Get drama
        drama = await drama_repo.get_drama(test_drama_id)
        assert drama is not None
        assert drama["id"] == test_drama_id

    @pytest.mark.asyncio
    async def test_get_drama_complete_with_nested_data(self, drama_repo, test_drama_id, cleanup_test_dramas):
        """Test getting complete drama with nested characters and episodes."""
        # Create drama with nested data
        drama_model = Drama(
            id=test_drama_id,
            title="Complete Test Drama",
            description="Drama with nested data",
            premise="Test premise",
            characters=[
                Character(
                    id=f"char_{uuid.uuid4().hex[:8]}",
                    name="Test Character",
                    description="A test character",
                    gender="male",
                    voice_description="Deep voice",
                    main=True
                )
            ],
            episodes=[
                Episode(
                    id=f"ep_{uuid.uuid4().hex[:8]}",
                    title="Episode 1",
                    description="First episode",
                    scenes=[
                        Scene(
                            id=f"scene_{uuid.uuid4().hex[:8]}",
                            description="Opening scene"
                        )
                    ]
                )
            ]
        )

        # Save complete drama
        saved = await drama_repo.save_drama_complete(drama_model, TEST_USER_ID)
        assert saved is not None
        cleanup_test_dramas.append(test_drama_id)

        # Get complete drama
        retrieved = await drama_repo.get_drama_complete(test_drama_id)
        assert retrieved is not None
        assert retrieved.id == test_drama_id
        assert len(retrieved.characters) == 1
        assert retrieved.characters[0].name == "Test Character"
        assert len(retrieved.episodes) == 1
        assert retrieved.episodes[0].title == "Episode 1"
        assert len(retrieved.episodes[0].scenes) == 1

    @pytest.mark.asyncio
    async def test_get_user_dramas(self, drama_repo, test_drama_id, cleanup_test_dramas):
        """Test getting all dramas for a user."""
        # Create test drama
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="User Test Drama",
            description="Test description",
            premise="Test premise"
        )
        cleanup_test_dramas.append(test_drama_id)

        # Get user dramas
        dramas = await drama_repo.get_user_dramas(TEST_USER_ID, limit=10)
        assert isinstance(dramas, list)
        assert any(d["id"] == test_drama_id for d in dramas)

    @pytest.mark.asyncio
    async def test_update_drama_status(self, drama_repo, test_drama_id, cleanup_test_dramas):
        """Test updating drama status."""
        # Create drama
        await drama_repo.create_drama(
            drama_id=test_drama_id,
            user_id=TEST_USER_ID,
            title="Status Test Drama",
            description="Test description",
            premise="Test premise",
            status="pending"
        )
        cleanup_test_dramas.append(test_drama_id)

        # Update status
        updated = await drama_repo.update_drama_status(test_drama_id, "completed")
        assert updated is not None
        assert updated["status"] == "completed"

    @pytest.mark.asyncio
    async def test_delete_drama_complete(self, drama_repo, test_drama_id):
        """Test deleting drama and all related data."""
        # Create drama with nested data
        drama_model = Drama(
            id=test_drama_id,
            title="Delete Test Drama",
            description="Will be deleted",
            premise="Test premise",
            characters=[
                Character(
                    id=f"char_{uuid.uuid4().hex[:8]}",
                    name="Character to delete",
                    description="Test",
                    gender="female",
                    voice_description="Test",
                    main=False
                )
            ],
            episodes=[]
        )

        # Save drama
        await drama_repo.save_drama_complete(drama_model, TEST_USER_ID)

        # Verify it exists
        drama = await drama_repo.get_drama(test_drama_id)
        assert drama is not None

        # Delete drama
        deleted = await drama_repo.delete_drama_complete(test_drama_id)
        assert deleted is True

        # Verify it's gone
        drama = await drama_repo.get_drama(test_drama_id)
        assert drama is None


class TestRepositoryEdgeCases:
    """Tests for repository edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_drama(self, drama_repo):
        """Test getting non-existent drama returns None."""
        drama = await drama_repo.get_drama("nonexistent_drama_id")
        assert drama is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, job_repo):
        """Test getting non-existent job returns None."""
        job = await job_repo.get_job_by_job_id("nonexistent_job_id")
        assert job is None

    @pytest.mark.asyncio
    async def test_empty_user_dramas(self, drama_repo):
        """Test getting dramas for user with no dramas."""
        fake_user_id = "00000000-0000-0000-0000-000000000099"
        dramas = await drama_repo.get_user_dramas(fake_user_id)
        assert isinstance(dramas, list)
        assert len(dramas) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
