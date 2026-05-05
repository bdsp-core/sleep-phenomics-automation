#!/usr/bin/env python3
"""
User Workflow Performance Profiler for Sauron's Eye

This script simulates and times the actual user workflows you mentioned:
- File upload processing
- Plot generation after upload
- Forward/backward navigation response times  
- CSV download generation
- Real-time viewer updates

Uses direct EEG processing without depending on app modules.
"""

import time
import os
import sys
import json
import pandas as pd
import numpy as np
from contextlib import contextmanager
from typing import Dict, Tuple, List
import io

try:
    import mne
    from scipy import signal
    import matplotlib.pyplot as plt
    MNE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")
    MNE_AVAILABLE = False

@contextmanager
def time_operation(operation_name: str, target_time: float = None):
    """Context manager to time operations with user-friendly feedback"""
    print(f"\n🧪 Testing {operation_name}")
    print("-" * (len(operation_name) + 10))
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # User experience feedback
        if target_time:
            if duration <= target_time:
                status = "✅ EXCELLENT"
                feedback = f"Under target ({target_time}s)"
            elif duration <= target_time * 1.5:
                status = "🟡 ACCEPTABLE" 
                feedback = f"Close to target ({target_time}s)"
            else:
                status = "❌ NEEDS WORK"
                feedback = f"Over target ({target_time}s)"
        else:
            if duration < 0.5:
                status = "🚀 INSTANT"
                feedback = "Feels instantaneous to users"
            elif duration < 1.0:
                status = "⚡ FAST"
                feedback = "Good responsiveness"
            elif duration < 3.0:
                status = "🟡 SLOW"
                feedback = "Users may notice delay"
            else:
                status = "🔴 VERY SLOW"
                feedback = "Users will be frustrated"
        
        print(f"⏱️  Duration: {duration:.3f} seconds")
        print(f"📊 Rating: {status}")
        print(f"💭 Impact: {feedback}")

