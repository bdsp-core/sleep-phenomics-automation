// Display parameters
var dur = 30;

// global vars
var mychart;
var Y, mm, nn, tt, ekg;
var t2, time_stamps;
var max_ind, eeg_start;
var ratio;
var aspect_ratio = 2;
var plotBuilt = false;
var selectedFile = null;
var gain = .005;
var channelGains = {};  // Per-channel gain multipliers
var recordingDuration = null;
var pendingJumpTime = null;
var pendingAutoScale = false;

// Default bandpass filter settings per standard PSG channel
const CHANNEL_FILTERS = {
    'F3-M2':       {low: 0.3,  high: 35},
    'F4-M1':       {low: 0.3,  high: 35},
    'C3-M2':       {low: 0.3,  high: 35},
    'C4-M1':       {low: 0.3,  high: 35},
    'O1-M2':       {low: 0.3,  high: 35},
    'O2-M1':       {low: 0.3,  high: 35},
    'E1-M2':       {low: 0.3,  high: 35},
    'E2-M1':       {low: 0.3,  high: 35},
    'CHIN1-CHIN2': {low: 10,   high: 100},
    'LAT':         {low: 10,   high: 100},
    'RAT':         {low: 10,   high: 100},
    'SNORE':       {low: 10,   high: 100},
    'ECG':         {low: 0.3,  high: 100},
    'PTAF':        {low: 0.03, high: 100},
    'AIRFLOW':     {low: 0.1,  high: 15},
    'CHEST':       {low: 0.1,  high: 15},
    'ABD':         {low: 0.1,  high: 15},
    'SpO2':        {low: 0.1,  high: 15},
};

// Buffer setup
const bufferLength = 30;                            // Total length of data buffer
const fetch_pad = 5;                               // Define proximity to edge of data buffer to trigger fetching new data
const preload_length = 4;                          // Segments of data to load before allowing user to begin scrolling
let buffer = new Array(bufferLength).fill(null);    // Buffer to store data from different segments
let requestedIndices = [];                          // List of indices of EEG segments which have been requested but not yet received
let readPointer = 0;                                // Index of segment in buffer currently being displayed to user

Chart.defaults.plugins.tooltip.enabled = false;

function increase_gain() {
    const scaleSelect = document.getElementById('scaleChannelSelect');
    if (!scaleSelect || scaleSelect.value === 'all') {
        gain = gain * 1.5;
    } else {
        const ch = scaleSelect.value;
        channelGains[ch] = (channelGains[ch] || 1.0) * 1.5;
    }
    display_segment(buffer[readPointer]);
}

function decrease_gain() {
    const scaleSelect = document.getElementById('scaleChannelSelect');
    if (!scaleSelect || scaleSelect.value === 'all') {
        gain = gain / 1.5;
    } else {
        const ch = scaleSelect.value;
        channelGains[ch] = (channelGains[ch] || 1.0) / 1.5;
    }
    display_segment(buffer[readPointer]);
}

function autoScaleSignals() {
    const data_chunk = buffer[readPointer];
    if (!data_chunk || !data_chunk.seg || data_chunk.seg.length === 0) return;

    const seg = data_chunk.seg;
    const channels = data_chunk.channels;
    const Fs = data_chunk.Fs;

    // Apply same filtering pipeline as plot_psg
    var [filteredY, reref_channels] = bipolarReRef(seg, channels);

    filteredY = filteredY.map((signal, i) => {
        const chName = reref_channels[i];
        const filt = CHANNEL_FILTERS[chName];
        if (filt) {
            return butterworthBandpassFilter([signal], Fs, filt.low, filt.high)[0];
        }
        return signal;
    });

    const notch_f = document.getElementById('notch_f').value;
    if (notch_f !== 'off') {
        filteredY = butterworthNotchFilter(filteredY, Fs, parseFloat(notch_f), 1);
    }

    // Set per-channel gains so every channel spans ~0.9 display units (channel spacing = 1.0)
    const targetRange = 0.9;
    reref_channels.forEach((chName, i) => {
        const signal = filteredY[i];
        let mn = signal[0], mx = signal[0];
        for (let j = 1; j < signal.length; j++) {
            if (signal[j] < mn) mn = signal[j];
            if (signal[j] > mx) mx = signal[j];
        }
        const range = mx - mn;
        if (range > 0) {
            channelGains[chName] = targetRange / (range * gain);
        }
    });

    display_segment(data_chunk);
}

