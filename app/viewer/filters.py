from scipy.signal import butter, iirnotch, filtfilt

def createFilter(Fs, low_f='off', high_f='off', notch_f='off', notch_quality=30):
    """
    Create highpass, lowpass, bandpass, and/or notch filter

    Parameters:
    - Fs: float
        Sampling frequency of the data in Hz.
    - high_f: float or 'off', optional
        Highpass filter cutoff frequency in Hz. If 'off', no highpass filter is applied.
    - low_f: float or 'off', optional
        Lowpass filter cutoff frequency in Hz. If 'off', no lowpass filter is applied.
    - notch_f: float or 'off', optional
        Frequency for the notch filter in Hz. If 'off', no notch filter is applied.
    - notch_quality: float, optional
        Quality factor for the notch filter. Default is 30 (higher is narrower).
    
    Returns:
    - filterParams: dictionary
        A dictionary containing computed filter coefficients
    """

    # Check for bandpass case (when both highpass and lowpass are specified)
    if high_f != 'off' and low_f != 'off':
        if float(high_f) < float(low_f):
            raise ValueError("Highpass frequency must be lower than the lowpass frequency for a bandpass filter.")
        passParams = butter(4, [float(low_f), float(high_f)], fs=Fs, btype='band')

    # Apply only lowpass filter if specified and no high
    elif high_f != 'off':
        passParams = butter(4, float(high_f), fs=Fs, btype='low')

    # Apply only highpass filter if specified and no lowpass
    elif low_f != 'off':
        passParams = butter(4, float(low_f), fs=Fs, btype='high')
        
    # If neither highpass or lowpass filters are specifed, don't
    # apply any filtering
    else:
        passParams = None

    # Apply notch filter if specified
    if notch_f == 'off':
        notchParams = None
    else:
        notchParams = iirnotch(float(notch_f), notch_quality, fs=Fs)

    return {"passParams":passParams,"notchParams":notchParams}

def applyFilter(x,passParams = None,notchParams = None):
    if passParams is not None:
        x = filtfilt(passParams[0], passParams[1], x)
    if notchParams is not None:
        x = filtfilt(notchParams[0], notchParams[1], x)
    return x
