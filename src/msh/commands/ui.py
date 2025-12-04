import click
import os
import json
import subprocess
import http.server
import socketserver
from typing import Optional, Dict, Any
from msh.logger import logger as console

@click.command()
@click.option('--port', default=3000, help='Port to serve the UI on.')
def ui(port: int) -> None:
    """Serves the msh UI dashboard."""
    cwd = os.getcwd()
    ui_dir = os.path.join(cwd, ".msh", "ui")
    
    # Ensure UI dir exists (user drops build here)
    if not os.path.exists(ui_dir):
        os.makedirs(ui_dir)
        # Create a dummy index.html if empty
        with open(os.path.join(ui_dir, "index.html"), "w") as f:
            f.write("<h1>msh Dashboard</h1><p>Drop your React build here.</p>")
            
    # Custom Handler to serve catalog and stream logs
    class MshHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ui_dir, **kwargs)
        
        def guess_type(self, path: str) -> str:
            """Override to add .jsx MIME type support."""
            if path.endswith('.jsx'):
                return 'text/javascript'
            return super().guess_type(path)
            
        def do_GET(self) -> None:
            if self.path == "/api/catalog.json":
                catalog_path = os.path.join(cwd, ".msh", "msh_catalog.json")
                if os.path.exists(catalog_path):
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    with open(catalog_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, "Catalog not found")
            
            elif self.path == "/api/quality.json":
                # Aggregate quality metrics from test results
                test_results_file = os.path.join(cwd, ".msh", "test_results.json")
                quality_data: Dict[str, Any] = {
                    "overall": {
                        "total_tests": 0,
                        "passed": 0,
                        "failed": 0,
                        "pass_rate": 0.0
                    },
                    "assets": []
                }
                
                if os.path.exists(test_results_file):
                    try:
                        with open(test_results_file, "r") as f:
                            all_results = json.load(f)
                        
                        total_tests = 0
                        total_passed = 0
                        total_failed = 0
                        
                        for asset_name, results in all_results.items():
                            summary = results.get("summary", {})
                            asset_total = summary.get("total", 0)
                            asset_passed = summary.get("passed", 0)
                            asset_failed = summary.get("failed", 0)
                            
                            total_tests += asset_total
                            total_passed += asset_passed
                            total_failed += asset_failed
                            
                            pass_rate = asset_passed / asset_total if asset_total > 0 else 0.0
                            
                            quality_data["assets"].append({
                                "name": asset_name,
                                "tests": results.get("tests", []),
                                "last_run": results.get("timestamp"),
                                "summary": {
                                    "total": asset_total,
                                    "passed": asset_passed,
                                    "failed": asset_failed,
                                    "pass_rate": pass_rate
                                }
                            })
                        
                        # Calculate overall metrics
                        quality_data["overall"]["total_tests"] = total_tests
                        quality_data["overall"]["passed"] = total_passed
                        quality_data["overall"]["failed"] = total_failed
                        quality_data["overall"]["pass_rate"] = total_passed / total_tests if total_tests > 0 else 0.0
                        
                    except (json.JSONDecodeError, IOError, OSError) as e:
                        # Log error but return empty structure
                        console.debug(f"Failed to load test results for quality API: {e}")
                        pass
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(quality_data, indent=2).encode('utf-8'))
            
            elif self.path.startswith("/api/stream/run"):
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                asset_name = query.get('asset', [None])[0]
                
                if not asset_name:
                    self.send_error(400, "Missing asset parameter")
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                try:
                    # Run msh run <asset> --force-color
                    process = subprocess.Popen(
                        ["msh", "run", asset_name, "--force-color"],
                        cwd=cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1  # Line buffered
                    )

                    for line in process.stdout:
                        # Format as SSE data
                        data = f"data: {line}"
                        self.wfile.write(data.encode('utf-8'))
                        self.wfile.flush()
                    
                    process.wait()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()

                except Exception as e:
                    console.print(f"[red]Error streaming logs: {e}[/red]")
                    self.wfile.write(f"data: Error: {str(e)}\n\n".encode('utf-8'))
            
            else:
                super().do_GET()

    console.print(f"[bold green][OK] Dashboard running at http://localhost:{port}[/bold green]")
    
    # Use ThreadingHTTPServer for concurrent requests (UI + SSE)
    # Allow socket reuse to avoid "Address already in use" errors
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    
    with http.server.ThreadingHTTPServer(("", port), MshHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

@click.command()
@click.option('--debug', is_flag=True, help='Enable debug mode to see dbt logs.')
def lineage(debug: bool) -> None:
    """Generates and serves project documentation (dbt docs)."""
    cwd = os.getcwd()
    build_dir = os.path.join(cwd, ".msh", "build")
    
    if not os.path.exists(build_dir):
        console.print("[bold red]Build directory not found. Run 'msh run' first.[/bold red]")
        return

    console.print("[bold blue]Generating documentation...[/bold blue]")
    try:
        dbt_args = ["dbt", "docs", "generate", "--project-dir", build_dir, "--profiles-dir", build_dir]
        if not debug:
            # Suppress dbt's own output in normal mode
            dbt_args.append("--quiet")
        subprocess.run(
            dbt_args,
            check=True,
            capture_output=not debug
        )
        
        console.print("[bold blue]Serving documentation...[/bold blue]")
        # docs serve doesn't support --quiet, but we can still capture output
        subprocess.run(
            ["dbt", "docs", "serve", "--project-dir", build_dir, "--profiles-dir", build_dir],
            check=True,
            capture_output=not debug
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red][ERROR][/bold red] Documentation: Generation failed")
        if debug:
            console.print(f"[dim]Return code: {e.returncode}[/dim]")
            if e.stdout:
                console.print(f"[dim]dbt stdout:[/dim]\n{e.stdout.decode('utf-8', errors='replace')}")
            if e.stderr:
                console.print(f"[dim]dbt stderr:[/dim]\n{e.stderr.decode('utf-8', errors='replace')}")
            if not e.stdout and not e.stderr:
                console.print(f"[dim]Error details: {str(e)}[/dim]")
        elif not debug:
            if e.returncode == 2: # Compilation Error
                console.print("[bold red][ERROR][/bold red] Documentation: Compilation Error. Check your SQL references.")
                console.print("[yellow]Ensure you are using {{ ref('asset_name') }} correctly.[/yellow]")
            else:
                console.print("[bold red][ERROR][/bold red] Documentation: Generation failed. Run with --debug for details.")
