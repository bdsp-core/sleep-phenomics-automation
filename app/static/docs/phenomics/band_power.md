# EEG Band Power

## Overview
EEG band power quantifies the spectral energy of the EEG signal within canonical frequency bands (delta, theta, alpha, sigma, beta) stratified by sleep stage. It is one of the most widely reported EEG phenotypes in sleep research and clinical neurophysiology.

## Clinical Implication
Band power profiles are sensitive to aging, sleep disorders, and pharmacological effects. Reduced delta power during N3 reflects impaired sleep depth and is elevated in Alzheimer's disease risk. Elevated beta activity during sleep is a hallmark of cortical hyperarousal in chronic insomnia. Sigma power captures sleep spindle density and is linked to memory consolidation capacity.

## Strengths
- Well-validated across decades of sleep EEG literature
- Provides channel- and stage-specific resolution, enabling localized comparisons
- Both absolute (dB) and relative (%) power are reported, allowing normalization for individual differences in overall signal amplitude
- Sensitive to subtle medication and intervention effects

## Limitations
- Sensitive to electrode impedance, movement artifacts, and amplifier drift
- Absolute power values are not directly comparable across recording systems or electrode placements
- Requires sufficient sleep in each stage for stable estimates (sparse N3 epochs reduce reliability of N3-specific metrics)
- Does not capture temporal dynamics within an epoch (e.g., spindle bursts vs. sustained power)

## Calculation Method
Power spectral density (PSD) is estimated using the multitaper method (time-bandwidth product = 4, 7 tapers) applied to non-overlapping 30-second epochs. Absolute band power is computed by integrating the PSD over each frequency band. Relative power is expressed as the fraction of total broadband power (0.3–35 Hz). Results are averaged across artifact-free epochs within each sleep stage. Output columns follow the pattern `BP_abs_<band>_<channel>_<stage>` and `BP_rel_<band>_<channel>_<stage>`.

## Reference
- Prerau MJ et al. "Sleep Neurophysiological Dynamics Through the Lens of Multitaper Spectral Analysis." *Physiology*, 2017.
- Rechtschaffen A, Kales A. *A Manual of Standardized Terminology, Techniques and Scoring System for Sleep Stages of Human Subjects*. NIH Publication, 1968.
