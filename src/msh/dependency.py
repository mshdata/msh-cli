import jinja2
from jinja2 import nodes
from typing import List, Dict, Any, Optional
from rich.console import Console
from msh.logger import logger as console_logger

class DependencyResolver:
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console: Console = console or Console()
        self.env: jinja2.Environment = jinja2.Environment()

    def resolve(self, execution_plan: List[Dict[str, Any]], selector: str) -> List[Dict[str, Any]]:
        """
        Filters the execution plan based on the asset selector (+asset, asset+, asset).
        """
        # Build Graph
        asset_map = {asset["name"]: asset for asset in execution_plan}
        upstreams = {asset["name"]: set() for asset in execution_plan}
        downstreams = {asset["name"]: set() for asset in execution_plan}
        
        # Re-build upstreams list properly using Jinja2 AST
        for asset in execution_plan:
            name = asset["name"]
            sql = asset.get("raw_sql", "")
            try:
                ast = self.env.parse(sql)
                # Find all function calls
                for call in ast.find_all(nodes.Call):
                    # Check if the call is to 'ref'
                    if isinstance(call.node, nodes.Name) and call.node.name == 'ref':
                        # Extract arguments
                        # ref('model') or ref('package', 'model')
                        # The model name is the last argument
                        if call.args:
                            # Assuming string literals for now
                            last_arg = call.args[-1]
                            if isinstance(last_arg, nodes.Const):
                                ref_name = last_arg.value
                                if ref_name in asset_map:
                                    upstreams[name].add(ref_name)
                                    downstreams[ref_name].add(name)
            except Exception as e:
                # If parsing fails (e.g. invalid Jinja), log warning but continue
                # This allows the pipeline to proceed even if dependency resolution fails
                console_logger.warning(f"Failed to parse SQL for asset '{name}' (dependency resolution may be incomplete): {e}")
                pass

        # Parse Selector
        target_assets = set()
        
        if selector.startswith("+"):
            # Upstreams
            base_name = selector[1:]
            if base_name not in asset_map:
                return []
            
            queue = [base_name]
            visited = set()
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                target_assets.add(current)
                for up in upstreams[current]:
                    queue.append(up)
                    
        elif selector.endswith("+"):
            # Downstreams
            base_name = selector[:-1]
            if base_name not in asset_map:
                return []
                
            queue = [base_name]
            visited = set()
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                target_assets.add(current)
                for down in downstreams[current]:
                    queue.append(down)
        else:
            # Single Asset
            if selector in asset_map:
                target_assets.add(selector)
            else:
                return []

        # Filter and Sort (Topological Sort)
        filtered_plan = [asset for asset in execution_plan if asset["name"] in target_assets]
        
        sorted_plan = []
        visited = set()
        
        def visit(name):
            if name in visited:
                return
            if name not in target_assets:
                return
            
            for up in upstreams[name]:
                if up in target_assets:
                    visit(up)
            
            visited.add(name)
            sorted_plan.append(asset_map[name])
            
        for asset in filtered_plan:
            visit(asset["name"])
            
        return sorted_plan
