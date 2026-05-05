#!/usr/bin/env python3
"""
Web Application User Experience Profiler for Sauron's Eye

This script measures actual user workflow timings by interacting with the running Flask app:
- Upload file → measure complete upload time
- Navigate (forward/backward) → measure plot update time  
- Download CSV → measure generation and transfer time
- Change settings → measure plot refresh time

Usage: python webapp_user_experience_profiler.py [server_url]
Make sure your Flask app is running first!
"""

import time
import requests
import os
import sys
from typing import Dict, Optional
import json

class WebAppUserExperienceProfiler:
    """Test actual user workflows against the running web application"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Saurons-Eye-Performance-Profiler/1.0'
        })
        
    def check_server_status(self) -> bool:
        """Check if the Flask server is running and responding"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=10)
            if response.status_code == 200:
                print(f"✅ Server is running at {self.base_url}")
                return True
            else:
                print(f"❌ Server responded with status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to server: {e}")
            return False
    
    def measure_file_upload(self, edf_file_path: str) -> Dict[str, float]:
        """Measure complete file upload workflow timing"""
        print("\n" + "="*50)
        print("📤 TESTING FILE UPLOAD WORKFLOW")
        print("="*50)
        
        if not os.path.exists(edf_file_path):
            print(f"❌ Test file not found: {edf_file_path}")
            return {'error': 'file_not_found'}
        
        file_size_mb = os.path.getsize(edf_file_path) / (1024 * 1024)
        print(f"📁 Upload file: {edf_file_path} ({file_size_mb:.1f} MB)")
        
        results = {}
        
        # Step 1: Load upload page
        print("\n🔄 Step 1: Loading upload page...")
        start_time = time.time()
        try:
            response = self.session.get(f"{self.base_url}/")
            page_load_time = time.time() - start_time
            results['page_load_time'] = page_load_time
            print(f"   ⏱️  Page load: {page_load_time:.3f}s")
            
            if response.status_code != 200:
                print(f"   ❌ Failed to load page: {response.status_code}")
                return results
                
        except Exception as e:
            print(f"   ❌ Error loading page: {e}")
            return results
        
        # Step 2: Upload file
        print("\n📤 Step 2: Uploading file...")
        upload_start_time = time.time()
        try:
            with open(edf_file_path, 'rb') as f:
                files = {'file': (os.path.basename(edf_file_path), f, 'application/octet-stream')}
                
                # This is the actual upload request users make
                response = self.session.post(f"{self.base_url}/upload", files=files, timeout=120)
                
            upload_total_time = time.time() - upload_start_time
            results['upload_total_time'] = upload_total_time
            
            print(f"   ⏱️  Upload complete: {upload_total_time:.3f}s")
            print(f"   📊 Upload speed: {file_size_mb/upload_total_time:.1f} MB/s")
            
            if response.status_code == 302:  # Redirect after successful upload
                print("   ✅ Upload successful - redirecting to viewer")
                results['upload_success'] = True
                
                # Step 3: Follow redirect to viewer (initial plot load)
                print("\n📊 Step 3: Loading initial plot...")
                plot_start_time = time.time()
                
                final_response = self.session.get(response.url, timeout=60)
                initial_plot_time = time.time() - plot_start_time
                results['initial_plot_time'] = initial_plot_time
                
                print(f"   ⏱️  Initial plot load: {initial_plot_time:.3f}s")
                
                if final_response.status_code == 200:
                    print("   ✅ Viewer loaded successfully")
                    results['viewer_success'] = True
                else:
                    print(f"   ❌ Viewer failed to load: {final_response.status_code}")
                    
            else:
                print(f"   ❌ Upload failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                results['upload_success'] = False
                
        except Exception as e:
            upload_time = time.time() - upload_start_time
            print(f"   ❌ Upload error after {upload_time:.1f}s: {e}")
            results['upload_error'] = str(e)
            results['upload_time_before_error'] = upload_time
        
        # Calculate total workflow time
        total_time = time.time() - start_time
        results['total_workflow_time'] = total_time
        
        print(f"\n📋 UPLOAD WORKFLOW SUMMARY:")
        print(f"   Total time: {total_time:.3f}s")
        if results.get('upload_success'):
            print("   Status: ✅ SUCCESS")
        else:
            print("   Status: ❌ FAILED")
            
        return results
    
    def measure_navigation_performance(self) -> Dict[str, float]:
        """Measure navigation button response times"""
        print("\n" + "="*50)
        print("🧭 TESTING NAVIGATION PERFORMANCE")
        print("="*50)
        
        results = {}
        
        # Test forward navigation
        print("\n➡️  Testing FORWARD navigation...")
        start_time = time.time()
        try:
            # This simulates clicking the forward button
            response = self.session.post(
                f"{self.base_url}/load_eeg",
                json={'action': 'forward'},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            forward_time = time.time() - start_time
            results['forward_navigation_time'] = forward_time
            
            if response.status_code == 200:
                data_size_kb = len(response.content) / 1024
                print(f"   ⏱️  Forward click response: {forward_time:.3f}s")
                print(f"   📊 Data received: {data_size_kb:.1f} KB")
                print("   ✅ Forward navigation working")
            else:
                print(f"   ❌ Forward navigation failed: {response.status_code}")
                print(f"   Response: {response.text[:100]}...")
                
        except Exception as e:
            forward_time = time.time() - start_time
            print(f"   ❌ Forward navigation error after {forward_time:.3f}s: {e}")
            results['forward_navigation_error'] = str(e)
        
        # Test backward navigation
        print("\n⬅️  Testing BACKWARD navigation...")
        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.base_url}/load_eeg",
                json={'action': 'backward'},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            backward_time = time.time() - start_time
            results['backward_navigation_time'] = backward_time
            
            if response.status_code == 200:
                data_size_kb = len(response.content) / 1024
                print(f"   ⏱️  Backward click response: {backward_time:.3f}s")
                print(f"   📊 Data received: {data_size_kb:.1f} KB")
                print("   ✅ Backward navigation working")
            else:
                print(f"   ❌ Backward navigation failed: {response.status_code}")
                
        except Exception as e:
            backward_time = time.time() - start_time
            print(f"   ❌ Backward navigation error after {backward_time:.3f}s: {e}")
            results['backward_navigation_error'] = str(e)
        
        # Test rapid clicking (user rapidly navigating)
        print("\n🔄 Testing RAPID NAVIGATION (10 clicks)...")
        rapid_times = []
        
        for i in range(10):
            start_time = time.time()
            try:
                response = self.session.post(
                    f"{self.base_url}/load_eeg",
                    json={'action': 'forward'},
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                
                click_time = time.time() - start_time
                rapid_times.append(click_time)
                
                if i == 0:  # Print details for first click only
                    if response.status_code == 200:
                        print(f"   ⏱️  Click {i+1}: {click_time:.3f}s ✅")
                    else:
                        print(f"   ⏱️  Click {i+1}: {click_time:.3f}s ❌ (status: {response.status_code})")
                elif i == 9:  # Print details for last click
                    print(f"   ⏱️  Click {i+1}: {click_time:.3f}s")
                    
            except Exception as e:
                click_time = time.time() - start_time
                rapid_times.append(click_time)
                if i < 2:  # Only print first few errors
                    print(f"   ⏱️  Click {i+1}: {click_time:.3f}s ❌ ({e})")
        
        if rapid_times:
            avg_rapid_time = sum(rapid_times) / len(rapid_times)
            max_rapid_time = max(rapid_times)
            min_rapid_time = min(rapid_times)
            
            results['rapid_navigation_avg'] = avg_rapid_time
            results['rapid_navigation_max'] = max_rapid_time
            results['rapid_navigation_min'] = min_rapid_time
            
            print(f"   📊 Average response: {avg_rapid_time:.3f}s")
            print(f"   📊 Fastest response: {min_rapid_time:.3f}s")
            print(f"   📊 Slowest response: {max_rapid_time:.3f}s")
            
            # User experience rating
            if avg_rapid_time < 0.5:
                print("   🚀 Rating: EXCELLENT - Feels instant")
            elif avg_rapid_time < 1.0:
                print("   ⚡ Rating: GOOD - Responsive")
            elif avg_rapid_time < 2.0:
                print("   🟡 Rating: SLOW - Noticeable delay")
            else:
                print("   🔴 Rating: VERY SLOW - Frustrating")
        
        return results
    
    def measure_csv_download(self) -> Dict[str, float]:
        """Measure CSV download generation and transfer time"""
        print("\n" + "="*50)
        print("💾 TESTING CSV DOWNLOAD")
        print("="*50)
        
        results = {}
        
        print("\n📄 Requesting CSV download...")
        start_time = time.time()
        
        try:
            # This simulates user clicking "Download CSV" button
            response = self.session.get(f"{self.base_url}/download/csv", timeout=60)
            
            download_time = time.time() - start_time
            results['csv_download_time'] = download_time
            
            if response.status_code == 200:
                file_size_mb = len(response.content) / (1024 * 1024)
                
                print(f"   ⏱️  Download time: {download_time:.3f}s")
                print(f"   📊 File size: {file_size_mb:.2f} MB")
                print(f"   📊 Transfer speed: {file_size_mb/download_time:.1f} MB/s")
                
                # Check if it's actually CSV content
                content_type = response.headers.get('content-type', '')
                if 'csv' in content_type.lower() or response.content.startswith(b'epoch') or response.content.startswith(b'timestamp'):
                    print("   ✅ Valid CSV file received")
                    results['csv_valid'] = True
                    
                    # Count lines to estimate data rows
                    lines = response.content.decode('utf-8', errors='ignore').count('\n')
                    print(f"   📊 Estimated rows: {lines:,}")
                    results['csv_rows'] = lines
                else:
                    print(f"   ⚠️  Unexpected content type: {content_type}")
                    print(f"   First 100 chars: {response.content[:100]}")
                    
            else:
                print(f"   ❌ Download failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                results['csv_download_error'] = response.status_code
                
        except Exception as e:
            download_time = time.time() - start_time
            print(f"   ❌ Download error after {download_time:.3f}s: {e}")
            results['csv_download_error'] = str(e)
            results['csv_download_time'] = download_time
        
        return results
    
    def measure_settings_changes(self) -> Dict[str, float]:
        """Measure plot update times when user changes settings"""
        print("\n" + "="*50)
        print("⚙️ TESTING SETTINGS CHANGES")
        print("="*50)
        
        results = {}
        
        # Test page size changes (different time windows)
        page_sizes = [10, 30, 60]  # seconds
        
        for page_size in page_sizes:
            print(f"\n📏 Testing {page_size}s page size...")
            start_time = time.time()
            
            try:
                response = self.session.post(
                    f"{self.base_url}/load_eeg",
                    json={'page_size': page_size},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                update_time = time.time() - start_time
                results[f'page_size_{page_size}s_time'] = update_time
                
                if response.status_code == 200:
                    data_size_mb = len(response.content) / (1024 * 1024)
                    print(f"   ⏱️  Plot update: {update_time:.3f}s")
                    print(f"   📊 Data size: {data_size_mb:.2f} MB")
                    
                    # User experience rating for this page size
                    if update_time < 1.0:
                        print("   ✅ Responsive")
                    elif update_time < 3.0:
                        print("   🟡 Acceptable")
                    else:
                        print("   🔴 Slow")
                else:
                    print(f"   ❌ Failed: {response.status_code}")
                    
            except Exception as e:
                update_time = time.time() - start_time
                print(f"   ❌ Error after {update_time:.3f}s: {e}")
                results[f'page_size_{page_size}s_error'] = str(e)
        
        return results
    
    def measure_spectrogram_loading(self) -> Dict[str, float]:
        """Measure spectrogram generation time"""
        print("\n" + "="*50)
        print("📈 TESTING SPECTROGRAM LOADING")
        print("="*50)
        
        results = {}
        
        print("\n🔬 Loading spectrogram view...")
        start_time = time.time()
        
        try:
            response = self.session.get(f"{self.base_url}/spectrogram", timeout=120)
            
            spectrogram_time = time.time() - start_time
            results['spectrogram_load_time'] = spectrogram_time
            
            if response.status_code == 200:
                # Check if we got HTML (spectrogram page) or data
                content_size_mb = len(response.content) / (1024 * 1024)
                
                print(f"   ⏱️  Spectrogram load: {spectrogram_time:.3f}s")
                print(f"   📊 Response size: {content_size_mb:.2f} MB")
                
                if 'html' in response.headers.get('content-type', '').lower():
                    print("   ✅ Spectrogram page loaded")
                else:
                    print("   ✅ Spectrogram data received")
                    
                # Rate user experience
                if spectrogram_time < 5.0:
                    print("   🚀 Fast loading")
                elif spectrogram_time < 15.0:
                    print("   ⚡ Acceptable for analysis tool")
                else:
                    print("   🔴 Very slow - users may abandon")
                    
            else:
                print(f"   ❌ Spectrogram failed: {response.status_code}")
                results['spectrogram_error'] = response.status_code
                
        except Exception as e:
            spectrogram_time = time.time() - start_time
            print(f"   ❌ Spectrogram error after {spectrogram_time:.3f}s: {e}")
            results['spectrogram_error'] = str(e)
            results['spectrogram_load_time'] = spectrogram_time
        
        return results
    
    def run_complete_user_experience_test(self, edf_file_path: str = None) -> Dict:
        """Run complete user experience testing suite"""
        print("Sauron's Eye - Web Application User Experience Profiler")
        print("=" * 65)
        print("🎯 Testing REAL user workflows against running Flask app")
        print("👤 Measuring actual response times users experience")
        
        # Check server availability
        if not self.check_server_status():
            print("\n❌ CRITICAL ERROR: Flask server not available!")
            print("Start your Flask app first:")
            print("   python app.py")
            print("   python -m flask run")
            print(f"   Then make sure it's accessible at {self.base_url}")
            return {'error': 'server_not_available'}
        
        # Find test EDF file if not provided
        if not edf_file_path:
            test_files = [
                "sample_psg.edf",
                "app/data/1/sample_psg.edf",
                "app/data/2/sample_psg.edf"
            ]
            
            for test_file in test_files:
                if os.path.exists(test_file):
                    edf_file_path = test_file
                    break
                    
            if not edf_file_path:
                print("\n⚠️  No EDF test file found. Upload test will be skipped.")
                print("Place a sample EDF file in current directory for full testing.")
        
        all_results = {}
        
        # Run all user workflow tests
        if edf_file_path:
            all_results['upload'] = self.measure_file_upload(edf_file_path)
        
        all_results['navigation'] = self.measure_navigation_performance()
        all_results['csv_download'] = self.measure_csv_download()
        all_results['settings'] = self.measure_settings_changes()
        all_results['spectrogram'] = self.measure_spectrogram_loading()
        
        # Generate user-focused summary
        self.generate_user_experience_summary(all_results)
        
        return all_results
    
    def generate_user_experience_summary(self, results: Dict):
        """Generate summary focused on real user experience"""
        print("\n" + "="*65)
        print("🎯 USER EXPERIENCE SUMMARY")
        print("="*65)
        
        print("\n⚡ KEY USER WORKFLOW TIMINGS:")
        print("-" * 40)
        
        # Extract key timings
        timings = [
            ("File Upload (Complete)", results.get('upload', {}).get('total_workflow_time'), 15.0),
            ("Forward Navigation", results.get('navigation', {}).get('forward_navigation_time'), 0.5),
            ("Backward Navigation", results.get('navigation', {}).get('backward_navigation_time'), 0.5),
            ("CSV Download", results.get('csv_download', {}).get('csv_download_time'), 10.0),
            ("Spectrogram Load", results.get('spectrogram', {}).get('spectrogram_load_time'), 15.0),
            ("30s Plot Update", results.get('settings', {}).get('page_size_30s_time'), 2.0)
        ]
        
        for operation, timing, target in timings:
            if timing is not None:
                if timing <= target:
                    status = "✅ GOOD"
                elif timing <= target * 1.5:
                    status = "🟡 SLOW"
                else:
                    status = "🔴 VERY SLOW"
                    
                print(f"  {operation:<25} {timing:>6.3f}s  {status}")
            else:
                print(f"  {operation:<25} {'N/A':>6}   ⚪ SKIP")
        
        print("\n📊 CRITICAL FINDINGS:")
        print("-" * 25)
        
        # Navigation performance (most critical)
        nav_time = results.get('navigation', {}).get('forward_navigation_time')
        if nav_time is not None:
            if nav_time > 1.0:
                print("🔴 CRITICAL: Navigation is too slow! Users will notice lag.")
            elif nav_time > 0.5:
                print("🟡 WARNING: Navigation could be faster for better UX.")
            else:
                print("✅ EXCELLENT: Navigation feels instant.")
        
        # Upload workflow
        upload_time = results.get('upload', {}).get('total_workflow_time')
        if upload_time is not None:
            if upload_time > 30:
                print("🔴 CRITICAL: File upload takes too long! Users may abandon.")
            elif upload_time > 15:
                print("🟡 WARNING: Upload time is on the edge of user patience.")
            else:
                print("✅ GOOD: Upload completes in reasonable time.")
        
        print("\n💡 OPTIMIZATION RECOMMENDATIONS:")
        print("-" * 35)
        
        # Specific recommendations based on results
        recommendations = []
        
        if nav_time and nav_time > 0.5:
            recommendations.append("• URGENT: Optimize navigation - cache plot data, reduce processing")
            
        if upload_time and upload_time > 20:
            recommendations.append("• Optimize file upload - async processing, progress indicators")
            
        csv_time = results.get('csv_download', {}).get('csv_download_time')
        if csv_time and csv_time > 10:
            recommendations.append("• Optimize CSV generation - pre-compute or stream data")
            
        spec_time = results.get('spectrogram', {}).get('spectrogram_load_time')
        if spec_time and spec_time > 20:
            recommendations.append("• Optimize spectrogram - reduce resolution or compute on-demand")
            
        if not recommendations:
            recommendations.append("• 🎉 All workflows are performing well!")
            
        for rec in recommendations:
            print(rec)
            
        print("\n🎯 USER EXPERIENCE PRIORITIES:")
        print("-" * 35)
        print("1. Navigation speed (most frequent action)")
        print("2. Initial file upload (first impression)")
        print("3. Plot updates (interactive feedback)")
        print("4. Download speed (task completion)")
        
        print(f"\n📱 Tested against: {self.base_url}")
        print("💡 Run this regularly to track performance changes!")

def main():
    # Get server URL from command line or use default
    server_url = "http://localhost:5000"
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    
    print("🔧 Usage Instructions:")
    print("1. Start your Flask application:")
    print("   python app.py")
    print("2. Run this profiler:")
    print(f"   python {sys.argv[0]} [server_url]")
    print(f"3. Default server: {server_url}")
    print()
    
    profiler = WebAppUserExperienceProfiler(server_url)
    results = profiler.run_complete_user_experience_test()
    
    return results

if __name__ == "__main__":
    main()