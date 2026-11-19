# Ashika Module – Location Similarity and Fusion

## 1. Overview

This module is part of the **AI-Powered Lost Object Recovery Network Using Computer Vision and Similarity-Based Matching** project.

It focuses on geographical similarity calculation, location-based evaluation, and the initial implementation of multimodal fusion ranking.

The module has two main components:

1. **Location Similarity:** Calculates geographical distances and similarity scores between Lost and Found reports.
2. **Multimodal Fusion:** Combines image, text and location similarity scores to produce an overall matching score and rank potential matches.

---

## 2. Location Similarity Module

### 2.1 Methodology

The Haversine formula is used to calculate the geographical distance between the coordinates of Lost and Found reports.

- Earth's mean radius: 6,371,000 metres
- Input: Latitude and longitude of both reports
- Output: Geographical distance in metres

The distance is converted into a similarity score using an exponential decay function:

\[
S_{location} = e^{-d/\tau}
\]

Where:

- `d` = geographical distance between reports
- `τ` = distance decay parameter
- `S_location` = location similarity score between 0 and 1

A smaller distance produces a higher similarity score.

The default value of `τ = 200` is used for generating the current pairwise location results. Different tau values are also examined during evaluation.

### 2.2 Missing Location Information

If either report has missing latitude or longitude coordinates, the location similarity score for that pair is recorded as `None`.

Location is treated as a supporting matching signal rather than a strict condition for identifying a match.

### 2.3 Location Evaluation

Location matching performance is evaluated using the labelled pairs in `ground_truth_pairs.csv`.

The evaluation includes:

- ROC-AUC using inverse geographical distance
- Comparison of positive and negative pair similarity scores across different tau values
- Precision, recall and F1-score analysis across different classification thresholds
- Distance distribution analysis for positive and negative pairs

Only labelled pairs are used for evaluation. Unlabelled combinations are not automatically treated as negative matches.

---

## 3. Location Dataset and Generated Results

The current dataset contains:

- 55 Lost reports
- 50 Found reports
- 2,750 possible Lost–Found combinations

The generated pairwise results contain all 2,750 combinations.

### Output CSV Files

| File | Description |
|---|---|
| `location_similarity_results.csv` | Complete pairwise location scores in the original dataset order. |
| `location_similarity_ranked.csv` | The same pairwise results arranged in descending order of location similarity. |

Both files contain the following columns:

| Column | Description |
|---|---|
| `lost_report_id` | Identifier of the Lost report |
| `found_report_id` | Identifier of the Found report |
| `distance_m` | Geographical distance in metres |
| `location_similarity` | Calculated location similarity score |

The current generated output contains 2,750 valid location scores with no missing coordinate values.

### Visualisation

`location_distance_distribution.png` illustrates the geographical distance distributions of positive and negative labelled pairs.

It helps examine how geographical proximity differs between actual matches and non-matches.

---

## 4. Multimodal Fusion Module

### 4.1 Purpose

The fusion component is intended to combine three matching signals:

- Image similarity
- Text similarity
- Location similarity

The purpose is to produce an overall matching score for each Lost–Found pair and rank potential matches.

### 4.2 Implementation

`fusion_ranking.py` contains the initial fusion-ranking implementation.

The module also includes test scripts to examine how the fusion logic behaves when different similarity signals are available or missing.

### 4.3 Testing

The following test files are included:

- `test_fusion.py` – Tests fusion score calculation when similarity signals are available.
- `test_fusion_missing.py` – Tests fusion behaviour when one or more similarity signals are missing.

The fusion component is currently experimental. Final weights, evaluation and integration are still subject to further testing using the verified image and text similarity outputs.

---

## 5. Files and Their Purpose

| File | Description |
|---|---|
| `location_similarity.py` | Core geographical distance and similarity calculation functions |
| `generate_location_results.py` | Generates all Lost–Found location similarity combinations |
| `evaluate_location.py` | Evaluates location matching performance using labelled pairs |
| `plot_location_distribution.py` | Generates the geographical distance distribution visualisation |
| `test_location.py` | Tests the basic location distance calculation |
| `fusion_ranking.py` | Initial multimodal fusion and ranking implementation |
| `test_fusion.py` | Tests fusion score calculation |
| `test_fusion_missing.py` | Tests fusion behaviour with missing similarity signals |

---

## 6. Running the Scripts

The module is designed to work within the main project directory.

Expected project structure:

```text
Lost_Object_Recovery/
│
├── ashika_module/
│   ├── README.md
│   └── Python scripts
│
├── dataset/
│   ├── items.csv
│   ├── locations.csv
│   └── ground_truth_pairs.csv
│
└── results/
```

Run the commands from the `ashika_module` directory.

**Generate pairwise location results:**

```bash
python generate_location_results.py
```

**Evaluate location matching performance:**

```bash
python evaluate_location.py
```

**Run the basic location test:**

```bash
python test_location.py
```

**Run fusion tests:**

```bash
python test_fusion.py
python test_fusion_missing.py
```

The scripts use paths relative to the main project structure. Keep `ashika_module`, `dataset` and `results` in their expected locations.

---

## 7. Limitations and Current Status

### Location Similarity

- The geographical coordinates in the current dataset are simulated.
- Geographical proximity alone cannot establish whether two reports refer to the same object.
- The same object may be reported at different locations depending on when and where it was lost or recovered.
- Location similarity is therefore intended to support image and text matching rather than replace them.

### Multimodal Fusion

- The initial fusion implementation and missing-signal tests are available.
- Final fusion weights and ranking performance require further experimentation.
- Final integration depends on the verified image and text similarity outputs from the respective modules.

---

**Module:** Ashika Module  
**Project:** AI-Powered Lost Object Recovery Network Using Computer Vision and Similarity-Based Matching