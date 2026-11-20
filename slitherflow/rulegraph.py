"""Get a rule graph by running `snakemake --rulegraph` in a project."""
import shutil
import subprocess
import sys
from pathlib import Path


def rulegraph_from_project(project, snakemake="snakemake", extra=()):
    """Run `snakemake --rulegraph` in a project directory and return the DOT text."""
    exe = shutil.which(snakemake) or (snakemake if Path(snakemake).is_file() else None)
    if not exe:
        sys.exit(f"cannot find '{snakemake}': activate the environment that has Snakemake, or pass --snakemake PATH")
    project = Path(project)
    if not project.is_dir():
        sys.exit(f"project directory not found: {project}")
    cmd = [exe, "--rulegraph", "--nolock", *extra]
    print(f"running: {' '.join(cmd)}  (in {project})", file=sys.stderr)
    res = subprocess.run(cmd, cwd=project, capture_output=True, text=True)
    if res.returncode != 0 or "digraph" not in res.stdout:
        tail = "\n".join((res.stderr or res.stdout).strip().splitlines()[-15:])
        sys.exit(f"`snakemake --rulegraph` failed in {project} (exit {res.returncode}):\n{tail}\n\n"
                 "If the workflow needs a config or profile to resolve, pass it after `--`, "
                 "e.g. `-- --configfile config/test.yaml`.")
    return res.stdout[res.stdout.index("digraph"):]
