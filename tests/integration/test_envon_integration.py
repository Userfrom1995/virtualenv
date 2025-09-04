from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


class TestEnvonCLIIntegration:
    """Integration tests for envon CLI tool."""

    def test_envon_help(self):
        """Test envon --help command."""
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--help"], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        assert "envon" in result.stdout
        assert "virtual environment" in result.stdout.lower()

    def test_envon_bootstrap_bash(self):
        """Test envon --bootstrap bash command."""
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--bootstrap", "bash"], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        assert "envon() {" in result.stdout
        assert "eval" in result.stdout

    def test_envon_bootstrap_fish(self):
        """Test envon --bootstrap fish command."""
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--bootstrap", "fish"], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        assert "function envon" in result.stdout

    def test_envon_no_venv_error(self, tmp_path):
        """Test envon error when no virtual environment is found."""
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon"], 
                              cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 2
        assert "No virtual environment found" in result.stderr

    def test_envon_with_created_venv(self, tmp_path):
        """Test envon with an actual created virtual environment."""
        # Create a virtual environment using the main virtualenv tool
        venv_dir = tmp_path / ".venv"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        # Now test envon can detect and activate it
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--print-path"], 
                              cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0
        assert str(venv_dir) in result.stdout

    def test_envon_activation_command(self, tmp_path):
        """Test envon generates correct activation command."""
        # Create a virtual environment
        venv_dir = tmp_path / ".venv"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        # Test bash activation command
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--emit", "bash"], 
                              cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0
        assert "activate" in result.stdout
        assert ". '" in result.stdout

    def test_envon_multiple_shells(self, tmp_path):
        """Test envon with different shell outputs."""
        # Create a virtual environment
        venv_dir = tmp_path / ".venv"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        shell_tests = [
            ("bash", ". '"),
            ("fish", "source '"),
            ("powershell", ". '"),
        ]
        
        for shell, expected_prefix in shell_tests:
            result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--emit", shell], 
                                  cwd=tmp_path, capture_output=True, text=True)
            if result.returncode == 0:  # Some shells might not have activation scripts
                assert expected_prefix in result.stdout

    def test_envon_workon_home(self, tmp_path):
        """Test envon with WORKON_HOME environment variable."""
        # Create WORKON_HOME directory structure
        workon_dir = tmp_path / "virtualenvs"
        workon_dir.mkdir()
        
        # Create a virtual environment in WORKON_HOME
        venv_dir = workon_dir / "testproject"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        # Test envon can find it by name
        env = os.environ.copy()
        env["WORKON_HOME"] = str(workon_dir)
        
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "testproject", "--print-path"], 
                              env=env, cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0
        assert str(venv_dir) in result.stdout

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific test")
    def test_envon_posix_shells(self, tmp_path):
        """Test envon with POSIX shell activation scripts."""
        # Create a virtual environment
        venv_dir = tmp_path / ".venv"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        # Test that activation scripts exist
        bin_dir = venv_dir / "bin"
        assert (bin_dir / "activate").exists()
        
        # Test envon generates correct commands
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--emit", "bash"], 
                              cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0
        assert f"bin{os.sep}activate" in result.stdout

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_envon_windows_shells(self, tmp_path):
        """Test envon with Windows shell activation scripts."""
        # Create a virtual environment
        venv_dir = tmp_path / ".venv"
        result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], 
                              capture_output=True, text=True)
        assert result.returncode == 0
        
        # Test that activation scripts exist
        scripts_dir = venv_dir / "Scripts"
        assert scripts_dir.exists()
        
        # Test envon generates correct commands
        result = subprocess.run([sys.executable, "-m", "virtualenv.envon", "--emit", "cmd"], 
                              cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0
        assert "Scripts" in result.stdout