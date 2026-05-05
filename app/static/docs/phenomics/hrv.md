# Heart Rate Variability (HRV)

## Overview
Heart rate variability (HRV) measures the variation in time between successive heartbeats (RR intervals) derived from the ECG. During sleep, HRV reflects autonomic nervous system (ANS) balance and is modulated by sleep stage, respiration, and arousal state.

## Clinical Implication
Reduced RMSSD and HF power during sleep are established markers of cardiovascular risk, autonomic neuropathy, and sleep apnea severity. Elevated LF/HF ratio during NREM indicates sympathetic dominance and is elevated in hypertension, heart failure, and diabetes. HRV trajectories across the night differentiate healthy aging from pathological autonomic dysfunction and are prognostic for major adverse cardiovascular events (MACE).

## Strengths
- Well-standardized metrics with extensive normative databases
- Captures both short-term (vagal, RMSSD) and long-term (sympathovagal, SDNN) autonomic regulation
- Non-invasive; derivable from a single ECG lead
- Stage-specific HRV reveals selective autonomic changes in REM vs. NREM that are not visible in daytime recordings

## Limitations
- Valid computation requires clean R-peak detection; ectopic beats and arrhythmias (e.g., atrial fibrillation) invalidate standard HRV metrics
- Frequency-domain interpretation assumes stationarity within analysis windows, which is not strictly met during sleep stage transitions
- LF power is not a pure sympathetic index — it reflects both sympathetic and parasympathetic contributions
- HRV norms are age- and sex-dependent; comparison without appropriate reference data is unreliable

## Calculation Method
R-peaks are detected from the ECG using a Pan-Tompkins algorithm followed by artifact rejection (ectopic beat correction via interpolation). Time-domain metrics (SDNN, RMSSD, pNN50) are computed per sleep stage on artifact-free RR series. Frequency-domain metrics (LF: 0.04–0.15 Hz, HF: 0.15–0.4 Hz) are estimated using Lomb-Scargle periodogram on the irregularly sampled RR series. Non-linear metrics (SD1, SD2, SampEn) are computed on 5-minute windows within each sleep stage.

## Reference
- Task Force of the European Society of Cardiology. "Heart rate variability: standards of measurement, physiological interpretation, and clinical use." *Circulation*, 1996.
- Penzel T et al. "Comparison of detrended fluctuation analysis and spectral analysis for heart rate variability in sleep and sleep apnea." *IEEE Trans Biomed Eng*, 2003.
