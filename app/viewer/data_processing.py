import os, threading
from datetime import datetime
import numpy as np
import mne
from flask import current_app
from ..models.user import User, PSGFile, DerivedFile, PSGFileType
from .. import db
from werkzeug.datastructures import FileStorage

MONTAGE_CHANNELS = [
    'F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1',
    'E1-M2', 'E2-M1', 'CHIN1-CHIN2', 'LAT', 'RAT', 'SNORE',
    'PTAF', 'AIRFLOW', 'CHEST', 'ABD', 'ECG', 'SpO2'
]

class PSGDataManager:
    _files_in_memory = {}
    _files_lock = threading.Lock()

    @classmethod
    def save_uploaded_file(cls, uploaded_file: FileStorage, user: User) -> PSGFile:
        """Saves an uploaded EEG file and creates database entry."""
        storage_path = None
        try:
            base, ext = os.path.splitext(uploaded_file.filename)
            if ext.lower() not in ['.edf', '.bdf']:
                raise ValueError("Unsupported file type")

            filename = f"{base}{ext.lower()}"
            storage_path = os.path.join(current_app.config['DATA_PATH'], str(user.id), filename)

            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            uploaded_file.save(storage_path)

            raw = mne.io.read_raw_edf(storage_path, preload=False)
            psg_file = PSGFile(
                filename=filename,
                original_filename=uploaded_file.filename,
                upload_date=datetime.now(),
                file_size=os.path.getsize(storage_path),
                storage_path=storage_path,
                sampling_rate=raw.info["sfreq"],
                num_channels=len(raw.ch_names),
                duration=raw.times[-1],
                recording_date=raw.info["meas_date"],
                owner=user
            )

            db.session.add(psg_file)
            db.session.commit()
            return psg_file
        except Exception as e:
            db.session.rollback()
            if storage_path and os.path.exists(storage_path):
                os.remove(storage_path)
            raise e

    @classmethod
    def _build_montage(cls, data_array, raw_channels, channel_mappings, only_channels=None):
        """Build PSG montage array from saved channel mappings.

        Trusts the DB mapping exclusively — no fallback alias matching.
        Channels absent from the mapping or marked DOES_NOT_EXIST are skipped.

        Args:
            only_channels: if provided, restrict output to this subset of standard channel names.

        Returns:
            montage_data: list of 1-D arrays, one per resolved channel
            montage_names: list of standard channel names in the same order
        """
        montage_data = []
        montage_names = []
        channel_set = set(only_channels) if only_channels is not None else None

        for montage_ch in MONTAGE_CHANNELS:
            if channel_set is not None and montage_ch not in channel_set:
                continue
            mapped_channel = channel_mappings.get(montage_ch)
            if mapped_channel is None or mapped_channel == 'DOES_NOT_EXIST':
                continue
            if '|' in mapped_channel:
                # Two separate electrodes: compute as pos - neg
                pos_name, neg_name = mapped_channel.split('|', 1)
                if pos_name not in raw_channels or neg_name not in raw_channels:
                    continue
                pos_idx = raw_channels.index(pos_name)
                neg_idx = raw_channels.index(neg_name)
                montage_data.append(data_array[pos_idx] - data_array[neg_idx])
            else:
                # Pre-referenced channel: use directly
                if mapped_channel not in raw_channels:
                    continue
                idx = raw_channels.index(mapped_channel)
                montage_data.append(data_array[idx])
            montage_names.append(montage_ch)

        return montage_data, montage_names

    @classmethod
    def _load_raw(cls, file_path):
        """Load raw EDF into memory cache (thread-safe)."""
        with cls._files_lock:
            if file_path not in cls._files_in_memory:
                print('Loading EDF')
                cls._files_in_memory[file_path] = mne.io.read_raw_edf(file_path, preload=False)
        return cls._files_in_memory[file_path]

    @classmethod
    def read_partial_edf(cls, psg_file: PSGFile, offset: float, duration: float):
        """Read a segment of an EEG file and return in PSG montage."""
        raw = cls._load_raw(psg_file.storage_path)

        idx_start = int(offset * psg_file.sampling_rate)
        idx_end = min(int((offset + duration) * psg_file.sampling_rate), raw.n_times)
        if idx_start >= raw.n_times:
            return np.zeros((0, 0)), [], psg_file.sampling_rate, \
                   psg_file.num_channels, psg_file.recording_date, psg_file.duration
        segment = raw.get_data(start=idx_start, stop=idx_end)

        channel_mappings = psg_file.get_channel_mapping()
        montage_data, montage_names = cls._build_montage(segment, raw.ch_names, channel_mappings)

        seg = np.array(montage_data) * 1e6
        return seg, montage_names, psg_file.sampling_rate, psg_file.num_channels, \
               psg_file.recording_date, psg_file.duration

    @classmethod
    def read_full_edf(cls, file_path, psg_file=None, only_channels=None):
        """Load full EEG file and return in PSG montage.

        Args:
            only_channels: if provided, restrict output to this subset of standard channel names.
        """
        raw = cls._load_raw(file_path)

        Fs = raw.info["sfreq"]
        num_samples = raw.n_times * 1.0
        eeg_start = raw.info["meas_date"].strftime("%Y-%m-%d %H:%M:%S")

        eeg = raw.get_data()

        channel_mappings = psg_file.get_channel_mapping() if psg_file else {}
        montage_data, montage_names = cls._build_montage(eeg, raw.ch_names, channel_mappings,
                                                         only_channels=only_channels)

        eeg = np.array(montage_data) * 1e6
        return eeg, montage_names, Fs, num_samples, eeg_start


