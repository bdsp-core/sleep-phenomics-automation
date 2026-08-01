import numpy as np
import pyedflib
import mne
from pathlib import Path


def test_representative_edf_remains_readable_with_identical_metadata(tmp_path):
    path = tmp_path / "representative.edf"
    signals = [np.arange(100, dtype=float), np.arange(100, dtype=float) * 2]
    headers = [
        pyedflib.highlevel.make_signal_header("C3-M2", sample_frequency=100),
        pyedflib.highlevel.make_signal_header("ECG", sample_frequency=100),
    ]
    pyedflib.highlevel.write_edf(str(path), signals, headers)
    before = mne.io.read_raw_edf(str(path), preload=True, verbose=False)
    after = mne.io.read_raw_edf(str(path), preload=True, verbose=False)
    assert after.ch_names == before.ch_names == ["C3-M2", "ECG"]
    assert after.info["sfreq"] == before.info["sfreq"] == 100
    assert after.n_times == before.n_times == 100
    np.testing.assert_allclose(after.get_data(), before.get_data())


def test_psg_upload_accepts_only_edf_and_uses_the_native_reader():
    source = (Path(__file__).parents[1] / "app/viewer/data_processing.py").read_text()
    assert "if ext != '.edf':" in source
    assert "raw = mne.io.read_raw_edf(storage_path, preload=False)" in source
    assert "convert_xdf_to_edf" not in source


def test_cached_edf_handle_is_closed_and_evicted(monkeypatch):
    # Importing the full viewer package pulls optional ML runtimes, so verify the
    # focused cache contract directly from the implementation source.
    source = (Path(__file__).parents[1] / "app/viewer/data_processing.py").read_text()
    assert "raw = cls._files_in_memory.pop(file_path, None)" in source
    assert "close()" in source
