#!/usr/bin/env python3
"""
Local micro-benchmarks: EDF load, auto channel-mapping, montage build, and phenotype pipeline.

This script avoids importing the full Flask app and instead uses lightweight copies
of the mapping and montage logic to measure key operations.
"""

import time
import os
import sys
import re
import argparse

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mne
import numpy as np

# Minimal standard montage and regex patterns (copied from app/viewer/routes.py)
MONTAGE_CHANNELS = [
    'F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1',
    'E1-M2', 'E2-M1', 'CHIN1-CHIN2', 'LAT', 'RAT', 'SNORE',
    'PTAF', 'AIRFLOW', 'CHEST', 'ABD', 'ECG', 'SpO2'
]

ch_regex_patterns = {
    'F3-M2':      r'(EEG\s+)*(?:F3[:_\s-]*[MA]|[MA]2[:_\s-]*F3)',
    'F4-M1':      r'(EEG\s+)*(?:F4[:_\s-]*[MA]|[MA]1[:_\s-]*F4)',
    'C3-M2':      r'(EEG\s+)*(?:C3[:_\s-]*[MA]|[MA]2[:_\s-]*C3)',
    'C4-M1':      r'(EEG\s+)*(?:C4[:_\s-]*[MA]|[MA]1[:_\s-]*C4)',
    'O1-M2':      r'(EEG\s+)*(?:O1[:_\s-]*[MA]|[MA]2[:_\s-]*O1)',
    'O2-M1':      r'(EEG\s+)*(?:O2[:_\s-]*[MA]|[MA]1[:_\s-]*O2)',
    'E1-M2':      r'(?:E1[:_\s-]*[AM]2|[AM]2[:_\s-]*E1|EOG[:_\s-]*1|EOG[:_\s(-]*L(EFT)?|LEOG)',
    'E2-M1':      r'(?:E2[:_\s-]*[AM]1|[AM]1[:_\s-]*E2|EOG[:_\s-]*2|EOG[:_\s(-]*R(IGHT)?|REOG)',
    'CHIN1-CHIN2': r'(?:CHIN1[:_\s-]*CHIN2|EMG1[:_\s-]*EMG2|EMG[:_\s-]*CHIN|\bCHIN\b)',
    'ECG':        r'\bE[CK]G\d*\b',
    'SpO2':       r'(?:S[AP]O2|O2[:_\s-]*SAT|OXYGEN)',
    'AIRFLOW':    r'(?:AIRFLOW|(NASAL[:_\s]*)?FLOW)',
    'CHEST':      r'(RIP)*[:_\s-]*(?:CHEST|THO)',
    'ABD':        r'(RIP)*[:_\s-]*ABD',
    'LAT':        r'(?:LAT\b|LEG[:_\s(-]*L(EFT)?|LEFT[:_\s-]*LEG)',
    'RAT':        r'(?:RAT\b|LEG[:_\s(-]*R(IGHT)?|RIGHT[:_\s-]*LEG)',
    'SNORE':      r'SNOR',
    'PTAF':       r'(?:PTAF|\bPRES)',
}

ch_single_regex_patterns = {
    'F3':    r'(EEG\s+)?F3(\s*[-_]?\s*REF)?\s*$',
    'F4':    r'(EEG\s+)?F4(\s*[-_]?\s*REF)?\s*$',
    'C3':    r'(EEG\s+)?C3(\s*[-_]?\s*REF)?\s*$',
    'C4':    r'(EEG\s+)?C4(\s*[-_]?\s*REF)?\s*$',
    'O1':    r'(EEG\s+)?O1(\s*[-_]?\s*REF)?\s*$',
    'O2':    r'(EEG\s+)?O2(\s*[-_]?\s*REF)?\s*$',
    'M1':    r'(EEG\s+)?(M1|A1)(\s*[-_]?\s*REF)?\s*$',
    'M2':    r'(EEG\s+)?(M2|A2)(\s*[-_]?\s*REF)?\s*$',
    'E1':    r'(EOG\s*[-_]?\s*(L(?:EFT)?|1)|E1(\s*[-_]?\s*REF)?|LEOG)\s*$',
    'E2':    r'(EOG\s*[-_]?\s*(R(?:IGHT)?|2)|E2(\s*[-_]?\s*REF)?|REOG)\s*$',
    'CHIN1': r'(CHIN1|EMG\s*[-_]?\s*(1|CHIN)|\bCHIN\b)\s*$',
    'CHIN2': r'(CHIN2|EMG\s*[-_]?\s*2)\s*$',
}


