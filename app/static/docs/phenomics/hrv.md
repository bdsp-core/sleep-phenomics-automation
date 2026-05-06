# Heart Rate Variability (HRV)

## Overview
Heart rate variability (HRV) measures the variation in time between successive heartbeats (RR intervals) derived from the ECG. During sleep, HRV reflects autonomic nervous system (ANS) balance and is modulated by sleep stage, respiration, and arousal state.

## Output Phenotypes

### Pictures on the website
none

### Phentoype values in CSV to be downloaded
Please check the document in [hrv-analysis](https://aura-healthcare.github.io/hrv-analysis/hrvanalysis.html#module-hrvanalysis.extract_features)
- HRV_mean_nni: Mean NN interval (millisecond)
- HRV_sdnn: standard deviation of NN interval
- HRV_sdsd: standard deviation of differences between adjacent NN intervals
- HRV_nni_50: number of interval differences of successive NN intervals greater than 50 ms.
- HRV_pnni_50: proportion of nni_50 by the total number of NN intervals
- HRV_nni_20: number of interval differences of successive NN intervals greater than 20 ms.
- HRV_pnni_20: proportion of nni_20 by the total number of NN intervals
- HRV_rmssd: square root of the mean of the sum of the squares of differences between adjacent RR intervals
- HRV_median_nni: median absolute of the differences between adjacent NN intervals
- HRV_range_nni: difference between the maximum and minimum nn_interval
- HRV_cvsd: coefficient of variation of successive differences equal to the rmssd divided by mean_nni.
- HRV_cvnni: coefficient of variation equal to the ratio of sdnn divided by mean_nni.
- HRV_mean_hr: mean heart rate (/minute)
- HRV_max_hr: max heart rate (/minute)
- HRV_min_hr: min heart rate (/minute)
- HRV_std_hr: standard deviation of heart rate
- HRV_lf: variance (= power) in the low frequency (0.04-0.15Hz)
- HRV_hf: variance (= power) in the high frequency (0.15-0.4Hz)
- HRV_lf_hf_ratio: lf/hf ratio, could reflect sympatho/vagal balance
- HRV_lfnu: normalized lf power
- HRV_hfnu: normalized hf power
- HRV_total_power: total power spectral density
- HRV_vlf: variance (= power) in the very low frequency (0.003-0.04Hz)
- HRV_sd1: standard deviation of projection of the Poincaré plot on the line perpendicular to the line of identity
- HRV_sd2: standard deviation of the projection of the Poincaré plot on the line of identity (y=x)
- HRV_ratio_sd2_sd1: ratio between SD2 and SD1

## Clinical Implication
RMSSD reflects high frequency (fast or parasympathetic) influences on HRV.
VLF reflects an intrinsic rhythm produced by the heart which is modulated primarily by sympathetic activity.
LF reflects sympathetic activity and can be reduced by the beta-adrenergic antagonist propanolol.
HF reflects fast changes in beat-to-beat variability due to parasympathetic (vagal) activity, which can be decreased by anticholinergic drugs or vagal blockade.

## Strengths
- Captures both short-term (vagal, RMSSD) and long-term (sympathovagal, SDNN) autonomic regulation
- Well-standardized metrics with extensive studies

## Limitations
- Valid computation requires clean R-peak detection; ectopic beats and arrhythmias (e.g., atrial fibrillation) invalidate standard HRV metrics
- HRV norms are age- and sex-dependent; comparison without appropriate reference data is unreliable

## Calculation Method
R-peaks are detected from the ECG using a Pan-Tompkins algorithm followed by artifact rejection (ectopic beat correction via interpolation). Time-domain metrics are computed on artifact-free RR series. Frequency-domain metrics are estimated using Lomb-Scargle periodogram on the irregularly sampled RR series. Non-linear metrics (SD1, SD2) are computed based on the Poincaré plot.

## Reference
- Camm, A. J., Malik, M., Bigger, J. T., Breithardt, G., Cerutti, S., Cohen, R. J., ... & Singer, D. H. (1996). Heart rate variability: standards of measurement, physiological interpretation and clinical use. Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology. Circulation, 93(5), 1043-1065.
