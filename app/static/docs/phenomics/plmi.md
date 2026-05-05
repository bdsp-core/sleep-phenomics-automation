# Periodic Limb Movement Index (PLMI)

## Overview
The Periodic Limb Movement Index (PLMI) counts the number of periodic limb movements (PLMs) per hour of sleep. PLMs are repetitive, stereotyped EMG bursts in the leg muscles that occur in sequences during sleep and can trigger cortical arousals and sleep fragmentation.

## Clinical Implication
PLMI ≥ 15/hour meets the AASM threshold for periodic limb movement disorder (PLMD) when accompanied by clinical symptoms. PLMs are highly prevalent in restless legs syndrome (RLS, >80% of patients), narcolepsy, and REM sleep behavior disorder. Elevated PLMI is independently associated with hypertension, coronary artery disease, and stroke risk. PLM-associated arousals are a significant but often under-recognized cause of non-restorative sleep and excessive daytime sleepiness.

## Strengths
- Provides objective, automated scoring of an otherwise labor-intensive manual task
- PLM-associated arousal index offers a functional measure of sleep disruption from limb movements
- PLMI is a diagnostic criterion for PLMD and a severity measure in RLS
- Stage-specific PLM counts distinguish sleep-state-dependent from state-independent motor activity

## Limitations
- Requires bilateral leg EMG placement (tibialis anterior); unilateral recording misses contralateral-only events
- Artifact rejection is critical — movement, sweat, and electrode noise can produce false positives
- PLM counts vary night-to-night; a single-night estimate may not be representative
- Does not distinguish between idiopathic PLM and PLM secondary to OSA or medications (e.g., antidepressants, dopamine antagonists)

## Calculation Method
Limb movement events are detected by CAISR's EMG classifier from leg EMG channels. Candidate movements must have duration 0.5–10 seconds and amplitude exceeding 8 µV above resting baseline. A series is classified as periodic if ≥ 4 consecutive movements occur with inter-movement intervals of 5–90 seconds. PLM events coinciding with respiratory events (within 2 seconds of an apnea/hypopnea termination) are excluded per AASM rules. PLM-associated arousals are flagged when a cortical arousal is detected within 0.5–2 seconds of a PLM onset.

## Reference
- Berry RB et al. *AASM Manual for the Scoring of Sleep and Associated Events*, version 2.6. AASM, 2020.
- Ferri R et al. "Computer-assisted detection of nocturnal leg motor activity in patients with restless legs syndrome and periodic leg movements during sleep." *Sleep*, 2005.