function go_to_start() {
    if (!buffer[readPointer]) return;
    jumpToTime(0);
}

function go_to_end() {
    if (!buffer[readPointer] || recordingDuration == null) return;
    jumpToTime(recordingDuration - dur);
}

function updateBuffer(data_chunk) {
    // Determine what index in entire recording the read pointer is currently pointing to
    if (buffer[readPointer] == null) {
        current_index = 0;
    } else {
        current_index = buffer[readPointer].index; 
    }
    
    // Determine where in the read buffer the new chunk should be added
    dist_from_current_index = data_chunk.index - current_index;
    bufferIndex = readPointer + dist_from_current_index;
    
    // If new chunk can be added to buffer without changing buffer size, add it
    if (bufferIndex >= 0 && bufferIndex < bufferLength){
        buffer[bufferIndex] = data_chunk;
    }
}

function maybe_read_data(selected_file, idx, callback, initialRead = false, wait = false) {
    // Checks whether a specific section of data has already been requested before sending a read request.
    // Has same signature as read_data()
    
    if (!requestedIndices.includes(idx)) {
        requestedIndices.push(idx); // Add index to list of requested indices
        read_data(selected_file, idx, function(data_chunk) {
            // Remove index from list of requested indices once it's received
            requestedIndices = requestedIndices.filter(item => item !== idx);
            
            // Call the rest of the callback function
            callback(data_chunk);
        }, initialRead, wait)
    }
}

function initializeBufferCallback(data_chunk, i) {
    buffer[i] = data_chunk; // Move data into buffer
    
    // Code to execute if buffer is now full
    if (!buffer.slice(0,preload_length).some(el => el === null)) {

        // Show container first so Plotly can measure the correct width
        document.getElementById('eeg_container').style.display = 'block';
        document.getElementById('loading_Indicator').style.display = 'none';

        // Display plot; auto-scale on initial file load
        if (pendingAutoScale) {
            pendingAutoScale = false;
            autoScaleSignals();
        } else {
            display_segment(buffer[readPointer]);
        }

        // If switching page sizes, jump back to the previous page start time
        if (pendingJumpTime !== null) {
            const t = pendingJumpTime;
            pendingJumpTime = null;
            jumpToTime(t);
        }
    }
}

function jumpBufferCallback(data_chunk, i, start, end, clickedIdx) {
    console.log(`i = ${i}`);
    buffer[i] = data_chunk; // Move data into buffer

    const loadCenter = Math.min(clickedIdx,bufferLength/2);  // Index in buffer around which to preload data
    const preloadSection = buffer.filter((_,idx) => Math.abs(idx - loadCenter) <= preload_length); // Section of buffer to pre-load data into
    if (!preloadSection.some(el => el === null)) {
        // Code to execute if section of buffer to pre-load is now full

        // Display plot
        readPointer = loadCenter;
        display_segment(buffer[readPointer]);

        // Hide loading indicator and display EEG containiner
        document.getElementById('myChart_eeg').style.display = 'block';
        document.getElementById('loadingMessage').style.display = 'none';
        
        // Begin loading data outside pre-load section
        const firstIdx = Math.max(0,buffer[readPointer].index-bufferLength/2); // Index in recording of first element in new buffer after jumping
        for (let i = start; i < end; i++) {
            if (Math.abs(i - loadCenter) > preload_length) {
                maybe_read_data(selected_file,i+firstIdx,updateBuffer,false,false);
            }
        }
    }
}

function initialize() {
    // Loads the first section of an EDF recording into the data buffer along with 
    // the recording's associated report and spectrogram
    
    // Reset global state variables
    buffer = new Array(bufferLength).fill(null);
    requestedIndices = [];
    plotBuilt = false;
    readPointer = 0;
    recordingDuration = null;
    
    // Get selected file
    selected_file = document.getElementById('currentFile').value;
    if (!selected_file) {
        alert("Select a file to view or upload a new one")
        return
    }
    
    // Hide EEG container and display loading indicator
    document.getElementById('eeg_container').style.display = 'none';
    document.getElementById('loading_Indicator').style.display = 'block';
    
    // Load a certain amount of data into buffer before allowing user to begin scrolling
    for (let i = 0; i < preload_length; i++) {
        read_data(selected_file,
            i,                        // Indicates which segment of PSG to request
            (data_chunk) => {initializeBufferCallback(data_chunk, i)}, // Callback processes each data segment once it's received
            initialRead = (i == 0),   // Return report only on first read
            wait = false,             // All requests are run asyncronously
            returnReport = (i == 0)); // Return report only once
    }
    
    // Rest of data can be loaded as user scrolls
    for (let i = preload_length; i < buffer.length; i++) {
        if (max_ind !== null && i > max_ind) break;
        maybe_read_data(selected_file,i,updateBuffer,false,false);
    }
}

