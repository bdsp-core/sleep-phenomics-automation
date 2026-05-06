# EEG Band Power

## Overview
EEG band power quantifies the amplitude of the spectral components of the EEG signal within several frequency bands averaged by sleep stage.
The frequency bands include:
- slow: 0.3-1Hz
- delta: 1-4Hz
- theta: 4-8Hz
- alpha: 8-12Hz
- sigma: 11-16Hz
- beta: 12-30Hz

## Output Phenotypes

### Pictures on the website
- Spectrogram

### Phentoype values in CSV to be downloaded
- BP_\<abs/rel\>_\<band\>_\<channel\>_\<sleep stage\>: (absolute or relative) band power at a channel during a sleep stage. Absolute power is in decibels (10xlog10(uV^2/Hz)). Relative power is in %, where total power is from 0.3-35Hz.

## Clinical Implication
Band power profiles are sensitive to aging, sleep disorders, and pharmacological effects. Reduced delta power during N3 reflects reduced sleep depth. Elevated beta power during sleep is associated with insomnia. Sigma power captures sleep spindle density.

## Strengths
- Well-established
- Provides channel- and stage-specific resolution, enabling localized comparisons
- Both absolute (dB) and relative (%) power are reported, allowing normalization for individual differences in overall signal amplitude

## Limitations
- Sensitive to electrode impedance, movement artifacts, and amplifier drift
- Absolute power values are not directly comparable across recording systems or electrode placements
- Requires sufficient sleep in each stage for stable estimates (sparse N3 epochs reduce reliability of N3-specific metrics)
- Does not capture temporal dynamics within an epoch (e.g., spindle bursts vs. sustained power)

## Calculation Method
Power spectral density (PSD) is estimated using the multitaper method (bandwidth = 0.5Hz, 7 tapers) applied to non-overlapping 30-second epochs.

## Reference
- Prerau, M. J., Brown, R. E., Bianchi, M. T., Ellenbogen, J. M., & Purdon, P. L. (2017). Sleep neurophysiological dynamics through the lens of multitaper spectral analysis. Physiology, 32(1), 60-92.
