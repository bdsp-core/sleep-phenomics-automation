#!/usr/bin/env python3
"""
Performance Profiler for Sauron's Eye Sleep EEG Analysis Application

This script profiles the major functions identified in the codebase to provide
speed estimates for performance optimization.
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

# Add the app directory to the path
app_path = os.path.join(os.path.dirname(__file__), 'app')
sys.path.insert(0, app_path)

# Also add the project root to path for proper imports
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

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

class PerformanceProfiler:
    """Main profiler class for the application"""
    
    def __init__(self):
        self.results: Dict[str, float] = {}
        
    def profile_edf_loading(self, sample_edf_path: str = None):
        """Profile EDF file loading and processing functions"""
        try:
            # Try absolute imports first, then fall back to direct imports
            try:
                from app.viewer.data_processing import EEGDataManager
                from app.viewer.edf import EEGFeatureComputation
            except ImportError:
                # Fallback to importing from current directory structure
                import viewer.data_processing as dp
                import viewer.edf as edf_module
                EEGDataManager = dp.EEGDataManager
                EEGFeatureComputation = edf_module.EEGFeatureComputation
            
            if not sample_edf_path:
                print("Warning: No sample EDF path provided, skipping EDF loading tests")
                return
                
            print("\n=== EDF Loading and Processing Performance ===")
            
            # Test EEGDataManager functions
            with profile_context("EDF Partial Read"):
                manager = EEGDataManager(sample_edf_path)
                data = manager.read_partial_edf(start_time=0, duration=300)  # 5 minutes
                
            with profile_context("EDF Full Read"):
                full_data = manager.read_full_edf()
                
            with profile_context("Spectrogram Computation"):
                manager.compute_spectrogram()
                
            # Test EEGFeatureComputation functions
            with profile_context("EEG Feature Preprocessing"):
                feature_comp = EEGFeatureComputation(sample_edf_path)
                feature_comp.preprocess_data()
                
            with profile_context("Band Power Computation"):
                feature_comp.compute_band_powers()
                
            with profile_context("Spindle Detection"):
                feature_comp.detect_spindles()
                
            with profile_context("Slow Oscillation Detection"):
                feature_comp.detect_slow_oscillations()
                
        except ImportError as e:
            print(f"Note: Could not import app EDF modules - {e}")
            print("This is expected when running outside the app context.")
            print("Use performance_profiler_standalone.py for standalone testing.")
        except Exception as e:
            print(f"Error profiling EDF functions: {e}")
    
    def profile_signal_processing(self):
        """Profile signal processing functions"""
        try:
            # Try absolute imports first, then fall back to direct imports
            try:
                from app.viewer.data_processing import get_region_spectra, region_spectrum
            except ImportError:
                import viewer.data_processing as dp
                get_region_spectra = dp.get_region_spectra
                region_spectrum = dp.region_spectrum
            
            print("\n=== Signal Processing Performance ===")
            
            # Generate sample EEG data for testing
            sample_rate = 256  # Hz
            duration = 300  # 5 minutes
            n_channels = 19
            n_samples = sample_rate * duration
            
            # Create realistic EEG-like signal
            np.random.seed(42)
            sample_data = np.random.randn(n_channels, n_samples) * 50  # microvolts
            
            # Add some realistic frequency components
            time_vec = np.linspace(0, duration, n_samples)
            for ch in range(n_channels):
                # Add alpha rhythm (~10 Hz)
                sample_data[ch] += 30 * np.sin(2 * np.pi * 10 * time_vec + np.random.rand() * 2 * np.pi)
                # Add theta rhythm (~6 Hz)
                sample_data[ch] += 20 * np.sin(2 * np.pi * 6 * time_vec + np.random.rand() * 2 * np.pi)
            
            with profile_context("Region Spectrum Computation"):
                # Test single region spectrum
                frontal_channels = [0, 1, 2]  # Mock frontal channels
                spectrum_result = region_spectrum(sample_data[frontal_channels], sample_rate)
                
            with profile_context("Full Region Spectra"):
                # Mock channel groups for all regions
                channel_groups = {
                    'frontal': [0, 1, 2, 3, 4, 5],
                    'central': [6, 7, 8, 9, 10, 11], 
                    'occipital': [12, 13, 14, 15, 16, 17]
                }
                
                spectra_result = get_region_spectra(sample_data, sample_rate, channel_groups)
                
        except ImportError as e:
            print(f"Note: Could not import signal processing modules - {e}")
            print("This is expected when running outside the app context.")
            print("Use performance_profiler_standalone.py for standalone testing.")
        except Exception as e:
            print(f"Error profiling signal processing: {e}")
    
    def profile_ml_inference(self, sample_edf_path: str = None):
        """Profile ML model inference"""
        try:
            # Try absolute imports first, then fall back to direct imports
            try:
                from app.ml_models.spikenet2.spikenet2 import predict, initialize_model
            except ImportError:
                import ml_models.spikenet2.spikenet2 as ml_module
                predict = ml_module.predict
                initialize_model = ml_module.initialize_model
            
            print("\n=== ML Model Inference Performance ===")
            
            if not sample_edf_path:
                print("Warning: No sample EDF path provided, skipping ML inference tests")
                return
            
            with profile_context("Model Initialization"):
                model = initialize_model()
                
            with profile_context("ML Prediction"):
                predictions = predict(sample_edf_path)
                
        except ImportError as e:
            print(f"Error importing ML modules: {e}")
        except Exception as e:
            print(f"Error profiling ML inference: {e}")
    
    def profile_filtering(self):
        """Profile filtering functions"""
        try:
            # Try absolute imports first, then fall back to direct imports
            try:
                from app.viewer.filters import createFilter, applyFilter
            except ImportError:
                import viewer.filters as filters_module
                createFilter = filters_module.createFilter
                applyFilter = filters_module.applyFilter
            
            print("\n=== Signal Filtering Performance ===")
            
            # Generate sample data
            sample_rate = 256
            duration = 60  # 1 minute
            n_samples = sample_rate * duration
            sample_signal = np.random.randn(n_samples) * 50
            
            with profile_context("Filter Creation"):
                # Test different filter types
                lowpass_filter = createFilter('lowpass', 30, sample_rate)
                highpass_filter = createFilter('highpass', 0.5, sample_rate)
                notch_filter = createFilter('notch', 50, sample_rate)
                
            with profile_context("Filter Application"):
                filtered_lp = applyFilter(sample_signal, lowpass_filter)
                filtered_hp = applyFilter(sample_signal, highpass_filter)
                filtered_notch = applyFilter(sample_signal, notch_filter)
                
        except ImportError as e:
            print(f"Note: Could not import filter modules - {e}")
            print("This is expected when running outside the app context.")
            print("Use performance_profiler_standalone.py for standalone testing.")
        except Exception as e:
            print(f"Error profiling filtering: {e}")
    
    def profile_web_routes(self):
        """Profile web route functions that don't require Flask context"""
        print("\n=== Web Route Performance (Limited Testing) ===")
        print("Note: Full route testing requires Flask application context")
        
        # Test data serialization performance
        with profile_context("Large Data Serialization"):
            # Simulate the type of data sent in load_eeg route
            mock_spectrogram_data = {
                'frontal': np.random.randn(1000, 100).tolist(),
                'central': np.random.randn(1000, 100).tolist(),
                'occipital': np.random.randn(1000, 100).tolist()
            }
            
            import json
            serialized = json.dumps(mock_spectrogram_data)
            
        print(f"Serialized data size: {len(serialized) / (1024*1024):.2f} MB")
    
    def run_comprehensive_profile(self, sample_edf_path: str = None):
        """Run all profiling tests"""
        print("Sauron's Eye Performance Profiler")
        print("=" * 50)
        
        if sample_edf_path and not os.path.exists(sample_edf_path):
            print(f"Warning: Sample EDF path {sample_edf_path} does not exist")
            sample_edf_path = None
        
        # Run all profiling tests
        self.profile_signal_processing()
        self.profile_filtering()
        self.profile_web_routes()
        self.profile_edf_loading(sample_edf_path)
        self.profile_ml_inference(sample_edf_path)
        
        print("\n" + "=" * 50)
        print("Profiling Complete!")
        print("\nPerformance Summary:")
        print("- Signal processing functions are likely the bottleneck")
        print("- Consider optimizing spectral analysis with faster FFT implementations")
        print("- ML inference time depends heavily on model complexity and device (CPU/GPU)")
        print("- EDF loading can be optimized with better caching strategies")
        

if __name__ == "__main__":
    profiler = PerformanceProfiler()
    
    # Check if sample EDF path is provided
    sample_edf = None
    if len(sys.argv) > 1:
        sample_edf = sys.argv[1]
    
    # Look for sample EDF files in common locations
    potential_paths = [
        "sample_data/sample.edf",
        "app/data/sample.edf",
        "test_data/sample.edf"
    ]
    
    if not sample_edf:
        for path in potential_paths:
            if os.path.exists(path):
                sample_edf = path
                break
    
    profiler.run_comprehensive_profile(sample_edf)