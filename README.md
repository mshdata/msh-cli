# msh: The Atomic Data Engine

> **Stop gluing Python scripts to SQL files.** Define Ingestion, Transformation, and Lineage in a single, version-controlled asset.

[![License](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE)

## The Problem: Fragmented Data Stacks

In the modern data stack, your pipeline is fragmented:
*   **Ingestion** happens in one tool (Airbyte, Fivetran), often defined in UI or JSON.
*   **Transformation** happens in another (dbt, SQL), defined in `.sql` files.
*   **Orchestration** happens in a third (Airflow, Dagster), defined in Python.

This separation creates friction. Adding a new column requires touching three different systems. Debugging a failure requires tracing lineage across boundaries.

## The Solution: The Atomic Asset

**msh** unifies these steps into a single **Atomic Asset**. An `.msh` file defines *everything* about a data product: where it comes from, how it changes, and where it goes.

### Example: `models/orders.msh`

**Option 1: Direct Credentials (Fully Atomic)**
```yaml
name: orders

ingest:
  type: sql_database
  credentials: "postgresql://user:pass@prod-db.com/sales"
  table: "public.orders"

transform: |
  SELECT 
    id as order_id,
    customer_id,
    total_amount,
    created_at
  FROM {{ source }}
  WHERE status = 'completed'
```

**Option 2: Source References (DRY for Large Projects)**

Define sources once in `msh.yaml`:
```yaml
# msh.yaml
sources:
  - name: prod_db
    type: sql_database
    credentials: "${DB_PROD_CREDENTIALS}"  # Environment variable
    schema: public
    tables:
      - name: orders
        description: Customer orders table
      - name: customers
        description: Customer master data
  
  - name: jsonplaceholder
    type: rest_api
    endpoint: "https://jsonplaceholder.typicode.com"
    resources:
      - name: users
      - name: posts
```

Then reference in `.msh` files:
```yaml
# models/staging/stg_orders.msh
name: stg_orders
ingest:
  source: prod_db
  table: orders

transform: |
  SELECT * FROM {{ source }}
```

```yaml
# models/staging/stg_users.msh
name: stg_users
ingest:
  source: jsonplaceholder
  resource: users

transform: |
  SELECT id, name, email FROM {{ source }}
```

**Benefits:**
- ✅ **DRY**: Define credentials once, reference everywhere
- ✅ **Environment Variables**: Use `${VAR_NAME}` for sensitive credentials
- ✅ **Backward Compatible**: Direct credentials still work
- ✅ **dbt-style**: Familiar pattern for dbt users

## Key Capabilities

### ⚡ Smart Ingest
**Save API costs and storage.** msh parses your SQL transformation *before* running ingestion. It detects exactly which columns you are selecting (`id`, `userId`, `title`) and instructs the ingestion engine to **only fetch those fields** from the API or Database.

### 🔵/🟢 Blue/Green Deployment
**Zero downtime swaps.** Every run creates a new version of your tables (e.g., `raw_orders_a1b2`, `model_orders_a1b2`). The live view is only swapped (`CREATE OR REPLACE VIEW`) once the new version is fully built and tested. Your dashboards never break during a run.

### ↩️ Atomic Rollbacks
**Instant recovery.** Deployed a bug? No problem.
```bash
msh rollback orders
```
msh instantly swaps the view back to the previous successful version. No data needs to be re-processed.

### 🔌 Universal Connectivity
**The Full Data Lifecycle.** msh supports every flow your data needs:
*   **API to DB**: Ingest from REST/GraphQL APIs directly into your warehouse.
*   **DB to DB**: Replicate and transform data between databases (e.g., Postgres -> Snowflake).
*   **Reverse ETL**: Push transformed models back to operational systems (e.g., Snowflake -> Salesforce).

### 🚀 Publish Command
**Activate your data.** Push your transformed models to external systems with a single command.
```bash
msh publish orders --to salesforce
```

### 🔀 Git-Aware Development
**Isolated workspaces.** When working on different git branches, msh automatically creates isolated schemas. Developers can work simultaneously without conflicts. Production deployments always use standard schemas.

### ⚡ Bulk Operations
**Process multiple assets at once.** Run, rollback, and query multiple assets with a single command. Perfect for automation and CI/CD pipelines.

### 🔍 Dependency Selection
**Run upstream or downstream dependencies.** Use `+asset_name` to run all upstream dependencies, or `asset_name+` to run the asset and all downstream dependents.

### 🤖 AI-Powered Features
**Get AI assistance for your data assets.** Use AI to explain, review, generate, and fix your `.msh` files. Includes glossary management and context-aware suggestions.

### 🔎 Auto-Discovery
**Generate `.msh` files automatically.** Probe REST APIs or SQL databases and automatically generate configuration files with inferred schemas and types.

### 📊 Data Sampling & Preview
**Preview your data before running.** Sample data from assets to verify transformations and test queries without running the full pipeline.

### 📚 Glossary Management
**Define and link business terms.** Create a shared glossary of business terms, metrics, and dimensions. Link them to assets and columns for better documentation and AI context.

### 🔒 Schema Contracts
**Control schema evolution.** Define how schemas should evolve (`freeze` or `evolve`) to prevent unexpected changes or allow controlled growth.

## Usage Examples

### Git-Aware Development
```bash
# Each developer gets isolated schemas automatically
git checkout feature/new-api
msh run                    # Uses: main_feature_new_api

git checkout bugfix/issue-123
msh run                    # Uses: main_bugfix_issue_123

# Production always uses standard schemas
msh run --env prod         # Uses: main
```

### Bulk Operations
```bash
# Run all assets
msh run --all

# Rollback multiple assets
msh rollback orders,revenue,users

# Rollback all assets
msh rollback --all

# Get JSON output for automation
msh status --format json
```

### Dependency Selection
```bash
# Run asset and all upstream dependencies
msh run +fct_orders

# Run asset and all downstream dependents
msh run fct_orders+

# Run specific asset only
msh run fct_orders
```

### Command Aliases
```bash
# All asset commands can be accessed via 'msh asset'
msh asset run orders
msh asset rollback orders
msh asset status
msh asset sample orders --size 10
msh asset versions orders
```

### AI Commands
```bash
# Explain what an asset does
msh ai explain models/orders.msh

# Review asset for risks and issues
msh ai review models/orders.msh

# Generate a new asset from description
msh ai new --name customer_metrics

# Fix a broken asset
msh ai fix models/orders.msh

# Generate tests for an asset
msh ai tests models/orders.msh

# Generate context pack for AI
msh ai context --asset orders --json
```

### Auto-Discovery
```bash
# Discover REST API and generate .msh file
msh discover https://api.github.com/repos/dlt-hub/dlt/issues --name github_issues

# Discover SQL database and generate .msh file
msh discover postgresql://user:pass@host:5432/db --name customers --table public.users

# Write to file automatically
msh discover https://api.example.com/data --name api_data --write
```

### Data Sampling
```bash
# Sample 10 rows from an asset
msh sample orders --size 10

# Sample with specific environment
msh sample orders --env prod --size 100
```

### Glossary Management
```bash
# Add a glossary term
msh glossary add-term "Customer Lifetime Value" --description "Total revenue from a customer"

# Link term to asset and column
msh glossary link-term "Customer Lifetime Value" --asset customers --column customer_id

# List all glossary terms
msh glossary list --json

# Export glossary for AI context
msh glossary export --json
```

### Schema Contracts
```yaml
# models/orders.msh
name: orders

ingest:
  type: sql_database
  source: prod_db
  table: orders

contract:
  evolution: freeze  # Prevent new columns from being added

transform: |
  SELECT * FROM {{ source }}
```

### Layered Projects (dbt-style)

Build complex DAGs with staging → intermediate → marts layers:

```yaml
# msh.yaml
sources:
  - name: prod_db
    type: sql_database
    credentials: "${DB_PROD_CREDENTIALS}"
    schema: public
    tables:
      - name: orders
      - name: customers
```

```yaml
# models/staging/stg_orders.msh
name: stg_orders
ingest:
  source: prod_db
  table: orders
transform: |
  SELECT 
    id as order_id,
    customer_id,
    amount,
    created_at
  FROM {{ source }}
```

```yaml
# models/intermediate/int_order_customer.msh
name: int_order_customer
transform: |
  SELECT 
    o.order_id,
    o.amount,
    c.name as customer_name
  FROM {{ ref('stg_orders') }} o
  JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id
```

```yaml
# models/marts/fct_orders.msh
name: fct_orders
transform: |
  SELECT 
    order_id,
    customer_name,
    amount,
    created_at
  FROM {{ ref('int_order_customer') }}
```

**Dependency Resolution:**
- Use `{{ ref('model_name') }}` to reference other `.msh` files
- msh automatically builds the DAG and runs models in correct order
- Run upstream dependencies: `msh run +fct_orders` (runs all dependencies)
- Run downstream: `msh run fct_orders+` (runs fct_orders and dependents)

## Architecture

**msh** acts as the **Control Plane** for best-in-class open source tools:
*   **Extract/Load**: Powered by **dlt** (Data Load Tool).
*   **Transform**: Powered by **dbt** (Data Build Tool).
*   **Orchestrate**: Powered by **msh-engine**.

You get the power of the ecosystem without the boilerplate.

## Installation & Quickstart

### 1. Install
```bash
pip install msh-cli
```

### 2. Initialize a Project
```bash
msh init
cd my_msh_project
```

### 3. Run the Pipeline
```bash
msh run
```

### 4. View the Dashboard
```bash
msh ui
```

## Command Reference

### Core Commands
- `msh init` - Initialize a new msh project
- `msh run [asset]` - Run assets (use `--all` for all assets)
- `msh rollback [asset]` - Rollback to previous version
- `msh status` - Show deployment status
- `msh plan` - Show execution plan without running
- `msh doctor` - Diagnose project configuration issues

### Asset Commands (Aliases)
- `msh asset run [asset]` - Run assets
- `msh asset rollback [asset]` - Rollback assets
- `msh asset status` - Show status
- `msh asset sample [asset]` - Sample data from asset
- `msh asset versions [asset]` - Show version history
- `msh asset preview [asset]` - Preview transformation SQL

### AI Commands
- `msh ai explain <asset>` - Explain what an asset does
- `msh ai review <asset>` - Review asset for risks
- `msh ai new` - Generate new asset from description
- `msh ai fix <asset>` - Fix broken asset
- `msh ai tests <asset>` - Generate tests for asset
- `msh ai context` - Generate AI context pack

### Discovery & Development
- `msh discover <source>` - Auto-discover and generate .msh file
- `msh sample <asset>` - Sample data from asset
- `msh validate` - Validate .msh file syntax
- `msh fmt` - Format .msh files

### Glossary Commands
- `msh glossary add-term <name>` - Add glossary term
- `msh glossary link-term <term> --asset <asset>` - Link term to asset
- `msh glossary list` - List all terms
- `msh glossary export` - Export glossary as JSON

### Utility Commands
- `msh ui` - Launch web dashboard
- `msh lineage` - Show asset lineage graph
- `msh manifest` - Generate project manifest
- `msh config` - Configure msh settings

## Supported Destinations

msh supports all major data warehouses and databases:

- **Snowflake** - Full support with optimized connection handling, schema sanitization, and error handling
- **PostgreSQL** - Native support with connection pooling
- **DuckDB** - Default local development database
- **BigQuery** - Google Cloud BigQuery support
- **Redshift** - Amazon Redshift support
- **MySQL** - MySQL database support
- **SQLite** - SQLite support for testing

## Configuration

### Environment Variables

For Snowflake:
```bash
# dlt / msh (Ingestion & Orchestration)
export DESTINATION__SNOWFLAKE__CREDENTIALS__DATABASE="ANALYTICS"
export DESTINATION__SNOWFLAKE__CREDENTIALS__PASSWORD="secure_password"
export DESTINATION__SNOWFLAKE__CREDENTIALS__USERNAME="MSH_USER"
export DESTINATION__SNOWFLAKE__CREDENTIALS__HOST="xyz123.snowflakecomputing.com"
export DESTINATION__SNOWFLAKE__CREDENTIALS__WAREHOUSE="COMPUTE_WH"
export DESTINATION__SNOWFLAKE__CREDENTIALS__ROLE="TRANSFORMER"

# dbt (Transformation)
export SNOWFLAKE_ACCOUNT="xyz123"
export SNOWFLAKE_USER="MSH_USER"
export SNOWFLAKE_PASSWORD="secure_password"
export SNOWFLAKE_ROLE="TRANSFORMER"
export SNOWFLAKE_DATABASE="ANALYTICS"
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
```

For PostgreSQL:
```bash
export DESTINATION__POSTGRES__CREDENTIALS="postgresql://user:pass@host:5432/db"
export POSTGRES_HOST="localhost"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="password"
export POSTGRES_DB="analytics"
```

## License

**msh** is licensed under the **Business Source License (BSL 1.1)**.
You may use this software for non-production or development purposes. Production use requires a commercial license.
