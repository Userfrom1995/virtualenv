from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from virtualenv.envon import (
    EnvonError,
    _choose_interactively,
    _emit_activation_fallback,
    _generate_activation_command,
    _list_venvs_in_dir,
    detect_shell,
    emit_activation,
    emit_bootstrap,
    find_nearest_venv,
    is_venv_dir,
    main,
    parse_args,
    resolve_target,
)


class TestIsVenvDir:
    """Test virtual environment detection."""

    def test_empty_path(self):
        assert not is_venv_dir(Path())

    def test_non_existent_path(self, tmp_path):
        non_existent = tmp_path / "nonexistent"
        assert not is_venv_dir(non_existent)

    def test_regular_directory(self, tmp_path):
        regular_dir = tmp_path / "regular"
        regular_dir.mkdir()
        assert not is_venv_dir(regular_dir)

    def test_pyvenv_cfg_detection(self, tmp_path):
        """Test pyvenv.cfg file detection (most reliable method)."""
        venv_dir = tmp_path / "test_venv"
        venv_dir.mkdir()
        
        # Create pyvenv.cfg file
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\ninclude-system-site-packages = false\n")
        
        assert is_venv_dir(venv_dir)

    def test_posix_layout_detection(self, tmp_path):
        """Test POSIX virtual environment layout."""
        venv_dir = tmp_path / "test_venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        
        # Create activate script
        (bin_dir / "activate").write_text("# Activation script")
        
        assert is_venv_dir(venv_dir)

    def test_windows_layout_detection(self, tmp_path):
        """Test Windows virtual environment layout."""
        venv_dir = tmp_path / "test_venv"
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir(parents=True)
        
        # Test batch script
        (scripts_dir / "activate.bat").write_text("@echo off")
        assert is_venv_dir(venv_dir)
        
        # Clean up and test PowerShell script
        (scripts_dir / "activate.bat").unlink()
        (scripts_dir / "Activate.ps1").write_text("# PowerShell activation")
        assert is_venv_dir(venv_dir)

    def test_other_shells_detection(self, tmp_path):
        """Test detection of other shell activation scripts."""
        venv_dir = tmp_path / "test_venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        
        # Test fish shell
        (bin_dir / "activate.fish").write_text("# Fish activation")
        assert is_venv_dir(venv_dir)
        
        # Test csh
        (bin_dir / "activate.fish").unlink()
        (bin_dir / "activate.csh").write_text("# C Shell activation")
        assert is_venv_dir(venv_dir)
        
        # Test nushell
        (bin_dir / "activate.csh").unlink()
        (bin_dir / "activate.nu").write_text("# Nushell activation")
        assert is_venv_dir(venv_dir)


