# Sourya live image module integration

Copied the actual four files from `sourya_module/` into `modules/image_module/`, retaining existing experiments and data. The Flask `backend/app/services/image_adapter.py` imports `image_similarity` and validates its returned score. The model is lazily initialized and cached by Sourya's implementation. Backend dependencies now include `torch` and `open_clip_torch`.

## Verification
- Source-level integration test: PASS (`python tests/test_sourya_integration.py`).
- Python compilation: PASS.
- Dependency installation: BLOCKED by package-index DNS/network access (`open_clip_torch` unavailable in this environment).
- Actual live OpenCLIP inference: NOT EXECUTED; pretrained weights must be downloaded on first use.
- Flask end-to-end: NOT EXECUTED; Flask is not installed in this environment.

## Windows PowerShell commands
From `Lost_Object_Recovery_Final`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r modules\image_module\requirements.txt
python -c "from modules.image_module.image_matcher import image_similarity; print(image_similarity('data/Images/L001.jpg', 'data/Images/F001.jpg'))"
python tests\test_sourya_integration.py
cd backend
python run.py
```

First live inference requires internet access for OpenCLIP pretrained weights (unless cached). Image-only Lost reports are accepted by the route; text-only and both are also supported. Found reports reject missing images. Complete runtime verification remains pending.