function jumpToTime(time) {
    // Jump to a point the user clicks on the spectrogram
    const timeIdx = Math.round(time/dur); // Index of clicked segment
    
    // If already on the clicked segment, do nothing
    if (timeIdx == buffer[readPointer].index) {
        return
    }
    
    const firstIdx = Math.max(0,timeIdx-bufferLength/2);            // Index of first element in new buffer after jumping
    const lastIdx = firstIdx + bufferLength;                        // Index of last element in new buffer after jumping
    const firstLoadedIdx = buffer[readPointer].index - readPointer; // Index of first element in current buffer before jumping
    const lastLoadedIdx = firstLoadedIdx + bufferLength;            // Index of last element in current buffer before jumping
    
    // If possible, keep elements that have already been loaded
    if ((firstIdx <= lastLoadedIdx) && (lastIdx > lastLoadedIdx)) {
        // If new buffer after jumping will overlap on left side with existing buffer
        buffer = buffer.slice(firstIdx - lastLoadedIdx - 1);
        buffer = buffer.concat(new Array(bufferLength - buffer.length).fill(null));
        var start = lastLoadedIdx - firstIdx;
        var end = bufferLength;
    } else if ((lastIdx >= firstLoadedIdx) && (firstIdx < firstLoadedIdx)) {
        // If new buffer after jumping will overlap on right side with existing buffer
        buffer = buffer.slice(0,lastIdx - firstLoadedIdx + 1);
        buffer = new Array(bufferLength - buffer.length).fill(null).concat(buffer);
        var start = 0;
        var end = bufferLength + firstLoadedIdx - lastIdx - 1;
    } else {
        // No overlap
        buffer = new Array(bufferLength).fill(null);
        var start = 0;
        var end = bufferLength;
    }
    
    // If nothing left to load into pre-load section, skip pre-loading
    if ((start > bufferLength/2 + preload_length) || (end < bufferLength/2 - preload_length)) {
        // Display plot
        readPointer = Math.round(bufferLength/2);
        display_segment(buffer[readPointer]);
                
        // Begin loading data outside pre-load section
        for (let i = start; i <= end; i++) {
            if (Math.abs(i - bufferLength/2) > preload_length) {
                if (max_ind !== null && i + firstIdx > max_ind) continue;
                maybe_read_data(selected_file,i+firstIdx,updateBuffer,false,false);
            }
        }
        return
    }

    // Hide EEG container and display loading indicator
    document.getElementById('myChart_eeg').style.display = 'none';
    document.getElementById('loadingMessage').style.display = 'block';

    // Load all PSG data surrounding the clicked point
    for (let i = start; i <= end; i++) {
        if (max_ind !== null && i + firstIdx > max_ind) continue;
        if (Math.abs(i - Math.min(timeIdx,bufferLength/2)) <= preload_length) {
            // Only load data in pre-load section and don't allow user to scroll until this section is loaded
            callback = (data_chunk) => {jumpBufferCallback(data_chunk,i,start,end,timeIdx)};
            read_data(selected_file,i+firstIdx,callback,false,false);
        }
    }
}

// Moves the read pointer to the right, fetches new data if necessary
function go_right() {
    if (buffer[readPointer].index == max_ind){
        console.log("At end of recording")
        return
    }

    if (readPointer == bufferLength){
        // If user tries to scroll faster than can load, do nothing 
        console.log("Scrolling too fast, at edge of buffer")
        return
    }
    
    if (buffer[readPointer+1] == null){
        // If user tries to scroll to point that hasn't been loaded yet, do nothing 
        console.log("Scrolling too fast, next point not yet loaded")
        return
    }
    
    // Move read pointer to next segment and display it
    readPointer++;
    display_segment(buffer[readPointer]);
    
    // Check if we need more data on the right side
    if (readPointer >= buffer.length - fetch_pad) {
        fetch_and_append_data(selected_file, buffer[readPointer].index+bufferLength-readPointer, 'right');
    }
}

