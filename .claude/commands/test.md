---
description: Run the complete unit test and skill regression suite
---

# /test

Execute the automated test suite to verify skill schemas, progressive disclosure, frontmatter parsing, and orchestrator execution.

## Instructions
1. Run the test suite:
   ```bash
   .venv\Scripts\python.exe -m unittest discover tests
   ```
2. Verify all test cases pass:
   - Frontmatter parsing and metadata extraction
   - Progressive disclosure catalog indexing
   - System prompt rendering
   - Orchestrator skill binding
   - Executive governance synthesis
3. If any test fails, diagnose the failure and suggest or apply the corrective fix.
