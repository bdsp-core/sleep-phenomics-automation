# Sleep Spindles & Slow Oscillations

## Overview
Sleep spindles (11–16 Hz bursts) and slow oscillations (SOs, <1 Hz) are the defining micro-scale events of NREM sleep. Their co-occurrence and temporal coupling are fundamental to sleep-dependent memory consolidation and synaptic homeostasis.

## Output Phenotypes

### Pictures on the website
none

### Phentoype values in CSV to be downloaded
Please check the document in [Luna](https://zzz.nyspi.org/luna/ref/spindles-so/).
SP_DENS_<channel>_<all/fast/slow>: spindle density (/minute)
SP_CDENS_<channel>_<all/fast/slow>: SO-coupled spindle density
SP_UDENS_<channel>_<all/fast/slow>: SO-uncoupled spindle density
SP_DUR_<channel>_<all/fast/slow>: spindle duration (second)
SP_FRQ_<channel>_<all/fast/slow>: spindle frequency (Hz)
SP_FVAR_<channel>_<all/fast/slow>: spindle frequency variance
SP_CHIRP_<channel>_<all/fast/slow>: spindle chirp
SP_AMP_<channel>_<all/fast/slow>: spindle amplitude
SP_ISA_S_<channel>_<all/fast/slow>: integrated spindle activity averaged across spindles
SP_R_PHASE_IF_<channel>_<all/fast/slow>: circular correlation between SO phase and spindle instantaneous frequency
SP_SYMM_<channel>_<all/fast/slow>: spindle symmetry
SP_DISPERSION_<channel>_<all/fast/slow>: spindle dispersion
SP_DISPERSION_P_<channel>_<all/fast/slow>: spindle dispersion p-value
SP_Q_<channel>_<all/fast/slow>: spindle quality index
SO_<channel>: SO count
SO_AMP_P2P_<channel>: SO peak-to-peak amplitude
SO_AMP_NEG_<channel>: SO negative peak amplitude
SO_AMP_POS_<channel>: SO positive peak amplitude
SO_DUR_<channel>: SO duration
SO_DUR_NEG_<channel>: SO negative peak duration
SO_DUR_POS_<channel>: SO positive peak duration
SO_RATE_<channel>: SO rate (density, /minute)
SO_SLOPE_<channel>: SO peak-to-peak slope
SP_COUPL_ANGLE_<channel>_<all/fast/slow>: spindle-SO coupling phase angle
SP_COUPL_MAG_<channel>_<all/fast/slow>: spindle-SO coupling magitude
SP_COUPL_OVERLAP_<channel>_<all/fast/slow>: spindle-SO coupling overlap
SP_COUPL_PV_<channel>_<all/fast/slow>: spindle-SO coupling p-value

## Clinical Implication
Spindle density declines with aging and is further reduced in Alzheimer's disease, schizophrenia, and following traumatic brain injury. SO amplitude is diminished in depression and chronic insomnia. The degree of spindle coupled within the SO up-state (spindle–SO coupling) is related to memory consolidation.

## Strengths
- Reports spindle and slow oscillation characteristics that are not in standard clinical scoring
- Spindle–SO coupling index offers a mechanistically grounded biomarker of memory function

## Limitations
- Detection thresholds require calibration; results can vary across detection algorithms
- Requires sufficient N2/N3 sleep for stable event counts

## Calculation Method
Implemented in [Luna](https://zzz.nyspi.org/luna/ref/spindles-so/).

## Reference
- Purcell, S. M., Manoach, D. S., Demanuele, C., Cade, B. E., Mariani, S., Cox, R., ... & Stickgold, R. (2017). Characterizing sleep spindles in 11,630 individuals from the National Sleep Research Resource. Nature communications, 8(1), 15930.
