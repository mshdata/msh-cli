import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from sqlalchemy.engine import Engine

from msh.logger import logger as console
from msh.compiler import MshCompiler
from msh_engine.lifecycle import StateManager
from msh_engine.db_utils import get_connection_engine
from msh.managers import IngestManager, TransformManager
from msh.catalog import CatalogGenerator
from msh.dependency import DependencyResolver
from msh.utils.config import load_msh_config, get_target_schema, get_raw_dataset

from msh.constants import (
    DEFAULT_BUILD_DIR, DEFAULT_DESTINATION,
    DEFAULT_RAW_DATASET
)

class Orchestrator:
    def __init__(
        self, 
        env: str, 
        debug: bool, 
        dry_run: bool, 
        deploy: bool = True, 
        asset_selector: Optional[str] = None
    ) -> None:
        self.cwd: str = os.getcwd()
        self.env: str = env
        self.debug: bool = debug
        self.dry_run: bool = dry_run
        self.deploy: bool = deploy
        self.asset_selector: Optional[str] = asset_selector
        self.console: Console = Console()
        
        self.build_dir: str = os.path.join(self.cwd, DEFAULT_BUILD_DIR)
        
        # Load Config
        self.msh_config: Dict[str, Any] = load_msh_config(self.cwd)
        self.dest: str = self.msh_config.get("destination", DEFAULT_DESTINATION)
        
        # Determine Target Schema and Raw Dataset with git-aware suffixes in dev
        self.target_schema: str = get_target_schema(self.dest, self.msh_config, self.env)
        self.raw_dataset: str = get_raw_dataset(self.msh_config, self.env)
                
        # Initialize State Manager
        self.state_manager: StateManager = StateManager(
            destination=self.dest,
            dataset_name="msh_meta"
        )
        
        self.threads: int = self.msh_config.get("execution", {}).get("threads", 1)
            
        # DuckDB Safety Lock
        if self.dest == "duckdb" and self.threads > 1:
            self.console.print("[bold yellow][WARN] DuckDB does not support parallel writes. Forcing threads=1.[/bold yellow]")
            self.threads = 1
            
        # Connect
        try:
            self.engine: Engine = get_connection_engine(self.dest)
        except Exception as e:
            console.print(f"[bold red]Failed to connect to destination '{self.dest}': {e}[/bold red]")
            raise e

        # Initialize Helpers
        self.catalog_generator: CatalogGenerator = CatalogGenerator(self.cwd, self.build_dir, self.console)
        self.dependency_resolver: DependencyResolver = DependencyResolver(self.console)

    def run(self) -> None:
        if self.dry_run:
            console.print(f"[bold yellow]DRY RUN MODE: Simulating execution for env: {self.env}...[/bold yellow]")
        elif not self.deploy:
            console.print(f"[bold blue]PREVIEW MODE: Running pipeline without deployment for env: {self.env}...[/bold blue]")
        else:
            console.print(f"[bold blue]Weaving data (Blue/Green) for env: {self.env}...[/bold blue]")
            
        # 1. Compile
        compiler = MshCompiler(self.build_dir, self.msh_config, self.env)
        execution_plan = self._compile(compiler)
        if not execution_plan:
            return

        # 1.5 Filter Execution Plan based on Asset Selector
        if self.asset_selector:
            # Validate selector is not empty
            selector = self.asset_selector.strip() if isinstance(self.asset_selector, str) else str(self.asset_selector)
            if not selector:
                console.print(f"[bold red][ERROR][/bold red] Orchestrator: Empty asset selector provided.")
                return
            
            execution_plan = self.dependency_resolver.resolve(execution_plan, selector)
            if not execution_plan:
                console.print(f"[bold red]No assets found matching selector: {selector}[/bold red]")
                return
            console.print(f"[bold cyan]Selected {len(execution_plan)} assets to run.[/bold cyan]")

        # 2. Ingest
        ingest_manager = IngestManager(
            engine=self.engine,
            threads=self.threads,
            dry_run=self.dry_run,
            debug=self.debug,
            raw_dataset=self.raw_dataset,
            dest=self.dest,
            cwd=self.cwd,
            build_dir=self.build_dir,
            env=self.env,
            target_schema=self.target_schema
        )
        ingest_manager.run_phase(execution_plan)
        
        # 3. Transform & Swap
        transform_manager = TransformManager(
            engine=self.engine,
            dry_run=self.dry_run,
            debug=self.debug,
            deploy=self.deploy,
            target_schema=self.target_schema,
            raw_dataset=self.raw_dataset,
            build_dir=self.build_dir,
            env=self.env,
            state_manager=self.state_manager,
            cwd=self.cwd
        )
        transform_manager.run_phase(execution_plan)
        
        console.print("Done!")
        
        # 4. Catalog
        self.catalog_generator.generate(execution_plan)

    def _compile(self, compiler: MshCompiler) -> Optional[List[Dict[str, Any]]]:
        # Clean legacy
        legacy_artifacts = ["dbt_project.yml", "profiles.yml"]
        for artifact in legacy_artifacts:
            if os.path.exists(os.path.join(self.cwd, artifact)):
                console.print(f"[bold yellow][WARNING] Found legacy artifact in root: {artifact}[/bold yellow]")
        
        # Gitignore
        gitignore_path = os.path.join(self.cwd, ".gitignore")
        try:
            if os.path.exists(gitignore_path):
                with open(gitignore_path, "r") as f:
                    if ".msh/" not in f.read():
                        with open(gitignore_path, "a") as f2:
                            f2.write("\n.msh/\n")
            else:
                with open(gitignore_path, "w") as f:
                    f.write(".msh/\n")
        except (IOError, PermissionError) as e:
            console.print(f"[yellow][WARNING] Could not update .gitignore: {e}[/yellow]")

        # Scan
        models_path = os.path.join(self.cwd, "models")
        search_path = Path(models_path) if os.path.exists(models_path) else Path(self.cwd)
        msh_files = [f for f in search_path.glob("*.msh") if f.is_file()]
        
        if not msh_files:
            console.print(f"[yellow]No .msh files found.[/yellow]")
            console.print(f"[dim]Tip: Create assets in the 'models/' directory or run 'msh create asset <name>' to scaffold a new asset.[/dim]")
            return None
            
        console.print(f"Found {len(msh_files)} .msh files.")
        
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
            
        compiler.generate_dbt_artifacts()
        
        execution_plan = []
        for file_path in msh_files:
            try:
                asset_data, content_hash = compiler.parse(file_path)
                metadata = compiler.compile_model(asset_data, content_hash)
                metadata["ingest"] = asset_data.get("ingest")
                metadata["file_path"] = str(file_path.absolute())
                execution_plan.append(metadata)
            except Exception as e:
                console.print(f"[bold red][ERROR][/bold red] Compile: Failed to compile {file_path}: {e}")
                console.print(f"[yellow]Tip: Check the YAML syntax and ensure all required fields are present. Run 'msh validate' for detailed validation.[/yellow]")
                continue
                
        compiler.generate_sources_yml(execution_plan)
        compiler.generate_schema_yml(execution_plan)
        compiler.generate_exposures_yml(execution_plan)
        
        return execution_plan
