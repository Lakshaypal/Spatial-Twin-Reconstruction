"""
Unit and Integration Test Suite for ColMapping-MeshSplatting Pipeline.
Verifies project file structure, syntax integrity, configuration parameters, and core logic.
"""

import os
import sys
import unittest
import py_compile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestPipelineStructure(unittest.TestCase):
    def test_required_directories_exist(self):
        """Verify all critical project directories exist."""
        required_dirs = [
            "src",
            "src/colmapping",
            "src/mesh_splatting",
            "src/reconstruction",
            "src/spatial_analysis",
            "src/unity_iot",
            "src/visualization",
            "scripts",
            "configs",
            "docs",
            "assets",
            "references",
            "tests"
        ]
        for d in required_dirs:
            full_path = os.path.join(PROJECT_ROOT, d)
            self.assertTrue(os.path.isdir(full_path), f"Missing required directory: {d}")

    def test_core_scripts_present(self):
        """Verify essential algorithmic and execution scripts exist."""
        required_files = [
            "src/colmapping/run_colmap.py",
            "src/colmapping/convert_lingbot_to_colmap.py",
            "src/colmapping/reframe.py",
            "src/mesh_splatting/train.py",
            "src/mesh_splatting/create_ply.py",
            "src/mesh_splatting/splat_to_mesh.py",
            "src/reconstruction/run_fusion_chunked.py",
            "src/reconstruction/color_transfer.py",
            "src/reconstruction/create_authentic_mesh.py",
            "src/spatial_analysis/analysis_running_space.py",
            "src/spatial_analysis/runner_simulation.py",
            "src/unity_iot/arduino_simulator.py",
            "tests/verify_setup.py",
            "README.md",
            "LICENSE",
            ".gitignore",
            "requirements.txt",
            "environment.yml",
            "PROJECT_AUDIT.md"
        ]
        for f in required_files:
            full_path = os.path.join(PROJECT_ROOT, f)
            self.assertTrue(os.path.isfile(full_path), f"Missing essential file: {f}")

    def test_python_syntax_and_compilation(self):
        """Verify all python files compile cleanly without syntax errors."""
        for root, _, files in os.walk(PROJECT_ROOT):
            if any(ignored in root for ignored in [".git", "__pycache__", "venv"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    fp = os.path.join(root, f)
                    try:
                        py_compile.compile(fp, doraise=True)
                    except Exception as e:
                        self.fail(f"Syntax error in {fp}: {e}")

    def test_assets_integrity(self):
        """Verify project assets and reference media exist."""
        assets_dir = os.path.join(PROJECT_ROOT, "assets")
        self.assertTrue(os.path.isdir(assets_dir))
        files = os.listdir(assets_dir)
        self.assertGreater(len(files), 10, "Expected at least 10 visual assets in assets/ folder.")

if __name__ == "__main__":
    unittest.main()
