from pathlib import Path

import mne
import numpy as np
import pytest

from spa_xdf_parser import (
    XDFEmptyError,
    XDFError,
    XDFStreamSelectionRequired,
    convert_xdf_to_edf,
)


def _signal(name="EEG", rate=100, labels=("C3", "C4"), samples=200, timestamps=None):
    timestamps = np.arange(samples) / (rate or 100) if timestamps is None else np.asarray(timestamps)
    channels = [{"label": [label], "unit": ["uV"]} for label in labels]
    return {
        "info": {
            "name": [name], "type": ["EEG"], "nominal_srate": [str(rate)],
            "desc": [{"channels": [{"channel": channels}]}],
        },
        "time_stamps": timestamps,
        "time_series": np.column_stack([
            np.sin(2 * np.pi * (index + 1) * timestamps) for index in range(len(labels))
        ]),
    }


def _marker():
    return {
        "info": {"name": ["Markers"], "type": ["Markers"], "nominal_srate": ["0"]},
        "time_stamps": np.array([0.05, 0.12]),
        "time_series": [["lights off"], ["N2"]],
    }


def _convert(tmp_path, streams, selected=None):
    source = tmp_path / "input.xdf"
    source.write_bytes(b"mock xdf payload")
    destination = tmp_path / "normalized.edf"
    result = convert_xdf_to_edf(
        str(source), str(destination), selected_stream_id=selected,
        loader=lambda _path: (streams, {}),
    )
    return result, destination


def test_single_eeg_stream_is_converted(tmp_path):
    result, destination = _convert(tmp_path, [_signal()])
    raw = mne.io.read_raw_edf(destination, preload=True, verbose=False)
    assert result.selected_stream_id == 0
    assert raw.ch_names == ["C3", "C4"]
    assert raw.info["sfreq"] == 100
    assert raw.n_times == 200


def test_markers_are_aligned_as_edf_annotations(tmp_path):
    result, destination = _convert(tmp_path, [_signal(), _marker()])
    raw = mne.io.read_raw_edf(destination, preload=False, verbose=False)
    assert result.marker_count == 2
    assert list(raw.annotations.description) == ["lights off", "N2"]
    assert np.allclose(raw.annotations.onset, [0.05, 0.12], atol=0.01)


def test_multiple_signal_streams_require_explicit_selection(tmp_path):
    source = tmp_path / "ambiguous.xdf"
    source.write_bytes(b"mock")
    streams = [_signal("EEG"), _signal("Aux", labels=("ECG",))]
    with pytest.raises(XDFStreamSelectionRequired) as exc:
        convert_xdf_to_edf(str(source), str(tmp_path / "out.edf"), loader=lambda _: (streams, {}))
    assert [s["name"] for s in exc.value.streams] == ["EEG", "Aux"]
    result, _ = _convert(tmp_path, streams, selected=1)
    assert result.selected_stream_id == 1


@pytest.mark.parametrize("payload,loader,error", [
    (b"", lambda _: ([], {}), XDFEmptyError),
    (b"not an xdf", lambda _: (_ for _ in ()).throw(RuntimeError("bad magic")), XDFError),
])
def test_empty_corrupt_and_renamed_files_are_rejected(tmp_path, payload, loader, error):
    source = tmp_path / "renamed.xdf"
    source.write_bytes(payload)
    with pytest.raises(error):
        convert_xdf_to_edf(str(source), str(tmp_path / "out.edf"), loader=loader)


def test_missing_labels_and_rate_are_inferred(tmp_path):
    stream = _signal(rate=0, labels=("placeholder",))
    stream["info"]["desc"] = []
    stream["time_series"] = np.arange(20, dtype=float)[:, None]
    stream["time_stamps"] = np.arange(20) / 128
    result, destination = _convert(tmp_path, [stream])
    raw = mne.io.read_raw_edf(destination, preload=False, verbose=False)
    assert raw.ch_names == ["Channel 1"]
    assert raw.info["sfreq"] == pytest.approx(128)
    assert any("inferred" in warning for warning in result.warnings)


def test_irregular_stream_is_resampled(tmp_path):
    timestamps = np.cumsum(np.r_[0, np.repeat(0.01, 998), 0.02])
    result, destination = _convert(tmp_path, [_signal(samples=1000, timestamps=timestamps)])
    raw = mne.io.read_raw_edf(destination, preload=False, verbose=False)
    assert raw.n_times >= 1000
    assert any("resampled" in warning for warning in result.warnings)


def test_representative_large_supported_stream(tmp_path):
    # 16 channels x 60,000 samples exercises conversion without committing a large fixture.
    result, destination = _convert(tmp_path, [_signal(labels=tuple(f"EEG{i}" for i in range(16)), samples=60_000)])
    assert result.streams[0]["sample_count"] == 60_000
    assert destination.stat().st_size > 0
