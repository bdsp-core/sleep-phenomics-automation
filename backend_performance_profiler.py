#!/usr/bin/env python3
"""
Backend Performance Profiler for Sauron's Eye

This script directly tests the backend functions to measure performance
of actual user operations without requiring the Flask server to be running.
"""

import time
import os
import sys
import json
import tempfile
import io
from contextlib import contextmanager
from typing import Dict, Any
import pandas as pd
import numpy as np

# Add app to path for imports
app_path = os.path.join(os.path.dirname(__file__), 'app')
if app_path not in sys.path:
    sys.path.insert(0, app_path)

@contextmanager
def time_operation(operation_name: str):
    """Context manager to time operations and display results"""
    print(f"\n--- Testing {operation_name} ---")
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # Performance categories
        if duration > 5.0:
            status = "🔴 SLOW"
            advice = "Needs optimization"
        elif duration > 2.0:
            status = "🟡 MODERATE"
            advice = "Could be faster"
        elif duration > 0.5:
            status = "🟢 GOOD"
            advice = "Acceptable performance"
        else:
            status = "🚀 FAST" 
            advice = "Excellent performance"
            
        print(f"✓ {operation_name}: {duration:.4f} seconds {status}")
        print(f"  {advice}")

class BackendPerformanceProfiler:
    """Profile backend operations directly"""
    
    def __init__(self):
        self.results = {}
        self.test_edf_path = None
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Set up test environment and locate test files"""
        # Look for sample EDF files
        potential_files = [
            "sample_psg.edf",
            "app/data/1/sample_psg.edf",
            "app/data/2/sample_psg.edf"
        ]
        
        for file_path in potential_files:
            if os.path.exists(file_path):
                self.test_edf_path = file_path
                print(f"📁 Using test EDF file: {file_path}")
                break
                
        if not self.test_edf_path:
            print("⚠️  No test EDF file found. Some tests will be skipped.")
    
    def profile_file_upload_processing(self) -> Dict:
        """Profile the backend file upload processing"""
        results = {}
        
        if not self.test_edf_path:
            print("Skipping file upload tests - no EDF file available")
            return results
            
        try:
            # Import the required modules
            from viewer.data_processing import EEGDataManager
            
            with time_operation("File Upload - EDF Loading"):
                # Simulate file upload by loading EDF
                manager = EEGDataManager()
                raw_data = manager.load_edf_file(self.test_edf_path)
                if raw_data:
                    results['edf_loading'] = time.perf_counter() - time.perf_counter()
                    print(f"  Loaded: {raw_data.times[-1]/3600:.1f} hours, {len(raw_data.ch_names)} channels")
            
            with time_operation("File Upload - Initial Processing"):
                # Simulate initial processing (preprocessing, basic analysis)
                if raw_data:
                    # Apply standard preprocessing
                    processed_data = manager.preprocess_data(raw_data)
                    results['initial_processing'] = time.perf_counter() - time.perf_counter()
                    
            with time_operation("File Upload - Metadata Extraction"):
                # Extract metadata that would be stored
                metadata = {
                    'duration': raw_data.times[-1] if raw_data else 0,
                    'sampling_rate': raw_data.info['sfreq'] if raw_data else 0,
                    'channels': len(raw_data.ch_names) if raw_data else 0,
                    'file_size': os.path.getsize(self.test_edf_path)
                }
                results['metadata_extraction'] = time.perf_counter() - time.perf_counter()
                print(f"  File size: {metadata['file_size']/(1024*1024):.1f} MB")
                
        except ImportError as e:
            print(f"Could not import required modules: {e}")
            results['error'] = str(e)
        except Exception as e:
            print(f"Error in file upload processing: {e}")
            results['error'] = str(e)
            
        return results
    
    def profile_plot_generation(self) -> Dict:
        """Profile plot generation operations"""
        results = {}
        
        if not self.test_edf_path:
            print("Skipping plot generation tests - no EDF file available")
            return results
            
        try:
            from viewer.data_processing import EEGDataManager
            
            # Load data once for all tests
            manager = EEGDataManager()
            raw_data = manager.load_edf_file(self.test_edf_path)
            
            if not raw_data:
                print("Could not load EDF data for plot testing")
                return results
            
            # Test different page sizes
            page_sizes = [10, 30, 60, 300]  # seconds
            
            for page_size in page_sizes:
                with time_operation(f"Plot Data Generation - {page_size}s Window"):
                    # Simulate getting data for a time window
                    start_time = 0
                    end_time = min(page_size, raw_data.times[-1])
                    
                    # Extract data for the time window
                    window_data = raw_data.copy().crop(tmin=start_time, tmax=end_time)
                    
                    # Convert to format suitable for plotting (like the web app does)
                    plot_data = {
                        'timestamps': window_data.times.tolist(),
                        'channels': {}
                    }
                    
                    for i, ch_name in enumerate(window_data.ch_names):
                        # Sample data for web transmission (every Nth point)
                        data = window_data.get_data()[i]
                        sampling_factor = max(1, len(data) // 1000)  # Max 1000 points for web
                        sampled_data = data[::sampling_factor]
                        plot_data['channels'][ch_name] = sampled_data.tolist()
                    
                    # Estimate JSON serialization time
                    json_str = json.dumps(plot_data)
                    data_size_mb = len(json_str) / (1024 * 1024)
                    
                    results[f'plot_generation_{page_size}s'] = time.perf_counter() - time.perf_counter()
                    print(f"  Data size: {data_size_mb:.2f} MB")
                    
        except Exception as e:
            print(f"Error in plot generation: {e}")
            results['error'] = str(e)
            
        return results
    
    def profile_navigation_operations(self) -> Dict:
        """Profile navigation operations (forward/backward)"""
        results = {}
        
        if not self.test_edf_path:
            print("Skipping navigation tests - no EDF file available")
            return results
            
        try:
            from viewer.data_processing import EEGDataManager
            
            manager = EEGDataManager()
            raw_data = manager.load_edf_file(self.test_edf_path)
            
            if not raw_data:
                return results
            
            # Simulate navigation scenarios
            page_size = 30  # 30 second windows
            total_duration = raw_data.times[-1]
            
            with time_operation("Forward Navigation - Single Step"):
                # Simulate moving forward 30 seconds
                current_time = 0
                new_time = min(current_time + page_size, total_duration)
                
                # Extract new data window
                window_data = raw_data.copy().crop(tmin=new_time, tmax=min(new_time + page_size, total_duration))
                
                # Convert for web display
                plot_data = self._prepare_plot_data(window_data)
                json_size = len(json.dumps(plot_data)) / (1024 * 1024)
                
                results['forward_navigation'] = time.perf_counter() - time.perf_counter()
                print(f"  Response size: {json_size:.2f} MB")
            
            with time_operation("Backward Navigation - Single Step"):
                # Simulate moving backward 30 seconds
                current_time = 60  # Start from 1 minute in
                new_time = max(current_time - page_size, 0)
                
                window_data = raw_data.copy().crop(tmin=new_time, tmax=min(new_time + page_size, total_duration))
                plot_data = self._prepare_plot_data(window_data)
                
                results['backward_navigation'] = time.perf_counter() - time.perf_counter()
            
            with time_operation("Jump to Specific Time"):
                # Simulate jumping to a specific time (e.g., 5 minutes in)
                target_time = 300  # 5 minutes
                if target_time < total_duration:
                    window_data = raw_data.copy().crop(tmin=target_time, tmax=min(target_time + page_size, total_duration))
                    plot_data = self._prepare_plot_data(window_data)
                    
                    results['time_jump'] = time.perf_counter() - time.perf_counter()
            
            with time_operation("Rapid Navigation Sequence"):
                # Simulate user rapidly clicking through data
                start_time = time.perf_counter()
                
                for i in range(10):
                    nav_time = i * 30  # Every 30 seconds
                    if nav_time < total_duration:
                        window_data = raw_data.copy().crop(tmin=nav_time, tmax=min(nav_time + page_size, total_duration))
                        plot_data = self._prepare_plot_data(window_data)
                
                total_time = time.perf_counter() - start_time
                results['rapid_navigation'] = total_time / 10  # Average per navigation
                print(f"  Average per navigation: {results['rapid_navigation']:.4f}s")
                print(f"  Navigation rate: {10/total_time:.1f} operations/second")
                
        except Exception as e:
            print(f"Error in navigation operations: {e}")
            results['error'] = str(e)
            
        return results
    
    def profile_spectrogram_generation(self) -> Dict:
        """Profile spectrogram generation"""
        results = {}
        
        if not self.test_edf_path:
            print("Skipping spectrogram tests - no EDF file available")
            return results
            
        try:
            from viewer.data_processing import EEGDataManager
            
            manager = EEGDataManager()
            raw_data = manager.load_edf_file(self.test_edf_path)
            
            if not raw_data:
                return results
            
            with time_operation("Spectrogram Computation"):
                # Simulate spectrogram computation for first 5 minutes
                duration = min(300, raw_data.times[-1])  # 5 minutes max
                test_data = raw_data.copy().crop(tmin=0, tmax=duration)
                
                # Compute spectrogram for each EEG channel
                import matplotlib.pyplot as plt
                from scipy import signal
                
                spectrograms = {}
                for i, ch_name in enumerate(test_data.ch_names[:6]):  # First 6 channels only
                    if 'EEG' in ch_name.upper() or any(x in ch_name for x in ['F3', 'F4', 'C3', 'C4', 'O1', 'O2']):
                        data = test_data.get_data()[i]
                        f, t, Sxx = signal.spectrogram(data, fs=test_data.info['sfreq'], 
                                                     nperseg=512, noverlap=256)
                        spectrograms[ch_name] = {
                            'frequencies': f.tolist(),
                            'times': t.tolist(), 
                            'power': Sxx.tolist()
                        }
                
                # Calculate data size
                json_size = len(json.dumps(spectrograms)) / (1024 * 1024)
                results['spectrogram_generation'] = time.perf_counter() - time.perf_counter()
                print(f"  Spectrogram data size: {json_size:.2f} MB")
                print(f"  Processed {len(spectrograms)} channels")
                
        except Exception as e:
            print(f"Error in spectrogram generation: {e}")
            results['error'] = str(e)
            
        return results
    
    def profile_ml_prediction(self) -> Dict:
        """Profile ML model prediction"""
        results = {}
        
        try:
            # Try to import ML model
            from ml_models.spikenet2.spikenet2 import predict, initialize_model
            
            if not self.test_edf_path:
                print("Skipping ML prediction tests - no EDF file available")
                return results
            
            with time_operation("ML Model Initialization"):
                # This would normally be done once when app starts
                try:
                    model = initialize_model()
                    results['model_initialization'] = time.perf_counter() - time.perf_counter()
                    print("  Model loaded successfully")
                except Exception as e:
                    print(f"  Model initialization failed: {e}")
                    return results
            
            with time_operation("ML Prediction on EDF File"):
                # Run prediction on the test file
                predictions = predict(self.test_edf_path)
                results['ml_prediction'] = time.perf_counter() - time.perf_counter()
                
                if predictions:
                    print(f"  Generated {len(predictions)} predictions")
                    unique_predictions = set(predictions) if isinstance(predictions, list) else "N/A"
                    print(f"  Unique sleep stages: {unique_predictions}")
                else:
                    print("  No predictions generated")
                    
        except ImportError:
            print("ML modules not available - skipping ML prediction tests")
            results['ml_not_available'] = True
        except Exception as e:
            print(f"Error in ML prediction: {e}")
            results['error'] = str(e)
            
        return results
    
    def profile_download_generation(self) -> Dict:
        """Profile file download generation"""
        results = {}
        
        with time_operation("CSV Export Generation"):
            # Generate a sample CSV export (similar to what the app would create)
            sample_data = {
                'timestamp': pd.date_range('2023-01-01', periods=1000, freq='30S'),
                'sleep_stage': np.random.choice(['Wake', 'N1', 'N2', 'N3', 'REM'], 1000),
                'confidence': np.random.uniform(0.7, 1.0, 1000),
                'epoch': range(1000)
            }
            
            df = pd.DataFrame(sample_data)
            
            # Convert to CSV string (simulating download preparation)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_string = csv_buffer.getvalue()
            
            file_size_mb = len(csv_string.encode()) / (1024 * 1024)
            results['csv_generation'] = time.perf_counter() - time.perf_counter()
            print(f"  CSV size: {file_size_mb:.2f} MB")
            print(f"  Rows exported: {len(df)}")
        
        with time_operation("Annotations Export"):
            # Generate sample annotations export
            annotations_data = {
                'start_time': np.random.uniform(0, 3600, 100),
                'duration': np.random.uniform(1, 30, 100),
                'annotation': np.random.choice(['Spindle', 'K-complex', 'Arousal', 'Movement'], 100),
                'confidence': np.random.uniform(0.8, 1.0, 100)
            }
            
            annotations_df = pd.DataFrame(annotations_data)
            json_data = annotations_df.to_json(orient='records')
            
            file_size_kb = len(json_data.encode()) / 1024
            results['annotations_generation'] = time.perf_counter() - time.perf_counter()
            print(f"  Annotations size: {file_size_kb:.1f} KB")
            print(f"  Annotations count: {len(annotations_df)}")
            
        return results
    
    def _prepare_plot_data(self, raw_data):
        """Helper function to prepare data for plotting (like the web app does)"""
        # Sample data for efficient web transmission
        plot_data = {
            'timestamps': raw_data.times[::10].tolist(),  # Every 10th sample
            'channels': {}
        }
        
        for i, ch_name in enumerate(raw_data.ch_names):
            data = raw_data.get_data()[i]
            sampled_data = data[::10]  # Every 10th sample
            plot_data['channels'][ch_name] = sampled_data.tolist()
            
        return plot_data
    
    def run_comprehensive_profile(self):
        """Run complete backend performance profile"""
        print("Sauron's Eye Backend Performance Profiler")
        print("=" * 60)
        print("Testing backend operations directly (no Flask server required)")
        
        all_results = {}
        
        print("\n" + "📤 FILE UPLOAD PROCESSING" + "=" * 35)
        all_results['upload'] = self.profile_file_upload_processing()
        
        print("\n" + "📊 PLOT GENERATION" + "=" * 40) 
        all_results['plot_generation'] = self.profile_plot_generation()
        
        print("\n" + "🧭 NAVIGATION OPERATIONS" + "=" * 35)
        all_results['navigation'] = self.profile_navigation_operations()
        
        print("\n" + "📈 SPECTROGRAM GENERATION" + "=" * 35)
        all_results['spectrogram'] = self.profile_spectrogram_generation()
        
        print("\n" + "🧠 ML PREDICTION" + "=" * 42)
        all_results['ml_prediction'] = self.profile_ml_prediction()
        
        print("\n" + "💾 DOWNLOAD GENERATION" + "=" * 38)
        all_results['downloads'] = self.profile_download_generation()
        
        # Generate summary
        self.generate_performance_summary(all_results)
        
        return all_results
    
    def generate_performance_summary(self, results: Dict):
        """Generate performance summary and recommendations"""
        print("\n" + "=" * 60)
        print("📊 BACKEND PERFORMANCE SUMMARY")
        print("=" * 60)
        
        # Key user-facing metrics
        key_metrics = [
            ("File Upload Processing", "upload", "edf_loading"),
            ("30s Plot Generation", "plot_generation", "plot_generation_30s"),
            ("Forward Navigation", "navigation", "forward_navigation"),
            ("Spectrogram Generation", "spectrogram", "spectrogram_generation"),
            ("CSV Export", "downloads", "csv_generation"),
            ("ML Prediction", "ml_prediction", "ml_prediction")
        ]
        
        print("\n⚡ KEY PERFORMANCE METRICS:")
        print("-" * 40)
        
        for metric_name, category, key in key_metrics:
            if category in results and key in results[category]:
                time_val = results[category][key]
                if time_val > 5:
                    status = "🔴 SLOW"
                elif time_val > 2:
                    status = "🟡 MODERATE"
                elif time_val > 0.5:
                    status = "🟢 GOOD"
                else:
                    status = "🚀 FAST"
                    
                print(f"{metric_name:<25} {time_val:>8.3f}s  {status}")
            else:
                print(f"{metric_name:<25} {'N/A':>8}   ⚪ SKIP")
        
        print("\n🎯 USER EXPERIENCE IMPACT:")
        print("-" * 30)
        print("• File Upload: First impression - should be < 5s")
        print("• Navigation: Real-time feel - should be < 0.5s") 
        print("• Plot Updates: Smooth interaction - should be < 1s")
        print("• Downloads: User patience - should be < 10s")
        print("• ML Prediction: Background process - can be > 10s")
        
        print("\n💡 OPTIMIZATION STRATEGIES:")
        print("-" * 30)
        print("• Cache preprocessed data to avoid recomputation")
        print("• Use data sampling for web display (keep full resolution on backend)")
        print("• Implement progressive loading for large files")
        print("• Use background tasks for ML predictions")
        print("• Compress data transfers with gzip")
        print("• Consider WebSocket for real-time updates")

if __name__ == "__main__":
    profiler = BackendPerformanceProfiler()
    profiler.run_comprehensive_profile()