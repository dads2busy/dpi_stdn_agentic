#!/bin/bash

# Test script for LLM Fallback Cache Integration (Steps 1-3.3)
# Usage: bash test_llm_cache_integration.sh

echo "======================================="
echo "Testing LLM Fallback Cache Integration"
echo "======================================="
echo ""

PASSED=0
FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test 1: Check if llm_fallback_cache.py exists
echo "[Test 1] Checking if llm_fallback_cache.py exists..."
if [ -f "src/stdn_agentic/data/llm_fallback_cache.py" ]; then
    echo -e "${GREEN}✓ PASS${NC}: llm_fallback_cache.py exists"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_fallback_cache.py not found"
    ((FAILED++))
fi
echo ""

# Test 2: Check if __init__.py exports LLMFallbackCache
echo "[Test 2] Checking if __init__.py exports LLMFallbackCache..."
if grep -q "LLMFallbackCache" "src/stdn_agentic/data/__init__.py"; then
    echo -e "${GREEN}✓ PASS${NC}: LLMFallbackCache found in __init__.py"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: LLMFallbackCache not exported in __init__.py"
    ((FAILED++))
fi
echo ""

# Test 3: Check if repository.py imports LLMFallbackCache
echo "[Test 3] Checking if repository.py imports LLMFallbackCache..."
if grep -q "from .llm_fallback_cache import LLMFallbackCache" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: LLMFallbackCache import found in repository.py"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: LLMFallbackCache import not found in repository.py"
    ((FAILED++))
fi
echo ""

# Test 4: Check if CountryDataRepository.__init__ has enable_llm_cache parameter
echo "[Test 4] Checking if __init__ has enable_llm_cache parameter..."
if grep -q "enable_llm_cache" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: enable_llm_cache parameter found"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: enable_llm_cache parameter not found"
    ((FAILED++))
fi
echo ""

# Test 5: Check if CountryDataRepository.__init__ has llm_cache_dir parameter
echo "[Test 5] Checking if __init__ has llm_cache_dir parameter..."
if grep -q "llm_cache_dir" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_cache_dir parameter found"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_cache_dir parameter not found"
    ((FAILED++))
fi
echo ""

# Test 6: Check if CountryDataRepository.__init__ has llm_cache_ttl_hours parameter
echo "[Test 6] Checking if __init__ has llm_cache_ttl_hours parameter..."
if grep -q "llm_cache_ttl_hours" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_cache_ttl_hours parameter found"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_cache_ttl_hours parameter not found"
    ((FAILED++))
fi
echo ""

# Test 7: Check if LLMFallbackCache is instantiated
echo "[Test 7] Checking if LLMFallbackCache is instantiated..."
if grep -q "self.llm_cache = LLMFallbackCache" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: LLMFallbackCache instantiation found"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: LLMFallbackCache instantiation not found"
    ((FAILED++))
fi
echo ""

# Test 8: Check if get_country_data has hs_code parameter
echo "[Test 8] Checking if get_country_data has hs_code parameter..."
if grep -A 10 "async def get_country_data" "src/stdn_agentic/data/repository.py" | grep -q "hs_code"; then
    echo -e "${GREEN}✓ PASS${NC}: hs_code parameter found in get_country_data"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: hs_code parameter not found in get_country_data"
    ((FAILED++))
fi
echo ""

# Test 9: Check if get_country_data checks LLM cache
echo "[Test 9] Checking if get_country_data queries LLM cache..."
if grep -q "self.llm_cache.get_countries" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: LLM cache query found in get_country_data"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: LLM cache query not found in get_country_data"
    ((FAILED++))
fi
echo ""

# Test 10: Check if get_country_data saves to LLM cache
echo "[Test 10] Checking if get_country_data saves to LLM cache..."
if grep -q "self.llm_cache.set_countries" "src/stdn_agentic/data/repository.py"; then
    echo -e "${GREEN}✓ PASS${NC}: LLM cache save found in get_country_data"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: LLM cache save not found in get_country_data"
    ((FAILED++))
fi
echo ""

# Test 11: Check if .env has ENABLE_LLM_FALLBACK_CACHE
echo "[Test 11] Checking if .env has ENABLE_LLM_FALLBACK_CACHE..."
if grep -q "ENABLE_LLM_FALLBACK_CACHE" ".env"; then
    echo -e "${GREEN}✓ PASS${NC}: ENABLE_LLM_FALLBACK_CACHE found in .env"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: ENABLE_LLM_FALLBACK_CACHE not found in .env"
    ((FAILED++))
fi
echo ""

# Test 12: Check if config.json has enable_llm_fallback_cache
echo "[Test 12] Checking if config.json has enable_llm_fallback_cache..."
if grep -q "enable_llm_fallback_cache" "config.json"; then
    echo -e "${GREEN}✓ PASS${NC}: enable_llm_fallback_cache found in config.json"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: enable_llm_fallback_cache not found in config.json"
    ((FAILED++))
fi
echo ""

