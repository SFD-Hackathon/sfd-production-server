# Testing Guide

## Quick Start

### 1. Install Test Dependencies

```bash
pip install -r test-requirements.txt
```

### 2. Start the Server

```bash
# In terminal 1
source venv/bin/activate
python main.py
```

Server should start at `http://localhost:8000`

### 3. Run Tests

```bash
# In terminal 2
source venv/bin/activate

# Run all tests in order (smallest to largest)
pytest test_generation.py -v -s

# Run specific test
pytest test_generation.py::test_character_generation -v -s
pytest test_generation.py::test_episode_generation -v -s
pytest test_generation.py::test_drama_generation -v -s
```

---

## Test Levels

Tests are organized from smallest (fastest) to largest (slowest):

### Level 0: Health Check
- **Test**: `test_health_check`
- **Duration**: <1 second
- **What it tests**: Server is running

```bash
pytest test_generation.py::test_health_check -v
```

### Level 1: Asset-Level Tests
- **Test**: `test_character_generation`
- **Assets Generated**: 1 character video
- **Duration**: ~30-60 seconds
- **What it tests**: Single asset generation (character audition video)

```bash
pytest test_generation.py::test_character_generation -v -s
```

### Level 2: Episode-Level Tests
- **Test**: `test_episode_generation`
- **Assets Generated**:
  - 2 scenes (storyboards)
  - 4 scene assets (2 storyboards + 2 video clips)
- **Duration**: ~2-5 minutes
- **What it tests**: Episode-level DAG execution

```bash
pytest test_generation.py::test_episode_generation -v -s
```

### Level 3: Drama-Level Tests (Full DAG)
- **Test**: `test_drama_generation`
- **Assets Generated**:
  - 2 characters (portraits)
  - 2 scenes (storyboards)
  - 4 scene assets (storyboards + clips)
- **Duration**: ~3-10 minutes
- **What it tests**: Full hierarchical DAG execution
  - h=1: Characters + Episodes (parallel)
  - h=2: Scenes (parallel, depends on h=1)
  - h=3: Scene Assets (parallel, depends on h=2)

```bash
pytest test_generation.py::test_drama_generation -v -s
```

### Utility Tests
- **Test**: `test_job_listing`
- **Duration**: <1 second
- **What it tests**: Job status retrieval

```bash
pytest test_generation.py::test_job_listing -v -s
```

---

## Expected Output

### Successful Test Run

```
test_generation.py::test_health_check PASSED
test_generation.py::test_character_generation PASSED
test_generation.py::test_episode_generation PASSED
test_generation.py::test_drama_generation PASSED
test_generation.py::test_job_listing PASSED

================ 5 passed in 420.32s ================
```

### During Test Execution

You'll see real-time progress:

```
TEST 1: Character Image Generation
⏳ Waiting for job job_abc123...
  Status: pending | Elapsed: 0s
  Status: running | Elapsed: 5s
  Status: running | Elapsed: 10s
✅ Job completed in 32s
✅ Character asset generated successfully
   Video URL: https://pub-xxx.r2.dev/10000/test_drama_xxx/...
```

---

## Debugging Failed Tests

### Check Server Logs

In terminal 1 (server), watch for errors:
```
ERROR: Failed to generate asset ep01_s01_storyboard: ...
```

### Check Job Status

If a test times out, manually check job status:

```bash
# Get drama_id from test output
drama_id="test_drama_1234567890"

# Get job_id from test output
job_id="job_abc123"

# Check status
curl http://localhost:8000/dramas/$drama_id/jobs/$job_id
```

### Check Environment Variables

Ensure all required API keys are set in `.env`:

```bash
cat .env | grep -E "(GEMINI|SORA|OPENAI|R2)"
```

Required:
- ✅ `GEMINI_API_KEY` - For image generation
- ✅ `SORA_API_KEY` - For video generation
- ✅ `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` - For R2 uploads

---

## Test Configuration

### Modify Timeouts

Edit `test_generation.py` to adjust timeouts:

```python
# Increase timeout for slow generation
final_job = client.wait_for_job(drama_id, job_id, timeout=600)  # 10 min
```

### Disable Cleanup

To inspect generated dramas after tests, comment out cleanup in `test_drama` fixture:

```python
# Cleanup (optional - comment out to inspect results)
# print(f"\n🧹 Cleaning up test drama {drama_id}")
# client.delete(f"/dramas/{drama_id}")
```

### Run Tests in Isolation

Run one test at a time to isolate issues:

```bash
pytest test_generation.py::test_character_generation -v -s --tb=short
```

---

## Test Data

The test suite creates a drama with:

**Characters:**
- `char_detective` - Detective Nova (female, cybernetic detective)
- `char_ai` - ARIA (AI entity)

**Episodes:**
- `ep01` - "The Awakening"

**Scenes:**
- `ep01_s01` - Office scene with detective
- `ep01_s02` - Digital realm encounter

**Assets:**
- `ep01_s01_storyboard` - Image (depends on char_detective)
- `ep01_s01_clip` - Video (depends on storyboard)
- `ep01_s02_storyboard` - Image (depends on char_detective, char_ai)
- `ep01_s02_clip` - Video (depends on storyboard)

---

## Continuous Integration

To run tests in CI:

```yaml
# .github/workflows/test.yml
name: Test Generation

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt -r test-requirements.txt
      - run: python main.py &
      - run: sleep 5  # Wait for server
      - run: pytest test_generation.py -v
    env:
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      SORA_API_KEY: ${{ secrets.SORA_API_KEY }}
      R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
      R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
      R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
```

---

## Troubleshooting

### Test hangs on job polling

**Cause**: Generation failed but job status not updated
**Solution**: Check server logs for generation errors

### ImportError: No module named 'pytest'

**Cause**: Test dependencies not installed
**Solution**: `pip install -r test-requirements.txt`

### Connection refused

**Cause**: Server not running
**Solution**: Start server in another terminal: `python main.py`

### 401 Unauthorized

**Cause**: API key authentication enabled
**Solution**: Set `API_KEY` in `test_generation.py` or disable auth in `.env`

### Job fails with "GEMINI_API_KEY not found"

**Cause**: Missing API key
**Solution**: Add `GEMINI_API_KEY` to `.env` file

---

## Performance Benchmarks

Expected test durations (with working API keys):

| Test | Assets | Expected Time |
|------|--------|---------------|
| Health Check | 0 | <1s |
| Character Generation | 1 | 30-60s |
| Episode Generation | 6 | 2-5 min |
| Drama Generation | 8 | 3-10 min |
| Job Listing | 0 | <1s |

**Total test suite**: ~6-16 minutes

---

## Next Steps

After tests pass:

1. **Inspect Generated Assets**: Check R2 bucket for uploaded files
2. **View in API Docs**: Visit `http://localhost:8000/docs`
3. **Test Frontend Integration**: Use generated drama in frontend app
4. **Deploy to Production**: Run tests against production API

---

## Support

If tests fail:
1. Check server logs (terminal 1)
2. Verify `.env` configuration
3. Review test output for specific errors
4. Check `MIGRATION_STATUS.md` for implementation status
