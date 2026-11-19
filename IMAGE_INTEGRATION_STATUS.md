# Sourya image matcher integration

Integrated the supplied `sourya_module/image_matcher.py` into `modules/image_module/image_matcher.py` where the Flask adapter already looks for it. The implementation uses OpenCLIP ViT-B-32 / laion2b_s34b_b79k, with lazily cached weights, cosine scoring mapped to [0,1], and validation of invalid image paths. `backend/requirements.txt` includes `torch` and `open_clip_torch`.

The live matcher requires pretrained weights at first run, which may require internet access. If the weights or dependencies are unavailable, the existing matching service logs the failure and continues with text and location modalities. This is not evidence that full image inference was executed successfully.

Run the Flask app after installing dependencies; submit a Lost and Found report each with images to exercise actual live inference. See backend setup instructions for local startup.
