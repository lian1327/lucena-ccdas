# Classifier v2 evaluation

Algorithm selected: **linear_svm** (highest cross-validated macro-F1 (category)). Features: TF-IDF word 1–2-grams + char_wb 2–5-grams on normalised text.
Data: {'real': 4, 'synthetic': 3977} → 3184 training / 797 held-out test reports.

## Model comparison (category)

| Model | CV macro-F1 (5-fold) | Test accuracy | Test macro-F1 |
|---|---|---|---|
| majority_baseline | — | 0.197 | 0.041 |
| complement_nb | 0.996 ± 0.004 | 0.998 | 0.996 |
| logistic_regression | 0.999 ± 0.002 | 1.000 | 1.000 |
| linear_svm | 0.999 ± 0.003 | 1.000 | 1.000 |

## Per category (held-out test set)

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Business Permit Concerns | 1.000 | 1.000 | 1.000 | 27 |
| Drainage Problems | 1.000 | 1.000 | 1.000 | 139 |
| Other Community Issues | 1.000 | 1.000 | 1.000 | 41 |
| Public Safety Concerns | 1.000 | 1.000 | 1.000 | 84 |
| Road Damage | 1.000 | 1.000 | 1.000 | 121 |
| Solid Waste Concerns | 1.000 | 1.000 | 1.000 | 157 |
| Streetlight Issues | 1.000 | 1.000 | 1.000 | 104 |
| Traffic Concerns | 1.000 | 1.000 | 1.000 | 124 |

Category accuracy **1.000**, macro-F1 **1.000**. Sub-type accuracy 0.999.

## Auto-assign policy (confidence threshold vs. coverage)

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 100.0% | 100.0% |
| ≥ 60% | 100.0% | 100.0% |
| ≥ 70% | 100.0% | 100.0% |
| ≥ 80% | 100.0% | 100.0% |
| ≥ 90% | 99.2% | 100.0% |

## Hand-written challenge set

161 complaints written independently of the synthetic generator: accuracy **0.913**, macro-F1 **0.892**, sub-type accuracy 0.857.

| Category | Precision | Recall | F1 | n |
|---|---|---|---|---|
| Business Permit Concerns | 1.000 | 0.800 | 0.889 | 15 |
| Drainage Problems | 1.000 | 0.960 | 0.980 | 25 |
| Other Community Issues | 1.000 | 0.500 | 0.667 | 6 |
| Public Safety Concerns | 0.958 | 0.920 | 0.939 | 25 |
| Road Damage | 0.676 | 0.920 | 0.780 | 25 |
| Solid Waste Concerns | 0.952 | 1.000 | 0.976 | 20 |
| Streetlight Issues | 0.950 | 0.950 | 0.950 | 20 |
| Traffic Concerns | 1.000 | 0.920 | 0.958 | 25 |

Auto-assign on the challenge set:

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 95.7% | 94.2% |
| ≥ 60% | 89.4% | 97.2% |
| ≥ 70% | 85.1% | 98.5% |
| ≥ 80% | 81.4% | 99.2% |
| ≥ 90% | 70.8% | 100.0% |

Misclassified examples:

- “The asphalt near the public market is peeling off, ang daming bato na nagkalat” → streetlight (expected road_damage, confidence 44%)
- “Ang mga materyales ng ginagawang bahay nasa kalsada na po” → solid_waste (expected road_damage, confidence 28%)
- “blinking street lamp sa Maharlika, baka masira na tuluyan” → road_damage (expected streetlight, confidence 54%)
- “konting ulan lang lubog na agad yung kalsada sa amin” → road_damage (expected drainage, confidence 63%)
- “Ang daming aso sa kalye, hinahabol ang mga nagmomotor” → road_damage (expected public_safety, confidence 44%)
- “karerahan ng motor sa diversion road tuwing gabi, ang ingay” → road_damage (expected public_safety, confidence 44%)
- “Puno ng vendors yung sidewalk sa bayan, napipilitan kaming maglakad sa kalsada” → road_damage (expected business_permit, confidence 59%)
- “sidewalk sa may terminal ginawang palengke” → road_damage (expected business_permit, confidence 54%)
- “pakiayos po yung mga nakapwesto sa bangketa” → road_damage (expected business_permit, confidence 70%)
- “cars parked on the sidewalk sa may school” → road_damage (expected traffic, confidence 88%)
- “missing road signs sa kurbada, may naaksidente na” → road_damage (expected traffic, confidence 56%)
- “may nawawalang senior citizen sa aming lugar” → road_damage (expected other, confidence 56%)

## Limitations

- Synthetic reports are generated from phrase banks; scores on them are optimistic.
- The challenge set is small and written by the developers; real LGU reports are the decisive test.
- Retrain with `--real-only` or `--extra-csv` once anonymised LGU complaints are available.