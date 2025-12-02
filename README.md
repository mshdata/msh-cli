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

## License

**msh** is licensed under the **Business Source License (BSL 1.1)**.
You may use this software for non-production or development purposes. Production use requires a commercial license.
