# Sleep Staging & Apnea/Arousal/Limb Movement Detection with CAISR

## Overview
Complete Artificial Intelligence Sleep Report (CAISR) is a system for comprehensive automated sleep analysis, including sleep staging, arousal detection, apnea identification, and limb movement analysis.

## Output Phenotypes

### Pictures on the website
- Hypnogram
- Hypnodensity

### Phentoype values in CSV to be downloaded
- MACRO_CAISR_hours_psg: time in bed (hour)
- MACRO_CAISR_hours_sleep: total sleep time (hour)
- MACRO_CAISR_sleep_efficiency: sleep efficiency (%)
 - MACRO_CAISR_sleep_latency: sleep onset (minute)
 - MACRO_CAISR_waso: Wake after sleep onset (minute)
 - MACRO_CAISR_r_latency: REM latency from first sleep epoch (minute)
 - MACRO_CAISR_W_min: Wake time (minutes)
 - MACRO_CAISR_N1_min: N1 time (minutes)
 - MACRO_CAISR_N2_min: N2 time (minutes)
 - MACRO_CAISR_N3_min: N3 time (minutes)
 - MACRO_CAISR_REM_min: REM time (minutes)
 - MACRO_CAISR_perc_n1: N1 percent in TST (%)
 - MACRO_CAISR_perc_n2: N2 percent in TST (%)
 - MACRO_CAISR_perc_n3: N3 percent in TST (%)
 - MACRO_CAISR_perc_r: REM percent in TST (%)
 - MACRO_CAISR_sfi: sleep fragmentation index

## Clinical Implication
The sleep architecture (macrostructure) provides basic information about the overall structure of sleep, such as sleep latency, wake after sleep onset, and sleep fragmentation.

## Strengths
- Provides a complete overnight hypnogram, apnea/hypopnea, arousal, and limb movements without manual scoring
- Trained on large multi-site PSG datasets covering diverse populations and equipment
- Consistent and reproducible — eliminates inter-scorer variability

## Limitations
- Performance may degrade for recordings with poor signal quality or non-standard montages
- Performance may degrade for pediatric population
- Automated staging does not capture all nuances scored by an expert technologist
- Results should be interpreted alongside clinical context, not as standalone diagnoses

## Calculation Method
CAISR applies a both deep learning and rule-based approaches to EEG, EOG, chin EMG, limb EMG, and respiratory signals.

## Reference
- Nasiri, S., Ganglberger, W., Nassi, T., Meulenbrugge, E. J., Moura Junior, V., Ghanta, M., ... & Westover, M. B. (2025). CAISR: achieving human-level performance in automated sleep analysis across all clinical sleep metrics. Sleep, 48(8), zsaf134.
- Haba-Rubio, J., Ibanez, V., & Sforza, E. (2004). An alternative measure of sleep fragmentation in clinical practice: the sleep fragmentation index. Sleep medicine, 5(6), 577-581.
