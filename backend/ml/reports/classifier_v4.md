# Classifier v4 evaluation

Algorithm selected: **linear_svm** (highest cross-validated macro-F1 (category)). Features: TF-IDF word 1–2-grams + char_wb 2–5-grams on normalised text.
Data: {'synthetic': 4074} → 3259 training / 815 held-out test reports.

## Model comparison (category)

| Model | CV macro-F1 (5-fold) | Test accuracy | Test macro-F1 |
|---|---|---|---|
| majority_baseline | — | 0.210 | 0.043 |
| complement_nb | 0.998 ± 0.002 | 0.998 | 0.998 |
| logistic_regression | 0.999 ± 0.002 | 1.000 | 1.000 |
| linear_svm | 1.000 ± 0.001 | 1.000 | 1.000 |

## Per category (held-out test set)

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Business Permit Concerns | 1.000 | 1.000 | 1.000 | 27 |
| Drainage Problems | 1.000 | 1.000 | 1.000 | 147 |
| Other Community Issues | 1.000 | 1.000 | 1.000 | 49 |
| Public Safety Concerns | 1.000 | 1.000 | 1.000 | 72 |
| Road Damage | 1.000 | 1.000 | 1.000 | 128 |
| Solid Waste Concerns | 1.000 | 1.000 | 1.000 | 171 |
| Streetlight Issues | 1.000 | 1.000 | 1.000 | 98 |
| Traffic Concerns | 1.000 | 1.000 | 1.000 | 123 |

Category accuracy **1.000**, macro-F1 **1.000**. Sub-type accuracy 1.000.

## Auto-assign policy (confidence threshold vs. coverage)

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 100.0% | 100.0% |
| ≥ 60% | 100.0% | 100.0% |
| ≥ 70% | 100.0% | 100.0% |
| ≥ 80% | 99.9% | 100.0% |
| ≥ 90% | 99.6% | 100.0% |

## Hand-written challenge set

161 complaints written independently of the synthetic generator: accuracy **0.913**, macro-F1 **0.887**, sub-type accuracy 0.857.

| Category | Precision | Recall | F1 | n |
|---|---|---|---|---|
| Business Permit Concerns | 0.857 | 0.800 | 0.828 | 15 |
| Drainage Problems | 1.000 | 0.960 | 0.980 | 25 |
| Other Community Issues | 1.000 | 0.500 | 0.667 | 6 |
| Public Safety Concerns | 0.960 | 0.960 | 0.960 | 25 |
| Road Damage | 0.742 | 0.920 | 0.821 | 25 |
| Solid Waste Concerns | 0.952 | 1.000 | 0.976 | 20 |
| Streetlight Issues | 0.950 | 0.950 | 0.950 | 20 |
| Traffic Concerns | 0.957 | 0.880 | 0.917 | 25 |

Auto-assign on the challenge set:

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 96.3% | 94.2% |
| ≥ 60% | 90.7% | 96.6% |
| ≥ 70% | 87.0% | 97.9% |
| ≥ 80% | 82.6% | 98.5% |
| ≥ 90% | 71.4% | 99.1% |

Misclassified examples:

- “The asphalt near the public market is peeling off, ang daming bato na nagkalat” → streetlight (expected road_damage, confidence 46%)
- “Ang mga materyales ng ginagawang bahay nasa kalsada na po” → solid_waste (expected road_damage, confidence 44%)
- “blinking street lamp sa Maharlika, baka masira na tuluyan” → road_damage (expected streetlight, confidence 69%)
- “konting ulan lang lubog na agad yung kalsada sa amin” → road_damage (expected drainage, confidence 55%)
- “Ang daming aso sa kalye, hinahabol ang mga nagmomotor” → road_damage (expected public_safety, confidence 42%)
- “Puno ng vendors yung sidewalk sa bayan, napipilitan kaming maglakad sa kalsada” → road_damage (expected business_permit, confidence 57%)
- “nagtitinda ng prutas sa mismong kalsada, traffic tuloy” → traffic (expected business_permit, confidence 64%)
- “pakiayos po yung mga nakapwesto sa bangketa” → road_damage (expected business_permit, confidence 79%)
- “cars parked on the sidewalk sa may school” → road_damage (expected traffic, confidence 93%)
- “Ginawang garahe yung kalye namin, hindi makalabas ang sasakyan” → business_permit (expected traffic, confidence 49%)
- “missing road signs sa kurbada, may naaksidente na” → road_damage (expected traffic, confidence 53%)
- “may nawawalang senior citizen sa aming lugar” → road_damage (expected other, confidence 55%)

## Limitations

- Synthetic reports are generated from phrase banks; scores on them are optimistic.
- The challenge set is small and written by the developers; real LGU reports are the decisive test.
- Retrain with `--real-only` or `--extra-csv` once anonymised LGU complaints are available.