# Test Suite

Test suite for SFD Production Server drama generation API.

## Test Files

### 1. `test_api.py`
Simple API endpoint tests for basic functionality.

**Tests:**
- Health endpoint
- Drama creation from premise
- Job status polling
- Get drama by ID
- List dramas

**Run:**
```bash
python tests/test_api.py
```

### 2. `test_generation.py`
Comprehensive generation tests from asset-level to drama-level.

**Tests:**
- Health check
- Character audition video generation
- Episode asset generation
- Full drama generation with hierarchical DAG

**Run:**
```bash
python tests/test_generation.py
```

### 3. `test_drama_create.py`
Tests for POST /dramas endpoint with single character.

**Tests:**
- Create drama from premise (async mode) with single character
- Create drama from JSON (sync mode) with single character
- Verify character image generation
- Verify drama cover image generation

**Run:**
```bash
python tests/test_drama_create.py
```

## Test Assets

### `cartoon_boy_character.jpg`
Reference image for character generation tests (101 KB).

## Prerequisites

1. **Server Running:**
   ```bash
   python main.py
   # Or
   uvicorn main:app --reload
   ```

2. **Environment Variables:**
   ```bash
   # Required in .env
   OPENAI_API_KEY=your_openai_api_key
   GEMINI_API_KEY=your_gemini_api_key
   SORA_API_KEY=your_sora_api_key
   R2_ACCOUNT_ID=your_r2_account_id
   R2_ACCESS_KEY_ID=your_r2_access_key_id
   R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
   R2_BUCKET=sfd-production
   R2_PUBLIC_URL=https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev
   ```

3. **Dependencies:**
   ```bash
   pip install -r test-requirements.txt
   ```

## Running All Tests

```bash
# Run individual test files
python tests/test_api.py
python tests/test_drama_create.py
python tests/test_generation.py

# Or use pytest (if installed)
pytest tests/ -v
```

## Test Configuration

### Base URL
Default: `http://localhost:8000`

Override with environment variable:
```bash
export API_BASE_URL=https://api.shortformdramas.com
python tests/test_api.py
```

### Timeouts
- Character generation: ~30-60 seconds
- Episode generation: ~2-5 minutes
- Full drama generation: ~5-15 minutes

## Expected Output

### Success
```
==================================================
POST /dramas Test Suite - Single Character
==================================================

🏥 Testing health endpoint...
✅ Server is running

--------------------------------------------------
🎭 Testing POST /dramas (sync mode) with single character JSON...
Status: 201
Response summary:
   ID: test_drama_json_1700000000
   Title: The Boy Detective
   Characters: 1
   Episodes: 1

✅ Test passed: Drama created from JSON with single character

--------------------------------------------------

--------------------------------------------------
🎭 Testing POST /dramas (async mode) with single character...
Status: 202
Response: {
  "dramaId": "test_drama_single_char_1700000000",
  "jobId": "job_abc123",
  "status": "pending"
}

✅ Drama creation queued successfully
   Drama ID: test_drama_single_char_1700000000
   Job ID: job_abc123

⏳ Waiting for drama generation to complete...
   Attempt 1/60: Status = processing
   Attempt 2/60: Status = processing
   Attempt 3/60: Status = completed
✅ Drama generation completed!

📖 Retrieving generated drama...
   Title: The Young Detective
   Characters: 1
   Episodes: 1

   Character: Alex Chen
   Description: A brilliant young detective with a keen eye for detail...
   Image URL: https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/...
   ✅ Character image generated
   Drama Cover URL: https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/...
   ✅ Drama cover image generated

✅ Test passed: Drama created with single character from premise

--------------------------------------------------

==================================================
✅ All tests passed!
==================================================
```

### Failure
```
❌ Test failed: Expected 201 Created, got 500
❌ Unexpected error: Connection refused
```

## Troubleshooting

### Server Not Running
```
❌ Health check failed. Is the server running?
```
**Solution:** Start the server:
```bash
python main.py
```

### API Keys Missing
```
❌ Test failed: API key not configured
```
**Solution:** Check `.env` file has all required API keys.

### Timeout
```
❌ Drama generation timed out after 300 seconds
```
**Solution:**
- Check server logs for errors
- Verify API keys are valid
- Increase timeout in test file

