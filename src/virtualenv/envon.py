from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

try:
    from virtualenv.run.plugin.base import PluginLoader
except ImportError:
    # Fallback if plugin system not available
    PluginLoader = None

try:  # version info for managed bootstrap tagging
    from virtualenv.version import __version__ as VENV_VERSION
except Exception:  # pragma: no cover - defensive fallback
    VENV_VERSION = "unknown"


PREFERRED_NAMES = (".venv", "venv", "env", ".env")


class EnvonError(Exception):
    pass


def is_venv_dir(path: Path) -> bool:
    """Return True if the given path looks like a Python virtual environment directory."""
    if not path or not path.is_dir():
        return False
    
    # Check for pyvenv.cfg file - this is the most reliable indicator
    if (path / "pyvenv.cfg").exists():
        return True
    
    # Try to use virtualenv's activation system to detect available scripts
    if PluginLoader:
        try:
            activators = PluginLoader.entry_points_for("virtualenv.activate")
            # Check if any activation scripts exist
            for activator_name in ["bash", "batch", "powershell", "fish", "cshell", "nushell"]:
                if activator_name in activators:
                    # Check common script locations based on platform
                    if activator_name == "bash" and (path / "bin" / "activate").exists():
                        return True
                    if activator_name == "batch" and (path / "Scripts" / "activate.bat").exists():
                        return True
                    if activator_name == "powershell" and (path / "Scripts" / "Activate.ps1").exists():
                        return True
                    if activator_name == "fish" and (path / "bin" / "activate.fish").exists():
                        return True
                    if activator_name == "cshell" and (path / "bin" / "activate.csh").exists():
                        return True
                    if activator_name == "nushell" and (path / "bin" / "activate.nu").exists():
                        return True
        except Exception:
            # Fall back to hardcoded detection
            pass
    
    # Fallback: hardcoded detection for compatibility
    # Windows layout
    if (path / "Scripts" / "activate.bat").exists() or (path / "Scripts" / "Activate.ps1").exists():
        return True
    # POSIX layout
    if (path / "bin" / "activate").exists():
        return True
    # Other shells
    if (path / "bin" / "activate.fish").exists() or (path / "bin" / "activate.csh").exists() or (path / "bin" / "activate.nu").exists():
        return True
    return False


def find_nearest_venv(start: Path) -> Path | None:
    """Walk upwards from start to root and try common names; return the first venv path found."""
    cur = start
    tried: list[Path] = []
    while True:
        for name in PREFERRED_NAMES:
            cand = cur / name
            tried.append(cand)
            if is_venv_dir(cand):
                return cand
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None


