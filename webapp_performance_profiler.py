#!/usr/bin/env python3
"""
Web Application Performance Profiler for Sauron's Eye

This script profiles actual user workflows:
- File upload processing time
- Plot generation after upload
- Navigation (forward/backward buttons) response time
- CSV download generation time
- Real-time viewer update performance
"""

import time
import requests
import os
import sys
from contextlib import contextmanager
import json
from typing import Dict, List, Optional
import tempfile
import shutil

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
        print(f"✓ {operation_name}: {duration:.4f} seconds")
        if duration > 5.0:
            print(f"  ⚠️  SLOW - Consider optimization")
        elif duration > 2.0:
            print(f"  ⚡ MODERATE - Could be faster")
        else:
            print(f"  🚀 FAST - Good performance")

class WebAppPerformanceProfiler:
    """Profile real user workflows in the web application"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.results = {}
        
    def check_server_available(self) -> bool:
        """Check if the Flask server is running"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def profile_file_upload(self, edf_file_path: str) -> Dict:
        """Profile the complete file upload workflow"""
        if not os.path.exists(edf_file_path):
            print(f"Error: EDF file not found: {edf_file_path}")
            return {}
            
        results = {}
        
        with time_operation("File Upload - Complete Workflow"):
            # Step 1: Initial page load
            with time_operation("Initial Page Load"):
                response = self.session.get(f"{self.base_url}/")
                results['page_load'] = response.elapsed.total_seconds()
            
            # Step 2: File upload POST request
            with time_operation("File Upload POST Request"):
                with open(edf_file_path, 'rb') as f:
                    files = {'file': (os.path.basename(edf_file_path), f, 'application/octet-stream')}
                    response = self.session.post(f"{self.base_url}/upload", files=files)
                    results['upload_post'] = response.elapsed.total_seconds()
                    
                    if response.status_code != 302:  # Should redirect after upload
                        print(f"Upload failed with status: {response.status_code}")
                        print(f"Response: {response.text[:200]}")
                        return results
            
            # Step 3: Redirect to viewer (initial plot generation)
            with time_operation("Post-Upload Redirect and Initial Plot Load"):
                # Follow the redirect
                if response.history:
                    final_url = response.url
                    viewer_response = self.session.get(final_url)
                    results['initial_plot_load'] = viewer_response.elapsed.total_seconds()
                    
        return results
    
    def profile_plot_navigation(self) -> Dict:
        """Profile plot navigation (forward/backward buttons)"""
        results = {}
        
        # Test forward navigation
        with time_operation("Forward Button Navigation"):
            # Simulate clicking forward button (AJAX request)
            response = self.session.post(f"{self.base_url}/load_eeg", 
                                       json={'action': 'forward', 'current_time': 0})
            if response.status_code == 200:
                results['forward_navigation'] = response.elapsed.total_seconds()
                print(f"  Data size: {len(response.content)} bytes")
            else:
                print(f"Forward navigation failed: {response.status_code}")
        
        # Test backward navigation  
        with time_operation("Backward Button Navigation"):
            response = self.session.post(f"{self.base_url}/load_eeg",
                                       json={'action': 'backward', 'current_time': 30})
            if response.status_code == 200:
                results['backward_navigation'] = response.elapsed.total_seconds()
                print(f"  Data size: {len(response.content)} bytes")
            else:
                print(f"Backward navigation failed: {response.status_code}")
        
        # Test jump to specific time
        with time_operation("Jump to Specific Time"):
            response = self.session.post(f"{self.base_url}/load_eeg",
                                       json={'action': 'jump', 'target_time': 300})  # 5 minutes
            if response.status_code == 200:
                results['time_jump'] = response.elapsed.total_seconds()
                print(f"  Data size: {len(response.content)} bytes")
            else:
                print(f"Time jump failed: {response.status_code}")
                
        return results
    
    def profile_plot_generation(self) -> Dict:
        """Profile different plot generation operations"""
        results = {}
        
        # Test different page sizes (affects plot complexity)
        page_sizes = [10, 30, 60]  # seconds
        
        for page_size in page_sizes:
            with time_operation(f"Plot Generation - {page_size}s Page"):
                response = self.session.post(f"{self.base_url}/load_eeg",
                                           json={'page_size': page_size, 'current_time': 0})
                if response.status_code == 200:
                    results[f'plot_{page_size}s'] = response.elapsed.total_seconds()
                    data_size_mb = len(response.content) / (1024 * 1024)
                    print(f"  Data size: {data_size_mb:.2f} MB")
                else:
                    print(f"Plot generation failed for {page_size}s: {response.status_code}")
        
        # Test spectrogram generation
        with time_operation("Spectrogram Generation"):
            response = self.session.get(f"{self.base_url}/spectrogram")
            if response.status_code == 200:
                results['spectrogram'] = response.elapsed.total_seconds()
                data_size_mb = len(response.content) / (1024 * 1024)
                print(f"  Data size: {data_size_mb:.2f} MB")
            else:
                print(f"Spectrogram generation failed: {response.status_code}")
                
        return results
    
    def profile_ml_predictions(self) -> Dict:
        """Profile ML model prediction operations"""
        results = {}
        
        with time_operation("ML Model Prediction"):
            response = self.session.post(f"{self.base_url}/predict")
            if response.status_code == 200:
                results['ml_prediction'] = response.elapsed.total_seconds()
                try:
                    data = response.json()
                    predictions_count = len(data.get('predictions', []))
                    print(f"  Generated {predictions_count} predictions")
                except:
                    print(f"  Response size: {len(response.content)} bytes")
            else:
                print(f"ML prediction failed: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                
        return results
    
    def profile_downloads(self) -> Dict:
        """Profile file download operations"""
        results = {}
        
        # Test CSV download
        with time_operation("CSV Export Download"):
            response = self.session.get(f"{self.base_url}/download/csv")
            if response.status_code == 200:
                results['csv_download'] = response.elapsed.total_seconds()
                file_size_mb = len(response.content) / (1024 * 1024)
                print(f"  File size: {file_size_mb:.2f} MB")
            else:
                print(f"CSV download failed: {response.status_code}")
        
        # Test other download types if available
        download_types = ['annotations', 'predictions', 'report']
        for download_type in download_types:
            with time_operation(f"{download_type.title()} Download"):
                response = self.session.get(f"{self.base_url}/download/{download_type}")
                if response.status_code == 200:
                    results[f'{download_type}_download'] = response.elapsed.total_seconds()
                    file_size_mb = len(response.content) / (1024 * 1024)
                    print(f"  File size: {file_size_mb:.2f} MB")
                elif response.status_code == 404:
                    print(f"  {download_type} download not available (404)")
                else:
                    print(f"  {download_type} download failed: {response.status_code}")
                    
        return results
    
    def profile_realtime_updates(self) -> Dict:
        """Profile real-time viewer updates"""
        results = {}
        
        # Simulate rapid navigation (like user scrolling through data)
        with time_operation("Rapid Navigation Sequence"):
            start_time = time.perf_counter()
            navigation_times = []
            
            for i in range(10):  # 10 rapid requests
                response = self.session.post(f"{self.base_url}/load_eeg",
                                           json={'current_time': i * 30})  # Every 30 seconds
                if response.status_code == 200:
                    navigation_times.append(response.elapsed.total_seconds())
                
            end_time = time.perf_counter()
            total_time = end_time - start_time
            avg_request_time = sum(navigation_times) / len(navigation_times) if navigation_times else 0
            
            results['rapid_navigation_total'] = total_time
            results['rapid_navigation_avg'] = avg_request_time
            print(f"  Average request time: {avg_request_time:.4f} seconds")
            print(f"  Requests per second: {10/total_time:.2f}")
            
        return results
    
    def profile_memory_usage(self) -> Dict:
        """Profile memory-intensive operations"""
        results = {}
        
        # Test large file processing
        with time_operation("Large Data Request"):
            # Request a large time window
            response = self.session.post(f"{self.base_url}/load_eeg",
                                       json={'page_size': 300, 'current_time': 0})  # 5 minute window
            if response.status_code == 200:
                results['large_data_request'] = response.elapsed.total_seconds()
                data_size_mb = len(response.content) / (1024 * 1024)
                print(f"  Data transferred: {data_size_mb:.2f} MB")
            else:
                print(f"Large data request failed: {response.status_code}")
                
        return results
    
    def run_comprehensive_profile(self, edf_file_path: str = None):
        """Run complete web application performance profile"""
        print("Sauron's Eye Web Application Performance Profiler")
        print("=" * 60)
        
        if not self.check_server_available():
            print("❌ ERROR: Flask server not available!")
            print(f"Please start the server at {self.base_url}")
            print("Run: python app.py")
            return
            
        print(f"✅ Server available at {self.base_url}")
        
        # Use default EDF file if not provided
        if not edf_file_path:
            test_files = ["sample_psg.edf", "app/data/1/sample_psg.edf"]
            for test_file in test_files:
                if os.path.exists(test_file):
                    edf_file_path = test_file
                    break
                    
        if not edf_file_path:
            print("❌ No EDF file found for testing!")
            print("Please provide an EDF file path as argument")
            return
            
        print(f"📁 Using test file: {edf_file_path}")
        
        # Run all profiling tests
        all_results = {}
        
        print("\n" + "🔄 UPLOAD WORKFLOW TESTING" + "=" * 40)
        all_results['upload'] = self.profile_file_upload(edf_file_path)
        
        print("\n" + "🎯 NAVIGATION TESTING" + "=" * 40)
        all_results['navigation'] = self.profile_plot_navigation()
        
        print("\n" + "📊 PLOT GENERATION TESTING" + "=" * 40)
        all_results['plots'] = self.profile_plot_generation()
        
        print("\n" + "🧠 ML PREDICTION TESTING" + "=" * 40)
        all_results['ml'] = self.profile_ml_predictions()
        
        print("\n" + "💾 DOWNLOAD TESTING" + "=" * 40)
        all_results['downloads'] = self.profile_downloads()
        
        print("\n" + "⚡ REAL-TIME PERFORMANCE TESTING" + "=" * 40)
        all_results['realtime'] = self.profile_realtime_updates()
        
        print("\n" + "🧮 MEMORY USAGE TESTING" + "=" * 40)
        all_results['memory'] = self.profile_memory_usage()
        
        # Summary report
        self.generate_summary_report(all_results)
        
        return all_results
    
    def generate_summary_report(self, results: Dict):
        """Generate a comprehensive summary report"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY REPORT")
        print("=" * 60)
        
        # Key metrics
        key_metrics = [
            ("File Upload", "upload", "upload_post"),
            ("Initial Plot Load", "upload", "initial_plot_load"), 
            ("Forward Navigation", "navigation", "forward_navigation"),
            ("Backward Navigation", "navigation", "backward_navigation"),
            ("30s Plot Generation", "plots", "plot_30s"),
            ("CSV Download", "downloads", "csv_download"),
            ("ML Prediction", "ml", "ml_prediction"),
            ("Average Navigation", "realtime", "rapid_navigation_avg")
        ]
        
        print("\n🚀 KEY USER-FACING PERFORMANCE METRICS:")
        print("-" * 45)
        
        for metric_name, category, key in key_metrics:
            if category in results and key in results[category]:
                time_val = results[category][key]
                status = "🔴 SLOW" if time_val > 3 else "🟡 OK" if time_val > 1 else "🟢 FAST"
                print(f"{metric_name:<25} {time_val:>8.3f}s  {status}")
            else:
                print(f"{metric_name:<25} {'N/A':>8}   ⚪ SKIP")
        
        print("\n📈 OPTIMIZATION RECOMMENDATIONS:")
        print("-" * 35)
        
        # Generate recommendations based on results
        recommendations = []
        
        if 'upload' in results and results['upload'].get('upload_post', 0) > 5:
            recommendations.append("⚡ File upload is slow - consider file size limits or async processing")
            
        if 'navigation' in results and results['navigation'].get('forward_navigation', 0) > 1:
            recommendations.append("⚡ Navigation is slow - optimize EEG data loading and caching")
            
        if 'plots' in results and results['plots'].get('plot_30s', 0) > 2:
            recommendations.append("⚡ Plot generation is slow - consider plot caching or optimization")
            
        if 'downloads' in results and results['downloads'].get('csv_download', 0) > 3:
            recommendations.append("⚡ CSV download is slow - consider compression or streaming")
            
        if 'ml' in results and results['ml'].get('ml_prediction', 0) > 10:
            recommendations.append("⚡ ML prediction is slow - consider model optimization or GPU acceleration")
            
        if recommendations:
            for rec in recommendations:
                print(f"• {rec}")
        else:
            print("• 🎉 All operations are performing well!")
            
        print("\n💡 GENERAL RECOMMENDATIONS:")
        print("• Cache processed EEG data for faster navigation")
        print("• Implement progressive loading for large datasets")
        print("• Use compression for data transfers")
        print("• Consider WebSocket for real-time updates")
        print("• Optimize database queries if using persistent storage")

if __name__ == "__main__":
    # Get server URL and EDF file from command line
    server_url = "http://localhost:5000"
    edf_file = None
    
    if len(sys.argv) > 1:
        edf_file = sys.argv[1]
    if len(sys.argv) > 2:
        server_url = sys.argv[2]
    
    print("Web Application Performance Profiler")
    print("Usage: python webapp_performance_profiler.py [edf_file] [server_url]")
    print(f"Testing server: {server_url}")
    
    profiler = WebAppPerformanceProfiler(server_url)
    profiler.run_comprehensive_profile(edf_file)