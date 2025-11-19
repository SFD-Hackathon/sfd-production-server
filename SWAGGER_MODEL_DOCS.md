# Swagger UI Model Selection Documentation

This document shows how the model parameter appears in Swagger UI after the updates.

## Updated Endpoints with Model Selection

### 1. POST /dramas (Create Drama)

**Request Body Schema (JSON Mode):**
```json
{
  "premise": "string",
  "id": "string (optional)",
  "model": "gemini-3-pro-preview (default)"
}
```

**Model Field Documentation:**
- **Type**: string
- **Default**: `gemini-3-pro-preview`
- **Description**: AI model to use for drama generation. Options: 'gemini-3-pro-preview' (default, Google Gemini 3 Pro Preview) or 'gpt-5.1' (OpenAI GPT-5.1)
- **Examples**:
  - `gemini-3-pro-preview`
  - `gpt-5.1`

**Endpoint Description:**
```
Create a new drama (supports three modes).

Mode 1 (Async - JSON): Send JSON with "premise" field → AI generates drama + character images + cover image → Returns job ID (202)
Mode 2 (Async - Multipart): Send form data with "premise" + optional "reference_image" file → AI generates drama using reference → Returns job ID (202)
Mode 3 (Sync): Send JSON with "drama" field → Saves drama as-is → Returns drama object (201)

Mode 1 & 2 generate: ✅ Drama structure, ✅ Character portraits, ✅ Cover image
Mode 1 & 2 do NOT generate: ❌ Scene assets (use POST /dramas/{id}/generate)

AI Model Selection (Mode 1 & 2):
- Default: gemini-3-pro-preview (Google Gemini 3 Pro Preview) - High-quality, fast, cost-effective
- Alternative: gpt-5.1 (OpenAI GPT-5.1) - Available for comparison
- Specify using "model" field in JSON or form data
- If not specified, defaults to Gemini 3 Pro Preview
```

---

### 2. POST /dramas/{drama_id}/improve (Improve Drama)

**Request Body Schema:**
```json
{
  "feedback": "string (required)",
  "newDramaId": "string (optional)",
  "model": "gemini-3-pro-preview (default)"
}
```

**Model Field Documentation:**
- **Type**: string
- **Default**: `gemini-3-pro-preview`
- **Description**: AI model to use for drama improvement. Options: 'gemini-3-pro-preview' (default, Google Gemini 3 Pro Preview) or 'gpt-5.1' (OpenAI GPT-5.1)
- **Examples**:
  - `gemini-3-pro-preview`
  - `gpt-5.1`

**Endpoint Description:**
```
Improve drama with feedback

Queue an async job to improve an existing drama based on feedback.
The selected AI model will regenerate the drama incorporating your feedback.
Creates a new improved version with a new ID.

AI Model Selection:
- Default: gemini-3-pro-preview (Google Gemini 3 Pro Preview)
- Alternative: gpt-5.1 (OpenAI GPT-5.1)
- Specify using "model" field in request body
- If not specified, defaults to Gemini 3 Pro Preview
```

---

### 3. POST /dramas/{drama_id}/critic (Critique Drama)

**Request Body Schema:**
```json
{
  "model": "gemini-3-pro-preview (default)"
}
```

**Model Field Documentation:**
- **Type**: string
- **Default**: `gemini-3-pro-preview`
- **Description**: AI model to use for drama critique. Options: 'gemini-3-pro-preview' (default, Google Gemini 3 Pro Preview) or 'gpt-5.1' (OpenAI GPT-5.1)
- **Examples**:
  - `gemini-3-pro-preview`
  - `gpt-5.1`

**Endpoint Description:**
```
Get AI-powered critical feedback on a drama script

Queue an async job to get expert critical analysis of the drama's storytelling,
character development, pacing, dialogue, and overall narrative quality.

The critique focuses on:
- Story structure and pacing
- Character development and consistency
- Dialogue quality and authenticity
- Emotional impact and engagement
- Scene composition and flow
- Overall narrative coherence

AI Model Selection:
- Default: gemini-3-pro-preview (Google Gemini 3 Pro Preview) - High-quality critique analysis
- Alternative: gpt-5.1 (OpenAI GPT-5.1)
- Specify using "model" field in request body
- If not specified, defaults to Gemini 3 Pro Preview

Returns immediately with a job ID. Use the job status endpoint to retrieve
the critique feedback once the job completes.
```

---

## How It Appears in Swagger UI

### Dropdown/Select Behavior
In Swagger UI, the `model` field will appear as a text input field with:
- **Default value pre-filled**: `gemini-3-pro-preview`
- **Placeholder showing**: Example values
- **Detailed description**: Explaining both options

### Try It Out Example

**Example Request Body (Create Drama):**
```json
{
  "premise": "A detective discovers their AI assistant has become sentient and is secretly helping them solve crimes",
  "model": "gemini-3-pro-preview"
}
```

**To use GPT-5.1 instead:**
```json
{
  "premise": "A detective discovers their AI assistant has become sentient and is secretly helping them solve crimes",
  "model": "gpt-5.1"
}
```

**To use default (omit model field):**
```json
{
  "premise": "A detective discovers their AI assistant has become sentient and is secretly helping them solve crimes"
}
```
This will automatically use `gemini-3-pro-preview`.

---

## Key Highlights in Swagger UI

✅ **Clear Default**: Every endpoint clearly shows `gemini-3-pro-preview` as the default
✅ **Example Values**: Both model options are listed as examples
✅ **Detailed Descriptions**: Full explanation of each model option
✅ **Emphasized in Docs**: Each endpoint description explicitly mentions model selection
✅ **User-Friendly**: Users can simply omit the field to use the recommended default

---

## Testing the Updated UI

1. Start the server: `python main.py`
2. Open Swagger UI: http://localhost:8000/docs
3. Navigate to any of these endpoints:
   - `POST /dramas`
   - `POST /dramas/{drama_id}/improve`
   - `POST /dramas/{drama_id}/critic`
4. Click "Try it out"
5. See the `model` field with default value `gemini-3-pro-preview`
6. See the detailed description explaining both options