def _list_venvs_in_dir(root: Path) -> list[Path]:
    """Return all virtualenv directories directly under root.

    Preference order: common names first (PREFERRED_NAMES) in that order, then any other subdirectory
    that looks like a venv in alphabetical order.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for name in PREFERRED_NAMES:
        cand = root / name
        if is_venv_dir(cand):
            found.append(cand)
            seen.add(cand)
    # Scan all subdirectories
    try:
        for child in sorted([p for p in root.iterdir() if p.is_dir()]):
            if child in seen:
                continue
            if is_venv_dir(child):
                found.append(child)
    except FileNotFoundError:
        pass
    return found


def _choose_interactively(candidates: list[Path], context: str) -> Path:
    """Prompt the user to choose a venv when multiple are found.

    If stdin is not a TTY, print options and raise EnvonError.
    """
    if not sys.stdin.isatty():
        lines = "\n".join(f"  {i+1}) {p}" for i, p in enumerate(candidates))
        raise EnvonError(
            f"Multiple virtual environments found in {context}. Choose one by passing a path or name:\n{lines}"
        )
    print(f"Multiple virtual environments found in {context}:", file=sys.stderr)
    for i, p in enumerate(candidates, 1):
        print(f"  {i}) {p}", file=sys.stderr)
    while True:
        # Print prompt to stderr so command substitution doesn't capture it
        sys.stderr.write("Select [1-{}]: ".format(len(candidates)))
        sys.stderr.flush()
        try:
            sel = sys.stdin.readline()
        except Exception:
            raise EnvonError("Aborted.")
        if not sel:
            raise EnvonError("Aborted.")
        sel = sel.strip()
        if not sel:
            continue
        if sel.isdigit():
            idx = int(sel)
            if 1 <= idx <= len(candidates):
                return candidates[idx - 1]
        print("Invalid selection.", file=sys.stderr)


def resolve_target(target: str | None) -> Path:
    if not target:
        # First, prefer venvs directly in the current directory; if multiple, ask.
        cwd = Path.cwd()
        in_here = _list_venvs_in_dir(cwd)
        if len(in_here) == 1:
            return in_here[0]
        if len(in_here) > 1:
            return _choose_interactively(in_here, str(cwd))
        # Fallback to walking upwards to find a named venv (e.g., project/.venv)
        venv = find_nearest_venv(cwd)
        if not venv:
            raise EnvonError("No virtual environment found here. Create one (e.g., '.venv') or pass a path.")
        return venv

    p = Path(target)
    if p.exists():
        if p.is_dir() and is_venv_dir(p):
            return p
        # Allow passing project root; try common children
        multiple = _list_venvs_in_dir(p)
        if len(multiple) == 1:
            return multiple[0]
        if len(multiple) > 1:
            return _choose_interactively(multiple, str(p))
        raise EnvonError(f"Path does not appear to contain a virtual environment: {p}")

    # Fallback: WORKON_HOME name
    workon = os.environ.get("WORKON_HOME")
    if workon:
        cand = Path(workon) / target
        if is_venv_dir(cand):
            return cand
    raise EnvonError(f"Cannot resolve virtual environment from argument: {target}")


def detect_shell(explicit: str | None) -> str:
    if explicit:
        return explicit.lower()

    # Heuristics by platform/env
    if os.name == "nt":
        # Prefer powershell if detected
        parent_proc = os.environ.get("PSModulePath") or os.environ.get("PROMPT")
        if parent_proc and "PSModulePath" in os.environ:
            return "powershell"
        return "cmd"
    # POSIX
    shell = os.environ.get("SHELL", "").lower()
    if "fish" in shell:
        return "fish"
    if "csh" in shell or "tcsh" in shell:
        return "cshell"
    if "nu" in shell or "nushell" in shell:
        return "nushell"
    return "bash"


def emit_activation(venv: Path, shell: str) -> str:
    """Generate activation command using virtualenv's activation plugin system."""
    shell = shell.lower()
    
    # Map shell names to activator entry point names
    shell_to_activator = {
        "bash": "bash",
        "zsh": "bash",  # zsh uses bash activator
        "sh": "bash",   # sh uses bash activator
        "fish": "fish",
        "csh": "cshell",
        "tcsh": "cshell",
        "cshell": "cshell",
        "nu": "nushell",
        "nushell": "nushell",
        "powershell": "powershell",
        "pwsh": "powershell",
        "cmd": "batch",
        "batch": "batch",
        "bat": "batch",
    }
    
    activator_name = shell_to_activator.get(shell)
    if not activator_name:
        raise EnvonError(f"Unsupported shell: {shell}")
    
    # Try to use the plugin system to get proper script names
    if PluginLoader:
        try:
            activators = PluginLoader.entry_points_for("virtualenv.activate")
            if activator_name in activators:
                activator_class = activators[activator_name]
                
                # Create a minimal mock creator to get script names
                class MockCreator:
                    def __init__(self, venv_path):
                        self.dest = venv_path
                        if (venv_path / "Scripts").exists():  # Windows
                            self.bin_dir = venv_path / "Scripts"
                        else:  # POSIX
                            self.bin_dir = venv_path / "bin"
                
                mock_creator = MockCreator(venv)
                
                # Try to determine activation script name from the activator
                try:
                    # Create a temporary activator instance with minimal options
                    class MockOptions:
                        prompt = None
                    
                    activator = activator_class(MockOptions())
                    
                    # Get the templates to determine script names
                    if hasattr(activator, 'templates'):
                        for template in activator.templates():
                            if hasattr(activator, 'as_name'):
                                script_name = activator.as_name(template)
                            else:
                                script_name = template
                            
                            script_path = mock_creator.bin_dir / script_name
                            if script_path.exists():
                                return _generate_activation_command(script_path, shell)
                except Exception:
                    # Fall back to hardcoded approach if activator instantiation fails
                    pass
        except Exception:
            # Fall back to hardcoded paths if plugin system fails
            pass
    
    # Fallback: Use hardcoded script detection
    return _emit_activation_fallback(venv, shell)


def _generate_activation_command(script_path: Path, shell: str) -> str:
    """Generate the appropriate activation command for the given script and shell."""
    shell = shell.lower()
    
    if shell in {"bash", "zsh", "sh"}:
        return f". '{script_path.as_posix()}'"
    elif shell == "fish":
        return f"source '{script_path.as_posix()}'"
    elif shell in {"csh", "tcsh", "cshell"}:
        return f"source '{script_path.as_posix()}'"
    elif shell in {"nu", "nushell"}:
        return f"overlay use '{script_path.as_posix()}'"
    elif shell in {"powershell", "pwsh"}:
        return f". '{script_path.as_posix()}'"
    elif shell in {"cmd", "batch", "bat"}:
        return f"call \"{script_path}\""
    
    raise EnvonError(f"Unknown shell command format for: {shell}")


