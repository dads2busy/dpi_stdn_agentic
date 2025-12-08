# Refactored Extractor Tests

This test suite validates the refactored extractor classes without running the full pipeline.

## What's Tested

### ✅ **ComponentExtractor**
- Initialization with all parameters
- Simple single-agent component extraction
- Multi-agent debate-based extraction
- Confidence and reasoning preservation

### ✅ **MaterialsExtractor**
- Initialization with debate/non-debate modes
- Input validation (components, ontology)
- Safe materials extraction with retry logic
- Ontology constraint enforcement
- Material confidence and reasoning

### ✅ **CountryDataEnricher**
- Initialization
- Country data enrichment with confidence
- Null value handling
- Integration with materials data

### ✅ **Integration Tests**
- Component → Materials pipeline
- Materials → Country data pipeline
- Data structure compatibility

## Running the Tests

### **Run all tests:**
```bash
pytest tests/test_refactored_extractors.py -v
```

### **Run specific test class:**
```bash
# Test only ComponentExtractor
pytest tests/test_refactored_extractors.py::TestComponentExtractor -v

# Test only MaterialsExtractor
pytest tests/test_refactored_extractors.py::TestMaterialsExtractor -v

# Test only CountryDataEnricher
pytest tests/test_refactored_extractors.py::TestCountryDataEnricher -v

# Test only integration
pytest tests/test_refactored_extractors.py::TestExtractorIntegration -v
```

### **Run specific test:**
```bash
pytest tests/test_refactored_extractors.py::TestComponentExtractor::test_extract_components_simple -v
```

### **Run with coverage:**
```bash
pytest tests/test_refactored_extractors.py --cov=stdn_agentic.orchestrator --cov-report=html
```

### **Run with detailed output:**
```bash
pytest tests/test_refactored_extractors.py -vv --tb=long
```

## Test Features

### **Mocked Dependencies**
- All tests use mocked agents and repositories
- No actual API calls are made
- Fast execution (< 1 second total)

### **Fixtures**
- `mock_deps`: Mocked STDN dependencies
- `mock_reporter`: Mocked debate reporter
- `mock_debater`: Mocked multi-agent debater
- `mock_country_repo`: Mocked country data repository
- `sample_component_list`: Sample components with confidence
- `sample_materials_list`: Sample materials with confidence

### **Test Coverage**

| Class | Tests | Coverage |
|-------|-------|----------|
| ComponentExtractor | 3 | Initialization, simple extraction, debate extraction |
| MaterialsExtractor | 4 | Initialization, validation (success/fail), safe extraction |
| CountryDataEnricher | 3 | Initialization, enrichment, null handling |
| Integration | 2 | Component→Materials, Materials→Country pipelines |

**Total: 12 tests**

## Expected Output

When all tests pass, you should see:

```
============================== test session starts ===============================
collected 12 items

tests/test_refactored_extractors.py::TestComponentExtractor::test_initialization PASSED
tests/test_refactored_extractors.py::TestComponentExtractor::test_extract_components_simple PASSED
tests/test_refactored_extractors.py::TestComponentExtractor::test_extract_components_with_debate PASSED
tests/test_refactored_extractors.py::TestMaterialsExtractor::test_initialization PASSED
tests/test_refactored_extractors.py::TestMaterialsExtractor::test_validate_inputs_success PASSED
tests/test_refactored_extractors.py::TestMaterialsExtractor::test_validate_inputs_empty_ontology PASSED
tests/test_refactored_extractors.py::TestMaterialsExtractor::test_extract_materials_safe PASSED
tests/test_refactored_extractors.py::TestCountryDataEnricher::test_initialization PASSED
tests/test_refactored_extractors.py::TestCountryDataEnricher::test_enrich_with_country_data PASSED
tests/test_refactored_extractors.py::TestCountryDataEnricher::test_enrich_handles_null_country_data PASSED
tests/test_refactored_extractors.py::TestExtractorIntegration::test_component_to_materials_pipeline PASSED
tests/test_refactored_extractors.py::TestExtractorIntegration::test_materials_to_country_pipeline PASSED

=============================== 12 passed in 0.15s ===============================
```

## Benefits of These Tests

1. **Fast Feedback** - Tests run in milliseconds, not minutes
2. **No Dependencies** - No API keys, databases, or external services needed
3. **Isolated Testing** - Each extractor is tested independently
4. **Integration Coverage** - Verifies extractors work together correctly
5. **Confidence Validation** - Ensures confidence scores flow through the pipeline
6. **Error Handling** - Tests validation and error cases

## Troubleshooting

### **Import Errors**
If you get import errors, make sure you're in the project root and the package is installed:
```bash
pip install -e .
```

### **Async Test Warnings**
If you see warnings about async tests, install pytest-asyncio:
```bash
pip install pytest-asyncio
```

### **Missing Fixtures**
If fixtures aren't found, make sure you're running from the project root:
```bash
cd /path/to/dpi_stdn_agentic
pytest tests/test_refactored_extractors.py -v
```