// Moves the read pointer to the left, fetches new data if necessary
function go_left() {
    if (buffer[readPointer].index == 0){
        console.log("At beginning of recording")
        return
    }
        
    if (readPointer == 0){
        // If user tries to scroll faster than can load, do nothing 
        console.log("Scrolling too fast, at edge of buffer")
        return
    }
    
    if (buffer[readPointer-1] == null){
        // If user tries to scroll to point that hasn't been loaded yet, do nothing 
        console.log("Scrolling too fast, next point not yet loaded")
        return
    }
    
    // Move read pointer to previous segment and display it
    readPointer--;
    display_segment(buffer[readPointer]);

    // Check if we need more data on the left side
    if ((readPointer <= fetch_pad) && (buffer[readPointer].index-readPointer-1 >= 0)) {
        fetch_and_append_data(selected_file, buffer[readPointer].index-readPointer-1, 'left');
    }
}

// Adds data to the appropriate end of the buffer
function fetch_and_append_data(selected_file, index, direction, initialRead = false, wait = false) {
    if (direction === 'right') {
        buffer.shift(); // Remove oldest element from left
        buffer.push(null); // Add space for new element on right
        readPointer-- // Move read pointer over to adjust for addition of new element
        maybe_read_data(selected_file, index, updateBuffer);
    } else if (direction === 'left') {
        buffer.pop(); // Remove oldest element from right
        buffer.unshift(null); // Add space for new element on left
        readPointer++ // Move read pointer over to adjust for addition of new element
        maybe_read_data(selected_file, index, updateBuffer);
    }
}

// Reads data from the server
function read_data(selected_file, idx, callback, initialRead = false, wait = false, returnReport = false) {
    $.ajax({
        url: '/viewer/load_psg',
        type: 'POST',
        dataType: 'json',  // Tell jQuery to expect JSON and auto-parse it
        data: {
            'filename': selected_file,
            'offset': idx*dur,
            'duration': dur,
            'initialRead': initialRead,
            'returnReport': returnReport
        },
        success: function(data_chunk) {
            console.log('PSG snippet received');
            try {
                // Response is already parsed as JSON object by jQuery
                console.log('Response type:', typeof data_chunk);
                console.log('Response has seg:', data_chunk && data_chunk.seg ? 'yes' : 'no');
                
                // Check if response is empty
                if (!data_chunk) {
                    console.error('Empty response received');
                    alert('Error: Empty response from server');
                    return;
                }
                
                // Check if there's an error in the response
                if (data_chunk.error) {
                    console.error('Server error:', data_chunk.error);
                    alert('Error loading PSG data: ' + data_chunk.error);
                    return;
                }
                
                // Validate essential data fields
                if (!data_chunk.seg || !Array.isArray(data_chunk.seg)) {
                    console.error('Invalid seg data in response');
                    alert('Error: Invalid PSG data format received');
                    return;
                }
                
                console.log('Valid data chunk received, channels:', data_chunk.channels ? data_chunk.channels.length : 'undefined');
                if (data_chunk.channels) {
                    console.log('Channel list:', data_chunk.channels);
                }
                callback(data_chunk);
            } catch (error) {
                console.error('Data processing error:', error);
                console.error('Response received:', data_chunk);
                alert('Error processing PSG data. Check console for details.');
            }
        },
        error: function(error) {
            console.log('Error retrieving PSG snippet:')
            console.log(error);
        },
        async: !wait,
    });
}

// Applies data to the plot
function display_segment(data_chunk) {
    console.log(`Updating plot parameters`)
    if (!data_chunk) {
        console.log('No data_chunk provided to display_segment');
        return; // Ensure data is available before applying
    }

    console.log('Display segment called, plotBuilt:', plotBuilt);

    if (!plotBuilt) {
        eeg_start = data_chunk.eeg_start;
        max_ind = data_chunk.max_ind;
        recordingDuration = data_chunk.recording_duration;

        // Populate scale dropdown with only the channels present in this file,
        // in the same top-to-bottom visual order as the plot (reversed array).
        const select = document.getElementById('scaleChannelSelect');
        if (select && data_chunk.channels) {
            const prevValue = select.value;
            select.innerHTML = '<option value="all">All channels</option>';
            data_chunk.channels.forEach(ch => {
                const opt = document.createElement('option');
                opt.value = ch;
                opt.textContent = ch;
                select.appendChild(opt);
            });
            // Restore previous selection if still valid
            if ([...select.options].some(o => o.value === prevValue)) {
                select.value = prevValue;
            }
        }
    }

    const seg = data_chunk.seg;
    const channels = data_chunk.channels;
    const Fs = data_chunk.Fs;
    const nSamples = data_chunk.nSamples;
    
    plot_psg(seg, channels, Fs, nSamples);
    
    
    plotBuilt = true;
}