def _emit_activation_fallback(venv: Path, shell: str) -> str:
    """Fallback activation detection using hardcoded paths."""
    shell = shell.lower()
    
    if shell in {"bash", "zsh", "sh"}:
        act = venv / "bin" / "activate"
        if act.exists():
            return f". '{act.as_posix()}'"
    elif shell == "fish":
        act = venv / "bin" / "activate.fish"
        if act.exists():
            return f"source '{act.as_posix()}'"
    elif shell in {"csh", "tcsh", "cshell"}:
        act = venv / "bin" / "activate.csh"
        if act.exists():
            return f"source '{act.as_posix()}'"
    elif shell in {"nu", "nushell"}:
        act = venv / "bin" / "activate.nu"
        if act.exists():
            return f"overlay use '{act.as_posix()}'"
    elif shell in {"powershell", "pwsh"}:
        act = venv / "Scripts" / "Activate.ps1"
        if act.exists():
            return f". '{act.as_posix()}'"
    elif shell in {"cmd", "batch", "bat"}:
        act = venv / "Scripts" / "activate.bat"
        if act.exists():
            return f"call \"{act}\""
    
    raise EnvonError(
        f"No activation script found for shell '{shell}' in '{venv}'."
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="envon",
        description="Emit the activation command for the nearest or specified virtual environment.",
    )
    p.add_argument("target", nargs="?", help="Path, project root, or name (searched in WORKON_HOME)")
    p.add_argument("--emit", choices=[
        "bash", "zsh", "sh", "fish", "cshell", "csh", "tcsh", "nushell", "nu", "powershell", "pwsh", "cmd", "batch", "bat",
    ], help="Force shell output format")
    p.add_argument("--print-path", action="store_true", help="Print resolved venv path (no activation)")
    p.add_argument(
        "--bootstrap",
        choices=[
            "bash", "zsh", "sh", "fish", "nushell", "nu", "powershell", "pwsh", "csh", "tcsh", "cshell",
        ],
        help="Print a shell wrapper that evaluates envon's output so 'envon' directly activates the venv.",
    )
    p.add_argument(
        "--install",
        choices=[
            "bash", "zsh", "sh", "fish", "nushell", "nu", "powershell", "pwsh", "csh", "tcsh", "cshell",
        ],
        help="Install envon bootstrap function directly to shell configuration file.",
    )
    return p.parse_args(argv)


def emit_bootstrap(shell: str) -> str:
    """Generate the bootstrap function for the given shell."""
    s = shell.lower()
    if s in {"bash", "zsh", "sh"}:
        # Forward CLI flags to the real envon, only eval activation when args look like targets
        return (
            "envon() {\n"
            "  if [ \"$#\" -gt 0 ]; then\n"
            "    case \"$1\" in\n"
            "      --) shift ;;\n"
            "      help|-h|--help) command envon \"$@\"; return $? ;;\n"
            "      -*) command envon \"$@\"; return $? ;;\n"
            "    esac\n"
            "  fi\n"
            "  local cmd ec;\n"
            "  cmd=\"$(command envon --emit bash \"$@\")\"; ec=$?\n"
            "  if [ $ec -ne 0 ]; then printf %s\\n \"$cmd\" >&2; return $ec; fi\n"
            "  eval \"$cmd\";\n"
            "}\n"
        )
    if s == "fish":
        return (
            "function envon\n"
            "    if test (count $argv) -gt 0\n"
            "        set first $argv[1]\n"
            "        if test \"$first\" = \"--\"\n"
            "            set -e argv[1]\n"
            "        else if string match -rq '^(help|-h|--help|-).*' -- $first\n"
            "            command envon $argv\n"
            "            return $status\n"
            "        end\n"
            "    end\n"
            "    set cmd (command envon --emit fish $argv)\n"
            "    if test $status -ne 0\n"
            "        echo $cmd >&2\n"
            "        return 1\n"
            "    end\n"
            "    eval $cmd\n"
            "end\n"
        )
    if s in {"nushell", "nu"}:
        return (
            "def-env envon [...args] {\n"
            "  if ($args | is-empty) == false {\n"
            "    let first = ($args | get 0)\n"
            "    if ($first == \"--\") {\n"
            "      $args = ($args | skip 1)\n"
            "    } else if ($first in [help] or ($first | str starts-with '-')) {\n"
            "      ^envon ...$args\n"
            "      return\n"
            "    }\n"
            "  }\n"
            "  let cmd = (^envon --emit nushell ...$args)\n"
            "  overlay use $cmd\n"
            "}\n"
        )
    if s in {"powershell", "pwsh"}:
        return (
            "function envon {\n"
            "  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)\n"
            "  $envonExe = Get-Command envon -CommandType Application -ErrorAction SilentlyContinue\n"
            "  if (-not $envonExe) { Write-Error 'envon console script not found on PATH'; return }\n"
            "  if ($Args.Count -gt 0) {\n"
            "    if ($Args[0] -eq '--') { $Args = $Args[1..($Args.Count-1)] }\n"
            "    elseif ($Args[0] -eq 'help' -or $Args[0].StartsWith('-')) {\n"
            "      & $envonExe.Source @Args; return\n"
            "    }\n"
            "  }\n"
            "  $cmd = & $envonExe.Source --emit powershell @Args\n"
            "  if ($LASTEXITCODE -ne 0) { Write-Error $cmd; return }\n"
            "  Invoke-Expression $cmd\n"
            "}\n"
        )
    if s in {"csh", "tcsh", "cshell"}:
        # csh alias that forwards args, captures output, and evals it
        # Note: users may need to add this to their ~/.cshrc
        return (
            "alias envon 'set _ev=`envon --emit csh \\!*` && eval $_ev && unset _ev'\n"
        )
    raise EnvonError(f"Unsupported shell for bootstrap: {shell}")


