# Respiratory Self-Similarity

## Overview
Respiratory self-similarity measures the fractal and scale-invariant properties of the breathing pattern during sleep. A healthy respiratory control system produces complex, self-similar variability across timescales — loss of this complexity indicates physiological dysregulation of respiratory drive.

## Clinical Implication
Abnormal respiratory self-similarity distinguishes obstructive from central sleep apnea and identifies Cheyne-Stokes respiration in heart failure, where periodic breathing produces characteristic cyclic patterns (elevated regularity, low entropy). Reduced fractal scaling is observed in autonomic neuropathy, COPD, and following opioid use. In premature infants and elderly patients, abnormal respiratory complexity predicts apnea risk and adverse outcomes. Self-similarity metrics also track recovery from respiratory illness and ventilator weaning readiness.

## Strengths
- Sensitive to respiratory control abnormalities not captured by event-based scoring (AHI)
- Distinguishes between different types of sleep-disordered breathing (obstructive, central, mixed)
- Robust to differences in respiratory signal channel (thermistor, nasal pressure, or RIP belt)
- Provides a continuous severity measure along a physiological axis

## Limitations
- Requires sufficient sleep duration (≥ 4 hours) for stable fractal scaling estimates
- DFA scaling exponent interpretation is sensitive to signal preprocessing (detrending, artifact removal)
- Self-similarity metrics are unfamiliar to most clinicians; reference ranges are not yet standardized
- Results are confounded by positional breathing differences and REM vs. NREM-specific patterns

## Calculation Method
Breath-to-breath intervals are derived from the respiratory belt or nasal pressure signal using peak detection. **Detrended Fluctuation Analysis (DFA)**: the RMS fluctuation of the integrated and detrended interval series is computed at multiple timescales (4–256 breaths); the slope of log(fluctuation) vs. log(scale) gives the scaling exponent α. **Sample Entropy (SampEn)**: tolerance r = 0.2 × SD of the series, embedding dimension m = 2, computed on segments of ≥ 200 breaths. Analyses are performed separately for NREM and REM sleep.

## Reference
- Peng CK et al. "Long-range anticorrelations and non-Gaussian behavior of the heartbeat." *Physical Review Letters*, 1993.
- Richman JS, Moorman JR. "Physiological time-series analysis using approximate entropy and sample entropy." *American Journal of Physiology*, 2000.