class UserWorkflowProfiler:
    """Profile actual user workflows and operations"""
    
    def __init__(self):
        self.test_edf_path = self.find_test_file()
        self.cached_edf_data = None
        self.results = {}
        
    def find_test_file(self) -> str:
        """Find a test EDF file"""
        potential_files = [
            "sample_psg.edf",
            "app/data/1/sample_psg.edf", 
            "app/data/2/sample_psg.edf"
        ]
        
        for file_path in potential_files:
            if os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"📁 Found test file: {file_path} ({file_size_mb:.1f} MB)")
                return file_path
        
        print("⚠️  No test EDF file found")
        return None
    
    def profile_file_upload_workflow(self) -> Dict:
        """Profile the complete file upload workflow that users experience"""
        print("\n" + "="*60)
        print("📤 FILE UPLOAD WORKFLOW PERFORMANCE")
        print("="*60)
        print("Simulating: User selects file → clicks upload → sees initial visualization")
        
        results = {}
        
        if not self.test_edf_path or not MNE_AVAILABLE:
            print("Skipping upload tests - missing EDF file or MNE")
            return results
        
        # Step 1: File loading (what happens immediately after upload)
        with time_operation("File Upload - Loading EDF File", target_time=5.0):
            mne.set_log_level('WARNING')
            raw = mne.io.read_raw_edf(self.test_edf_path, preload=True, verbose=False)
            self.cached_edf_data = raw
            
            # Get file info
            duration_hours = raw.times[-1] / 3600
            file_size_mb = os.path.getsize(self.test_edf_path) / (1024 * 1024)
            
            print(f"📄 File: {duration_hours:.1f} hours, {len(raw.ch_names)} channels")
            print(f"💾 Size: {file_size_mb:.1f} MB")
        
        # Step 2: Initial preprocessing (needed before first plot)
        with time_operation("File Upload - Initial Preprocessing", target_time=10.0):
            # Apply standard preprocessing that would happen during upload
            raw_processed = raw.copy()
            raw_processed.notch_filter(50, verbose=False)
            raw_processed.filter(0.3, 95, verbose=False)
            
            # Select EEG channels
            eeg_channels = ['F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1']
            available_eeg = [ch for ch in eeg_channels if ch in raw_processed.ch_names]
            
            if available_eeg:
                raw_eeg = raw_processed.pick_channels(available_eeg)
                print(f"🧠 Selected {len(available_eeg)} EEG channels")
            else:
                raw_eeg = raw_processed
                print(f"🧠 Using all {len(raw_eeg.ch_names)} channels")
        
        # Step 3: First plot generation (what user sees after upload completes)
        with time_operation("File Upload - Initial Plot Generation", target_time=3.0):
            # Generate first 30 seconds of data for display
            plot_duration = 30  # seconds
            initial_data = raw_eeg.copy().crop(tmin=0, tmax=min(plot_duration, raw_eeg.times[-1]))
            
            # Prepare data for web display (downsample for efficiency)
            timestamps = initial_data.times
            plot_data = {}
            
            for i, ch_name in enumerate(initial_data.ch_names):
                channel_data = initial_data.get_data()[i]
                # Downsample for web display (max 2000 points)
                if len(channel_data) > 2000:
                    step = len(channel_data) // 2000
                    channel_data = channel_data[::step]
                    timestamps_sampled = timestamps[::step]
                else:
                    timestamps_sampled = timestamps
                
                plot_data[ch_name] = channel_data.tolist()
            
            # Simulate JSON serialization (what gets sent to browser)
            plot_json = json.dumps({
                'timestamps': timestamps_sampled.tolist(),
                'channels': plot_data
            })
            
            json_size_mb = len(plot_json) / (1024 * 1024)
            print(f"📊 Plot data size: {json_size_mb:.2f} MB")
        
        results['upload_total'] = sum([
            results.get('file_loading', 0),
            results.get('preprocessing', 0), 
            results.get('initial_plot', 0)
        ])
        
        return results
    
    def profile_navigation_performance(self) -> Dict:
        """Profile navigation operations (forward/backward buttons)"""
        print("\n" + "="*60)
        print("🧭 NAVIGATION PERFORMANCE") 
        print("="*60)
        print("Simulating: User clicks forward/backward → plot updates")
        
        results = {}
        
        if not self.cached_edf_data:
            print("No EDF data loaded - skipping navigation tests")
            return results
        
        raw = self.cached_edf_data
        page_size = 30  # 30 second windows (typical)
        
        # Test forward navigation
        with time_operation("Navigation - Forward Button Click", target_time=0.5):
            current_time = 0
            new_time = current_time + page_size
            
            # Extract new data window
            if new_time < raw.times[-1]:
                window_data = raw.copy().crop(tmin=new_time, tmax=min(new_time + page_size, raw.times[-1]))
                
                # Prepare for web display
                plot_data = self._prepare_web_data(window_data)
                json_response = json.dumps(plot_data)
                
                response_size_kb = len(json_response) / 1024
                print(f"📡 Response size: {response_size_kb:.1f} KB")
        
        # Test backward navigation
        with time_operation("Navigation - Backward Button Click", target_time=0.5):
            current_time = 60  # Start from 1 minute in
            new_time = max(current_time - page_size, 0)
            
            window_data = raw.copy().crop(tmin=new_time, tmax=min(new_time + page_size, raw.times[-1]))
            plot_data = self._prepare_web_data(window_data)
            json_response = json.dumps(plot_data)
            
            response_size_kb = len(json_response) / 1024
            print(f"📡 Response size: {response_size_kb:.1f} KB")
        
        # Test time jump (user clicks on timeline)
        with time_operation("Navigation - Jump to Specific Time", target_time=0.5):
            target_time = 300  # Jump to 5 minutes
            if target_time < raw.times[-1]:
                window_data = raw.copy().crop(tmin=target_time, tmax=min(target_time + page_size, raw.times[-1]))
                plot_data = self._prepare_web_data(window_data)
                json_response = json.dumps(plot_data)
        
        # Test rapid navigation (user rapidly clicking through data)
        with time_operation("Navigation - Rapid Clicking Sequence", target_time=0.3):
            # Simulate user rapidly clicking forward 10 times
            navigation_times = []
            
            for i in range(10):
                start = time.perf_counter()
                
                nav_time = i * 15  # Every 15 seconds
                if nav_time < raw.times[-1]:
                    window_data = raw.copy().crop(tmin=nav_time, tmax=min(nav_time + page_size, raw.times[-1]))
                    plot_data = self._prepare_web_data(window_data)
                    json_response = json.dumps(plot_data)
                
                navigation_times.append(time.perf_counter() - start)
            
            avg_nav_time = sum(navigation_times) / len(navigation_times)
            results['avg_navigation'] = avg_nav_time
            print(f"⚡ Average navigation: {avg_nav_time:.3f} seconds")
            print(f"🔄 Navigation rate: {1/avg_nav_time:.1f} clicks/second capacity")
        
        return results
    
    def profile_plot_updates(self) -> Dict:
        """Profile different plot update scenarios"""
        print("\n" + "="*60)
        print("📊 PLOT UPDATE PERFORMANCE")
        print("="*60) 
        print("Simulating: User changes settings → plot redraws")
        
        results = {}
        
        if not self.cached_edf_data:
            print("No EDF data loaded - skipping plot tests")
            return results
        
        raw = self.cached_edf_data
        
        # Test different page sizes (user changes time window)
        page_sizes = [10, 30, 60, 300]  # 10s, 30s, 1min, 5min
        
        for page_size in page_sizes:
            with time_operation(f"Plot Update - {page_size}s Time Window", target_time=1.0):
                window_data = raw.copy().crop(tmin=0, tmax=min(page_size, raw.times[-1]))
                plot_data = self._prepare_web_data(window_data)
                json_response = json.dumps(plot_data)
                
                data_size_mb = len(json_response) / (1024 * 1024)
                print(f"📊 Data size: {data_size_mb:.2f} MB")
                results[f'plot_{page_size}s'] = data_size_mb
        
        # Test amplitude scaling (user zooms in/out)
        with time_operation("Plot Update - Amplitude Scaling", target_time=0.2):
            # This would typically just be a client-side operation
            # But simulate the data preparation
            window_data = raw.copy().crop(tmin=0, tmax=30)
            plot_data = self._prepare_web_data(window_data, amplitude_scale=2.0)
            json_response = json.dumps(plot_data)
        
        return results
    
    def profile_spectrogram_generation(self) -> Dict:
        """Profile spectrogram generation (often slow)"""
        print("\n" + "="*60)
        print("📈 SPECTROGRAM GENERATION")
        print("="*60)
        print("Simulating: User clicks 'Show Spectrogram' → waits for visualization")
        
        results = {}
        
        if not self.cached_edf_data:
            print("No EDF data loaded - skipping spectrogram tests")
            return results
        
        raw = self.cached_edf_data
        
        # Test spectrogram for different durations
        durations = [60, 300, 600]  # 1min, 5min, 10min
        
        for duration in durations:
            with time_operation(f"Spectrogram - {duration//60}min of Data", target_time=10.0):
                # Get subset of data
                test_duration = min(duration, raw.times[-1])
                window_data = raw.copy().crop(tmin=0, tmax=test_duration)
                
                # Generate spectrogram for first EEG channel only
                eeg_channels = [ch for ch in window_data.ch_names if any(x in ch for x in ['F3', 'F4', 'C3', 'C4', 'O1', 'O2'])]
                
                if eeg_channels:
                    ch_idx = window_data.ch_names.index(eeg_channels[0])
                    data = window_data.get_data()[ch_idx]
                    
                    # Compute spectrogram
                    f, t, Sxx = signal.spectrogram(data, fs=window_data.info['sfreq'], 
                                                 nperseg=1024, noverlap=512)
                    
                    # Prepare for web display
                    spectrogram_data = {
                        'frequencies': f.tolist(),
                        'times': t.tolist(),
                        'power': Sxx.tolist()
                    }
                    
                    json_size = len(json.dumps(spectrogram_data)) / (1024 * 1024)
                    print(f"📊 Spectrogram size: {json_size:.2f} MB")
                    print(f"📐 Resolution: {len(f)} freq × {len(t)} time points")
                    
                    results[f'spectrogram_{duration}s'] = json_size
        
        return results
    
    def profile_download_operations(self) -> Dict:
        """Profile file download generation"""
        print("\n" + "="*60)
        print("💾 DOWNLOAD OPERATIONS")
        print("="*60)
        print("Simulating: User clicks download → file generates → download starts")
        
        results = {}
        
        # CSV Export (sleep stages, timestamps, etc.)
        with time_operation("Download - CSV Export Generation", target_time=5.0):
            # Generate realistic sleep staging data
            if self.cached_edf_data:
                duration = self.cached_edf_data.times[-1]
                epochs = int(duration // 30)  # 30-second epochs
            else:
                epochs = 1000
            
            csv_data = {
                'epoch': range(1, epochs + 1),
                'start_time': [i * 30 for i in range(epochs)],
                'sleep_stage': np.random.choice(['Wake', 'N1', 'N2', 'N3', 'REM'], epochs),
                'confidence': np.random.uniform(0.7, 1.0, epochs),
                'timestamp': pd.date_range('2023-01-01 22:00:00', periods=epochs, freq='30S')
            }
            
            df = pd.DataFrame(csv_data)
            
            # Generate CSV string
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_string = csv_buffer.getvalue()
            
            file_size_mb = len(csv_string.encode()) / (1024 * 1024)
            print(f"📊 CSV file size: {file_size_mb:.2f} MB")
            print(f"📄 Rows: {len(df):,}")
            
            results['csv_size_mb'] = file_size_mb
        
        # Annotations Export (events, artifacts, etc.)
        with time_operation("Download - Annotations Export", target_time=2.0):
            # Generate realistic annotations
            annotations_data = {
                'start_time': np.random.uniform(0, 3600, 500),  # Random times in first hour
                'duration': np.random.uniform(0.5, 10, 500),
                'annotation_type': np.random.choice(['Sleep_Spindle', 'K_Complex', 'Arousal', 'Movement', 'Artifact'], 500),
                'channel': np.random.choice(['F3-M2', 'F4-M1', 'C3-M2', 'C4-M1'], 500),
                'confidence': np.random.uniform(0.8, 1.0, 500)
            }
            
            annotations_df = pd.DataFrame(annotations_data)
            json_data = annotations_df.to_json(orient='records')
            
            file_size_kb = len(json_data.encode()) / 1024
            print(f"📊 Annotations file size: {file_size_kb:.1f} KB")
            print(f"📝 Annotations: {len(annotations_df)}")
            
            results['annotations_size_kb'] = file_size_kb
        
        # Raw Data Export (subset of EDF data)
        with time_operation("Download - Raw Data Export (1 hour)", target_time=15.0):
            if self.cached_edf_data:
                # Extract 1 hour of data
                duration = min(3600, self.cached_edf_data.times[-1])  # 1 hour max
                export_data = self.cached_edf_data.copy().crop(tmin=0, tmax=duration)
                
                # Simulate conversion to export format
                export_dict = {
                    'timestamps': export_data.times.tolist(),
                    'sampling_rate': export_data.info['sfreq'],
                    'channels': {}
                }
                
                for i, ch_name in enumerate(export_data.ch_names):
                    export_dict['channels'][ch_name] = export_data.get_data()[i].tolist()
                
                # Calculate hypothetical file size
                json_size = len(json.dumps(export_dict)) / (1024 * 1024)
                print(f"📊 Raw data export size: {json_size:.2f} MB")
                print(f"⏱️  Duration: {duration/60:.1f} minutes")
                
                results['raw_export_size_mb'] = json_size
        
        return results
    
    def _prepare_web_data(self, raw_data, amplitude_scale: float = 1.0) -> Dict:
        """Prepare EEG data for web display (downsampling, formatting)"""
        # Downsample for web efficiency
        timestamps = raw_data.times
        max_points = 2000  # Maximum points for web display
        
        if len(timestamps) > max_points:
            step = len(timestamps) // max_points
            timestamps = timestamps[::step]
        else:
            step = 1
        
        plot_data = {
            'timestamps': timestamps.tolist(),
            'channels': {},
            'sampling_info': {
                'original_rate': raw_data.info['sfreq'],
                'display_points': len(timestamps),
                'downsample_factor': step
            }
        }
        
        for i, ch_name in enumerate(raw_data.ch_names):
            channel_data = raw_data.get_data()[i]
            
            # Apply downsampling and scaling
            if step > 1:
                channel_data = channel_data[::step]
            
            channel_data = channel_data * amplitude_scale
            
            plot_data['channels'][ch_name] = channel_data.tolist()
        
        return plot_data
    
    def run_complete_profile(self):
        """Run comprehensive user workflow profiling"""
        print("Sauron's Eye - User Workflow Performance Profiler")
        print("=" * 65)
        print("🎯 Focus: Real user operations and response times")
        print("👤 Perspective: What users actually experience")
        
        if not MNE_AVAILABLE:
            print("\n❌ MNE not available - cannot run EEG processing tests")
            print("Install with: pip install mne")
            return
        
        if not self.test_edf_path:
            print("\n❌ No test EDF file found")
            print("Place a sample EDF file in the current directory")
            return
        
        all_results = {}
        
        # Run all workflow tests
        all_results['upload'] = self.profile_file_upload_workflow()
        all_results['navigation'] = self.profile_navigation_performance() 
        all_results['plots'] = self.profile_plot_updates()
        all_results['spectrogram'] = self.profile_spectrogram_generation()
        all_results['downloads'] = self.profile_download_operations()
        
        # Generate user-focused summary
        self.generate_user_experience_summary(all_results)
        
        return all_results
    
    def generate_user_experience_summary(self, results: Dict):
        """Generate summary focused on user experience"""
        print("\n" + "="*65)
        print("🎯 USER EXPERIENCE SUMMARY")
        print("="*65)
        
        print("\n⚡ CRITICAL USER WORKFLOWS:")
        print("-" * 35)
        
        # Key user workflows with UX impact
        workflows = [
            ("File Upload (Complete)", "First impression", 15.0, "Users will abandon if too slow"),
            ("Navigation (Forward/Back)", "Real-time interaction", 0.5, "Must feel instant"),
            ("Plot Updates", "Interactive feedback", 1.0, "Smooth interaction expected"),
            ("CSV Download", "Task completion", 10.0, "Users will wait for important data"),
            ("Spectrogram View", "Analysis tool", 5.0, "Analysis workflow - some delay OK")
        ]
        
        for workflow, importance, target, impact in workflows:
            print(f"\n📋 {workflow}")
            print(f"   🎯 Target: < {target}s")
            print(f"   💭 Impact: {impact}")
            print(f"   ⭐ Importance: {importance}")
        
        print("\n🚀 OPTIMIZATION PRIORITIES:")
        print("-" * 30)
        print("1. Navigation speed - Most frequent user action")
        print("2. Initial plot load - Sets user expectations") 
        print("3. Upload processing - First impression matters")
        print("4. Download generation - Task completion critical")
        print("5. Spectrogram - Nice-to-have, can be slower")
        
        print("\n💡 UX IMPROVEMENT STRATEGIES:")
        print("-" * 35)
        print("• Add loading indicators for operations > 1s")
        print("• Cache processed data to speed up navigation") 
        print("• Progressive loading: show partial results quickly")
        print("• Background processing for non-critical operations")
        print("• Optimize data transfer with compression")
        print("• Consider WebSocket for real-time updates")
        print("• Implement data pagination for large files")

if __name__ == "__main__":
    profiler = UserWorkflowProfiler()
    profiler.run_complete_profile()