# Custom Phenotype

## First Note
For users who wants to add new phenotypes, we assume you have coding ability. It is highly recommended to download/clone from [GitHub](https://github.com/bdsp-core/sleep-phenomics-automation), go to the `if __name__=='__main__':` part of app/viewer/feature_extract.py, develop and debug your code there, and paste the working code onto the webpage textbox. After it can run, please contact us to add this function to the SPA webpage so that everyone can use it. Thank you.

## Overview
The Custom Phenotype feature lets you inject arbitrary Python functions into the phenomics pipeline at runtime. Two functions can be provided:

- **Code** (required when enabled) — computes features and detections from PSG signals, exactly like any built-in phenotype.
- **Figure** (optional) — receives the outputs of Code and returns a Plotly figure to be displayed.

Both functions are written in **Python** and executed on the server side. The Figure function uses **Plotly** (`plotly.graph_objects` or `plotly.express`) so that the resulting figure can be serialised to JSON and rendered in the browser with the same Plotly.js library used for the hypnogram, spectrogram, and CPC plots.

---

## Code Function

### Signature

```python
def my_phenotype( sid=None,
    signals=None, fs=None, 
    channels=None,
    sleep_stages=None, 
    log=print, n_jobs=1, **kwargs
):
    feats   = {}   # {feature_name: scalar_value, ...}
    detects = {}   # {feature_name: non-scalar results (DataFrames, arrays, ...}
    return feats, detects
```

### Input Arguments

#### `sid`
`str` recording identifier

#### `signals`
`dict` mapping signal group → 2-D `numpy.ndarray` of shape `(n_channels, n_samples)`.

| Key | Signal |
|-----|--------|
| `'eeg'` | EEG |
| `'ecg'` | ECG |
| `'eog'` | EOG |
| `'chin_emg'` | Chin EMG |
| `'limb_emg'` | Leg EMG (LAT, RAT) |
| `'rip'` | Respiratory effort belts |
| `'nasalpressure'` | Nasal pressure |
| `'airflow'` | Thermistor airflow |
| `'spo2'` | Pulse oximetry (%) |

Only keys present in the recording are included. Always guard with `signals.get('eeg')`.

#### `fs`
Same keys as `signals`. Each value is the sampling rate in Hz (`float`).

#### `channels`
Same keys as `signals`. Each value is a list of channel name strings in the same row order as the array.

#### `sleep_stages`
1-D `numpy.ndarray` of length `n_epochs` (30-second epochs):

| Value | Stage |
|-------|-------|
| `1` | N3 |
| `2` | N2 |
| `3` | N1 |
| `4` | REM |
| `5` | Wake |
| `nan` | Unknown |

#### `log`
Call `log("message")` to write a line to the phenomics progress panel on the webpage.

### Return Values

#### `feats`
`dict` of `{str: scalar}`. Keys become row names in the downloaded CSV.

#### `detects`
`dict` of `{str: non-scalar results}`, such as `pandas.DataFrame` event tables and `numpy.ndarray` time series. Stored in the detections pickle (`.pkl`) download. Use `{}` if not needed.

---

## Figure Function

### Language
**Python**, using **Plotly** (`plotly.graph_objects` or `plotly.express`). The function must return a `plotly.graph_objects.Figure`. The figure is serialised to JSON by the server and rendered in the browser with Plotly.js.

### Signature

```python
def my_figure(feats, detects):
    # feats:   dict returned by the Code function
    # detects: dict returned by the Code function
    import plotly.graph_objects as go
    fig = go.Figure()
    # ... build the figure ...
    return fig   # must be a plotly.graph_objects.Figure
```

### Return Value
A `plotly.graph_objects.Figure`. The figure is displayed as a separate panel above the Display Options panel. If the function raises an exception or returns `None`, the panel is not shown.

---

## Examples

### Code — mean NREM delta power

Auxiliary functions must be prefixed with `_` so the pipeline picks the correct entry point.

```python
import numpy as np
from scipy.signal import welch

def _compute_epoch_delta(seg, fs_eeg):
    f, pxx = welch(seg, fs=fs_eeg, nperseg=min(len(seg), int(4 * fs_eeg)))
    return float(np.mean(pxx[(f >= 0.5) & (f < 4)]))

def delta_power(sid=None, signals=None, fs=None, channels=None,
                sleep_stages=None, log=print, n_jobs=1, **kwargs):
    eeg    = signals.get('eeg')
    fs_eeg = fs.get('eeg')
    if eeg is None:
        log("delta_power: no EEG — skipping.")
        return {}, {}

    nrem_mask = np.in1d(sleep_stages, [1, 2, 3])
    epoch_len = int(30 * fs_eeg)
    delta_vals = []
    for ep in np.where(nrem_mask)[0]:
        seg = eeg[0, ep * epoch_len: (ep + 1) * epoch_len]
        delta_vals.append(_compute_epoch_delta(seg, fs_eeg))

    mean_delta = float(np.nanmean(delta_vals)) if delta_vals else float('nan')
    log(f"delta_power: mean NREM delta = {mean_delta:.4f}")
    feats   = {'custom_delta_nrem': mean_delta}
    detects = {'delta_by_epoch': np.array(delta_vals)}
    return feats, detects
```

### Figure — per-epoch delta power time series

```python
def my_figure(feats, detects):
    import plotly.graph_objects as go
    import numpy as np

    delta = detects.get('delta_by_epoch')
    if delta is None or len(delta) == 0:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=delta,
        mode='lines',
        line=dict(color='steelblue', width=1.5),
        name='Delta power (NREM epochs)',
    ))
    fig.update_layout(
        title='Per-epoch NREM delta power',
        xaxis_title='NREM epoch index',
        yaxis_title='Power (µV²/Hz)',
        height=300,
        margin=dict(t=40, l=55, r=20, b=50),
    )
    return fig
```

---

## Notes
- The first **public** (non-underscore) function *defined in the code block* is used as the entry point. Imported functions (e.g. `from scipy.signal import welch`) are ignored. Prefix auxiliary functions with `_` so they are not mistaken for the main function.
- Packages can be installed via `subprocess.run('python -m pip install <package>', shell=True)`.
- Standard library and installed packages can be imported inside the function.
- Exceptions in either function are caught and logged; the rest of the pipeline continues unaffected.
- `feats` keys from the Code function appear in the downloaded phenotypes CSV alongside all built-in feature columns.