def get_shell_config_path(shell: str) -> Path:
    """Get the configuration file path for a given shell."""
    shell = shell.lower()
    home = Path.home()
    
    if shell in {"bash", "sh"}:
        # Try .bashrc first, fall back to .bash_profile
        bashrc = home / ".bashrc"
        if bashrc.exists():
            return bashrc
        return home / ".bash_profile"
    elif shell == "zsh":
        return home / ".zshrc"
    elif shell == "fish":
        config_dir = home / ".config" / "fish"
        return config_dir / "config.fish"
    elif shell in {"nushell", "nu"}:
        if os.name == "nt":  # Windows
            config_dir = Path(os.environ.get("APPDATA", home)) / "nushell"
        else:  # POSIX
            config_dir = home / ".config" / "nushell"
        return config_dir / "config.nu"
    elif shell in {"powershell", "pwsh"}:
        if os.name == "nt":  # Windows
            # Get PowerShell profile path
            documents = Path.home() / "Documents"
            if shell == "pwsh":  # PowerShell Core
                return documents / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
            else:  # Windows PowerShell
                return documents / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
        else:  # POSIX PowerShell Core
            return home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"
    elif shell in {"csh", "tcsh", "cshell"}:
        if shell == "tcsh":
            return home / ".tcshrc"
        return home / ".cshrc"
    
    raise EnvonError(f"Unknown shell configuration path for: {shell}")


def install_bootstrap(shell: str) -> str:
    """Install envon bootstrap function to shell configuration file."""
    shell = shell.lower()
    config_path = get_shell_config_path(shell)
    
    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Managed bootstrap: write function to a stable file and source it from RC with markers
    managed_file = get_managed_bootstrap_path(shell)
    managed_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate function content for the managed file
    target_shell = (
        "bash" if shell in {"bash", "zsh", "sh"} else
        "fish" if shell == "fish" else
        "nushell" if shell in {"nushell", "nu"} else
        "powershell" if shell in {"powershell", "pwsh"} else
        "csh" if shell in {"csh", "tcsh", "cshell"} else None
    )
    if target_shell is None:
        raise EnvonError(f"Unsupported shell for installation: {shell}")
    content = _managed_content_for_shell(target_shell)
    _write_managed_if_changed(managed_file, content)

    # Ensure RC contains a single, marked source block
    _ensure_rc_sources_managed(config_path, managed_file, shell)
    return (
        f"envon bootstrap installed:\n- managed: {managed_file}\n- rc: {config_path}\n"
        f"Restart your shell or run: source {config_path}"
    )


MARK_START = "# >>> envon bootstrap >>>"
MARK_END = "# <<< envon bootstrap <<<"


