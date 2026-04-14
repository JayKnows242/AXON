"""Pytest configuration for AXON tests."""
import os
import sys

# Set env vars before anything loads CTranslate2
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-placeholder")

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
