"""
Shared constants for STDN system
"""

# Debate parameters
DEFAULT_DEBATE_ROUNDS = 3
DEFAULT_CONVERGENCE_THRESHOLD = 0.75
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# USGS query parameters
USGS_DEFAULT_TOP_N = 5
USGS_QUERY_TIMEOUT = 30

# Cache settings
CACHE_TTL_HOURS = 24
MAX_CACHE_SIZE_MB = 500

# Output formats
SUPPORTED_EXPORT_FORMATS = ["csv", "json", "excel"]

# File paths
DEBATE_RESULTS_DIR = "output/transcripts"
CHECKPOINT_DIR = ".checkpoints"
CACHE_DIR = ".cache"