function findIndexOfClosest(arr, target) {
    let closestIndex = 0;
    let closestDifference = Math.abs(arr[0] - target);

    for (let i = 1; i < arr.length; i++) {
        const currentDifference = Math.abs(arr[i] - target);

        if (currentDifference < closestDifference) {
            closestIndex = i;
            closestDifference = currentDifference;
        }
    }

    return closestIndex;
}

// Removed get_report function as we no longer generate reports

function bipolarReRef(eeg, channels) {
    // Note: Channels are already in the desired PSG montage format from the backend
    // This function now just returns the data as-is since montage is handled server-side
    return [eeg, channels];
}

function AveReRef(eeg) {
    // Average re-referencing of eeg channels

    const ave = math.mean(eeg, 0); // mean along all channels
    return eeg.map(row => math.subtract(row, ave)) // Subtract average from each channel
}

function alignForPlot(seg, baseLine) { 
    // Change baseline of each signal so that they occupy different locations on plot
    const offset = baseLine.map(val => Array(seg[0].length).fill(val));
    seg = seg.map((row, i) => row.map((value, j) => value + offset[i][j]));

    return seg;
}

function butterworthBandpassFilter(signals, sampleRate, lowCutoffFrequency, highCutoffFrequency) {
    // Calculate filter coefficients
    const lowOmega = 2 * Math.PI * lowCutoffFrequency / sampleRate;
    const highOmega = 2 * Math.PI * highCutoffFrequency / sampleRate;
    const bandwidthOmega = highOmega - lowOmega;
    const centerOmega = (highOmega + lowOmega) / 2;
    const sin_bandwidth = Math.sin(bandwidthOmega / 2);
    const alpha = sin_bandwidth * Math.sqrt(2);
    const cos_center = Math.cos(centerOmega);

    // Second-order Butterworth bandpass filter coefficients
    const b0 = alpha;
    const b1 = 0;
    const b2 = -alpha;
    const a0 = 1 + alpha;
    const a1 = -2 * cos_center;
    const a2 = 1 - alpha;

    // Normalize coefficients
    const normalizedB0 = b0 / a0;
    const normalizedB1 = b1 / a0;
    const normalizedB2 = b2 / a0;
    const normalizedA1 = a1 / a0;
    const normalizedA2 = a2 / a0;

    // Apply filter to each signal in the array
    return signals.map((data) => {
        // Initialize variables for filtered signal
        let y = new Array(data.length).fill(0);
        let x1 = 0,
            x2 = 0; // Input delays
        let y1 = 0,
            y2 = 0; // Output delays

        // Apply filter to each sample in the data
        for (let i = 0; i < data.length; i++) {
            // Apply the filter equation
            y[i] = normalizedB0 * data[i] + normalizedB1 * x1 + normalizedB2 * x2 -
                normalizedA1 * y1 - normalizedA2 * y2;

            // Shift input and output delays
            x2 = x1;
            x1 = data[i];
            y2 = y1;
            y1 = y[i];
        }

        return y; // Filtered signal for this data array
    });
}


