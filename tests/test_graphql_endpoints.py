"""
Tests for GraphQL endpoints with Supabase integration.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.dal import get_supabase_client, DramaRepository
import uuid

# Test client
client = TestClient(app)

# Test user UUID (matches demo user in local Supabase)
TEST_USER_ID = "a1111111-1111-1111-1111-111111111111"


@pytest.fixture
async def cleanup_test_data():
    """Clean up test data after tests."""
    yield
    # Cleanup test dramas
    supabase = get_supabase_client()
    try:
        # Delete all test dramas (those created during tests)
        supabase.table("dramas").delete().ilike("title", "%Test Drama%").execute()
    except Exception as e:
        print(f"Cleanup warning: {e}")


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health check returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data


class TestGraphQLQueries:
    """Tests for GraphQL query endpoints."""

    def test_drama_summaries_empty(self):
        """Test drama summaries query returns empty list initially."""
        query = """
        {
            dramaSummaries(limit: 10) {
                id
                title
                description
                premise
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "dramaSummaries" in data["data"]
        assert isinstance(data["data"]["dramaSummaries"], list)

    def test_drama_summaries_with_user_filter(self):
        """Test drama summaries with user filter."""
        query = """
        query GetDramas($userId: String) {
            dramaSummaries(limit: 10, userId: $userId) {
                id
                title
                description
            }
        }
        """
        variables = {"userId": TEST_USER_ID}
        response = client.post("/graphql", json={"query": query, "variables": variables})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "dramaSummaries" in data["data"]

    def test_dramas_query_with_pagination(self):
        """Test dramas query with pagination."""
        query = """
        query GetDramas($limit: Int, $offset: Int) {
            dramas(limit: $limit, offset: $offset) {
                id
                title
                description
                characters {
                    id
                    name
                }
                episodes {
                    id
                    title
                }
            }
        }
        """
        variables = {"limit": 5, "offset": 0}
        response = client.post("/graphql", json={"query": query, "variables": variables})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "dramas" in data["data"]

    def test_single_drama_query_not_found(self):
        """Test querying a non-existent drama returns None."""
        query = """
        query GetDrama($id: String!) {
            drama(id: $id) {
                id
                title
            }
        }
        """
        variables = {"id": "non-existent-drama-id"}
        response = client.post("/graphql", json={"query": query, "variables": variables})
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["drama"] is None


class TestGraphQLMutations:
    """Tests for GraphQL mutation endpoints."""

    @pytest.mark.asyncio
    async def test_generate_character_image_drama_not_found(self):
        """Test generate character image fails gracefully when drama doesn't exist."""
        mutation = """
        mutation GenerateCharacterImage($dramaId: String!, $characterId: String!) {
            generateCharacterImage(dramaId: $dramaId, characterId: $characterId) {
                id
                name
                url
            }
        }
        """
        variables = {
            "dramaId": "non-existent-drama",
            "characterId": "non-existent-character"
        }
        response = client.post("/graphql", json={"query": mutation, "variables": variables})
        assert response.status_code == 200
        data = response.json()
        # Should return None when drama not found
        assert data["data"]["generateCharacterImage"] is None

    @pytest.mark.asyncio
    async def test_generate_cover_photo_drama_not_found(self):
        """Test generate cover photo fails gracefully when drama doesn't exist."""
        mutation = """
        mutation GenerateCoverPhoto($dramaId: String!) {
            generateCoverPhoto(dramaId: $dramaId) {
                id
                title
                url
            }
        }
        """
        variables = {"dramaId": "non-existent-drama"}
        response = client.post("/graphql", json={"query": mutation, "variables": variables})
        assert response.status_code == 200
        data = response.json()
        # Should return None when drama not found
        assert data["data"]["generateCoverPhoto"] is None


class TestGraphQLSchema:
    """Tests for GraphQL schema introspection."""

    def test_schema_introspection(self):
        """Test GraphQL schema introspection works."""
        query = """
        {
            __schema {
                queryType {
                    name
                }
                mutationType {
                    name
                }
                types {
                    name
                }
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "__schema" in data["data"]
        assert data["data"]["__schema"]["queryType"]["name"] == "Query"
        assert data["data"]["__schema"]["mutationType"]["name"] == "Mutation"

    def test_query_type_fields(self):
        """Test Query type has expected fields."""
        query = """
        {
            __type(name: "Query") {
                name
                fields {
                    name
                    type {
                        name
                    }
                }
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        fields = data["data"]["__type"]["fields"]
        field_names = [f["name"] for f in fields]

        # Check expected query fields exist
        assert "drama" in field_names
        assert "dramas" in field_names
        assert "dramaSummaries" in field_names

    def test_mutation_type_fields(self):
        """Test Mutation type has expected fields."""
        query = """
        {
            __type(name: "Mutation") {
                name
                fields {
                    name
                }
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        fields = data["data"]["__type"]["fields"]
        field_names = [f["name"] for f in fields]

        # Check expected mutation fields exist
        assert "generateCharacterImage" in field_names
        assert "generateCoverPhoto" in field_names


class TestErrorHandling:
    """Tests for GraphQL error handling."""

    def test_invalid_graphql_query(self):
        """Test invalid GraphQL query returns error."""
        query = """
        {
            invalidField {
                id
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data

    def test_missing_required_argument(self):
        """Test missing required argument returns error."""
        query = """
        query GetDrama {
            drama {
                id
                title
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data

    def test_malformed_json(self):
        """Test malformed JSON returns error."""
        response = client.post(
            "/graphql",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