class TestFindNearestVenv:
    """Test upward virtual environment search."""

    def test_no_venv_found(self, tmp_path):
        """Test when no virtual environment is found."""
        start_dir = tmp_path / "project" / "subdir"
        start_dir.mkdir(parents=True)
        
        result = find_nearest_venv(start_dir)
        assert result is None

    def test_venv_in_current_dir(self, tmp_path):
        """Test finding virtual environment in current directory."""
        project_dir = tmp_path / "project"
        venv_dir = project_dir / ".venv"
        venv_dir.mkdir(parents=True)
        
        # Create pyvenv.cfg to make it a valid venv
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = find_nearest_venv(project_dir)
        assert result == venv_dir

    def test_venv_in_parent_dir(self, tmp_path):
        """Test finding virtual environment in parent directory."""
        project_dir = tmp_path / "project"
        subdir = project_dir / "src" / "package"
        subdir.mkdir(parents=True)
        
        venv_dir = project_dir / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = find_nearest_venv(subdir)
        assert result == venv_dir

    def test_preferred_names_order(self, tmp_path):
        """Test that preferred names are checked in order."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        # Create multiple venvs with different names
        for name in ["env", ".venv", "venv"]:  # .venv should win due to PREFERRED_NAMES order
            venv_dir = project_dir / name
            venv_dir.mkdir()
            (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = find_nearest_venv(project_dir)
        assert result == project_dir / ".venv"  # .venv is first in PREFERRED_NAMES


class TestListVenvsInDir:
    """Test virtual environment listing in a directory."""

    def test_empty_directory(self, tmp_path):
        """Test empty directory returns no venvs."""
        result = _list_venvs_in_dir(tmp_path)
        assert result == []

    def test_no_venvs(self, tmp_path):
        """Test directory with no virtual environments."""
        (tmp_path / "src").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "tests").mkdir()
        
        result = _list_venvs_in_dir(tmp_path)
        assert result == []

    def test_preferred_names_first(self, tmp_path):
        """Test that preferred names come first in results."""
        # Create venvs with preferred and non-preferred names
        venv_names = ["custom-venv", ".venv", "env", "venv", "another-venv"]
        for name in venv_names:
            venv_dir = tmp_path / name
            venv_dir.mkdir()
            (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = _list_venvs_in_dir(tmp_path)
        result_names = [venv.name for venv in result]
        
        # Preferred names should come first in PREFERRED_NAMES order
        assert result_names[:3] == [".venv", "venv", "env"]
        # Non-preferred names should be alphabetical
        assert "another-venv" in result_names
        assert "custom-venv" in result_names

    def test_nonexistent_directory(self):
        """Test handling of non-existent directory."""
        result = _list_venvs_in_dir(Path("/nonexistent/path"))
        assert result == []


class TestDetectShell:
    """Test shell detection logic."""

    def test_explicit_shell(self):
        """Test explicit shell specification."""
        assert detect_shell("bash") == "bash"
        assert detect_shell("FISH") == "fish"
        assert detect_shell("PowerShell") == "powershell"

    @patch("os.name", "nt")
    def test_windows_shell_detection(self):
        """Test Windows shell detection."""
        with patch.dict(os.environ, {"PSModulePath": "C:\\Windows\\System32\\WindowsPowerShell"}):
            assert detect_shell(None) == "powershell"
        
        with patch.dict(os.environ, {}, clear=True):
            assert detect_shell(None) == "cmd"

    @patch("os.name", "posix")
    def test_posix_shell_detection(self):
        """Test POSIX shell detection."""
        test_cases = [
            ("/usr/bin/fish", "fish"),
            ("/bin/csh", "cshell"),
            ("/usr/bin/tcsh", "cshell"),
            ("/usr/bin/nu", "nushell"),
            ("/usr/bin/nushell", "nushell"),
            ("/bin/bash", "bash"),
            ("/usr/bin/zsh", "bash"),
            ("", "bash"),  # Default case
        ]
        
        for shell_path, expected in test_cases:
            with patch.dict(os.environ, {"SHELL": shell_path}):
                assert detect_shell(None) == expected


class TestEmitActivation:
    """Test activation command generation."""

    def test_bash_activation(self, tmp_path):
        """Test bash activation command generation."""
        venv_dir = tmp_path / "venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        
        activate_script = bin_dir / "activate"
        activate_script.write_text("# Bash activation")
        
        result = emit_activation(venv_dir, "bash")
        expected = f". '{activate_script.as_posix()}'"
        assert result == expected

    def test_powershell_activation(self, tmp_path):
        """Test PowerShell activation command generation."""
        venv_dir = tmp_path / "venv"
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir(parents=True)
        
        activate_script = scripts_dir / "Activate.ps1"
        activate_script.write_text("# PowerShell activation")
        
        result = emit_activation(venv_dir, "powershell")
        expected = f". '{activate_script.as_posix()}'"
        assert result == expected

    def test_fish_activation(self, tmp_path):
        """Test Fish shell activation command generation."""
        venv_dir = tmp_path / "venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        
        activate_script = bin_dir / "activate.fish"
        activate_script.write_text("# Fish activation")
        
        result = emit_activation(venv_dir, "fish")
        expected = f"source '{activate_script.as_posix()}'"
        assert result == expected

    def test_unsupported_shell(self, tmp_path):
        """Test error for unsupported shell."""
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        
        with pytest.raises(EnvonError, match="Unsupported shell: unsupported"):
            emit_activation(venv_dir, "unsupported")

    def test_missing_activation_script(self, tmp_path):
        """Test error when activation script is missing."""
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        
        with pytest.raises(EnvonError, match="No activation script found"):
            emit_activation(venv_dir, "bash")


class TestResolveTarget:
    """Test virtual environment target resolution."""

    def test_no_target_single_venv(self, tmp_path, monkeypatch):
        """Test resolution when no target is specified and single venv exists."""
        monkeypatch.chdir(tmp_path)
        
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = resolve_target(None)
        assert result == venv_dir

    def test_no_target_no_venv(self, tmp_path, monkeypatch):
        """Test error when no target specified and no venv found."""
        monkeypatch.chdir(tmp_path)
        
        with pytest.raises(EnvonError, match="No virtual environment found here"):
            resolve_target(None)

    def test_existing_path_target(self, tmp_path):
        """Test resolution with existing path target."""
        venv_dir = tmp_path / "my_venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = resolve_target(str(venv_dir))
        assert result == venv_dir

    def test_workon_home_fallback(self, tmp_path):
        """Test WORKON_HOME fallback."""
        workon_dir = tmp_path / "virtualenvs"
        workon_dir.mkdir()
        
        venv_dir = workon_dir / "myproject"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        with patch.dict(os.environ, {"WORKON_HOME": str(workon_dir)}):
            result = resolve_target("myproject")
            assert result == venv_dir

    def test_nonexistent_target(self, tmp_path):
        """Test error for non-existent target."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvonError, match="Cannot resolve virtual environment"):
                resolve_target("nonexistent")


