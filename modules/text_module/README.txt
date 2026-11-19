# OCR & NLP Text Matching Module (EasyOCR + TF-IDF)

## Project
AI-Powered Multimodal Lost Object Recovery System

## Module developed by
Shiny - OCR and NLP-based text matching. Output: text_similarity (0 to 1)

## Method
1. EasyOCR (English) reads visible text from each photo (boxes with confidence >= 0.30;
   image resized so the longest side is ~1024 px first).
2. Cleaning: lower-case, remove punctuation/symbols, drop stop-words and 1-character OCR noise,
   unify spelling variants (grey/gray, spectacles/eyeglasses...), light plural stripping.
3. Report text = cleaned description + cleaned OCR text (description is used even if OCR is empty).
4. TF-IDF (unigrams + bigrams, sublinear tf). IDF is learnt from all 105 reports.
5. Cosine similarity of the Lost and Found vectors, clipped to [0, 1].

## Common interface
Inputs : lost_report_id, found_report_id, lost_image_path, found_image_path,
         lost_description, found_description
Output : text_similarity (float, 0-1)
Function: compute_text_similarity(...) in text_similarity.py
          (compare_pair(...) returns the same plus text_available and the cleaned texts)

## Missing text
41 of the 50 Found reports have no description and most objects have no readable text.
If one side has NO text at all (no description, no OCR) the score is 0.0 and
text_available = False. For fusion, treat those rows as "signal missing": drop the text
weight and renormalise the others - do not treat the 0 as "dissimilar".

## Dataset
55 Lost + 50 Found reports, 105 images, 2,750 Lost x Found pairs, 160 labelled pairs
(40 matches, 120 non-matches). ground_truth_pairs.csv was rebuilt from the labelled pairs in
Sourya's image_similarity_results.csv (same pair_ids).

## Results (preliminary, on the available labelled data - not an independent real-world test)
- OCR found readable text in 24 of 105 images (many readings are noisy, e.g. brand logos).
- Only 32% of all pairs have usable text on both sides.
- Labelled pairs, all 160 (missing text counted as 0): ROC-AUC 0.639, Average Precision 0.504
- Labelled pairs where text exists on both sides (63 pairs): ROC-AUC 0.914, AP 0.886
- Harder test, same-category pairs only (75 pairs with text): ROC-AUC 0.859
- Mean score: matching pairs 0.178, non-matching 0.009
Text is therefore a strong signal when it exists, but it is sparse - it should be fused with
Sourya's image scores, not used alone.

## Files
- text_similarity.py              the module (functions + command line)
- test_text_similarity.py         test on sample pairs (same object / same category / different)
- sample_pair_test_results.csv    output of that test
- shiny_text_similarity.ipynb     Colab notebook that runs everything (already executed)
- ocr_results.csv                 raw + cleaned EasyOCR text for all 105 images
- text_similarity_results.csv     all 2,750 pairs: lost_report_id, found_report_id, text_similarity, text_available, label
- text_similarity_labelled_pairs.csv  the 160 labelled pairs with scores
- items_updated.csv               report table (from items_updated.xlsx; dates normalised)
- ground_truth_pairs.csv          labels
- requirements.txt

## How to run
Libraries: pip install -r requirements.txt   (EasyOCR downloads its model on first use; torch is installed with it)
Images are NOT included (60 MB): point --images at your Dataset/Images80+ folder.

  python test_text_similarity.py --items items_updated.csv --images "Dataset/Images80+"
  python text_similarity.py --items items_updated.csv --images "Dataset/Images80+" \
         --pairs ground_truth_pairs.csv --out text_similarity_results.csv
  (omit --pairs to score all 2,750 pairs)

Google Colab: open shiny_text_similarity.ipynb, upload items_updated.csv, ground_truth_pairs.csv and
the images (or mount Drive and edit IMAGES_DIR), then Runtime > Run all.
Image filenames and report IDs are used exactly as in the items table.
