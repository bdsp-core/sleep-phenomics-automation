# Cardiopulmonary Coupling (CPC)

## Overview
Cardiopulmonary coupling (CPC) analyzes the interaction between cardiac and respiratory rhythms during sleep via cross-spectral analysis of the ECG-derived respiratory signal (EDR) and the RR interval series. It quantifies stable versus unstable sleep physiology independently of traditional event-based scoring.

## Clinical Implication
CPC-derived stable sleep percentage is reduced in OSA, UARS, insomnia, and heart failure with Cheyne-Stokes respiration. The low-frequency coupling (LFC) component correlates strongly with AHI and arousal index, and provides continuous severity grading of sleep-disordered breathing. CPC has been validated as a surrogate for PSG-derived respiratory disturbance in large epidemiological cohorts and predicts incident cardiovascular disease independently of AHI.

## Strengths
- Provides a continuous, automated measure of sleep quality requiring only ECG — no separate respiratory sensor needed
- Highly robust to missing or noisy respiratory signals since respiratory effort is derived from ECG
- Sensitive to subtle cardiorespiratory dysregulation not captured by AHI or arousal index alone
- Validated in population-scale studies (Sleep Heart Health Study, MrOS Sleep Study)

## Limitations
- ECG-derived respiration is an indirect measure and may be inaccurate in patients with cardiac conduction abnormalities or obesity
- Performance is reduced in atrial fibrillation and frequent ectopy
- CPC components do not map directly to AASM-defined respiratory events, complicating clinical interpretation
- Reference ranges are population-derived and may not apply to all clinical subgroups

## Calculation Method
The ECG-derived respiratory signal (EDR) is extracted from beat-to-beat QRS amplitude modulation. Cross-spectral coherence between EDR and the RR interval series is computed using the multitaper method on 8.5-minute non-overlapping windows. Coherent power is partitioned into three components: elevated low-frequency coupling (e-LFC, 0.01–0.1 Hz, high coherence — stable NREM), high-frequency coupling (HFC, 0.1–0.4 Hz — stable sleep), and low-frequency coupling (LFC, 0.01–0.1 Hz, low coherence — unstable/apneic sleep). The coupling ratio is e-LFC / (e-LFC + LFC).

## Reference
- Thomas RJ, Mietus JE, Peng CK, Goldberger AL. "An electrocardiogram-based technique to assess cardiopulmonary coupling during sleep." *Sleep*, 2005.
- Thomas RJ et al. "Validation of a new sleep-quality biomarker." *Sleep*, 2014.