function butterworthLowpassFilter(signals, sampleRate, cutoffFrequency) {
    // Calculate filter coefficients
    const omega = 2 * Math.PI * cutoffFrequency / sampleRate;
    const cos_omega = Math.cos(omega);
    const sin_omega = Math.sin(omega);
    const alpha = sin_omega / Math.sqrt(2);

    // Second-order Butterworth lowpass filter coefficients
    const b0 = (1 - cos_omega) / 2;
    const b1 = 1 - cos_omega;
    const b2 = (1 - cos_omega) / 2;
    const a0 = 1 + alpha;
    const a1 = -2 * cos_omega;
    const a2 = 1 - alpha;

    // Normalize coefficients
    const normalizedB0 = b0 / a0;
    const normalizedB1 = b1 / a0;
    const normalizedB2 = b2 / a0;
    const normalizedA1 = a1 / a0;
    const normalizedA2 = a2 / a0;

    // Apply filter to each signal in the array
    return signals.map((data) => {
        // Initialize variables for filtered signal
        let y = new Array(data.length).fill(0);
        let x1 = 0,
            x2 = 0; // Input delays
        let y1 = 0,
            y2 = 0; // Output delays

        // Apply filter to each sample in the data
        for (let i = 0; i < data.length; i++) {
            // Apply the filter equation
            y[i] = normalizedB0 * data[i] + normalizedB1 * x1 + normalizedB2 * x2 -
                normalizedA1 * y1 - normalizedA2 * y2;

            // Shift input and output delays
            x2 = x1;
            x1 = data[i];
            y2 = y1;
            y1 = y[i];
        }
        return y; // Filtered signal for this data array
    });
}

function butterworthHighpassFilter(signals, sampleRate, cutoffFrequency) {
    // Calculate filter coefficients
    const omega = 2 * Math.PI * cutoffFrequency / sampleRate;
    const cos_omega = Math.cos(omega);
    const sin_omega = Math.sin(omega);
    const alpha = sin_omega / Math.sqrt(2);

    // Second-order Butterworth highpass filter coefficients
    const b0 = (1 + cos_omega) / 2;
    const b1 = -(1 + cos_omega);
    const b2 = (1 + cos_omega) / 2;
    const a0 = 1 + alpha;
    const a1 = -2 * cos_omega;
    const a2 = 1 - alpha;

    // Normalize coefficients
    const normalizedB0 = b0 / a0;
    const normalizedB1 = b1 / a0;
    const normalizedB2 = b2 / a0;
    const normalizedA1 = a1 / a0;
    const normalizedA2 = a2 / a0;

    // Apply filter to each signal in the array
    return signals.map((data) => {
        // Initialize variables for filtered signal
        let y = new Array(data.length).fill(0);
        let x1 = 0,
            x2 = 0; // Input delays
        let y1 = 0,
            y2 = 0; // Output delays

        // Apply filter to each sample in the data
        for (let i = 0; i < data.length; i++) {
            // Apply the filter equation
            y[i] = normalizedB0 * data[i] + normalizedB1 * x1 + normalizedB2 * x2 -
                normalizedA1 * y1 - normalizedA2 * y2;

            // Shift input and output delays
            x2 = x1;
            x1 = data[i];
            y2 = y1;
            y1 = y[i];
        }

        return y; // Filtered signal for this data array
    });
}

function butterworthNotchFilter(signals, sampleRate, notchFrequency, bandwidth) {
    
    // Calculate filter coefficients
    const omega = 2 * Math.PI * notchFrequency / sampleRate;
    const sin_omega = Math.sin(omega);
    const cos_omega = Math.cos(omega);
    const alpha = sin_omega * Math.sinh(Math.log(2) / 2 * bandwidth * omega / sin_omega);

    // Second-order Butterworth notch filter coefficients
    const b0 = 1;
    const b1 = -2 * cos_omega;
    const b2 = 1;
    const a0 = 1 + alpha;
    const a1 = -2 * cos_omega;
    const a2 = 1 - alpha;

    // Normalize coefficients
    const normalizedB0 = b0 / a0;
    const normalizedB1 = b1 / a0;
    const normalizedB2 = b2 / a0;
    const normalizedA1 = a1 / a0;
    const normalizedA2 = a2 / a0;

    // Apply filter to each signal in the array
    return signals.map((data) => {
        // Initialize variables for filtered signal
        let y = new Array(data.length).fill(0);
        let x1 = 0,
            x2 = 0; // Input delays
        let y1 = 0,
            y2 = 0; // Output delays

        // Apply filter to each sample in the data
        for (let i = 0; i < data.length; i++) {
            // Apply the filter equation
            y[i] = normalizedB0 * data[i] + normalizedB1 * x1 + normalizedB2 * x2 -
                normalizedA1 * y1 - normalizedA2 * y2;

            // Shift input and output delays
            x2 = x1;
            x1 = data[i];
            y2 = y1;
            y1 = y[i];
        }
        return y; // Filtered signal for this data array
    });
}


