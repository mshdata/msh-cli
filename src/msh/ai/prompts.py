"""
Prompt Templates for msh AI Commands.

Contains prompt templates for explain, review, new, fix, and tests commands.
"""
from typing import Dict, Any, Optional


def get_explain_prompt(context_pack: Dict[str, Any], asset_id: str) -> str:
    """
    Generate prompt for explain command.
    
    Args:
        context_pack: Context pack dictionary
        asset_id: Asset ID to explain
        
    Returns:
        Prompt string
    """
    # Find the asset
    assets = context_pack.get("assets", [])
    asset = None
    for a in assets:
        if a.get("id") == asset_id:
            asset = a
            break
    
    if not asset:
        return f"Asset '{asset_id}' not found in context pack."
    
    # Build prompt
    prompt = f"""You are a data engineering assistant helping to explain a data asset.

Asset ID: {asset_id}
Project: {context_pack.get('project', {}).get('name', 'unknown')}

Asset Details:
- Path: {asset.get('path', 'unknown')}
- Blocks: {list(asset.get('blocks', {}).keys())}

"""
    
    # Add ingest block info
    ingest = asset.get("blocks", {}).get("ingest", {})
    if ingest:
        prompt += f"Ingest:\n"
        prompt += f"- Type: {ingest.get('type', 'unknown')}\n"
        if ingest.get("source"):
            prompt += f"- Source: {ingest.get('source')}\n"
        if ingest.get("table"):
            prompt += f"- Table: {ingest.get('table')}\n"
        prompt += "\n"
    
    # Add transform block info
    transform = asset.get("blocks", {}).get("transform", {})
    if transform:
        sql = transform.get("sql", "")
        if len(sql) > 1000:
            sql = sql[:1000] + "... (truncated)"
        prompt += f"Transform SQL:\n{sql}\n\n"
        
        dependencies = transform.get("dependencies", [])
        if dependencies:
            prompt += f"Dependencies: {', '.join(dependencies)}\n\n"
    
    # Add schema info
    schema = asset.get("schema", {})
    columns = schema.get("columns", [])
    if columns:
        prompt += f"Schema ({len(columns)} columns):\n"
        for col in columns[:10]:  # Show first 10
            prompt += f"- {col.get('name', 'unknown')}: {col.get('type', 'unknown')}\n"
        if len(columns) > 10:
            prompt += f"... ({len(columns) - 10} more columns)\n"
        prompt += "\n"
    
    # Add lineage
    lineage = context_pack.get("lineage", [])
    upstream = [e.get("from") for e in lineage if e.get("to") == asset_id]
    downstream = [e.get("to") for e in lineage if e.get("from") == asset_id]
    
    if upstream:
        prompt += f"Upstream assets: {', '.join(upstream)}\n"
    if downstream:
        prompt += f"Downstream assets: {', '.join(downstream)}\n"
    
    prompt += """
Please provide a clear, concise explanation of what this asset does:
1. What data does it ingest?
2. What transformation does it perform?
3. What is the output schema?
4. What are its dependencies?
5. What is the business purpose (if inferable)?

Format your response as JSON with the following structure:
{
  "summary": "Brief summary",
  "grain": "Data grain (e.g., daily, transaction-level)",
  "upstream_assets": ["list", "of", "upstream"],
  "downstream_assets": ["list", "of", "downstream"],
  "business_terms": ["relevant", "business", "terms"],
  "policies": ["any", "policies", "that", "or empty list]
}
"""
    
    return prompt


def get_review_prompt(context_pack: Dict[str, Any], asset_id: str) -> str:
    """
    Generate prompt for review command.
    
    Args:
        context_pack: Context pack dictionary
        asset_id: Asset ID to review
        
    Returns:
        Prompt string
    """
    # Similar structure to explain but focused on review
    prompt = f"""You are a data engineering assistant reviewing a data asset for risks and issues.

Asset ID: {asset_id}
Project: {context_pack.get('project', {}).get('name', 'unknown')}

Please review this asset and identify:
1. Performance risks (e.g., missing indexes, inefficient queries)
2. Data quality risks (e.g., missing tests, potential null issues)
3. Glossary alignment issues (e.g., columns not linked to glossary terms)
4. Best practice violations
5. Suggested improvements

Format your response as JSON:
{{
  "summary": "Overall assessment",
  "risks": ["list", "of", "risks"],
  "glossary_issues": ["list", "of", "glossary", "issues"],
  "performance_notes": ["list", "of", "performance", "notes"],
  "suggested_changes": [{{"type": "change_type", "description": "change description"}}]
}}
"""
    
    return prompt


def get_new_asset_prompt(context_pack: Dict[str, Any], description: str, asset_name: Optional[str] = None) -> str:
    """
    Generate prompt for new asset generation.
    
    Args:
        context_pack: Context pack dictionary
        description: Natural language description of the asset
        asset_name: Optional suggested asset name
        
    Returns:
        Prompt string
    """
    prompt = f"""You are a data engineering assistant generating a new msh asset.

Project: {context_pack.get('project', {}).get('name', 'unknown')}
Warehouse: {context_pack.get('project', {}).get('warehouse', 'unknown')}

User Request: {description}
"""
    
    if asset_name:
        prompt += f"Suggested Asset Name: {asset_name}\n"
    
    # Include existing assets for context
    assets = context_pack.get("assets", [])
    if assets:
        prompt += f"\nExisting Assets ({len(assets)}):\n"
        for asset in assets[:5]:  # Show first 5
            prompt += f"- {asset.get('id', 'unknown')}: {asset.get('blocks', {}).get('transform', {}).get('sql', '')[:100]}...\n"
    
    prompt += """
Generate a complete .msh file YAML that includes:
1. An ingest block (choose appropriate type: rest_api, sql_database, etc.)
2. A transform block with SQL
3. Appropriate tests
4. Contract block if needed

Return ONLY the YAML content, no markdown formatting, no explanations.
"""
    
    return prompt


def get_fix_prompt(context_pack: Dict[str, Any], asset_id: str, error_message: Optional[str] = None) -> str:
    """
    Generate prompt for fix command.
    
    Args:
        context_pack: Context pack dictionary
        asset_id: Asset ID to fix
        error_message: Optional error message
        
    Returns:
        Prompt string
    """
    prompt = f"""You are a data engineering assistant fixing a broken data asset.

Asset ID: {asset_id}
"""
    
    if error_message:
        prompt += f"Error: {error_message}\n"
    
    prompt += """
Analyze the asset and suggest fixes. Return a JSON patch (RFC 6902) with the fixes.

Format:
{
  "patches": [{
    "file_path": "path/to/asset.msh",
    "diff": "unified diff string",
    "operations": [
      {"op": "replace", "path": "/transform", "value": "fixed SQL"}
    ]
  }]
}
"""
    
    return prompt


def get_tests_prompt(context_pack: Dict[str, Any], asset_id: str) -> str:
    """
    Generate prompt for tests command.
    
    Args:
        context_pack: Context pack dictionary
        asset_id: Asset ID to generate tests for
        
    Returns:
        Prompt string
    """
    prompt = f"""You are a data engineering assistant generating tests for a data asset.

Asset ID: {asset_id}

Analyze the asset schema and suggest appropriate tests. Return a JSON patch with test additions.

Format:
{
  "suggested_tests": ["test1", "test2"],
  "patch": {{
    "patches": [{{
      "file_path": "path/to/asset.msh",
      "operations": [
        {{"op": "add", "path": "/tests/-", "value": {{"name": "test_name", "type": "test_type"}}}}
      ]
    }}]
  }}
}
"""
    
    return prompt

