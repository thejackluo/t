"""Repository-level data locations, independent of the caller's working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data'
OUTPUT_DIR = ROOT / 'output'