def create_auto_mappings(standard_channels, edf_channels, previous_mapping=None):
    edf_channels_lower = {ch.lower(): ch for ch in edf_channels}
    auto_mappings = {}

    # previous mapping carryover
    if previous_mapping:
        for standard_ch, prev_edf_ch in previous_mapping.items():
            if standard_ch not in standard_channels:
                continue
            if '|' in prev_edf_ch:
                pos, neg = prev_edf_ch.split('|', 1)
                if pos.lower() in edf_channels_lower and neg.lower() in edf_channels_lower:
                    auto_mappings[standard_ch] = f'{edf_channels_lower[pos.lower()]}|{edf_channels_lower[neg.lower()]}'
            elif prev_edf_ch.lower() in edf_channels_lower:
                auto_mappings[standard_ch] = edf_channels_lower[prev_edf_ch.lower()]

    # exact match & regex
    for standard_ch in standard_channels:
        if standard_ch in auto_mappings:
            continue
        if standard_ch.lower() in edf_channels_lower:
            auto_mappings[standard_ch] = edf_channels_lower[standard_ch.lower()]
            continue
        if standard_ch not in ch_regex_patterns:
            continue
        pattern = re.compile(ch_regex_patterns[standard_ch], re.IGNORECASE)
        for edf_ch in edf_channels:
            if pattern.search(edf_ch):
                auto_mappings[standard_ch] = edf_ch
                break

    # referential fallback
    compiled_electrode = {elec: re.compile(pat, re.IGNORECASE) for elec, pat in ch_single_regex_patterns.items()}
    _referential_parts = {
        'F3-M2': ('F3', 'M2'), 'F4-M1': ('F4', 'M1'),
        'C3-M2': ('C3', 'M2'), 'C4-M1': ('C4', 'M1'),
        'O1-M2': ('O1', 'M2'), 'O2-M1': ('O2', 'M1'),
        'E1-M2': ('E1', 'M2'), 'E2-M1': ('E2', 'M1'),
        'CHIN1-CHIN2': ('CHIN1', 'CHIN2'),
    }
    for standard_ch in standard_channels:
        if standard_ch in auto_mappings:
            continue
        if standard_ch not in _referential_parts:
            continue
        pos_elec, neg_elec = _referential_parts[standard_ch]
        pos_ch = next((ch for ch in edf_channels if compiled_electrode[pos_elec].search(ch)), None)
        neg_ch = next((ch for ch in edf_channels if compiled_electrode[neg_elec].search(ch)), None)
        if pos_ch and neg_ch:
            auto_mappings[standard_ch] = f'{pos_ch}|{neg_ch}'

    return auto_mappings


def build_montage_from_raw(data_array, raw_channels, channel_mappings, only_channels=None):
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
            pos_name, neg_name = mapped_channel.split('|', 1)
            if pos_name not in raw_channels or neg_name not in raw_channels:
                continue
            pos_idx = raw_channels.index(pos_name)
            neg_idx = raw_channels.index(neg_name)
            montage_data.append(data_array[pos_idx] - data_array[neg_idx])
        else:
            if mapped_channel not in raw_channels:
                continue
            idx = raw_channels.index(mapped_channel)
            montage_data.append(data_array[idx])
        montage_names.append(montage_ch)

    return montage_data, montage_names


def main():
    parser = argparse.ArgumentParser(description='Local bench for EDF processing')
    parser.add_argument('--edf', type=str, help='Path to EDF file to test')
    args = parser.parse_args()

    # Find a sample EDF in repo if not provided
    if args.edf:
        edf_path = args.edf
        if not os.path.exists(edf_path):
            print(f'Provided EDF does not exist: {edf_path}')
            return
    else:
        potential = [
            os.path.join(ROOT, 'sample_psg.edf'),
            os.path.join(ROOT, 'app', 'data', '1', 'sample_psg.edf'),
            os.path.join(ROOT, 'app', 'data', '2', 'sample_psg.edf'),
        ]
        edf_path = next((p for p in potential if os.path.exists(p)), None)
        if not edf_path:
            print('No sample EDF found; please provide path with --edf')
            return

    print('Using EDF:', edf_path)

    # EDF load timing
    t0 = time.perf_counter()
    raw = mne.io.read_raw_edf(edf_path, preload=True, verbose=False)
    t1 = time.perf_counter()
    print(f'EDF load (preload=True): {t1-t0:.4f}s  channels={len(raw.ch_names)} duration={raw.times[-1]:.1f}s')

    # Auto-mapping timing
    edf_chs = raw.ch_names
    t0 = time.perf_counter()
    mapping = create_auto_mappings(MONTAGE_CHANNELS, edf_chs, previous_mapping=None)
    t1 = time.perf_counter()
    print(f'Auto-mapping: {t1-t0:.4f}s  mapped={len(mapping)}/{len(MONTAGE_CHANNELS)}')

    # Montage build timing (build montage from full data)
    data = raw.get_data()
    t0 = time.perf_counter()
    montage_data, montage_names = build_montage_from_raw(data, edf_chs, mapping)
    t1 = time.perf_counter()
    print(f'Montage build: {t1-t0:.4f}s  montage_channels={len(montage_names)}')

    # Try running phenomics pipeline (PSGFeatureComputation) if possible
    try:
        # Ensure app/viewer directory is importable
        viewer_dir = os.path.join(ROOT, 'app', 'viewer')
        if viewer_dir not in sys.path:
            sys.path.insert(0, viewer_dir)
        import importlib.util
        spec = importlib.util.spec_from_file_location('feature_extract', os.path.join(viewer_dir, 'feature_extract.py'))
        feat_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(feat_mod)

        # Prepare a mapping suitable for PSGFeatureComputation: mapping values are EDF names or pos|neg
        # Our mapping is already in this format
        t0 = time.perf_counter()
        comp = feat_mod.PSGFeatureComputation(edf_path, mapping, notch_freq=60, selected_features=['band_power'])
        df_feat, detections = comp.run()
        t1 = time.perf_counter()
        print(f'Phenotype pipeline run: {t1-t0:.4f}s  features={len(df_feat.columns)} detections={len(detections)}')
    except Exception as e:
        print('Phenotype pipeline could not be run:', e)


if __name__ == '__main__':
    main()
