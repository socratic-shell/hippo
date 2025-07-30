This is the Hippo project, a MCP server for memory storage and retrieval.

Consult the mdbook sources in the `md` directory below to find documentation on the design goals and overall structure of the project. Keep the mdbook up-to-date at all times as you evolve the code.

@md/SUMMARY.md

We track progress in github tracking issues on the repository `socratic-shell/hippo`:

@.socratic-shell/github-tracking-issues.md

and we use AI insight comments

@.socratic-shell/ai-insights.md

## Project Commands

**ALWAYS use these commands for consistency:**

### Type Checking
```bash
# Run mypy type checking (ALWAYS run this for code quality)
uv run mypy py/hippo/

# Check specific file
uv run mypy py/hippo/filename.py
```

### Testing
```bash
# Run all tests
uv run pytest py/hippo/

# Run specific test file
uv run pytest py/hippo/test_filename.py

# Run with verbose output
uv run pytest -v py/hippo/
```

### Development Server
```bash
# Run the MCP server
uv run python -m hippo.server

# Run with debug logging
uv run python -m hippo.server --debug
```

### Code Quality
```bash
# Lint and format code with ruff
uv run ruff check py/hippo/

# Auto-fix linting issues
uv run ruff check --fix py/hippo/

# Format code with ruff
uv run ruff format py/hippo/
```

### Documentation
```bash
# Build mdbook documentation
mdbook build md/

# Serve mdbook locally
mdbook serve md/
```

**Key Points:**
- **Always use `uv run`** for Python commands to ensure proper virtual environment
- **Always run mypy** when making code changes to maintain type safety
- **Use `rg` instead of workspace search** for searching code in this project

## Checkpointing

When checkpointing:

* Update tracking issue (if any)
* Check that mdbook is up-to-date if any user-impacting or design changes have been made
    * If mdbook is not up-to-date, ask user how to proceed
* Commit changes to git
    * If there are changes unrelated to what is being checkpointed, ask user how to proceed.