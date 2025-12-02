import click
import os
from msh.logger import logger as console

@click.command()
def init() -> None:
    """Scaffolds a new msh project."""
    cwd = os.getcwd()
    
    # Create models directory
    models_dir = os.path.join(cwd, "models")
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        
    # Create customers.msh (Source: SQL/DuckDB Generator)
    customers_msh = os.path.join(models_dir, "customers.msh")
    if not os.path.exists(customers_msh):
        with open(customers_msh, "w") as f:
            f.write("""name: customers

ingest:
  type: sql_database
  credentials: "duckdb:///msh.duckdb" # Self-referencing for demo
  table: "generate_series(1, 100) as t(id)" # DuckDB generator
  
transform: |
  SELECT 
    id, 
    'Customer ' || id as name,
    'user' || id || '@example.com' as email
  FROM {{ source }}
""")

    # Create orders.msh (Source: JSONPlaceholder API)
    orders_msh = os.path.join(models_dir, "orders.msh")
    if not os.path.exists(orders_msh):
        with open(orders_msh, "w") as f:
            f.write("""name: orders

ingest:
  type: rest_api
  config:
    client:
      base_url: "https://jsonplaceholder.typicode.com/"
    resources:
      - name: posts # Using posts as orders for demo data
        endpoint:
          path: "posts"

transform: |
  SELECT 
    id as order_id,
    userId as user_id,
    title as item_name,
    100 as amount
  FROM {{ source }}
""")

    # Create revenue.msh (Transform: Join)
    revenue_msh = os.path.join(models_dir, "revenue.msh")
    if not os.path.exists(revenue_msh):
        with open(revenue_msh, "w") as f:
            f.write("""name: revenue

# No ingest needed, purely transform

transform: |
  SELECT 
    c.name, 
    o.amount,
    o.item_name
  FROM {{ ref('customers') }} c 
  JOIN {{ ref('orders') }} o ON c.id = o.user_id
""")
    
    # Create msh.yaml
    msh_yaml = os.path.join(cwd, "msh.yaml")
    if not os.path.exists(msh_yaml):
        with open(msh_yaml, "w") as f:
            f.write("""project_name: my_msh_project

execution:
  threads: 4 # Parallel Ingest

# environments:
#   prod:
#     destination: snowflake
#     credentials: ...
""")
            
    # Create .env.example
    env_example = os.path.join(cwd, ".env.example")
    if not os.path.exists(env_example):
        with open(env_example, "w") as f:
            f.write("DESTINATION__DUCKDB__CREDENTIALS=duckdb:///msh.duckdb\\n")
            
    # Create .gitignore
    gitignore = os.path.join(cwd, ".gitignore")
    if os.path.exists(gitignore):
        with open(gitignore, "r") as f:
            content = f.read()
        if ".msh/" not in content:
            with open(gitignore, "a") as f:
                f.write("\\n.msh/\\ntarget/\\n.env\\n")
    else:
        with open(gitignore, "w") as f:
            f.write(".msh/\\ntarget/\\n.env\\n")

    # Create .dockerignore
    dockerignore = os.path.join(cwd, ".dockerignore")
    if not os.path.exists(dockerignore):
        with open(dockerignore, "w") as f:
            f.write(".git\\n.msh\\ntarget\\nvenv\\n__pycache__\\n*.pyc\\n.env\\n.DS_Store\\n")

    # Create .vscode/settings.json
    vscode_dir = os.path.join(cwd, ".vscode")
    if not os.path.exists(vscode_dir):
        os.makedirs(vscode_dir)
    
    settings_json = os.path.join(vscode_dir, "settings.json")
    if not os.path.exists(settings_json):
        with open(settings_json, "w") as f:
            f.write("""{
    "files.exclude": {
        "**/.msh": true,
        "**/target": true
    },
    "files.associations": {
        "*.msh": "yaml"
    }
}""")
            
    console.print("[bold green][OK] Initialized msh project.[/bold green]")

@click.group()
def generate() -> None:
    """Generates configuration files for automation."""
    pass

@generate.command()
def github() -> None:
    """Generates a GitHub Actions workflow."""
    cwd = os.getcwd()
    github_dir = os.path.join(cwd, ".github", "workflows")
    if not os.path.exists(github_dir):
        os.makedirs(github_dir)
        
    workflow_path = os.path.join(github_dir, "msh_schedule.yml")
    
    content = """name: msh Pipeline

on:
  schedule:
    - cron: '0 * * * *' # Hourly
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install msh
        run: |
          pip install msh-cli msh-engine
          
      - name: Run msh
        env:
          # Add your secrets here
          # DESTINATION__SNOWFLAKE__CREDENTIALS: ${{ secrets.SNOWFLAKE_CREDS }}
          MSH_ENV: prod
        run: msh run --env prod
"""
    with open(workflow_path, "w") as f:
        f.write(content)
        
    console.print(f"[bold green]Generated GitHub Actions workflow at {workflow_path}[/bold green]")
    console.print("[yellow]Remember to add your secrets to GitHub Settings![/yellow]")

@generate.command()
def airflow() -> None:
    """Generates an Airflow DAG."""
    cwd = os.getcwd()
    dags_dir = os.path.join(cwd, "dags")
    if not os.path.exists(dags_dir):
        os.makedirs(dags_dir)
        
    dag_path = os.path.join(dags_dir, "msh_pipeline.py")
    
    content = """from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG('msh_pipeline', 
         start_date=datetime(2023, 1, 1), 
         schedule_interval='@hourly', 
         catchup=False) as dag:
         
    run_msh = BashOperator(
        task_id='run_msh',
        bash_command='msh run --env prod'
    )
"""
    with open(dag_path, "w") as f:
        f.write(content)
        
    console.print(f"[bold green]Generated Airflow DAG at {dag_path}[/bold green]")
