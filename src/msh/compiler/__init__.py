"""
msh compiler module.

Provides MshCompiler class that composes parser, dbt generator, artifacts writer, and model compiler.
"""
import os
from typing import Optional, List, Dict, Any, Tuple, Union
from pathlib import Path

from msh.constants import DEFAULT_RAW_DATASET, DEFAULT_DESTINATION

from msh.compiler.parser import MshParser
from msh.compiler.dbt_generator import DbtArtifactGenerator
from msh.compiler.artifacts import DbtArtifactWriter
from msh.compiler.model import ModelCompiler


class MshCompiler:
    """
    Main compiler class that composes all compiler modules.
    
    Maintains backward compatibility with the original API.
    """
    
    def __init__(
        self, 
        build_dir: str, 
        msh_config: Optional[Dict[str, Any]] = None,
        env: str = "dev"
    ) -> None:
        """
        Initialize the compiler.
        
        Args:
            build_dir: Directory where build artifacts will be written
            msh_config: Optional configuration dictionary from msh.yaml
            env: Environment name ('dev' or 'prod'). Defaults to 'dev'.
        """
        self.build_dir: str = build_dir
        self.models_dir: str = os.path.join(build_dir, "models")
        self.msh_config: Dict[str, Any] = msh_config or {}
        self.env: str = env
        
        self.destination: str = self.msh_config.get("destination", DEFAULT_DESTINATION)
        self.raw_dataset: str = self.msh_config.get("raw_dataset", DEFAULT_RAW_DATASET)
        
        # Initialize sub-modules
        self.parser = MshParser(msh_config=self.msh_config)
        self.dbt_generator = DbtArtifactGenerator(
            self.build_dir, 
            self.models_dir, 
            self.msh_config,
            self.env
        )
        self.artifacts_writer = DbtArtifactWriter(
            self.models_dir,
            self.raw_dataset
        )
        # Determine project root (parent of .msh directory, which is parent of build_dir)
        # build_dir is typically .msh/build, so project_root is parent of .msh
        project_root = os.path.dirname(os.path.dirname(build_dir))
        # If build_dir doesn't follow expected structure, try parent of build_dir
        if not os.path.exists(os.path.join(project_root, "msh.yaml")):
            project_root = os.path.dirname(build_dir)
        
        self.model_compiler = ModelCompiler(
            self.models_dir,
            self.raw_dataset,
            msh_config=self.msh_config,
            project_root=project_root
        )
    
    def parse(self, file_path: Union[str, Path]) -> Tuple[Dict[str, Any], str]:
        """
        Reads YAML and separates ingest/transform.
        
        Delegates to MshParser.
        
        Args:
            file_path: Path to the .msh file
            
        Returns:
            Tuple of (parsed_data, content_hash)
        """
        return self.parser.parse_file(file_path)
    
    def extract_columns(self, sql: str) -> Optional[List[str]]:
        """
        Smart Ingest: Uses sqlglot to find columns in SELECT ... FROM {{ source }}
        
        Delegates to MshParser.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of column names, or None if extraction fails
        """
        return self.parser.extract_columns(sql)
    
    def generate_dbt_artifacts(self) -> None:
        """
        Generates dbt_project.yml and profiles.yml.
        
        Delegates to DbtArtifactGenerator.
        """
        self.dbt_generator.generate_all()
    
    def compile_model(self, asset: Dict[str, Any], content_hash: str) -> Dict[str, Any]:
        """
        Generates the SQL model for Blue/Green deployment.
        
        Delegates to ModelCompiler.
        
        Args:
            asset: Asset data dictionary
            content_hash: Content hash for versioning
            
        Returns:
            Dictionary containing compiled model metadata
        """
        return self.model_compiler.compile(
            asset, 
            content_hash,
            self.extract_columns
        )
    
    def generate_sources_yml(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/sources.yml for full lineage.
        
        Delegates to DbtArtifactWriter.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        self.artifacts_writer.write_sources(execution_plan)
    
    def generate_schema_yml(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/schema.yml for Atomic Quality (dbt tests).
        
        Delegates to DbtArtifactWriter.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        self.artifacts_writer.write_schema(execution_plan)
    
    def generate_exposures_yml(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/exposures.yml for Lineage (BI Dashboards).
        
        Delegates to DbtArtifactWriter.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        self.artifacts_writer.write_exposures(execution_plan)

