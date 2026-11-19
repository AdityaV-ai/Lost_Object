# OpenCLIP Multimodal Matching Module

## Project
AI-Powered Multimodal Lost Object Recovery System

## Module Developed
OpenCLIP-based image matching and image-text matching.

## Model Used
OpenCLIP ViT-B/32 with pretrained LAION-2B weights.

## Implemented Features
1. Image embedding generation for Lost and Found reports.
2. Image-to-image similarity using cosine similarity.
3. Image-to-text similarity using OpenCLIP.
4. Multimodal fusion using 50% image-to-image and 50% image-to-text similarity.
5. Ranking of potential Lost–Found matches.

## Dataset Used
- 55 Lost reports
- 50 Found reports
- 105 images
- 2,750 possible Lost–Found combinations

## Preliminary Evaluation
- Fusion ROC-AUC: 0.9925
- Average Precision: 0.9765
- Accuracy: 0.9313
- Balanced Accuracy: 0.9542
- Precision@10: 1.00

Note: These are preliminary results on the available labelled dataset, not independent real-world test results.

## Files Included
- sourya_openCLIP.ipynb – Complete implementation notebook
- image_embeddings.pt – Generated image embeddings
- image_similarity_results.csv – Image-to-image similarity results
- image_text_similarity_results.csv – Image-to-text similarity results
- final_multimodal_fusion_results.csv – Combined similarity results
- items_updated - items_updated.csv – Dataset report information

## Execution
Run the notebook in Google Colab with the required dataset files and install the open_clip_torch package.
