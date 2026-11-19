"""Image matcher contract checks; does not download model weights."""
import ast
from pathlib import Path


def test_live_image_matcher_has_required_entrypoint():
    path = Path(__file__).resolve().parents[3] / 'modules' / 'image_module' / 'image_matcher.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    assert any(isinstance(node, ast.FunctionDef) and node.name == 'image_similarity' for node in tree.body)
