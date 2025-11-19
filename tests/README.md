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

## Contributing

When adding new tests:
1. Create test file in `tests/` directory
2. Follow naming convention: `test_*.py`
3. Add docstrings explaining what is being tested
4. Update this README with test description
5. Ensure tests are idempotent and clean up after themselves
