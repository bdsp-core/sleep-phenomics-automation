# Respiratory Self-Similarity

## Overview
Respiratory self-similarity measures the fractal and scale-invariant properties of the breathing pattern during sleep. A healthy respiratory control system produces complex, self-similar variability across timescales — loss of this complexity indicates physiological dysregulation of respiratory drive.
High loop gain (HLG) is a driving mechanism of central sleep apnea or periodic breathing. Self-similarity is a way to identify expressed/manifest HLG via a cyclical self-similarity feature in respiratory effort signals.

## Output Phenotypes

### Pictures on the website
none

### Phentoype values in CSV to be downloaded
- SS_self_sim_perc: percentage of self-similar region
- SS_central_apneas: number of central apneas
- SS_central_hypopneas: number of central hypopneas
- SS_central_apnea_index: number of central apneas per hour of total sleep time
- SS_central_hypopnea_index: number of central hypopneas per hour of total sleep time

## Clinical Implication
Abnormal respiratory self-similarity distinguishes obstructive from central sleep apnea and identifies Cheyne-Stokes respiration in heart failure, where periodic breathing produces characteristic cyclic patterns.

## Strengths
- Sensitive to respiratory control abnormalities not captured by AHI
- Suggest an apnea endotype

## Limitations
- Presence of high similarity is a surrogate for HLG, not a direct measure
- Groundtruth central hypopnea is usually not scored.

## Calculation Method
Self-similarity is calculated by comparing short, consecutive segments of the respiratory effort signal to identify recurring waveform patterns over time; specifically, t
The respiratory effort signal is divided into overlapping windows. The similarity between pairs of windows is quantified using normalized cross-correlation, producing a measure of how repetitively the breathing pattern reproduced itself across cycles, with higher values indicating more periodic and self-similar respiratory dynamics associated with high loop gain.

## Reference
- Oppersma, E., Ganglberger, W., Sun, H., Thomas, R. J., & Westover, M. B. (2021). Algorithm for automatic detection of self-similarity and prediction of residual central respiratory events during continuous positive airway pressure. Sleep, 44(4), zsaa215.
