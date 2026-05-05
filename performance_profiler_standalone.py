#!/usr/bin/env python3
"""
Standalone Performance Profiler for Sauron's Eye Sleep EEG Analysis Application

This script provides performance testing without importing app modules,
focusing on core EEG processing operations that can be benchmarked independently.
"""

import time
import cProfile
import pstats
import functools
import sys
import os
from contextlib import contextmanager
from typing import Callable, Any, Dict, List
import numpy as np

try:
    import mne
    from scipy import signal
    from scipy.ndimage import gaussian_filter1d
    import pandas as pd
    MNE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")
    MNE_AVAILABLE = False

def timing_decorator(func: Callable) -> Callable:
    """Decorator to time function execution"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"{func.__name__}: {execution_time:.4f} seconds")
        return result
    return wrapper

@contextmanager
def profile_context(description: str):
    """Context manager for profiling code blocks"""
    print(f"\n--- Profiling {description} ---")
    profiler = cProfile.Profile()
    profiler.enable()
    start_time = time.perf_counter()
    
    try:
        yield profiler
    finally:
        end_time = time.perf_counter()
        profiler.disable()
        
        print(f"Total time: {end_time - start_time:.4f} seconds")
        
        # Create stats object and print top functions
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        print("Top 10 functions by cumulative time:")
        stats.print_stats(10)

class StandalonePerformanceProfiler:
    """Standalone profiler that doesn't depend on app modules"""
    
    def __init__(self):
        self.results: Dict[str, float] = {}
        
    def profile_edf_loading_standalone(self, sample_edf_path: str = None):
        """Profile EDF file loading using MNE directly"""
        if not MNE_AVAILABLE:
            print("Skipping EDF tests - MNE not available")
            return
            
        if not sample_edf_path or not os.path.exists(sample_edf_path):
            print("Warning: No valid sample EDF path provided, skipping EDF loading tests")
            return
                
        print("\n=== Standalone EDF Loading Performance ===")
        
        try:
            with profile_context("EDF File Loading"):
                mne.set_log_level('WARNING')
                raw = mne.io.read_raw_edf(sample_edf_path, preload=True, verbose=False)
                
            with profile_context("EDF Preprocessing"):
                # Standard sleep EEG preprocessing
                raw_copy = raw.copy()
                raw_copy.notch_filter(50, verbose=False)  # Remove power line noise
                raw_copy.filter(0.3, 95, verbose=False)   # Bandpass filter
                
            with profile_context("Channel Selection"):
                # Select EEG channels
                eeg_channels = ['F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1']
                available_eeg = [ch for ch in eeg_channels if ch in raw.ch_names]
                if available_eeg:
                    raw_eeg = raw_copy.pick_channels(available_eeg)
                else:
                    print("No standard EEG channels found")
                    return
                    
            print(f"Successfully loaded: {raw.times[-1]/3600:.2f} hours, {raw.info['sfreq']} Hz, {len(available_eeg)} EEG channels")
                
        except Exception as e:
            print(f"Error in EDF loading: {e}")
    
    def profile_spectral_analysis_standalone(self, sample_edf_path: str = None):
        """Profile spectral analysis operations"""
        if not MNE_AVAILABLE:
            print("Skipping spectral analysis tests - MNE not available")
            return
            
        print("\n=== Standalone Spectral Analysis Performance ===")
        
        if sample_edf_path and os.path.exists(sample_edf_path):
            # Test with real EDF data
            try:
                mne.set_log_level('WARNING')
                raw = mne.io.read_raw_edf(sample_edf_path, preload=True, verbose=False)
                
                # Select EEG channels and preprocess
                eeg_channels = ['F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1']
                available_eeg = [ch for ch in eeg_channels if ch in raw.ch_names]
                
                if not available_eeg:
                    print("No EEG channels found, using synthetic data")
                    sample_data, sample_rate = self._generate_synthetic_eeg()
                else:
                    raw_eeg = raw.copy().pick_channels(available_eeg)
                    raw_eeg.notch_filter(50, verbose=False)
                    raw_eeg.filter(0.3, 95, verbose=False)
                    
                    # Use first 5 minutes for testing
                    duration = min(300, raw_eeg.times[-1])  # 5 minutes max
                    raw_test = raw_eeg.copy().crop(tmin=0, tmax=duration)
                    
                    sample_data = raw_test.get_data()
                    sample_rate = raw_test.info['sfreq']
                    
            except Exception as e:
                print(f"Error loading real data, using synthetic: {e}")
                sample_data, sample_rate = self._generate_synthetic_eeg()
        else:
            # Generate synthetic EEG data
            sample_data, sample_rate = self._generate_synthetic_eeg()
        
        print(f"Testing with data shape: {sample_data.shape}, sampling rate: {sample_rate} Hz")
        
        # Test different spectral analysis methods
        with profile_context("Welch's Method PSD"):
            for i in range(sample_data.shape[0]):
                freqs, psd = signal.welch(sample_data[i], fs=sample_rate, nperseg=1024)
        
        with profile_context("Multitaper PSD (MNE)"):
            if MNE_AVAILABLE:
                psd, freqs = mne.time_frequency.psd_array_multitaper(
                    sample_data,
                    sfreq=sample_rate,
                    fmin=0.5,
                    fmax=50,
                    bandwidth=2.0,
                    verbose=False
                )
        
        with profile_context("Band Power Computation"):
            # Compute band powers for standard sleep EEG bands
            frequency_bands = {
                'Delta': (0.5, 4.0),
                'Theta': (4.0, 8.0),
                'Alpha': (8.0, 13.0),
                'Sigma': (11.0, 15.0),
                'Beta': (13.0, 30.0),
            }
            
            freqs, psd = signal.welch(sample_data[0], fs=sample_rate, nperseg=1024)
            total_power = np.trapz(psd, freqs)
            
            for band_name, (fmin, fmax) in frequency_bands.items():
                freq_mask = (freqs >= fmin) & (freqs <= fmax)
                band_power = np.trapz(psd[freq_mask], freqs[freq_mask])
                relative_power = (band_power / total_power) * 100
    
    def _generate_synthetic_eeg(self) -> tuple:
        """Generate realistic synthetic EEG data for testing"""
        sample_rate = 200  # Hz
        duration = 300  # 5 minutes
        n_channels = 6
        n_samples = int(sample_rate * duration)
        
        # Create realistic EEG-like signal
        np.random.seed(42)
        sample_data = np.random.randn(n_channels, n_samples) * 20  # microvolts
        
        # Add realistic frequency components
        time_vec = np.linspace(0, duration, n_samples)
        for ch in range(n_channels):
            # Add alpha rhythm (~10 Hz)
            sample_data[ch] += 30 * np.sin(2 * np.pi * 10 * time_vec + np.random.rand() * 2 * np.pi)
            # Add theta rhythm (~6 Hz)
            sample_data[ch] += 20 * np.sin(2 * np.pi * 6 * time_vec + np.random.rand() * 2 * np.pi)
            # Add delta rhythm (~2 Hz)
            sample_data[ch] += 50 * np.sin(2 * np.pi * 2 * time_vec + np.random.rand() * 2 * np.pi)
        
        return sample_data, sample_rate
    
    def profile_filtering_standalone(self):
        """Profile signal filtering operations"""
        print("\n=== Standalone Signal Filtering Performance ===")
        
        # Generate test signal
        sample_rate = 200
        duration = 60  # 1 minute
        n_samples = int(sample_rate * duration)
        
        # Create signal with multiple frequency components + noise
        time_vec = np.linspace(0, duration, n_samples)
        test_signal = (
            50 * np.sin(2 * np.pi * 2 * time_vec) +    # 2 Hz (delta)
            30 * np.sin(2 * np.pi * 6 * time_vec) +    # 6 Hz (theta)  
            40 * np.sin(2 * np.pi * 10 * time_vec) +   # 10 Hz (alpha)
            20 * np.sin(2 * np.pi * 50 * time_vec) +   # 50 Hz (power line)
            10 * np.random.randn(n_samples)            # Noise
        )
        
        print(f"Testing with signal: {len(test_signal)} samples at {sample_rate} Hz")
        
        with profile_context("Butterworth Lowpass Filter"):
            # Test lowpass filtering
            nyquist = sample_rate / 2
            low_cutoff = 30 / nyquist
            b, a = signal.butter(4, low_cutoff, btype='low')
            for _ in range(10):  # Multiple iterations
                filtered = signal.filtfilt(b, a, test_signal)
        
        with profile_context("Butterworth Highpass Filter"):
            # Test highpass filtering
            high_cutoff = 0.5 / nyquist
            b, a = signal.butter(4, high_cutoff, btype='high')
            for _ in range(10):
                filtered = signal.filtfilt(b, a, test_signal)
        
        with profile_context("Notch Filter (50 Hz)"):
            # Test notch filtering
            if MNE_AVAILABLE:
                # Create synthetic raw object for MNE filtering
                info = mne.create_info(ch_names=['test'], sfreq=sample_rate, ch_types=['eeg'])
                raw = mne.io.RawArray(test_signal.reshape(1, -1), info, verbose=False)
                for _ in range(5):
                    raw_filt = raw.copy().notch_filter(50, verbose=False)
            else:
                # Use scipy notch filter
                quality_factor = 30
                w0 = 50 / (sample_rate / 2)
                b, a = signal.iirnotch(w0, quality_factor)
                for _ in range(10):
                    filtered = signal.filtfilt(b, a, test_signal)
    
    def profile_data_serialization(self):
        """Profile data serialization performance (web routes)"""
        print("\n=== Data Serialization Performance ===")
        
        with profile_context("Large JSON Serialization"):
            # Simulate the type of data sent in web responses
            mock_data = {
                'eeg_data': np.random.randn(5000, 6).tolist(),
                'timestamps': np.linspace(0, 3600, 5000).tolist(),
                'spectrogram': {
                    'freqs': np.linspace(0.5, 50, 200).tolist(),
                    'power': np.random.randn(200, 100).tolist()
                },
                'band_powers': {
                    'delta': np.random.randn(100).tolist(),
                    'theta': np.random.randn(100).tolist(),
                    'alpha': np.random.randn(100).tolist(),
                    'beta': np.random.randn(100).tolist(),
                }
            }
            
            import json
            serialized = json.dumps(mock_data)
            
        print(f"Serialized data size: {len(serialized) / (1024*1024):.2f} MB")
        
        with profile_context("Pandas DataFrame Operations"):
            # Test dataframe operations common in the app
            df = pd.DataFrame({
                'timestamp': pd.date_range('2023-01-01', periods=10000, freq='0.1S'),
                'channel_1': np.random.randn(10000),
                'channel_2': np.random.randn(10000),
                'channel_3': np.random.randn(10000),
                'predictions': np.random.choice(['Wake', 'NREM1', 'NREM2', 'NREM3', 'REM'], 10000)
            })
            
            # Common operations
            grouped = df.groupby('predictions').agg({
                'channel_1': ['mean', 'std'],
                'channel_2': ['mean', 'std'],
                'channel_3': ['mean', 'std']
            })
            
            # Rolling window operations
            rolling_mean = df['channel_1'].rolling(window=100).mean()
    
    def run_comprehensive_profile(self, sample_edf_path: str = None):
        """Run all profiling tests"""
        print("Sauron's Eye Standalone Performance Profiler")
        print("=" * 55)
        
        if sample_edf_path and not os.path.exists(sample_edf_path):
            print(f"Warning: Sample EDF path {sample_edf_path} does not exist")
            sample_edf_path = None
        
        # Run all profiling tests
        self.profile_filtering_standalone()
        self.profile_data_serialization()
        self.profile_spectral_analysis_standalone(sample_edf_path)
        self.profile_edf_loading_standalone(sample_edf_path)
        
        print("\n" + "=" * 55)
        print("Profiling Complete!")
        print("\nPerformance Summary:")
        print("- Spectral analysis (multitaper PSD) is computationally intensive")
        print("- EDF file loading time depends on file size and preprocessing")
        print("- Filtering operations are relatively fast with scipy/MNE")
        print("- Data serialization for web responses can be a bottleneck")
        print("- Consider optimizing:")
        print("  * Use faster FFT implementations for spectral analysis")
        print("  * Cache preprocessed EDF data")
        print("  * Compress JSON responses")
        print("  * Use batch processing for large datasets")

if __name__ == "__main__":
    profiler = StandalonePerformanceProfiler()
    
    # Check if sample EDF path is provided
    sample_edf = None
    if len(sys.argv) > 1:
        sample_edf = sys.argv[1]
    else:
        # Look for sample EDF files in common locations
        potential_paths = [
            "sample_psg.edf",
            "app/data/sample_psg.edf",
            "app/data/1/sample_psg.edf",
            "test_data/sample.edf"
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                sample_edf = path
                break
    
    if sample_edf:
        print(f"Using sample EDF file: {sample_edf}")
    else:
        print("No sample EDF file found - will use synthetic data for testing")
    
    profiler.run_comprehensive_profile(sample_edf)