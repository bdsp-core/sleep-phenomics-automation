# Cardiopulmonary Coupling (CPC)

## Overview
Cardiopulmonary coupling (CPC) analyzes the interaction between cardiac and respiratory rhythms during sleep via cross-spectral analysis of the ECG-derived respiratory signal (EDR) and the RR interval series. It quantifies stable versus unstable sleep states independent of sleep stages.

## Output Phenotypes

### Pictures on the website
- CPC spectrogram in a mountain plot

### Phentoype values in CSV to be downloaded
- CPC_log_HF_power: log high frequency band power (0.1-0.4Hz), representing stable sleep
- CPC_log_LF_power: log low frequency band power (0.01-0.1Hz), representing unstable sleep
- CPC_log_VLF_power: log very low frequency band power (\<0.01Hz), representing W/REM sleep
- CPC_LF_HF_ratio: LF to HF ratio
- CPC_VLF_LH_ratio: VLF to (LF+HF) ratio

## Clinical Implication
CPC-derived stable sleep is reduced in OSA and insomnia. The HF coupling (HFC) component is associated with slow wave activity in EEG. CPC has been validated as a surrogate for PSG-derived respiratory disturbance in large epidemiological cohorts and predicts incident cardiovascular disease independently of AHI.

## Strengths
- Sensitive to subtle cardiorespiratory dysregulation not captured by AHI or arousal index alone
- Provides a continuous, automated measure of sleep quality based on ECG
- Validated in population-scale studies

## Limitations
- CPC is influenced by arrythmia such as atrial fibrillation and frequent ectopy
- CPC is sensitive to artifacts in R peaks

## Calculation Method
From a continuous, single-lead ECG, we extracted both the normal-to-normal sinus interbeat interval series and a corresponding electrocardiogram-derived respiration signal. Employing Fourier-based techniques, the product of the coherence and cross-power of these 2 simultaneous signals was used to generate a spectrographic representation of cardiopulmonary coupling dynamics during sleep. 

## Reference
- Thomas, R. J., Mietus, J. E., Peng, C. K., & Goldberger, A. L. (2005). An electrocardiogram-based technique to assess cardiopulmonary coupling during sleep. Sleep, 28(9), 1151-1161.
