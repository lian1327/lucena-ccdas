# Classifier v3 evaluation

Algorithm selected: **logistic_regression** (highest cross-validated macro-F1 (category)). Features: TF-IDF word 1–2-grams + char_wb 2–5-grams on normalised text.
Data: {'synthetic': 3045} → 2436 training / 609 held-out test reports.

## Model comparison (category)

| Model | CV macro-F1 (5-fold) | Test accuracy | Test macro-F1 |
|---|---|---|---|
| majority_baseline | — | 0.217 | 0.044 |
| complement_nb | 0.996 ± 0.003 | 1.000 | 1.000 |
| logistic_regression | 0.997 ± 0.004 | 0.998 | 0.998 |
| linear_svm | 0.997 ± 0.004 | 1.000 | 1.000 |

## Per category (held-out test set)

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Business Permit Concerns | 1.000 | 1.000 | 1.000 | 23 |
| Drainage Problems | 1.000 | 1.000 | 1.000 | 101 |
| Other Community Issues | 1.000 | 1.000 | 1.000 | 38 |
| Public Safety Concerns | 0.982 | 1.000 | 0.991 | 53 |
| Road Damage | 1.000 | 1.000 | 1.000 | 93 |
| Solid Waste Concerns | 1.000 | 0.992 | 0.996 | 132 |
| Streetlight Issues | 1.000 | 1.000 | 1.000 | 74 |
| Traffic Concerns | 1.000 | 1.000 | 1.000 | 95 |

Category accuracy **0.998**, macro-F1 **0.998**. Sub-type accuracy 0.998.

## Auto-assign policy (confidence threshold vs. coverage)

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 99.5% | 100.0% |
| ≥ 60% | 99.3% | 100.0% |
| ≥ 70% | 98.0% | 100.0% |
| ≥ 80% | 93.3% | 100.0% |
| ≥ 90% | 81.9% | 100.0% |

## Hand-written challenge set

161 complaints written independently of the synthetic generator: accuracy **0.919**, macro-F1 **0.897**, sub-type accuracy 0.876.

| Category | Precision | Recall | F1 | n |
|---|---|---|---|---|
| Business Permit Concerns | 1.000 | 0.867 | 0.929 | 15 |
| Drainage Problems | 1.000 | 0.920 | 0.958 | 25 |
| Other Community Issues | 1.000 | 0.500 | 0.667 | 6 |
| Public Safety Concerns | 0.926 | 1.000 | 0.962 | 25 |
| Road Damage | 0.742 | 0.920 | 0.821 | 25 |
| Solid Waste Concerns | 0.950 | 0.950 | 0.950 | 20 |
| Streetlight Issues | 0.950 | 0.950 | 0.950 | 20 |
| Traffic Concerns | 0.958 | 0.920 | 0.939 | 25 |

Auto-assign on the challenge set:

| Threshold | Share auto-assigned | Accuracy of those |
|---|---|---|
| ≥ 50% | 87.6% | 95.0% |
| ≥ 60% | 80.8% | 98.5% |
| ≥ 70% | 72.7% | 100.0% |
| ≥ 80% | 63.3% | 100.0% |
| ≥ 90% | 51.5% | 100.0% |

Misclassified examples:

- “The asphalt near the public market is peeling off, ang daming bato na nagkalat” → streetlight (expected road_damage, confidence 22%)
- “Ang mga materyales ng ginagawang bahay nasa kalsada na po” → solid_waste (expected road_damage, confidence 22%)
- “blinking street lamp sa Maharlika, baka masira na tuluyan” → road_damage (expected streetlight, confidence 41%)
- “konting ulan lang lubog na agad yung kalsada sa amin” → road_damage (expected drainage, confidence 51%)
- “broken drainage pipe sa ilalim ng kalsada, may sinkhole na” → road_damage (expected drainage, confidence 56%)
- “yung MRF namin sobrang puno na, hindi na makapagtapon” → public_safety (expected solid_waste, confidence 41%)
- “nagtitinda ng prutas sa mismong kalsada, traffic tuloy” → traffic (expected business_permit, confidence 55%)
- “pakiayos po yung mga nakapwesto sa bangketa” → road_damage (expected business_permit, confidence 56%)
- “cars parked on the sidewalk sa may school” → road_damage (expected traffic, confidence 64%)
- “missing road signs sa kurbada, may naaksidente na” → road_damage (expected traffic, confidence 66%)
- “may nawawalang senior citizen sa aming lugar” → road_damage (expected other, confidence 35%)
- “saan po pwede mag-apply ng scholarship ng city?” → road_damage (expected other, confidence 18%)

## Limitations

- Synthetic reports are generated from phrase banks; scores on them are optimistic.
- The challenge set is small and written by the developers; real LGU reports are the decisive test.
- Retrain with `--real-only` or `--extra-csv` once anonymised LGU complaints are available.