# Hypoxic Burden

## Overview
Hypoxic burden (HB) measures the total overnight oxygen desaturation load, integrating both the count and depth of SpO2 dips throughout sleep. It captures the cumulative hypoxic stress imposed on tissues and organs beyond what AHI alone conveys.

## Output Phenotypes

### Pictures on the website
none

### Phentoype values in CSV to be downloaded
- HB_desat: desaturation-based hypoxic burden (%min/h)
- HB_NREM_desat: desaturation-based hypoxic burden at NREM
- HB_REM_desat: desaturation-based hypoxic burden at REM

## Clinical Implication
Hypoxic burden is an independent predictor of mortality than AHI. Hypoxic burden provides a metric for treating OSA patients with low AHI but severe desaturations.

## Strengths
- Integrates both count and depth of SpO2 desaturation
- Provides a continuous, graded measure of hypoxemic stress not dichotomized by event thresholds

## Limitations
- No universally agreed cutoffs
- Requires a reliable SpO2 signal; artifact from movement or poor perfusion (cold hands, nail polish) can distort measurements

## Calculation Method
For each desaturation event, the drop in oxygen saturation from a pre-event baseline is tracked over time, the area of this desaturation curve is computed, and these individual areas are then summed across all events and normalized by total sleep time.

## Reference
- Esmaeili, N., Labarca, G., Hu, W. H., Vena, D., Messineo, L., Gell, L., ... & Azarbarzin, A. (2023). Hypoxic burden based on automatically identified desaturations is associated with adverse health outcomes. Annals of the American Thoracic Society, 20(11), 1633-1641.
- Azarbarzin, A., Sands, S. A., Stone, K. L., Taranto-Montemurro, L., Messineo, L., Terrill, P. I., ... & Wellman, A. (2019). The hypoxic burden of sleep apnoea predicts cardiovascular disease-related mortality: the Osteoporotic Fractures in Men Study and the Sleep Heart Health Study. European heart journal, 40(14), 1149-1157.
