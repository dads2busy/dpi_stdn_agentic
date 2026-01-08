# STDN Test Suite

This directory contains all tests for the Supply Technology Dependency Network (STDN) project.

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── README.md               # This file
│
├── unit/                   # Unit tests (fast, isolated)
│   ├── agents/            # Agent-specific unit tests
│   │   ├── test_materials_agent.py
│   │   └── test_agents.py
│   ├── data/              # Data layer unit tests
│   │   ├── test_usgs_client_queries.py
│   │   └── test_usgs_client_sql_inspect.py
│   ├── debate/            # Debate system unit tests
│   ├── normalization/     # Normalization tests
│   │   └── test_models.py
│   └── orchestrator/      # Orchestrator unit tests
│
├── integration/           # Integration tests (multi-component)
│   ├── test_debate_workflow.py
│   ├── test_enhanced_debate_workflow.py
│   ├── test_country_data_enrichment.py
│   └── test_phase2c_components.py
│
├── e2e/                   # End-to-end tests (full pipeline)
│   ├── test_full_pipeline.py
│   └── test_phase2c_pipeline.py
│
├── fixtures/              # Test data and fixtures
│
└── debug/                 # Debug scripts (not run by pytest)
    ├── debug_duckdb.py
    ├── debug_hs_codes.py
    ├── debug_agents_init.py
    ├── debug_factory.py
    ├── debug_imports.py
    └── debug_models.py
```

## Test Categories

### Unit Tests (`unit/`)
- **Purpose**: Test individual functions and classes in isolation
- **Speed**: Fast (< 1 second per test)
- **Dependencies**: Mocked or minimal
- **Organization**: Mirrors source code structure

Run unit tests:
```bash
pytest src/stdn_agentic/tests/unit/ -v
```

### Integration Tests (`integration/`)
- **Purpose**: Test interactions between multiple components
- **Speed**: Moderate (1-10 seconds per test)
- **Dependencies**: May use real dependencies within the project
- **Focus**: Workflows, data flow between components

Run integration tests:
```bash
pytest src/stdn_agentic/tests/integration/ -v
```

### End-to-End Tests (`e2e/`)
- **Purpose**: Test complete pipeline scenarios
- **Speed**: Slow (10+ seconds per test)
- **Dependencies**: Full pipeline with real or mocked external services
- **Focus**: User-facing functionality and complete workflows

Run e2e tests:
```bash
pytest src/stdn_agentic/tests/e2e/ -v
```

## Running Tests

### Run all tests
```bash
pytest src/stdn_agentic/tests/ -v
```

### Run specific test categories
```bash
# Unit tests only
pytest src/stdn_agentic/tests/unit/ -v

# Integration tests only
pytest src/stdn_agentic/tests/integration/ -v

# E2E tests only
pytest src/stdn_agentic/tests/e2e/ -v
```

### Run tests by marker
```bash
# Skip slow tests
pytest -m "not slow" -v

# Run only integration tests
pytest -m integration -v

# Run only tests that don't require API
pytest -m "not requires_api" -v
```

### Run specific test file
```bash
pytest src/stdn_agentic/tests/unit/agents/test_materials_agent.py -v
```

### Run with coverage
```bash
pytest src/stdn_agentic/tests/ --cov=stdn_agentic --cov-report=html
```

## Debug Scripts

The `debug/` directory contains standalone scripts for debugging and manual testing. These are not run by pytest and are intended for developer use:

```bash
# Run a debug script
python src/stdn_agentic/tests/debug/debug_agents_init.py
```

## Writing New Tests

### Naming Conventions
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<what_is_being_tested>`

### Test Organization Rules
1. **Unit tests** should mirror the source structure:
   - Test for `src/stdn_agentic/agents/materials_agent.py` → `tests/unit/agents/test_materials_agent.py`

2. **Integration tests** should focus on workflows:
   - Use descriptive names like `test_debate_workflow.py`

3. **E2E tests** should test complete scenarios:
   - Name tests after user-facing features

### Using Fixtures
Common fixtures are defined in `conftest.py`:
- `sample_ontology` - Standard material list
- `sample_components` - Standard component list
- `mock_stdn_dependencies` - Mocked dependencies
- `mock_run_context` - Mocked agent context

Example:
```python
def test_something(mock_run_context, sample_ontology):
    # Test uses fixtures automatically
    assert len(sample_ontology) > 0
```

### Test Markers
Add markers to categorize tests:
```python
@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.requires_api
def test_expensive_operation():
    # Test code here
    pass
```

## Best Practices

1. **Keep unit tests fast** - Mock external dependencies
2. **Use fixtures** - Share common setup via `conftest.py`
3. **Test edge cases** - Include None, empty, and invalid inputs
4. **Clear assertions** - Use descriptive assertion messages
5. **Independent tests** - Tests should not depend on each other
6. **Clean up** - Use fixtures with cleanup or context managers

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Pushes to main branch
- Scheduled nightly builds

All tests must pass before merging to main.
