# Arousal Burden

## Overview
Arousal burden quantifies the cumulative disruption of sleep continuity caused by cortical arousals — brief (3–15 second) returns toward wakefulness detectable in the EEG. Arousals fragment sleep architecture and impair restorative processes even when the subject does not consciously wake.

## Clinical Implication
Elevated arousal burden is the primary mechanism of non-restorative sleep in insomnia, upper airway resistance syndrome (UARS), and PTSD-related sleep disturbance. It is also elevated in periodic limb movement disorder, where each limb movement may trigger a cortical arousal. Arousal burden independently predicts daytime fatigue, cognitive performance deficits, and mood dysregulation. It is more sensitive than AHI for detecting mild sleep-disordered breathing (UARS) in patients without frank oxygen desaturation.

## Strengths
- Captures sleep fragmentation that is not visible in macro-architecture metrics (e.g., a patient with normal TST but high arousal burden)
- Continuous metric that tracks intervention response in pharmacological and behavioral sleep therapies
- More sensitive than AHI for UARS and mild OSA
- Provides complementary information to respiratory and movement event indices

## Limitations
- Arousal detection from EEG is sensitive to artifact; chin EMG arousals during REM require concurrent EMG activation per AASM rules
- Automated detection may under-count arousals in epochs with high-amplitude artifact
- Subcortical arousals (not visible in scalp EEG) are not captured
- Requires chin EMG for REM arousals; EEG-only arousal detection may miss REM-specific events

## Calculation Method
Arousal detection is performed by CAISR's arousal model, a deep learning classifier trained on expert-annotated PSG data using EEG and chin EMG channels. Detected events must meet AASM 2020 criteria: abrupt EEG frequency shift ≥ 3 seconds duration, preceded by ≥ 10 seconds of stable sleep, with concurrent chin EMG activation during REM. Arousal burden index = total arousal duration / total sleep time × 100 (%). Arousal index = total arousal count / total sleep time in hours.

## Reference
- Berry RB et al. *AASM Manual for the Scoring of Sleep and Associated Events*, version 2.6. AASM, 2020.
- Thomas RJ et al. "An electroencephalogram-based system to detect the sleep arousal burden." *Sleep*, 2014.