# Test 13: Check if config.json has llm_fallback_cache_dir
echo "[Test 13] Checking if config.json has llm_fallback_cache_dir..."
if grep -q "llm_fallback_cache_dir" "config.json"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_fallback_cache_dir found in config.json"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_fallback_cache_dir not found in config.json"
    ((FAILED++))
fi
echo ""

# Test 14: Check if config.json has llm_fallback_cache_ttl_hours
echo "[Test 14] Checking if config.json has llm_fallback_cache_ttl_hours..."
if grep -q "llm_fallback_cache_ttl_hours" "config.json"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_fallback_cache_ttl_hours found in config.json"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_fallback_cache_ttl_hours not found in config.json"
    ((FAILED++))
fi
echo ""

# Test 15: Check if country_data_enricher.py looks up hs_code (Step 4)
echo "[Test 15] Checking if country_data_enricher.py looks up hs_code..."
if grep -q "lookup_hs_code" "src/stdn_agentic/orchestrator/country_data_enricher.py"; then
    echo -e "${GREEN}✓ PASS${NC}: hs_code lookup found in country_data_enricher.py"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: hs_code lookup not found in country_data_enricher.py"
    ((FAILED++))
fi
echo ""

# Test 16: Check if country_data_enricher.py passes hs_code to get_country_data (Step 4)
echo "[Test 16] Checking if hs_code is passed to get_country_data..."
if grep -A 10 "await self.country_repo.get_country_data" "src/stdn_agentic/orchestrator/country_data_enricher.py" | grep -q "hs_code="; then
    echo -e "${GREEN}✓ PASS${NC}: hs_code parameter passed to get_country_data"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: hs_code parameter not passed to get_country_data"
    ((FAILED++))
fi
echo ""

# Test 17: Check if pipeline.py passes enable_llm_cache to CountryDataRepository (Step 5)
echo "[Test 17] Checking if pipeline.py passes enable_llm_cache..."
if grep -A 10 "CountryDataRepository(" "src/stdn_agentic/orchestrator/pipeline.py" | grep -q "enable_llm_cache"; then
    echo -e "${GREEN}✓ PASS${NC}: enable_llm_cache passed to CountryDataRepository"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: enable_llm_cache not passed to CountryDataRepository"
    ((FAILED++))
fi
echo ""

# Test 18: Check if pipeline.py passes llm_cache_dir to CountryDataRepository (Step 5)
echo "[Test 18] Checking if pipeline.py passes llm_cache_dir..."
if grep -A 10 "CountryDataRepository(" "src/stdn_agentic/orchestrator/pipeline.py" | grep -q "llm_cache_dir"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_cache_dir passed to CountryDataRepository"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_cache_dir not passed to CountryDataRepository"
    ((FAILED++))
fi
echo ""

# Test 19: Check if pipeline.py passes llm_cache_ttl_hours to CountryDataRepository (Step 5)
echo "[Test 19] Checking if pipeline.py passes llm_cache_ttl_hours..."
if grep -A 10 "CountryDataRepository(" "src/stdn_agentic/orchestrator/pipeline.py" | grep -q "llm_cache_ttl_hours"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_cache_ttl_hours passed to CountryDataRepository"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_cache_ttl_hours not passed to CountryDataRepository"
    ((FAILED++))
fi
echo ""

# Test 20: Check if ConfigModel has enable_llm_fallback_cache field (Step 5)
echo "[Test 20] Checking if ConfigModel has enable_llm_fallback_cache field..."
if grep -q "enable_llm_fallback_cache.*Field" "src/stdn_agentic/models.py"; then
    echo -e "${GREEN}✓ PASS${NC}: enable_llm_fallback_cache field found in ConfigModel"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: enable_llm_fallback_cache field not found in ConfigModel"
    ((FAILED++))
fi
echo ""

# Test 21: Check if ConfigModel has llm_fallback_cache_dir field (Step 5)
echo "[Test 21] Checking if ConfigModel has llm_fallback_cache_dir field..."
if grep -q "llm_fallback_cache_dir.*Field" "src/stdn_agentic/models.py"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_fallback_cache_dir field found in ConfigModel"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_fallback_cache_dir field not found in ConfigModel"
    ((FAILED++))
fi
echo ""

# Test 22: Check if ConfigModel has llm_fallback_cache_ttl_hours field (Step 5)
echo "[Test 22] Checking if ConfigModel has llm_fallback_cache_ttl_hours field..."
if grep -q "llm_fallback_cache_ttl_hours.*Field" "src/stdn_agentic/models.py"; then
    echo -e "${GREEN}✓ PASS${NC}: llm_fallback_cache_ttl_hours field found in ConfigModel"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}: llm_fallback_cache_ttl_hours field not found in ConfigModel"
    ((FAILED++))
fi
echo ""

# Summary
echo "======================================="
echo "TEST SUMMARY"
echo "======================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo "LLM Fallback Cache integration is complete."
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "Please review the failed tests and fix the integration."
    exit 1
fi
