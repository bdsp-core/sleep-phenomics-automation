# Sleep Spindles & Slow Oscillations

## Overview
Sleep spindles (11–16 Hz bursts) and slow oscillations (SOs, <1 Hz) are the defining micro-scale events of NREM sleep. Their co-occurrence and temporal coupling are fundamental to sleep-dependent memory consolidation and synaptic homeostasis.

## Clinical Implication
Spindle density declines with aging and is further reduced in Alzheimer's disease, schizophrenia, and following traumatic brain injury. SO amplitude is diminished in depression and chronic insomnia. The degree of spindle nesting within the SO up-state (spindle–SO coupling) is a direct measure of hippocampal-neocortical memory replay efficiency and is reduced in MCI and early dementia.

## Strengths
- Provides event-level resolution beyond coarse spectral power estimates
- Spindle–SO coupling index offers a mechanistically grounded biomarker of memory function
- Detects changes that are invisible to standard clinical scoring
- Applicable to single-channel EEG, making it suitable for ambulatory recordings

## Limitations
- Detection thresholds require calibration; results can vary across detection algorithms
- Spindle morphology varies substantially across frontal, central, and parietal electrodes
- Requires sufficient N2/N3 sleep for stable event counts
- Coupling metrics require aligned spindle and SO event lists and are sensitive to detection errors in either event type

## Calculation Method
Slow oscillations are detected as negative half-waves exceeding 75 µV peak-to-peak with a period of 0.5–2 seconds in N2/N3 epochs. Spindles are detected using a bandpass filter (11–16 Hz), envelope extraction, and amplitude thresholding (mean + 1.5 SD relative to a per-channel N2 baseline). Spindle–SO coupling is quantified by the mean vector length (modulation index) of the spindle envelope amplitude as a function of SO phase, estimated using the Hilbert transform.

## Reference
- Mölle M et al. "Grouping of spindle activity during slow oscillations in human non-rapid eye movement sleep." *Journal of Neuroscience*, 2002.
- Helfrich RF et al. "Bidirectional prefrontal-hippocampal dynamics organize information transfer during sleep for memory consolidation." *Nature Communications*, 2018.
