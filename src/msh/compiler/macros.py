"""
Macro loading and compilation module for msh compiler.

Handles loading SQL macros from macros/ directory and compiling them for use in Jinja2 templates.
"""
import os
import jinja2
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from msh.logger import logger as console


def load_macros(project_root: str, jinja_env: Optional[jinja2.Environment] = None) -> Dict[str, Callable]:
    """
    Loads all macros from macros/ directory.
    
    Scans the macros/ directory for .sql files, parses macro definitions,
    and compiles them into callable functions.
    
    Args:
        project_root: Root directory of msh project
        
    Returns:
        Dictionary mapping macro names to compiled macro functions
    """
    macros_dir = os.path.join(project_root, "macros")
    
    if not os.path.exists(macros_dir):
        return {}
    
    if not os.path.isdir(macros_dir):
        console.warning(f"macros/ exists but is not a directory, skipping macro loading")
        return {}
    
    macros = {}
    
    # Scan for .sql files in macros directory
    for file_path in Path(macros_dir).glob("*.sql"):
        try:
            file_macros = parse_macro_file(file_path, jinja_env)
            macros.update(file_macros)
        except Exception as e:
            console.warning(f"Failed to parse macros from {file_path.name}: {e}")
            continue
    
    if macros:
        console.debug(f"Loaded {len(macros)} macros from {macros_dir}")
    
    return macros


def parse_macro_file(file_path: Path, jinja_env: Optional[jinja2.Environment] = None) -> Dict[str, Callable]:
    """
    Parses a macro file and extracts macro definitions.
    
    Args:
        file_path: Path to macro file
        
    Returns:
        Dictionary mapping macro names to compiled macro functions
        
    Raises:
        ValueError: If macro file has syntax errors
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if not content.strip():
        return {}
    
    # Use provided environment or create a new one for parsing
    if jinja_env is None:
        env = jinja2.Environment(loader=jinja2.BaseLoader())
    else:
        env = jinja_env
    
    try:
        # Parse the template to extract macro nodes
        template = env.parse(content)
    except jinja2.TemplateSyntaxError as e:
        raise ValueError(f"Syntax error in macro file {file_path.name}: {e}")
    
    macros = {}
    
    # Find all macro nodes in the parsed template
    for node in template.find_all(jinja2.nodes.Macro):
        macro_name = node.name
        
        # Check for duplicate macro names
        if macro_name in macros:
            console.warning(
                f"Macro '{macro_name}' defined multiple times. "
                f"Last definition in {file_path.name} will be used."
            )
        
        # Compile macro into callable function
        try:
            compiled_macro = compile_macro(node, env, file_path, jinja_env)
            macros[macro_name] = compiled_macro
        except Exception as e:
            console.warning(f"Failed to compile macro '{macro_name}' from {file_path.name}: {e}")
            continue
    
    return macros


def compile_macro(
    macro_node: jinja2.nodes.Macro, 
    env: jinja2.Environment,
    file_path: Path,
    target_env: Optional[jinja2.Environment] = None
) -> Callable:
    """
    Compiles a Jinja2 macro node into a callable function.
    
    Args:
        macro_node: Jinja2 macro node
        env: Jinja2 environment
        file_path: Path to the macro file (needed to extract source)
        
    Returns:
        Callable macro function that can be used in Jinja2 templates
    """
    macro_name = macro_node.name
    
    # Read the file to get macro source
    with open(file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    
    # Extract the macro definition from the file
    # Find the macro block for this macro name
    macro_start = file_content.find(f"{{% macro {macro_name}")
    if macro_start == -1:
        raise ValueError(f"Could not find macro '{macro_name}' definition in {file_path}")
    
    # Find the matching {% endmacro %}
    macro_end = file_content.find("{% endmacro %}", macro_start)
    if macro_end == -1:
        raise ValueError(f"Could not find end of macro '{macro_name}' in {file_path}")
    
    # Extract macro definition (include the {% endmacro %})
    macro_end += len("{% endmacro %}")
    macro_def = file_content[macro_start:macro_end]
    
    # Create a function factory that captures the macro definition
    # Use target_env if provided (so macros can call other macros and use var())
    def create_macro_function(macro_source: str, name: str, path: str, env_to_use: Optional[jinja2.Environment] = None):
        def macro_func(*args, **kwargs):
            """
            Macro function that renders the macro with given arguments.
            """
            # Build call string with proper escaping
            call_parts = []
            
            # Handle positional arguments
            for arg in args:
                if isinstance(arg, str):
                    # Escape single quotes and wrap in quotes
                    escaped = arg.replace("'", "\\'").replace("\\", "\\\\")
                    call_parts.append(f"'{escaped}'")
                else:
                    call_parts.append(str(arg))
            
            # Handle keyword arguments
            for key, value in kwargs.items():
                if isinstance(value, str):
                    escaped = value.replace("'", "\\'").replace("\\", "\\\\")
                    call_parts.append(f"{key}='{escaped}'")
                else:
                    call_parts.append(f"{key}={value}")
            
            call_str = ", ".join(call_parts)
            
            # Create template with macro definition and call
            template_str = f"{macro_source}\n{{{{ {name}({call_str}) }}}}"
            
            # Use provided environment (which has other macros and var()) or create new one
            if env_to_use:
                # Use the same environment so macros can call other macros and use var()
                temp_env = env_to_use
            else:
                temp_env = jinja2.Environment(loader=jinja2.BaseLoader())
            
            template = temp_env.from_string(template_str)
            
            try:
                return template.render()
            except Exception as e:
                raise ValueError(f"Error rendering macro '{name}' from {path}: {e}")
        
        return macro_func
    
    return create_macro_function(macro_def, macro_name, str(file_path), target_env)