def get_managed_bootstrap_path(shell: str) -> Path:
    """Return the managed bootstrap file path for a shell."""
    shell = shell.lower()
    # Determine config base dir
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    envon_dir = base / "envon"

    name = (
        "envon.bash" if shell in {"bash", "zsh", "sh"} else
        "envon.fish" if shell == "fish" else
        "envon.nu" if shell in {"nushell", "nu"} else
        "envon.ps1" if shell in {"powershell", "pwsh"} else
        "envon.csh" if shell in {"csh", "tcsh", "cshell"} else None
    )
    if name is None:
        raise EnvonError(f"Unsupported shell: {shell}")
    return envon_dir / name


def _write_managed_if_changed(path: Path, content: str) -> None:
    """Write content to path if missing or different."""
    try:
        if path.exists() and path.read_text() == content:
            return
    except Exception:
        # If read fails, attempt to overwrite
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _ensure_rc_sources_managed(config_path: Path, managed_file: Path, shell: str) -> None:
    """Ensure the user's RC/profile sources the managed file, using idempotent markers."""
    rc_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

    # If already installed with markers, do nothing
    if MARK_START in rc_text and MARK_END in rc_text:
        return

    mf = managed_file.as_posix()
    if shell in {"bash", "zsh", "sh"}:
        block = f"\n{MARK_START}\n[ -f {mf} ] && . {mf}\n{MARK_END}\n"
    elif shell == "fish":
        block = f"\n{MARK_START}\nif test -f {mf}\n    source {mf}\nend\n{MARK_END}\n"
    elif shell in {"nushell", "nu"}:
        # guard exists via ls check
        block = (
            f"\n{MARK_START}\n"
            f"if (ls {mf} | is-empty) == false {{\n    source {mf}\n}}\n"
            f"{MARK_END}\n"
        )
    elif shell in {"powershell", "pwsh"}:
        block = (
            f"\n{MARK_START}\n"
            f"$envonPath = '{managed_file}'\nif (Test-Path $envonPath) {{ . $envonPath }}\n"
            f"{MARK_END}\n"
        )
    elif shell in {"csh", "tcsh", "cshell"}:
        block = f"\n{MARK_START}\nif ( -f {mf} ) source {mf}\n{MARK_END}\n"
    else:
        raise EnvonError(f"Unsupported shell: {shell}")

    # Append the block
    with config_path.open("a", encoding="utf-8") as f:
        f.write(block)


def _managed_content_for_shell(shell: str) -> str:
    """Build the content stored in the managed file, tagged with the package version.

    Including the version allows us to detect when an upgrade may require refreshing
    the managed file, while avoiding unnecessary rewrites.
    """
    body = emit_bootstrap(shell)
    header = f"# envon managed bootstrap - version: {VENV_VERSION}\n"
    return header + body


def _maybe_update_managed_current_shell(explicit_shell: str | None) -> None:
    """If a managed bootstrap file exists for the current/detected shell, refresh it when outdated.

    This runs silently on each invocation and only writes when the content differs,
    so normal runs stay fast and side-effect free for already up-to-date installs.
    """
    try:
        shell = detect_shell(explicit_shell)
        managed = get_managed_bootstrap_path(shell)
        if managed.exists():
            desired = _managed_content_for_shell(
                "bash" if shell in {"bash", "zsh", "sh"}
                else "fish" if shell == "fish"
                else "nushell" if shell in {"nushell", "nu"}
                else "powershell" if shell in {"powershell", "pwsh"}
                else "csh" if shell in {"csh", "tcsh", "cshell"}
                else shell
            )
            try:
                current = managed.read_text(encoding="utf-8")
            except Exception:
                current = ""
            if current != desired:
                _write_managed_if_changed(managed, desired)
    except Exception:
        # Never fail the main command due to a managed-file refresh issue
        pass


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv or sys.argv[1:])
    try:
        # Opportunistic refresh of managed bootstrap (no-op if not installed)
        _maybe_update_managed_current_shell(ns.emit)
        if ns.bootstrap:
            # print(f"DEBUG: sys.stdout is {sys.stdout!r}", file=sys.stderr)
            # data = emit_bootstrap(ns.bootstrap)
            # print(f"DEBUG: bootstrap length {len(data)}", file=sys.stderr)
            print(emit_bootstrap(ns.bootstrap))
           # os.write(1, emit_bootstrap(ns.bootstrap).encode())
            # print(f"DEBUG: bootstrap repr {data!r}", file=sys.stderr)

            # print("DEBUG: printed bootstrap function", file=sys.stderr)
            return 0
        if ns.install:
            result = install_bootstrap(ns.install)
            print(result)
            return 0
        venv = resolve_target(ns.target)
        if ns.print_path:
            print(str(venv))
            return 0
        shell = detect_shell(ns.emit)
        cmd = emit_activation(venv, shell)
        print(cmd)
        return 0
    except EnvonError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
