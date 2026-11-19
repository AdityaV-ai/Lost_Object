"""Dependency-free checks for the integration wiring (not actual OpenCLIP inference)."""
import ast
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root/'modules/image_module/image_matcher.py').read_text()
tree = ast.parse(source)
assert any(isinstance(x,ast.FunctionDef) and x.name=='image_similarity' for x in tree.body)
for name in ('image_matcher.py','__init__.py','README.md','requirements.txt'):
    assert (root/'modules/image_module'/name).is_file()
assert 'open_clip_torch' in (root/'backend/requirements.txt').read_text()
adapter = (root/'backend/app/services/image_adapter.py').read_text()
assert 'from modules.image_module.image_matcher import image_similarity' in adapter
lost = (root/'backend/app/routes/lost_routes.py').read_text()
found = (root/'backend/app/routes/found_routes.py').read_text()
assert 'request.files.get("image")' in lost
assert '"image" not in request.files' in found
print('PASS: Sourya module files, adapter wiring, dependencies and report validation source checks')