function applyFilter(signals, low_f, high_f, notch_f, sampleRate) {
    if (notch_f !== 'off') {
        signals = butterworthNotchFilter(signals, sampleRate, notch_f, 1)
    }
    if (low_f !== 'off') {
        signals = butterworthHighpassFilter(signals, sampleRate, low_f);
    }
    if (high_f !== 'off') {
        signals = butterworthLowpassFilter(signals, sampleRate, high_f);
    }
    return signals
}

function applyGain(signals, gain) {
    return signals.map(row => row.map(value => value * gain));
}

// PSG
function plot_psg(seg, channels, Fs, nSamples) {
    // Plot time-series PSG using standard PSG montage (always bipolar/standard)

    // Channels are already in PSG montage format from backend - pass through as-is
    var [Y, reref_channels] = bipolarReRef(seg, channels);

    // Generate dynamic graph display parameters based on actual channels
    var ch_c2 = [""].concat(reref_channels.slice().reverse()).concat([""]);
    var baseLine = Array.from({length: ch_c2.length}, (_, i) => ch_c2.length - 2 - i);

    // Apply per-channel default bandpass filter
    Y = Y.map((signal, i) => {
        const chName = reref_channels[i];
        const filt = CHANNEL_FILTERS[chName];
        if (filt) {
            return butterworthBandpassFilter([signal], Fs, filt.low, filt.high)[0];
        }
        return signal;
    });

    // Apply notch filter (global, from dropdown)
    const notch_f = document.getElementById('notch_f').value;
    if (notch_f !== 'off') {
        Y = butterworthNotchFilter(Y, Fs, parseFloat(notch_f), 1);
    }

    // Apply per-channel gain and align for plot
    Y = Y.map((signal, i) => {
        const chName = reref_channels[i];
        const chGain = gain * (channelGains[chName] || 1.0);
        return signal.map(v => v * chGain);
    });
    Y = alignForPlot(Y, baseLine);
    
    // Prepare the time and EEG data arrays
    let mm = seg[0].length;
    const segOffset = buffer[readPointer].index * dur;
    let tt = Array.from({length: mm}, (_, i) => segOffset + (i * dur) / mm); // evenly spaced over dur
    const t_start    = tt[0];
    const t_end      = tt[tt.length - 1];
    const t_page_end = t_start + dur;

    // Create traces for each EEG channel
    let traces = [];
    for (let i = 0; i < Y.length; i++) {
        traces.push({
            x: tt,
            y: Y[i],
            mode: 'lines',
            line: {
                width: 1,
                color: 'black'
            },
            name: reref_channels[i],
            yaxis: 'y1'
        });
    }

    // Dummy invisible trace referencing xaxis2 so Plotly renders the top axis
    traces.push({
        x: [t_start, t_page_end],
        y: [null, null],
        xaxis: 'x2',
        yaxis: 'y',
        mode: 'lines',
        line: {width: 0},
        showlegend: false,
        hoverinfo: 'none'
    });

    // No longer using spike indicators
    
    // No longer adding spike indicator traces

    // Tick interval (seconds) based on page size
    const tickIntervalMap = {10: 0.5, 30: 1, 60: 2, 300: 10, 600: 30};
    const tickInterval = tickIntervalMap[dur] || 1;

    // Generate tick positions at regular intervals across the full page
    const tickVals = [];
    for (let k = 0; t_start + k * tickInterval <= t_page_end + 1e-9; k++) {
        tickVals.push(t_start + k * tickInterval);
    }

    // Bottom axis: absolute time at page start and page end
    const bottomTickVals  = [t_start, t_page_end];
    const bottomTickTexts = formatTimes([t_start, t_page_end], eeg_start);

    // Top axis: relative seconds at every tick (0, 1, 2, … or 0, 0.5, 1, …)
    const topTickTexts = tickVals.map((_, i) => {
        const relSec = i * tickInterval;
        return Number.isInteger(relSec) ? `${relSec}` : `${relSec.toFixed(1)}`;
    });

    // Vertical dotted lines at every tick position
    let verticalLines = tickVals.map(t => ({
        type: 'line',
        x0: t, x1: t,
        y0: 0, y1: ch_c2.length - 2,
        line: {color: 'gray', width: 1, dash: 'dot'}
    }));

    // Layout settings
    let layout = {
        height: 580,
        autosize: true,
        xaxis: {
            tickvals: bottomTickVals,
            ticktext: bottomTickTexts,
            showticklabels: true,
            showgrid: false,
            zeroline: false,
            ticks: 'outside',
            tickfont: {size: 10},
            domain: [0, 1],
            range: [t_start, t_page_end]
        },
        xaxis2: {
            tickvals: tickVals,
            ticktext: topTickTexts,
            overlaying: 'x',
            side: 'top',
            showticklabels: true,
            showgrid: false,
            zeroline: false,
            ticks: 'outside',
            tickfont: {size: 10},
            range: [t_start, t_page_end]
        },
        yaxis: {
            range: [0, ch_c2.length-1],
            showgrid: false,
            fixedrange: true,
            'zeroline': false,
            tickvals: Array.from({length: ch_c2.length}, (_, i) => i),
            ticktext: Array.from({length: ch_c2.length}, (_, i) => ch_c2[i]),
            domain: [0, 1]
        },
        shapes: verticalLines,
        showlegend: false,
        margin: {
            t: 40,
            l: 90,
            r: 50,
            b: 50
        }
    };

    config = {
        staticPlot: true,
        responsive: true
    }

    // Plot the EEG data using Plotly
    if (plotBuilt) {
        Plotly.react('myChart_eeg', traces, layout, config);
    } else {
        Plotly.newPlot('myChart_eeg', traces, layout, config);
    }
}

