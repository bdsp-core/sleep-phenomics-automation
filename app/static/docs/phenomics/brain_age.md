# EEG Brain Age

## Overview
Brain age estimation uses machine learning to predict a subject's neurological age from sleep EEG features. The gap between predicted brain age and chronological age — the **brain age gap (BAG)** — is an index of brain health and resilience.

## Clinical Implication
A positive BAG (brain appears older than chronological age) is associated with cognitive decline, Alzheimer's disease risk, poor sleep quality, metabolic syndrome, and chronic stress. A negative BAG (younger-appearing brain) is generally associated with better brain health. BAG has been proposed as a surrogate endpoint in clinical trials targeting brain aging and as a longitudinal biomarker for monitoring intervention effects.

## Strengths
- Provides a single continuous summary of overall sleep EEG health
- Captures multivariate EEG features that are not captured by any single spectral measure
- Trained on normative data spanning a wide age range, enabling cross-sectional comparison to peers
- Non-invasive and derived from standard PSG without additional hardware

## Limitations
- Accuracy depends on signal quality and consistent electrode placement
- The model was trained on adult data; accuracy is reduced for ages outside the training range (<18 or >85 years)
- BAG is a statistical construct — individual predictions have uncertainty bounds (~5 years typical RMSE)
- Does not account for all sources of EEG variability (e.g., skull thickness, medications, hair/scalp impedance)
- Results are not validated for clinical diagnosis; intended for research use only

## Calculation Method
EEG spectral features (band power per channel and stage, spindle metrics, spectral edge frequency) are extracted from artifact-free NREM epochs. A regularized regression model (trained on normative PSG data from adults aged 18–85) maps these features to predicted age. The brain age gap is computed as `BAG = predicted_age − actual_age`. Actual age must be provided by the user for BAG computation; the model prediction itself does not require age as input.

## Reference
- Gómez C et al. "Age-related changes in EEG power spectral density during sleep." *Sleep Medicine*, 2019.
- Vézard L et al. "Sleep-based brain age estimation: from adult to aging brain." *Journal of Sleep Research*, 2022.
