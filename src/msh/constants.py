import os

# Paths
DEFAULT_BUILD_DIR = ".msh/build"
DEFAULT_RUN_META_DIR = ".msh/run_meta"
DEFAULT_LOGS_DIR = ".msh/logs"
DEFAULT_MODELS_DIR = "models"
DEFAULT_DUCKDB_PATH = "msh.duckdb"

# dbt Defaults
DEFAULT_PROJECT_NAME = "msh_project"
DEFAULT_PROFILE_NAME = "msh_profile"
DEFAULT_TARGET_NAME = "dev"

# Data Defaults
DEFAULT_RAW_DATASET = "msh_raw"
DEFAULT_DESTINATION = "duckdb"
DEFAULT_WRITE_DISPOSITION = "replace"

# Schemas
SCHEMA_MAIN = "main"
SCHEMA_PUBLIC = "public"

# Logging
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
