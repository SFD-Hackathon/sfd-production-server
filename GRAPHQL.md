# GraphQL API Documentation

The Drama API now supports **both REST and GraphQL** endpoints. GraphQL provides a flexible way to query exactly the data you need.

## GraphQL Endpoint

**Base URL:** `http://localhost:8000/graphql` (or your production URL)

**GraphQL Playground:** Navigate to `http://localhost:8000/graphql` in your browser to access the interactive GraphQL playground.

## Available Queries

### Get Drama by ID

```graphql
query {
  drama(id: "drama_123") {
    id
    title
    description
    premise
    url
    characters {
      id
      name
      description
      gender
      voiceDescription
      main
      url
    }
    episodes {
      id
      title
      description
      url
    }
  }
}
```

### Get All Dramas

```graphql
query {
  dramas {
    id
    title
    description
    url
    characters {
      name
      main
    }
    episodes {
      title
    }
  }
}
```

### Get Drama with Cover Photo

```graphql
query {
  drama(id: "drama_123") {
    id
    title
    coverPhoto
  }
}
```

## Available Mutations

### Generate Character Image

```graphql
mutation {
  generateCharacterImage(dramaId: "drama_123", characterId: "char_001") {
    id
    name
    url
  }
}
```

### Generate Cover Photo

```graphql
mutation {
  generateCoverPhoto(dramaId: "drama_123") {
    id
    title
    url
    characters {
      name
      url
    }
  }
}
```

## Example: Complete Workflow with GraphQL

### 1. Query a Drama

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ drama(id: \"drama_1jnx27h9azz7\") { id title url characters { id name main url } } }"
  }'
```

**Response:**
```json
{
  "data": {
    "drama": {
      "id": "drama_1jnx27h9azz7",
      "title": "The Price of Defiance",
      "url": "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/dramas/drama_1jnx27h9azz7/cover.png",
      "characters": [
        {
          "id": "char_elias_thorne",
          "name": "Elias Thorne",
          "main": true,
          "url": "https://..."
        }
      ]
    }
  }
}
```

### 2. Generate Character Image

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { generateCharacterImage(dramaId: \"drama_123\", characterId: \"char_001\") { id name url } }"
  }'
```

### 3. Generate Cover Photo

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { generateCoverPhoto(dramaId: \"drama_123\") { id url } }"
  }'
```

## GraphQL vs REST

### When to Use GraphQL

✅ **Use GraphQL when:**
- You need flexible querying (select only fields you need)
- You want to fetch related data in a single request
- You're building a frontend that needs various data shapes
- You want type safety and schema introspection

### When to Use REST

✅ **Use REST when:**
- You need simple, standardized CRUD operations
- You're working with existing REST-based tools
- You prefer URL-based caching
- You need file uploads (multipart/form-data)

## GraphQL Schema Types

### Drama
```graphql
type Drama {
  id: String!
  title: String!
  description: String!
  premise: String!
  url: String
  coverPhoto: String
  characters: [Character!]!
  episodes: [Episode!]!
}
```

### Character
```graphql
type Character {
  id: String!
  name: String!
  description: String!
  gender: String!
  voiceDescription: String!
  main: Boolean!
  url: String
}
```

### Episode
```graphql
type Episode {
  id: String!
  title: String!
  description: String!
  url: String
}
```

## Error Handling

GraphQL errors are returned in the `errors` array:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Drama must have at least one main character",
      "path": ["generateCoverPhoto"]
    }
  ]
}
```

## Interactive Playground

Visit `http://localhost:8000/graphql` in your browser to access the **GraphQL Playground** with:
- 🎯 Auto-completion
- 📖 Schema documentation
- 🔍 Query history
- ⚡ Real-time query execution

## Comparison: REST vs GraphQL

| Operation | REST | GraphQL |
|-----------|------|---------|
| Get drama with characters | `GET /dramas/drama_123` | `query { drama(id: "drama_123") { title characters { name } } }` |
| Get only drama title | Returns full object | `query { drama(id: "drama_123") { title } }` |
| Generate character image | `POST /dramas/{drama_id}/characters/{char_id}/generate` | `mutation { generateCharacterImage(...) { url } }` |
| Get cover photo | `GET /dramas/{drama_id}/cover_photo` | `query { coverPhoto(dramaId: "...") }` |

Both REST and GraphQL endpoints are fully supported and maintained. Choose the one that best fits your use case!
