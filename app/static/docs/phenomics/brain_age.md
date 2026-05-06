# EEG Brain Age

## Overview
The human electroencephalogram (EEG) of sleep undergoes profound changes with age. These changes can be conceptualized as "brain age (BA)," which can be compared to chronological age to reflect the degree of deviation from normal aging. 

## Output Phenotypes

### Pictures on the website
none

### Phentoype values in CSV to be downloaded
- brain_age: brain age (BA), in years
- brain_age_index: BAI, BA - chronological age, in years

## Clinical Implication
A positive brain age index (BAI, brain age minus chronological age, brain appears older than chronological age) is associated with Alzheimer's disease and related dementias. While a negative BAI is generally associated with better brain health. At an individual level, a rule-of-thumb is that BAI >+5 years should be considered old; and BAI <-5 years should be considered young.

## Strengths
- Provides a single continuous summary of overall sleep EEG health
- Captures multivariate EEG features that are not captured by any single spectral measure
- Validated in population-scale studies

## Limitations
- The model was trained on adults 18-80 years old. Accuracy is reduced for ages outside this range
- Better to have repeated measures of BA and take average to cancel the noise
- Results are not validated for clinical diagnosis; intended for research use only

## Calculation Method
A linear regression model based on band powers, spindles, and slow oscillations is trained on adults between 18-80 years old without major neurological or psychiatric diseases.

## Reference
- Sun, H., Paixao, L., Oliva, J. T., Goparaju, B., Carvalho, D. Z., van Leeuwen, K. G., ... & Westover, M. B. (2019). Brain age from the electroencephalogram of sleep. Neurobiology of aging, 74, 112-120.
- Sun, H., Milton, S., Fang, Y., Taha, H. B., Shiju, S., Thomas, R. J., ... & Leng, Y. (2026). Machine learning–based sleep electroencephalographic brain age index and dementia risk: an individual participant data meta-analysis. JAMA Network Open, 9(3), e261521.