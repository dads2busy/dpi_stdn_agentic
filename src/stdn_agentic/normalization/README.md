# STDN Normalization Module

## Overview

This module provides semantic normalization capabilities for STDN run outputs. It performs cross-run semantic reconciliation **without deduplication**, preserving all individual run records while normalizing names and attributes.

## Key Concept

If you have 3 separate run files with:
- Run 1: "LCD"
- Run 2: "Liquid Crystal Display"
- Run 3: "LCD Panel"

The normalization process will:
1. Keep all 3 records (no deduplication)
2. Normalize all to the same canonical name: "Liquid Crystal Display"
3. Preserve original values for traceability
4. Group them semantically with a `semantic_group_id`

## Data Models

### NormalizedComponent

Represents a single component from a specific run with both original and normalized fields.

```python
NormalizedComponent(
    # Original identity
    original_id="comp_001",
    original_name="LCD",
    source_run="run_20260105_100823",
    source_technology="smartphone",
    
    # Normalized fields (canonical)
    normalized_name="Liquid Crystal Display",
    normalized_type="hardware_component",
    normalized_description="Electronic visual display using liquid crystals",
    normalized_purpose="Provide visual output",
    normalized_characteristics=["electronic", "display", "visual_output"],
    
    # Semantic grouping
    semantic_group_id="group_0001",
    
    # Original values preserved
    original_type="hardware",
    original_description="Display component",
    original_purpose="Output",
    original_characteristics=["display"],
    
    # Metadata
    confidence=0.85,
    timestamp=datetime.now()
)
```

### SemanticGroup

Represents a group of semantically similar components with their canonical representation.

```python
SemanticGroup(
    group_id="group_0001",
    canonical_name="Liquid Crystal Display",
    canonical_type="hardware_component",
    canonical_description="Electronic visual display using liquid crystal technology",
    canonical_purpose="Provide visual output for user interaction",
    canonical_characteristics=["electronic", "display", "visual_output"],
    
    member_count=3,
    member_runs=["run_20260105_100823", "run_20260105_103456", "run_20260105_104521"],
    member_component_ids=["comp_run1_005", "comp_run2_003", "comp_run3_007"],
    
    confidence_avg=0.88,
    confidence_min=0.85,
    confidence_max=0.92
)
```

### ConsolidatedNormalizedSTDN

The complete output containing all normalized components, semantic groups, and metadata.

```python
ConsolidatedNormalizedSTDN(
    components=[...],  # All components from all runs
    semantic_groups=[...],  # Semantic groupings
    dependencies=[...],  # Optional: normalized dependencies
    normalization_metadata={
        "total_runs": 3,
        "total_components": 45,
        "semantic_groups": 30,
        "avg_group_size": 1.5,
        "reduction_ratio": 0.67
    }
)
```

## Module Structure

```
normalization/
├── __init__.py              # Module exports
├── models.py                # ✅ Step 1: Pydantic data models
├── run_loader.py            # Step 2: Load existing run files
├── embeddings.py            # Step 3: Generate semantic embeddings
├── clustering.py            # Step 4: Cluster similar components
├── canonical_selector.py    # Step 5: LLM-based canonical selection
└── manager.py               # Step 6: Orchestrate normalization
```

## Testing

### Run All Tests

```bash
cd /Users/ads7fg/git/dpi_stdn_agentic
python src/stdn_agentic/tests/normalization/test_models.py
```

### Run with pytest

```bash
pytest src/stdn_agentic/tests/normalization/test_models.py -v
```

### Expected Output

```
================================================================================
Testing STDN Normalization Models
================================================================================

[1/11] Testing NormalizedComponent creation...
✓ NormalizedComponent model works correctly

[2/11] Testing NormalizedComponent with materials...
✓ NormalizedComponent with materials works correctly

[3/11] Testing NormalizedComponent validation...
✓ Confidence validation works correctly

[4/11] Testing NormalizedDependency creation...
✓ NormalizedDependency model works correctly

[5/11] Testing SemanticGroup creation...
✓ SemanticGroup model works correctly

[6/11] Testing SemanticGroup with single member...
✓ SemanticGroup with single member works correctly

[7/11] Testing SemanticGroup validation...
✓ Member count validation works correctly

[8/11] Testing ConsolidatedNormalizedSTDN creation...
✓ ConsolidatedNormalizedSTDN model works correctly

[9/11] Testing JSON serialization...
✓ JSON serialization works correctly

[10/11] Testing full model integration...
✓ Full model integration works correctly

================================================================================
✓ All tests passed!
================================================================================
```

## Implementation Status

**Last Updated**: January 5, 2026 - Development paused after Step 2

- [x] **Step 1**: Data Models (COMPLETE - Tested 11/11)
- [x] **Step 2**: Run Loader (COMPLETE - Tested with 18 files, 1,610 components)
- [ ] **Step 3**: Embedding Generator (NEXT - Create embeddings.py)
- [ ] Step 4: Clustering Module
- [ ] Step 5: Canonical Selector
- [ ] Step 6: Normalization Manager
- [ ] Step 7: CLI Tool
- [ ] Step 8: Pipeline Integration

### Current Data Status
- 18 CSV run files loaded successfully
- 1,610 total components extracted
- 871 unique component names identified
- 20 technologies covered
- ~40-50% reduction potential estimated

### To Resume Development
1. Start with Step 3: Create `embeddings.py`
2. Install `sentence-transformers` package
3. Implement EmbeddingGenerator class
4. Generate embeddings for 871 unique names
5. See test_run_loader.py for current functionality

## Next Steps

1. **Test the models**: Run the test file to verify all models work correctly
2. **Move to Step 2**: Implement the run loader to read existing CSV/JSON files
3. **Proceed incrementally**: Each step builds on the previous one

## Usage Example (Future)

Once complete, you'll be able to:

```python
from stdn_agentic.normalization import NormalizationManager

# Create manager
manager = NormalizationManager(
    runs_dir="./output",
    consolidated_dir="./output/consolidated"
)

# Run normalization on all existing runs
result = await manager.normalize_all_runs()

print(f"Normalized {result.normalization_metadata['total_components']} components")
print(f"Into {result.normalization_metadata['semantic_groups']} semantic groups")
```

The output will be saved to:
- `./output/consolidated/consolidated_normalized_latest.json` (always current)
- `./output/consolidated/consolidated_normalized_TIMESTAMP.json` (archived versions)
