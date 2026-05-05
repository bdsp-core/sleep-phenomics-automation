# Sauron's Eye Performance Profiling Tools

This directory contains comprehensive performance profiling tools to measure the actual user experience of your sleep EEG web application.

## 🎯 What These Tools Measure

### Real User Workflows:
- **File Upload**: Complete workflow from file selection to initial plot display
- **Navigation**: Forward/backward button response times 
- **Plot Updates**: Time for plots to refresh when changing settings
- **Downloads**: CSV/data export generation and transfer times
- **Interactive Features**: Spectrogram loading, rapid navigation

## 📊 Available Profilers

### 1. `webapp_user_experience_profiler.py` ⭐ **PRIMARY TOOL**
**Tests actual user workflows against your running Flask application**

```bash
# Start your Flask app first
python app.py

# Then run the profiler
python webapp_user_experience_profiler.py
```

**Measures:**
- Complete file upload workflow (page load + upload + initial plot)
- Navigation button response times (forward, backward, rapid clicking)
- CSV download generation and transfer speed
- Plot update times for different page sizes
- Spectrogram loading performance

**Output:** Real timings that users experience, with UX ratings (Fast/Slow/Critical)

### 2. `demo_webapp_profiler.py` 📺 **DEMO VERSION**
**Shows what the real profiler output looks like with realistic timings**

```bash
python demo_webapp_profiler.py
```

Use this to see expected output format and typical performance ranges.

### 3. `performance_profiler_standalone.py` 🔧 **BACKEND PROFILER**
**Tests core EEG processing operations without Flask**

```bash
python performance_profiler_standalone.py [edf_file.edf]
```

**Measures:**
- EEG file loading and preprocessing
- Spectral analysis (multitaper PSD)
- Signal filtering operations
- Data serialization for web transfer

### 4. `performance_profiler.py` 🏗️ **APP-AWARE PROFILER**
**Tests app modules when available, fallback when not**

```bash
python performance_profiler.py [edf_file.edf]
```

## 🚀 Quick Start

### Option 1: Test Your Running Flask App (Recommended)
```bash
# Terminal 1: Start your Flask app
cd /path/to/saurons_eye
python app.py

# Terminal 2: Run the profiler
python webapp_user_experience_profiler.py
```

### Option 2: See Demo Output
```bash
python demo_webapp_profiler.py
```

### Option 3: Test Backend Performance Only
```bash
python performance_profiler_standalone.py sample_psg.edf
```

## 📋 Understanding the Output

### User Experience Ratings:
- ✅ **GOOD**: Fast enough, users won't notice delays
- 🟡 **SLOW**: Noticeable delay, could be improved  
- 🔴 **VERY SLOW**: Users will be frustrated, needs optimization

### Target Performance Times:
- **Navigation**: < 0.5s (must feel instant)
- **File Upload**: < 15s (first impression matters)
- **Plot Updates**: < 2s (interactive feedback)
- **Downloads**: < 10s (users will wait for important data)
- **Spectrogram**: < 15s (analysis tool, some delay OK)

### Critical Metrics:
1. **Navigation Speed**: Most frequent user action
2. **Upload Workflow**: Sets user expectations
3. **Plot Responsiveness**: Interactive feedback quality
4. **Download Speed**: Task completion success

## 🔧 Troubleshooting

### "Server not available" Error:
1. Make sure Flask app is running: `python app.py`
2. Check the URL: default is `http://localhost:5000`
3. Try custom URL: `python webapp_user_experience_profiler.py http://localhost:8000`

### "No EDF file found" Warning:
- Place `sample_psg.edf` in current directory
- Or specify file: `python profiler.py /path/to/file.edf`

### Slow Performance Issues:
1. **Navigation > 1s**: Cache plot data, optimize EEG loading
2. **Upload > 30s**: Implement progress bars, async processing
3. **Downloads > 15s**: Pre-compute data, use compression

## 📈 Using Results for Optimization

### High Priority (User will notice):
- Navigation delays > 0.5s
- Plot updates > 2s
- Upload failures or excessive delays

### Medium Priority (Nice to have):
- CSV downloads > 10s
- Spectrogram loading > 20s
- Large file upload optimization

### Optimization Strategies:
1. **Caching**: Store processed EEG data
2. **Compression**: Reduce data transfer sizes
3. **Progressive Loading**: Show partial results quickly
4. **Background Processing**: Non-blocking operations
5. **WebSocket**: Real-time updates

## 🎯 Regular Usage

Run these profilers regularly to:
- Track performance changes over time
- Test impact of new features
- Validate optimizations
- Ensure consistent user experience

**Recommended**: Run `webapp_user_experience_profiler.py` after any significant code changes.

## 📞 Support

If you encounter issues:
1. Check Flask app is running and accessible
2. Verify EDF test files are available
3. Review error messages for specific guidance
4. Check network/firewall settings if using custom URLs