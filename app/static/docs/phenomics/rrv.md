# Respiratory Rate Variability (RRV)

## Overview
Respiratory Rate Variability (RRV) characterizes the fluctuations in breathing rate and inter-breath interval timing during sleep. Analogous to heart rate variability for the cardiac system, RRV reflects the health of the central and autonomic respiratory control network.

## Clinical Implication
RRV is altered in a range of cardiorespiratory and neurological conditions. Reduced RRV (abnormally regular breathing) is seen in Cheyne-Stokes respiration, central sleep apnea, and brainstem lesions. Elevated RRV LF/HF ratio during NREM indicates increased sympathetic respiratory drive and is associated with heart failure and autonomic neuropathy. RRV metrics complement AHI by characterizing the respiratory pattern between discrete events and may detect subtle respiratory control dysfunction in patients with normal AHI.

## Strengths
- Provides information about respiratory control system dynamics not captured by event-based indices
- Distinguishes between types of sleep-disordered breathing (obstructive vs. central pattern)
- Computationally lightweight; requires only a single respiratory channel
- Stage-stratified analysis reveals REM-specific respiratory dysregulation

## Limitations
- Requires accurate breath-to-breath interval detection; noisy signals produce unreliable RRV
- Frequency-domain RRV assumes quasi-stationarity within analysis windows, which may not hold during frequent apneas
- Reference values for RRV metrics during sleep are not well-established
- High body mass index (BMI) can dampen respiratory belt signals, reducing detection accuracy

## Calculation Method
Breath-to-breath intervals (BBI) are extracted from peak-to-peak detection on the respiratory belt or nasal pressure signal after bandpass filtering (0.1–0.8 Hz). Artifact BBIs (> 3× or < 0.3× the local median) are interpolated. **Time-domain metrics**: SDBB (SD of BBI), RMSSD of successive BBI differences, coefficient of variation (CV = SDBB / mean BBI). **Frequency-domain metrics**: Lomb-Scargle periodogram of the BBI series; LF (0.04–0.15 Hz) and HF (0.15–0.4 Hz) power normalized to total power. Computed separately for NREM and REM sleep using ≥ 5-minute artifact-free segments.

## Reference
- Benchetrit G. "Breathing pattern in humans: diversity and individuality." *Respiration Physiology*, 2000.
- Raetz SL et al. "Dynamic characteristics of respiratory pattern and gas exchange during sleep." *Sleep*, 1991.