class TestBootstrap:
    """Test bootstrap function generation."""

    def test_bash_bootstrap(self):
        """Test bash bootstrap function generation."""
        result = emit_bootstrap("bash")
        assert "envon() {" in result
        assert "eval \"$cmd\"" in result

    def test_fish_bootstrap(self):
        """Test fish bootstrap function generation."""
        result = emit_bootstrap("fish")
        assert "function envon" in result
        assert "eval $cmd" in result

    def test_powershell_bootstrap(self):
        """Test PowerShell bootstrap function generation."""
        result = emit_bootstrap("powershell")
        assert "function envon {" in result
        assert "Invoke-Expression $cmd" in result

    def test_nushell_bootstrap(self):
        """Test Nushell bootstrap function generation."""
        result = emit_bootstrap("nushell")
        assert "def --env envon" in result
        assert "overlay use" in result
        assert "overlay use $act" in result

    def test_unsupported_shell_bootstrap(self):
        """Test error for unsupported shell bootstrap."""
        with pytest.raises(EnvonError, match="Unsupported shell for bootstrap"):
            emit_bootstrap("unsupported")


class TestParseArgs:
    """Test command line argument parsing."""

    def test_no_args(self):
        """Test parsing with no arguments."""
        result = parse_args([])
        assert result.target is None
        assert result.emit is None
        assert not result.print_path
        assert result.bootstrap is None

    def test_target_arg(self):
        """Test parsing with target argument."""
        result = parse_args(["my_venv"])
        assert result.target == "my_venv"

    def test_emit_flag(self):
        """Test --emit flag."""
        result = parse_args(["--emit", "fish"])
        assert result.emit == "fish"

    def test_print_path_flag(self):
        """Test --print-path flag."""
        result = parse_args(["--print-path"])
        assert result.print_path is True

    def test_bootstrap_flag(self):
        """Test --bootstrap flag."""
        result = parse_args(["--bootstrap", "bash"])
        assert result.bootstrap == "bash"

    def test_combined_args(self):
        """Test parsing with multiple arguments."""
        result = parse_args(["my_venv", "--emit", "powershell", "--print-path"])
        assert result.target == "my_venv"
        assert result.emit == "powershell"
        assert result.print_path is True


class TestMain:
    """Test main function."""

    def test_bootstrap_mode(self, capsys):
        """Test bootstrap mode."""
        result = main(["--bootstrap", "bash"])
        assert result == 0
        
        out, err = capsys.readouterr()
        assert "envon() {" in out
        assert not err

    def test_print_path_mode(self, tmp_path, monkeypatch, capsys):
        """Test print-path mode."""
        monkeypatch.chdir(tmp_path)
        
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        
        result = main(["--print-path"])
        assert result == 0
        
        out, err = capsys.readouterr()
        assert str(venv_dir) in out
        assert not err

    def test_activation_mode(self, tmp_path, monkeypatch, capsys):
        """Test normal activation mode."""
        monkeypatch.chdir(tmp_path)
        
        venv_dir = tmp_path / ".venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        
        activate_script = bin_dir / "activate"
        activate_script.write_text("# Activation script")
        
        result = main(["--emit", "bash"])
        assert result == 0
        
        out, err = capsys.readouterr()
        assert f". '{activate_script.as_posix()}'" in out
        assert not err

    def test_error_handling(self, tmp_path, monkeypatch, capsys):
        """Test error handling."""
        monkeypatch.chdir(tmp_path)
        
        result = main([])
        assert result == 2
        
        out, err = capsys.readouterr()
        assert not out
        assert "No virtual environment found" in err


class TestInteractiveChoice:
    """Test interactive choice functionality."""

    def test_non_tty_multiple_candidates(self, tmp_path):
        """Test multiple candidates in non-TTY environment."""
        candidates = [tmp_path / "venv1", tmp_path / "venv2"]
        
        with patch("sys.stdin.isatty", return_value=False):
            with pytest.raises(EnvonError, match="Multiple virtual environments found"):
                _choose_interactively(candidates, str(tmp_path))

    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdin.readline", return_value="1\n")
    def test_tty_valid_selection(self, mock_readline, mock_isatty, tmp_path):
        """Test valid selection in TTY environment."""
        candidates = [tmp_path / "venv1", tmp_path / "venv2"]
        
        result = _choose_interactively(candidates, str(tmp_path))
        assert result == candidates[0]

    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdin.readline", side_effect=["invalid\n", "3\n", "1\n"])
    def test_tty_invalid_then_valid_selection(self, mock_readline, mock_isatty, tmp_path):
        """Test invalid selection followed by valid selection."""
        candidates = [tmp_path / "venv1", tmp_path / "venv2"]
        
        result = _choose_interactively(candidates, str(tmp_path))
        assert result == candidates[0]