### Character Image Not Generated
```
⚠️  Character image not generated (might be OK if generation failed)
```
**Note:** Character image generation failures are logged but don't fail the test. Check server logs for details.

## CI/CD Integration

For automated testing in CI/CD pipelines:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r test-requirements.txt
      - name: Start server
        run: python main.py &
      - name: Wait for server
        run: sleep 5
      - name: Run tests
        run: |
          python tests/test_api.py
          python tests/test_drama_create.py
```

## Provider Tests (`test_providers.py`)

**NEW:** Unit tests for isolated provider-level API testing.

### Purpose
Test provider modules in isolation to debug low-level API issues without running the full server. Useful for:
- Verifying API credentials are working
- Testing provider-specific functionality
- Debugging timeouts or connection issues
- Performance benchmarking

### Run Tests
```bash
# All provider tests
pytest tests/test_providers.py -v -s

# Specific provider
pytest tests/test_providers.py::TestGeminiProvider -v -s
pytest tests/test_providers.py::TestOpenAIProvider -v -s
pytest tests/test_providers.py::TestSoraProvider -v -s

# Specific test
pytest tests/test_providers.py::TestGeminiProvider::test_generate_image_simple -v -s

# Skip slow tests (video generation takes 1-2 minutes)
pytest tests/test_providers.py -v -s -m "not slow"
```

### Test Categories

#### Gemini Provider Tests
- `test_generate_image_simple` - Basic image generation (~5-15s)
- `test_generate_image_with_reference` - Image with 9:16 aspect ratio reference (~5-15s)
- `test_generate_image_retry_logic` - Retry mechanism verification
- `test_text_generation_structured` - Structured text output (~2-5s)
- `test_provider_initialization` - Configuration validation

#### OpenAI Provider Tests
- `test_text_generation_structured` - Structured text generation (~2-5s)
- `test_provider_initialization` - Configuration validation

#### Sora Provider Tests ⚠️ SLOW
- `test_generate_video_simple` - Basic video (~60-120s)
- `test_generate_video_with_reference` - Video with reference image (~60-120s)
- `test_provider_initialization` - Configuration validation

#### Performance Tests
- `test_gemini_image_generation_speed` - Verify <30s generation time
- `test_concurrent_image_generation` - Parallel generation test

### Example Output
```bash
$ pytest tests/test_providers.py::TestGeminiProvider::test_generate_image_simple -v -s

tests/test_providers.py::TestGeminiProvider::test_generate_image_simple
🎨 Testing Gemini image generation...
Prompt: A cute cartoon dog sitting in a park, anime style, vibrant colors
INFO:app.providers.gemini_provider:[Gemini] Starting image generation attempt...
INFO:app.providers.gemini_provider:[Gemini] Adding 0 reference images
INFO:app.providers.gemini_provider:[Gemini] Sending request to https://api.nanobanana.ai/v1/chat/completions...
INFO:app.providers.gemini_provider:[Gemini] Received response - Status: 200
✓ Image generated successfully (234567 bytes)
PASSED [100%]
```

### Prerequisites
```bash
# Install pytest
pip install pytest pytest-asyncio

# Configure environment variables in .env
GEMINI_API_KEY=...
NANO_BANANA_API_KEY=...
NANO_BANANA_API_BASE=https://api.nanobanana.ai
OPENAI_API_KEY=...
SORA_API_KEY=...
SORA_API_BASE=https://api.t8star.cn
```

### Debugging with Provider Tests

If you encounter issues with generation endpoints:

1. **Test provider in isolation**
   ```bash
   pytest tests/test_providers.py::TestGeminiProvider::test_generate_image_simple -v -s
   ```

2. **Check for missing imports or configuration**
   ```bash
   pytest tests/test_providers.py::TestGeminiProvider::test_provider_initialization -v -s
   ```

3. **Performance issues**
   ```bash
   pytest tests/test_providers.py::TestProviderPerformance -v -s
   ```

This helps identify whether issues are:
- Provider-level (API keys, network, timeout)
- Application-level (routing, business logic)

## Contributing

When adding new tests:
1. Create test file in `tests/` directory
2. Follow naming convention: `test_*.py`
3. Add docstrings explaining what is being tested
4. Update this README with test description
5. Ensure tests are idempotent and clean up after themselves
