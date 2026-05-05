# Sleep Staging & Architecture (CAISR)

## Overview
Sleep staging classifies each 30-second epoch of a polysomnography (PSG) recording into one of five stages: Wake (W), REM (R), N1, N2, or N3. The CAISR (Clinical AI Sleep Report) pipeline uses deep learning models to perform automated staging and derives macro-architecture indices from the resulting hypnogram.

## Clinical Implication
Sleep stage distribution is a primary biomarker of neurological and psychiatric health. Reduced slow-wave sleep (N3) is associated with aging, neurodegenerative disease, and metabolic dysfunction. REM sleep abnormalities are linked to REM sleep behavior disorder (RBD), mood disorders, and narcolepsy. Sleep efficiency and WASO reflect overall sleep quality and are key targets in insomnia treatment.

## Strengths
- Provides a complete overnight hypnogram without manual scoring
- Derives multiple macro-architecture indices from a single model pass
- Trained on large multi-site PSG datasets covering diverse populations and equipment
- Consistent and reproducible — eliminates inter-scorer variability

## Limitations
- Performance may degrade for recordings with poor signal quality or non-standard montages
- Model generalization to pediatric populations or severe neurological conditions may be reduced
- Automated staging does not capture all nuances scored by an expert technologist
- Results should be interpreted alongside clinical context, not as standalone diagnoses

## Calculation Method
CAISR applies a multi-channel neural network to EEG, EOG, and chin EMG signals. The model outputs per-epoch posterior probability distributions over the five AASM sleep stages. A hidden Markov model (HMM) post-processing step enforces biologically plausible stage transitions. Macro-architecture features (TST, SE, WASO, REM latency, stage percentages) are derived directly from the scored hypnogram.

## Reference
- Berry RB et al. *AASM Manual for the Scoring of Sleep and Associated Events*, version 2.6. AASM, 2020.
- Phan H et al. "SeqSleepNet: End-to-End Hierarchical Recurrent Neural Network for Sequence-to-Sequence Automatic Sleep Staging." *IEEE Trans Neural Syst Rehabil Eng*, 2019.
