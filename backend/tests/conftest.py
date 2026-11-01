import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("LLM_PROVIDER", "mistral")
os.environ.setdefault("MISTRAL_API_KEY", "test-key")
