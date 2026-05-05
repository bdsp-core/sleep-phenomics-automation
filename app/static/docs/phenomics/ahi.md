# Apnea-Hypopnea Index (AHI)

## Overview
The Apnea-Hypopnea Index (AHI) is the standard clinical metric for diagnosing and grading obstructive sleep apnea (OSA). It counts the total number of apneas and hypopneas per hour of sleep and determines OSA severity classification per AASM guidelines.

## Clinical Implication
OSA affects approximately 1 billion people worldwide and is an independent risk factor for hypertension, atrial fibrillation, stroke, type 2 diabetes, and all-cause mortality. AHI is the primary criterion for initiating CPAP therapy. Moderate-to-severe OSA (AHI ≥ 15) is associated with a 2–3× increased risk of cardiovascular events. AHI also guides surgical decision-making and tracks treatment efficacy in longitudinal follow-up.

**Severity classification:**
| AHI (events/hour) | Severity |
|---|---|
| < 5 | Normal |
| 5 – 14.9 | Mild OSA |
| 15 – 29.9 | Moderate OSA |
| ≥ 30 | Severe OSA |

## Strengths
- Universally accepted clinical standard; enables comparison across institutions and studies
- Detects multiple respiratory event subtypes (obstructive, central, mixed, hypopnea, RERA)
- Provides a severity grade directly linked to treatment decision thresholds
- Automated CAISR scoring reduces manual technologist time

## Limitations
- AHI is a crude summary measure — two patients with the same AHI can have very different clinical severity depending on desaturation depth, event duration, and arousal frequency
- AHI underestimates OSA severity in REM-predominant or positional OSA
- Automated detection performance depends on signal quality of nasal pressure and respiratory belt channels
- AASM hypopnea criteria have changed across versions (2007 vs. 2012); ensure consistent rule application when comparing across datasets

## Calculation Method
Respiratory events are detected using CAISR's rule-based pipeline applied to nasal pressure (or thermistor), thoracic and abdominal respiratory inductance plethysmography (RIP), and SpO₂. Events are classified per AASM 2023 hierarchy:
- **Apnea**: ≥ 90% airflow reduction for ≥ 10 s
- **Hypopnea**: ≥ 30% airflow reduction for ≥ 10 s with ≥ 3% SpO₂ drop or arousal
- **RERA**: arousal-terminated airflow limitation not meeting apnea/hypopnea criteria

AHI = (apnea count + hypopnea count) / total sleep time in hours.

## Reference
- Berry RB et al. *AASM Manual for the Scoring of Sleep and Associated Events*, version 2.6. AASM, 2020.
- Benjafield AV et al. "Estimation of the global prevalence and burden of obstructive sleep apnoea: a literature-based analysis." *Lancet Respiratory Medicine*, 2019.