// Function to convert seconds to time stamps in HH:MM:SS format
function formatTimes(secondsArray, startTime = '2000-01-01 00:00:00') {
    const startDate = new Date(startTime); // Parse the start time as a Date object

    return secondsArray.map(seconds => {
        const currentDate = new Date(startDate.getTime() + seconds * 1000); // Add seconds
        const hours = String(currentDate.getHours()).padStart(2, '0');
        const minutes = String(currentDate.getMinutes()).padStart(2, '0');
        const secs = String(currentDate.getSeconds()).padStart(2, '0');
        return `${hours}:${minutes}:${secs}`;
    });
}


function expandOnes(arr, n) {
    let indices = new Set();  
    arr.forEach((val, i) => {
        if (val === 1) {
            for (let j = Math.max(0, i - n); j <= Math.min(arr.length - 1, i + n); j++) {
                indices.add(j);
            }
        }
    });
    indices.forEach(i => arr[i] = 1);  
    return arr;
}


// keyboard short-cut
document.onkeydown = function(event) {
    var key_event = event.code;
    switch (key_event) {
        case "ArrowUp":
            event.preventDefault();
            increase_gain();
            break;
        case "ArrowDown":
            event.preventDefault();
            decrease_gain();
            break;
        case "ArrowLeft":
            event.preventDefault();
            go_left();
            break;
        case "ArrowRight":
            event.preventDefault();
            go_right();
            break;

        default:
            break;
    }
}

/**
 * Resets all global variables to their initial state
 * This function should be called when we need to clear the viewer
 */
function resetGlobalVariables() {
    // Reset buffer and pointers
    buffer = [];
    readPointer = 0;
    writePointer = 0;
    
    // Reset EEG data variables
    seg = null;
    channels = null;
    Fs = null;
    num_samples = null;
    
    // Reset spectrogram data
    spectrogramFreqs = null;
    spectrogramTimes = null;
    region_spectra = null;
    region_names = null;
    
    // Reset navigation variables
    max_ind = 0;
    index = 0;
    
    // Reset any other state variables
    gainFactor = 1.0;
    
    // Clear the loading indicator
    document.getElementById('loading_Indicator').style.display = "none";
}

function setPageSize(newDur, clickedButton) {
    if (newDur !== dur) {
        // Capture current page start time before changing dur
        if (buffer[readPointer]) {
            pendingJumpTime = buffer[readPointer].index * dur;
        }

        // Update the global dur variable
        dur = newDur;
        
        // Update button styles
        const allButtons = document.querySelectorAll('.page-size-btn');
        allButtons.forEach(btn => {
            btn.className = 'page-size-btn inactive';
        });
        clickedButton.className = 'page-size-btn active';
        
        // Clear the current buffer and reset the viewer
        buffer = new Array(bufferLength).fill(null);
        requestedIndices = [];
        readPointer = 0;
        plotBuilt = false;
        
        // If a file is currently loaded, reinitialize with the new page size
        const currentFile = document.getElementById('currentFile').value;
        if (currentFile) {
            initialize();
        }
    }
}
