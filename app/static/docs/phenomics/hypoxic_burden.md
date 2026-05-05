# Hypoxic Burden

## Overview
Hypoxic burden (HB) measures the total overnight oxygen desaturation load, integrating both the frequency and depth of SpO₂ dips throughout sleep. It captures the cumulative hypoxic stress imposed on tissues and organs beyond what AHI alone conveys.

## Clinical Implication
Hypoxic burden is a stronger independent predictor of adverse health outcomes than AHI. In epidemiological cohorts (MESA, Osteoporotic Fractures in Men), higher hypoxic burden is associated with incident hypertension, atrial fibrillation, type 2 diabetes, cognitive impairment, and all-cause mortality — even after adjusting for AHI. T90 (time with SpO₂ < 90%) independently predicts perioperative risk and is a criterion for nocturnal oxygen supplementation in COPD comorbidity. Hypoxic burden provides a rationale for treating OSA patients with low AHI but severe desaturations.

## Strengths
- Captures the cardiovascular and metabolic consequence of apneas more directly than AHI
- Provides a continuous, graded measure of hypoxemic stress not dichotomized by event thresholds
- T90 is clinically actionable for oxygen therapy decisions
- Sensitive to treatment changes (CPAP efficacy monitored via reduction in hypoxic burden)

## Limitations
- Requires a reliable SpO₂ signal; artifact from movement or poor perfusion (cold hands, nail polish) can distort measurements
- Pulse oximetry has an averaging delay (typically 3–7 seconds) that can underestimate nadir severity for short events
- No universally agreed reference range; different studies use different desaturation thresholds (3% vs. 4%)
- Does not capture the rate of desaturation (abrupt vs. gradual), which may have independent biological significance

## Calculation Method
SpO₂ signal is artifact-rejected using amplitude and rate-of-change thresholds. Baseline SpO₂ is estimated as the 95th percentile over 5-minute rolling windows during sleep. For each desaturation event (SpO₂ falling ≥ 3% below baseline), the area under the desaturation curve (AUDC) is computed by integrating the difference between baseline and actual SpO₂ over event duration (units: %-seconds). Hypoxic burden = total AUDC / total sleep time in hours (%-min/hr). T90 = percentage of total sleep time with SpO₂ < 90%.

## Reference
- Azarbarzin A et al. "The hypoxic burden of sleep apnoea predicts cardiovascular disease-related mortality: the Osteoporotic Fractures in Men Study and the Sleep Heart Health Study." *European Heart Journal*, 2019.
- Lévy P et al. "Intermittent hypoxia and sleep-disordered breathing: current concepts and perspectives." *European Respiratory Journal*, 2016.
