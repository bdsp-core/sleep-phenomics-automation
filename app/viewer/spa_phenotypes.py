"""
Each public function has the same signature:
Input: sid, signals, fs, channels, sleep_stages, log, n_jobs, **kwargs
Output: feats, detects.
        feats is a dictionary that stores single value features. detects is a dictionary that stores non-single value detected events
"""
import sys, os, shutil, re, tempfile, datetime, subprocess
from itertools import groupby
import numpy as np
import pandas as pd
import mne
from pyedflib.highlevel import write_edf
from scipy.signal import filtfilt, find_peaks, detrend, resample_poly, savgol_filter, convolve
from scipy.interpolate import interp1d
import lunapi as lp, neurokit2 as nk
from hrvanalysis import (get_nn_intervals,
    get_time_domain_features, get_frequency_domain_features,
    get_poincare_plot_features)#, get_sampen)
from nitime.timeseries import TimeSeries
from nitime.analysis import MTCoherenceAnalyzer
from nitime.algorithms import mtm_cross_spectrum


_STAGE_MAP   = {5: 'W', 4: 'R', 3: 'N1', 2: 'N2', 1: 'N3'}
def _stage_to_txt(s):
    try:
        v = float(s)
        return _STAGE_MAP.get(int(v), 'W') if not np.isnan(v) else 'W'
    except Exception:
        return 'W'


def _caisr_result_to_pandas_events(df, event_col, mapping, fs):
    df['status'] = (df[event_col]!=df[event_col].shift(1)).cumsum()
    df = df.groupby(['status', event_col]).agg(
        Onset=('start_idx','min'),
        Stop=('end_idx','max')).reset_index()
    df = df[df[event_col]>0].reset_index(drop=True)
    df['Onset'] /= fs
    df['Stop'] /= fs
    df['Duration'] = df.Stop-df.Onset
    df['Description'] = df[event_col].apply(lambda x:mapping[x])
    return df[['Onset', 'Duration', 'Description']]


def _compute_sleep_macrostructures(ss, epoch_sec=30, prefix=''):
    """Compute standard sleep macrostructure metrics from a sleep-stage epoch array.

    ss : 1-D numpy array, values W=5, R=4, N1=3, N2=2, N3=1, NaN=unknown
    Returns a dict with prefixed keys.
    """
    valid = ~np.isnan(ss)
    if not valid.any():
        return {}

    first_valid = int(np.argmax(valid))
    last_valid  = int(len(ss) - 1 - np.argmax(valid[::-1]))
    ss_tib      = ss[first_valid : last_valid + 1]

    W_mask   = ss_tib == 5
    R_mask   = ss_tib == 4
    N1_mask  = ss_tib == 3
    N2_mask  = ss_tib == 2
    N3_mask  = ss_tib == 1
    slp_mask = R_mask | N1_mask | N2_mask | N3_mask

    TIB_min  = len(ss_tib) * epoch_sec / 60
    TST_min  = float(slp_mask.sum()) * epoch_sec / 60
    SE_pct   = (TST_min / TIB_min * 100) if TIB_min > 0 else np.nan
    W_min    = float(W_mask.sum())  * epoch_sec / 60
    N1_min   = float(N1_mask.sum()) * epoch_sec / 60
    N2_min   = float(N2_mask.sum()) * epoch_sec / 60
    N3_min   = float(N3_mask.sum()) * epoch_sec / 60
    REM_min  = float(R_mask.sum())  * epoch_sec / 60

    slp_idx  = np.where(slp_mask)[0]
    if len(slp_idx)>0:
        SOL_min  = (int(slp_idx[0]) * epoch_sec / 60) if len(slp_idx) > 0 else TIB_min
        WASO_min = (ss_tib[slp_idx[0]:slp_idx[-1]+1]==5).sum() * epoch_sec / 60 if len(slp_idx) > 0 else 0.0
        # SFI: Morrell, Mary J., et al. "Sleep fragmentation, awake blood pressure, and sleep-disordered breathing in a population-based study." American journal of respiratory and critical care medicine 162.6 (2000): 2091-2096.
        # Total number of awakenings/shifts to Stage 1 (from deeper NREM or REM sleep) divided by the total sleep time in hours
        sfi = ((np.in1d(ss_tib[:-1],[1,2,3,4])&(ss_tib[1:]==5)) | (np.in1d(ss_tib[:-1],[1,2,4])&(ss_tib[1:]==3))).sum() / (TST_min/60)
    else:
        SOL_min = np.nan
        WASO_min = np.nan
        sfi = np.nan

    rem_idx = np.where(ss_tib == 4)[0]
    if len(rem_idx) > 0:
        REMlat_min = (int(rem_idx[0]) - int(slp_idx[0])) * epoch_sec / 60
    else:
        REMlat_min = np.nan

    def _pct(v): return (v / TST_min * 100) if TST_min > 0 else np.nan

    return { # matched with CAISR report names
        prefix+'hours_psg':    TIB_min/60,
        prefix+'hours_sleep':    TST_min/60,
        prefix+'sleep_efficiency':     SE_pct,
        prefix+'sleep_latency':    SOL_min,
        prefix+'waso':   WASO_min,
        prefix+'r_latency': REMlat_min,
        prefix+'W_min':      W_min,
        prefix+'N1_min':     N1_min,
        prefix+'N2_min':     N2_min,
        prefix+'N3_min':     N3_min,
        prefix+'REM_min':    REM_min,
        prefix+'perc_n1':     _pct(N1_min),
        prefix+'perc_n2':     _pct(N2_min),
        prefix+'perc_n3':     _pct(N3_min),
        prefix+'perc_r':    _pct(REM_min),
        prefix+'sfi':    sfi,
    }


def _annot_classify_event(desc):
    """Map a raw annotation description string to a standardised event type."""
    d = str(desc).lower()
    has_apnea = 'apnea' in d or 'apnoea' in d
    if ('obs' in d) and has_apnea:          return 'obstructive apnea'
    if ('centr' in d) and has_apnea:        return 'central apnea'
    if ('mix' in d) and has_apnea:          return 'mixed apnea'
    if 'hypopnea' in d or 'hypopnoea' in d: return 'hypopnea'
    if 'rera' in d:                         return 'RERA'
    if 'pnea' in d:                         return 'hypopnea'   # unclassified pnea
    if 'arous' in d:                        return 'arousal'
    if 'periodic limb' in d or re.search(r'\bplm\b', d): return 'periodic limb movement'
    return None


def sleep_staging_from_annotation(sid=None, signals=None, fs=None, channels=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    annot_df           = kwargs['annot']
    signal_len_seconds = kwargs['signal_len_seconds']

    stage_map  = {'W': 5, 'R': 4, 'N1': 3, 'N2': 2, 'N3': 1}
    stage_rows = annot_df[annot_df['Description'].isin(stage_map)].copy()
    event_rows = annot_df[~annot_df['Description'].isin(stage_map)].copy()

    # ── Sleep stages ──────────────────────────────────────────────────────────
    ss = np.zeros(int(signal_len_seconds) // 30, dtype=float) + np.nan
    for row in stage_rows.itertuples(index=False):
        start = int(row.Onset / 30)
        stop  = min(int((row.Onset + row.Duration) / 30), len(ss))
        ss[start:stop] = stage_map[row.Description]

    prefix = 'MACRO_ANNOT_'
    feats   = _compute_sleep_macrostructures(ss, prefix=prefix)
    detects = {'sleep_stages_from_annotation': ss}

    if event_rows.empty:
        return feats, detects

    # ── Classify events ───────────────────────────────────────────────────────
    event_rows = event_rows.copy()
    event_rows['Description'] = event_rows['Description'].apply(_annot_classify_event)
    event_rows = event_rows[event_rows['Description'].notna()].reset_index(drop=True)

    if event_rows.empty:
        return feats, detects

    ah_mask  = event_rows['Description'].isin({'obstructive apnea','central apnea','mixed apnea','hypopnea'})
    rera_mask= event_rows['Description'] == 'RERA'
    ar_mask  = event_rows['Description'] == 'arousal'
    lm_mask  = event_rows['Description'] == 'periodic limb movement'

    if ah_mask.any() or rera_mask.any():
        detects['apnea_hypopnea_from_annotation'] = event_rows[ah_mask | rera_mask]
    if ar_mask.any():
        detects['arousal_from_annotation'] = event_rows[ar_mask]
    if lm_mask.any():
        detects['limb_movement_from_annotation'] = event_rows[lm_mask]

    # ── Compute indices ───────────────────────────────────────────────────────
    tst_h    = feats.get(f'{prefix}hours_sleep', 0.0)
    epoch_sec = 30
    nrem_h   = sum(feats.get(f'{prefix}{s}', 0.0) for s in ['N1_min','N2_min','N3_min']) / 60
    rem_h    = feats.get(f'{prefix}REM_min', 0.0) / 60

    # Assign stage to each event via epoch lookup
    def _stage_at(onset):
        ep = int(onset / epoch_sec)
        return ss[ep] if 0 <= ep < len(ss) else np.nan

    ev = event_rows.copy()
    ev['stage'] = ev['Onset'].apply(_stage_at)

    n_ah     = int(ah_mask.sum())
    n_rera   = int(rera_mask.sum())
    n_ar     = int(ar_mask.sum())
    n_lm     = int(lm_mask.sum())
    n_obs    = int((ev['Description'] == 'obstructive apnea').sum())
    n_cen    = int((ev['Description'] == 'central apnea').sum())
    n_mix    = int((ev['Description'] == 'mixed apnea').sum())
    n_hyp    = int((ev['Description'] == 'hypopnea').sum())

    nrem_stages = {1, 2, 3}
    ah_ev    = ev[ah_mask]
    n_ah_nrem = int(ah_ev['stage'].isin(nrem_stages).sum())
    n_ah_rem  = int((ah_ev['stage'] == 4).sum())

    def _index(count, hours):
        return float(count / hours) if hours > 0 else float('nan')

    ahi = _index(n_ah, tst_h)
    feats.update({
        f'{prefix}ahi':          ahi,
        f'{prefix}rdi':          _index(n_ah + n_rera,  tst_h),
        f'{prefix}oai':          _index(n_obs,          tst_h),
        f'{prefix}cai':          _index(n_cen,          tst_h),
        f'{prefix}mai':          _index(n_mix,          tst_h),
        f'{prefix}hyi':          _index(n_hyp,          tst_h),
        f'{prefix}rerai':        _index(n_rera,         tst_h),
        f'{prefix}arousal_index':_index(n_ar,           tst_h),
        f'{prefix}plmi':         _index(n_lm,           tst_h),
        f'{prefix}ahi_nrem':     _index(n_ah_nrem,      nrem_h),
        f'{prefix}ahi_rem':      _index(n_ah_rem,       rem_h),
    })

    log(f"TST = {tst_h:.1f} hour, AHI={ahi:.1f}/hour")
    return feats, detects


def sleep_staging_CAISR(sid=None, signals=None, fs=None, channels=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """
    output is a dictionary:
    sleep_stage: pandas.DataFrame, start_second, duration, description
    arousal: same as above
    apnea_hypopnea: same as above, including RERA
    limb_movement: same as above
    and macrostructure features
    """

    try:
        # run CAISR
        folder = kwargs['folder']  # per-job temp dir created by prepare_EDF_for_CAISR
        _caisr_app = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'ml_models', 'CAISR-App'))
        sys.path.insert(0, _caisr_app)
        from caisr import main as caisr_entry
        # tasks can be ['preprocess', 'stage', 'arousal', 'resp', 'limb', 'report']
        tasks = ['preprocess']
        if 'eeg' in signals:
            tasks.append('stage')
            tasks.append('arousal')
        if 'rip' in signals:
            tasks.append('resp')
        if 'limb_emg' in signals:
            tasks.append('limb')
        tasks.append('report')
        caisr_entry(folder, tasks)

        # get CAISR summary numbers
        path_rep = os.path.normpath(os.path.join(folder, 'reports/caisr_sleep_metrics_all_studies.csv'))
        df_rep = pd.read_csv(path_rep)
        #log(df_rep)
        #log(df_rep.study_id)
        #log(df_rep.study_id.dtype)

        # bug: when sid is all numerical, study_id is int and sid is str, no match
        #df_rep = df_rep[df_rep.study_id==sid].iloc[0,1:]
        df_rep = df_rep.iloc[0,1:] # fix: should always have one subject as always, just take the first line
        feats = {'MACRO_CAISR_'+k:v for k,v in df_rep.to_dict().items()}

        # get CAISR detects
        fs_eeg = fs['eeg']
        detects = {}
        path_res = os.path.normpath(os.path.join(folder, f'caisr_annotations/caisr_{sid}.csv'))
        df_res = pd.read_csv(path_res)
        if 'stage' in df_res.columns:
            detects['sleep_stages_CAISR'] = _caisr_result_to_pandas_events(df_res.copy(), 'stage', {9:'UNK', 5:'W', 4:'R', 3:'N1', 2:'N2', 1:'N3'}, fs_eeg)
        # Read float probabilities from the raw stage CSV — the report task inside Docker
        # renames prob_* → stage_prob_* then rounds them to integers (a Docker-side bug),
        # so the combined caisr_annotations CSV cannot be used for this.
        path_stage = os.path.normpath(os.path.join(folder, f'intermediate/stage/{sid}_stage.csv'))
        if os.path.exists(path_stage):
            df_stage = pd.read_csv(path_stage)
            if 'prob_n3' in df_stage.columns:
                df_ssp = df_stage.copy()
                df_ssp['Onset'] = df_ssp['start_idx'] / fs_eeg
                df_ssp['Duration'] = (df_ssp['end_idx'] - df_ssp['start_idx']) / fs_eeg
                detects['sleep_stages_prob_CAISR'] = df_ssp[['Onset', 'Duration', 'prob_w', 'prob_n1', 'prob_n2', 'prob_n3', 'prob_r']]
        if 'arousal' in df_res.columns:
            detects['arousal_CAISR'] = _caisr_result_to_pandas_events(df_res.copy(), 'arousal', {1:'arousal'}, fs_eeg)
        if 'resp' in df_res.columns:
            detects['apnea_hypopnea_CAISR'] = _caisr_result_to_pandas_events(df_res.copy(), 'resp', {1:'obstructive apnea', 2:'central apnea', 3:'mixed apnea', 4:'hypopnea', 5:'RERA'}, fs_eeg)
        if 'limb' in df_res.columns:
            df_res.loc[df_res.limb_plm==1, 'limb'] = 2
            detects['limb_movement_CAISR'] = _caisr_result_to_pandas_events(df_res.copy(), 'limb', {1:'isolated limb movement', 2:'periodic limb movement'}, fs_eeg)

    except Exception as ee:
        raise

    finally:
        # folder is a per-job temp dir — delete it entirely
        shutil.rmtree(folder, ignore_errors=True)

    # convert event-table to 30-second epoch array
    signal_len_seconds = kwargs['signal_len_seconds']
    ss = np.zeros(int(signal_len_seconds) // 30, dtype=float) + np.nan
    df_ss = detects['sleep_stages_CAISR']
    mapping = {'W': 5, 'R': 4, 'N1': 3, 'N2': 2, 'N3': 1}
    for ii in range(len(df_ss)):
        start = int(df_ss.Onset.iloc[ii] / 30)
        stop  = int((df_ss.Onset.iloc[ii] + df_ss.Duration.iloc[ii]) / 30)
        ss[start:stop] = mapping.get(df_ss.Description.iloc[ii], np.nan)
    detects['sleep_stages_CAISR'] = ss
    feats |= _compute_sleep_macrostructures(ss, prefix='MACRO_CAISR_')
    
    log(f"TST = {feats['MACRO_CAISR_hours_sleep']:.1f} hour, AHI={feats['MACRO_CAISR_ahi']:.1f}/hour")
    return feats, detects


#TODO
def sleep_staging_USleep(sid=None, signals=None, fs=None, channels=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    log(f"Total sleep time is {feats['MACRO_CAISR_hours_sleep']:.1f} hours from U-Sleep.")
    return {}, {}


def band_power(sid=None, signals=None, fs=None, channels=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute band power using multitaper PSD.
    Returns a dict with keys:
    BP_abs_<band>_<channel>_<stage>  (decibel)
    BP_rel_<band>_<channel>_<stage>  (%)
    """
    from mne.time_frequency import psd_array_multitaper

    if 'eeg' not in signals or 'eeg' not in channels or 'eeg' not in fs:
        return {}, {}
    eeg = signals['eeg']
    channels = channels['eeg']
    fs = fs['eeg']

    epoch_len = 30  # seconds
    freq_bands = {
        'slow_oscillation': (0.3, 1),
        'delta': (1, 4),
        'theta': (4, 8),
        'alpha': (8, 12),
        'sigma': (11, 16),
        'beta': (12, 30), }
    sleep_stage_names = {
        'W':5, 'R':4,
        'N1':3, 'N2':2, 'N3':1, }

    epoch_samples = int(epoch_len * fs)
    start_ids = np.arange(0, eeg.shape[-1]-epoch_samples+1, epoch_samples)
    n_epochs = len(start_ids)
    if n_epochs == 0:
        log("Warning: recording is too short for 30 s epochs.")
        return {}, {}
    assert len(sleep_stages)==n_epochs

    epochs = np.array([eeg[...,x:x+epoch_samples] for x in start_ids])
    psd, freq = psd_array_multitaper(
        epochs, fs, fmin=0.3, fmax=35,
        bandwidth=0.5, adaptive=False, low_bias=True,
        normalization='full', remove_dc=True,
        output='power', n_jobs=n_jobs, verbose=False)
    psd_db = 10*np.log10(psd)
    psd_db[np.isinf(psd_db)] = np.nan
    total_power = np.trapz(psd, freq, axis=-1)  # (n_epochs, n_ch)
    detects = {'psd':psd, 'psd_freq':freq, 'psd_db':psd_db, 'total_power':total_power,#TODO eeg_psd
               'fs':fs, 'start_ids':start_ids, 'eeg_channels':channels }

    feats = {}
    for ci, ch in enumerate(channels):
        for bandn, bf in freq_bands.items():
            for sname, snum in sleep_stage_names.items():
                fmask = (freq>=bf[0]) & (freq<bf[1])
                psd_ = psd[sleep_stages==snum][:,ci][..., fmask]
                bp = np.trapz(psd_, freq[fmask], axis=-1)  # (n_epochs,)
                rel_bp  = bp / total_power[sleep_stages==snum][:,ci]
                feats[f'BP_abs_{bandn}_{ch}_{sname}'] = 10*np.log10(np.nanmean(bp))
                feats[f'BP_rel_{bandn}_{ch}_{sname}'] = np.nanmean(rel_bp)*100.

    return feats, detects
    

def spindle_slow_oscillation(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Detect sleep spindles and slow oscillations from EEG.
    """
    luna_cmd_path = '/home/haoqisun/luna-base-1.2.3/luna'
    #macos_arm64_luna-v1.5.1'
    #macos_luna-v1.5.1
    #windows-luna-v1.5.1

    q = kwargs.get('q')
    if q is None:
        log("spindle & SO: quality index not provided — skipping.")
        return {}, {}

    eeg = signals.get('eeg')
    ch_eeg = channels.get('eeg')
    fs_eeg = fs.get('eeg')
    if eeg is None or ch_eeg is None or fs_eeg is None:
        log("spindle & SO: no EEG found in EDF — skipping.")
        return {}, {}
    ch_eeg2 = [x.replace(' ', '_').replace('-', '_') for x in ch_eeg]
    ch_luna2origin = {x2:x1 for x2,x1 in zip(ch_eeg2, ch_eeg)}
    ch_eeg = ch_eeg2

    # save edf for Luna
    work_dir = kwargs.get('work_dir') or ''
    luna_edf_path = os.path.join(work_dir, f'luna_edf_{sid}_spindle.edf')
    sig_hdrs = [{
        'label': ch_eeg[x],
        'dimension': 'uV',
        'sample_frequency': fs_eeg,
        'physical_min': eeg[x].min(),
        'physical_max': eeg[x].max(),
        'digital_min': -32768,
        'digital_max': 32767,
        'transducer': '',
        'prefilter': ''
    } for x in range(len(ch_eeg))]
    write_edf(luna_edf_path, list(eeg), sig_hdrs, file_type=0)

    stages_txt = [_stage_to_txt(s) for s in sleep_stages]
    fd, annot_path = tempfile.mkstemp(suffix='.eannot')
    with os.fdopen(fd, 'w') as fh:
        fh.write('\n'.join(stages_txt))

    proj = lp.proj()
    proj.silence()
    sid = str(sid)
    
    # first detect m-spindles, then save as .annot
    fd, annot_path_msp = tempfile.mkstemp(suffix='.annot')
    df_msps = []
    for ch in ch_eeg:
        p = proj.inst( sid )
        p.attach_edf(luna_edf_path)
        p.attach_annot(annot_path)
        cmd = [f'SIGNALS keep={ch}',
            'EPOCH',
            f'MASK ifnot=N2,N3',
            #f'MASK mask-if=edf_annot[artifact_{ch}]',
            'RE',
            f'SPINDLES sig={ch} th=3.5 fc-lower=11 fc-upper=15 fc-step=0.5 cycles=7 collate-within-channel per-spindle q={q}' ]
        p.eval(' & '.join([x.split('%')[0] for x in cmd]))
        
        df_msp = p.table('SPINDLES', 'CH_MSPINDLE')
        #print(ch, df_msp)
        if df_msp is None or len(df_msp)==0:
            df_msps.append(pd.DataFrame(columns=['ID', 'CH', 'MSPINDLE', 'MSP_DUR', 'MSP_F', 'MSP_FL', 'MSP_FU', 'MSP_SIZE', 'MSP_START', 'MSP_STAT', 'MSP_STOP']))
            continue
        df_msp['channel'] = ch
        #df_msp = df_msp.sort_values('MSP_START')
        df_msps.append(df_msp[['channel','MSP_START','MSP_STOP','MSP_F']])
        p.refresh()
        p.clear_vars()
        proj.clear_vars()
        proj.clear_ivars()
        proj.clear()
        
    df_msp = pd.concat(df_msps, axis=0, ignore_index=True)
    df_msp['class'] = 'sp_all'
    df_msp['MSP_START'] = df_msp.MSP_START.astype(float)
    df_msp['MSP_STOP'] = df_msp.MSP_STOP.astype(float)
    df_msp2 = df_msp.copy()
    df_msp2.loc[df_msp2.MSP_F<13, 'class'] = 'sp_slow'
    df_msp2.loc[df_msp2.MSP_F>=13, 'class'] = 'sp_fast'
    df_msp = pd.concat([df_msp, df_msp2], axis=0)
    df_msp['instance'] = '.'
    df_msp['meta'] = '.'
    df_msp[['class', 'instance', 'channel', 'MSP_START', 'MSP_STOP', 'meta']].to_csv(annot_path_msp, float_format='%.4f', index=False, header=None, sep='\t')
    
    # then compute features
    df_sp_events = []
    df_sp = []
    df_so = []
    for ch in ch_eeg:
        #p = proj.inst( sid )
        #p.attach_edf(luna_edf_path)
        #p.attach_annot(annot_path_msp)
        db_path = luna_edf_path[:-4]+f'_{ch}.db'
        cmd = [f'SIGNALS keep={ch}',
            'EPOCH',
            'RE',
            'TAG mysp/slow',
            f'SPINDLES precomputed=sp_slow per-spindle if so mag=3 verbose-coupling tl={ch} q={q}',
            'TAG mysp/fast',
            f'SPINDLES precomputed=sp_fast per-spindle if so mag=3 verbose-coupling tl={ch} q={q}',
            'TAG mysp/all',
            f'SPINDLES precomputed=sp_all per-spindle if so mag=3 verbose-coupling tl={ch} q={q}',
            ]
        # somehow p.var('annot-file', annot_path_msp) doesn't work
        #p.eval(' & '.join([x.split('%')[0] for x in cmd]))
        subprocess.run([luna_cmd_path, luna_edf_path, 'annot-file='+annot_path_msp, '-o', db_path,
            '-s', ' & '.join([x.split('%')[0] for x in cmd])])
        proj.import_db(db_path)
        
        df_sp_event_ = proj.table('SPINDLES', 'CH_F_SPINDLE_mysp')
        if df_sp_event_ is not None:
            df_sp_events.append( df_sp_event_[np.in1d(df_sp_event_.mysp,['slow','fast'])].drop(columns=['F','ID','SPINDLE']).rename(columns={'mysp':'TYPE'}) )
        df_sp_ = proj.table('SPINDLES', 'CH_F_mysp')
        if df_sp_ is not None:
            df_sp.append( df_sp_.drop(columns=['ID','F']).rename(columns={'mysp':'TYPE'}) )
        df_so_ = proj.table('SPINDLES', 'CH_mysp')
        if df_so_ is not None:
            df_so.append( df_so_.iloc[[0]].drop(columns=['ID','mysp']) )
        #p.refresh()
        #p.clear_vars()
        proj.clear_vars()
        proj.clear_ivars()
        proj.clear()
        if os.path.exists(db_path): os.remove(db_path)
        
    feats = {}
    detects = {}
    if len(df_sp_events)>0:
        detects['spindle_detection'] = pd.concat(df_sp_events, axis=0, ignore_index=True)
    if len(df_sp)>0:
        df_sp = pd.concat(df_sp, axis=0, ignore_index=True)
        for ii in range(len(df_sp)):
            for jj in range(df_sp.shape[1]):
                if df_sp.columns[jj] in ['CH','TYPE']: continue
                k = f'SP_{df_sp.columns[jj]}_{df_sp.CH.iloc[ii]}_{df_sp.TYPE.iloc[ii]}'
                feats[k] = df_sp.iloc[ii,jj]
    if len(df_so)>0:
        df_so = pd.concat(df_so, axis=0, ignore_index=True)
        for ii in range(len(df_so)):
            for jj in range(df_so.shape[1]):
                if df_so.columns[jj] in ['CH']: continue
                k = f'{df_so.columns[jj]}_{df_so.CH.iloc[ii]}'
                feats[k] = df_so.iloc[ii,jj]

    # remove unnecessary features:
    # for x in sorted(set([x.replace('_F3_M2','').replace('_F4_M1','').replace('_C3_M2','').replace('_C4_M1','').replace('_O1_M2','').replace('_O2_M1','').replace('_slow','').replace('_fast','').replace('_all','') for x in feats.keys()])):print(x)
    """
SO	number of SO detected
SO_AMP_NEG	negative peak amplitude
SO_AMP_POS	positive peak amplitude
SO_AMP_P2P	peak-to-peak amplitude
SO_DUR	SO duration
SO_DUR_NEG	negative peak duration
SO_DUR_POS	positive peak duration
SO_RATE	SO per minute
SO_SLOPE	slope from negative peak to negative-to-positive zero-crossing)
SP_DENS	spindle density
SP_CDENS	SO-coupled spindle density
SP_UDENS	SO-uncoupled spindle density
SP_AMP	spindle amplitude
SP_CHIRP	spindle chirp
SP_COUPL_ANGLE	Circular mean of SO phase at spindle peak
SP_COUPL_MAG	Magnitude of coupling (ITPC metric)
SP_COUPL_PV	Asymptotic p-value for the ITPC statistic
SP_COUPL_OVERLAP	Number of spindles overlapping a detected SO
SP_DISPERSION	Mean dispersion index of epoch spindle count
SP_DISPERSION_P	P-value for test of over-dispersion
SP_DUR	mean spindle duration
SP_FRQ	mean spindle frequency (from counting zero-crossings)
SP_FVAR	spindle frequency variance
SP_ISA_S	Mean integrated spindle activity (ISA) per spindle
SP_Q
SP_R_PHASE_IF	circular correlation between SO phase and instataneous spindle frequency
SP_SYMM	Mean spindle symmetry metric
    """
    delete = ['SO_TH_NEG', 'SO_TH_P2P',
'SO_TRANS', 'SO_TRANS_FREQ',
'SP_ACT_MN', 'SP_ACT_MX',
'SP_COUPL_ALL_ANGLE', 'SP_COUPL_ALL_MAG', 'SP_COUPL_ALL_PV', 'SP_COUPL_ANCHOR',
'SP_CWT_TH',
'SP_FFT', 'SP_FRNG', 'SP_FRNG2', 'SP_FRQ1', 'SP_FRQ2', 'SP_FVAR2', 'SP_FWHM',
'SP_ISA_M', 'SP_ISA_T',
'SP_MINS', 'SP_N', 'SP_N01', 'SP_N02', 'SP_NE', 'SP_NOSC',
'SP_P01', 'SP_P02',
'SP_SEC_AMP', 'SP_SEC_P2P', 'SP_SEC_TROUGH',
'SP_SYMM2', 'SP_SYMM_AMP', 'SP_SYMM_TROUGH',]
    feats = {k:v for k,v in feats.items() if not any([k.startswith(x+'_') for x in delete])}

    if annot_path and os.path.exists(annot_path):
        os.remove(annot_path)
    if annot_path_msp and os.path.exists(annot_path_msp):
        os.remove(annot_path_msp)
    if os.path.exists(luna_edf_path):
        os.remove(luna_edf_path)
    dens = np.nanmean([feats[f'SP_DENS_{ch}_all'] for ch in ch_eeg])
    log(f"Average spindle density across all channels is {dens:.2f}/minute.")
    return feats, detects


# ---------------------------------------------------------------------------
# Brain age — private helpers
# ---------------------------------------------------------------------------

_BA_MODEL_DIR   = os.path.join(os.path.dirname(__file__), 'brain-age-model-luna')
_BA_LUNA_SCRIPT_ECG = os.path.join(_BA_MODEL_DIR, 'm1-adult-age-luna-ecg.txt')
_BA_LUNA_SCRIPT_NO_ECG = os.path.join(_BA_MODEL_DIR, 'm1-adult-age-luna-no-ecg.txt')


def _ba_run_luna(edf_path, luna_cmd_path, stages_txt, ch_eeg, ch_ecg, age, notch_freq):#, ecg_flip):
    annot_path = None
    try:
        fd, annot_path = tempfile.mkstemp(suffix='.eannot')
        with os.fdopen(fd, 'w') as fh:
            fh.write('\n'.join(stages_txt))

        ch_eeg_str   = ','.join(ch_eeg)
        if notch_freq is None: notch_freq=60
        proj = lp.proj()
        proj.silence()
        p = proj.inst('x')
        p.attach_edf(edf_path)
        p.attach_annot(annot_path)

        #cmds = []
        #if ecg_flip:
        #    cmds.append(f'FLIP sig={ch_ecg}')

        p.vars({
            'age':        age,
            'cen':        ch_eeg_str,
            'ecg':        ch_ecg,
            'th':         4,
            'notch_freq': notch_freq,
            'mpath':      _BA_MODEL_DIR,
        })

        cmd_text = lp.cmdfile(luna_cmd_path)
        #cmds.extend(cmd_text.split('&'))
        p.eval(cmd_text)#' & '.join(cmds))

        res_bl      = p.table('PREDICT', 'BL')
        brain_age_v = float(res_bl.Y1.iloc[0])

        res_ftr    = p.table('PREDICT', 'FTR')
        feat_names = res_ftr['FTR'].tolist()
        feat_vals  = [float(v) for v in res_ftr['X'].tolist()]

        p.clear_vars()
        proj.clear_vars()
        proj.clear_ivars()
        proj.clear()

        return brain_age_v, feat_names, feat_vals

    except Exception:
        return None
    finally:
        if annot_path and os.path.exists(annot_path):
            os.remove(annot_path)


def brain_age(sid=None, signals=None, fs=None, channels=None, sleep_stages=None,
              log=print, n_jobs=1, **kwargs):
    """Estimate brain age from central EEG using the Luna Sun2019 Bayesian ridge model.

    Requires lunapi and neurokit2. Returns empty results gracefully if unavailable
    or if the recording lacks sufficient NREM epochs.
    """
    if sleep_stages is None or len(sleep_stages) == 0:
        log("brain_age: no sleep stages available — skipping.")
        return {}, {}

    actual_age = kwargs.get('actual_age')
    if actual_age is None:
        log("brain_age: actual_age not provided — skipping.")
        return {}, {}

    eeg = signals.get('eeg')
    ch_eeg = channels.get('eeg')
    fs_eeg = fs.get('eeg')
    if eeg is None or ch_eeg is None or fs_eeg is None or ('C3-M2' not in ch_eeg and 'C4-M1' not in ch_eeg):
        log("brain_age: no central EEG (C3/C4) found in EDF — skipping.")
        return {}, {}
    ch_eeg_ids = [xi for xi,x in enumerate(ch_eeg) if x in ['C3-M2', 'C4-M1']]
    ch_eeg = [ch_eeg[x] for x in ch_eeg_ids]
    eeg = eeg[ch_eeg_ids]
    ch_eeg = [x.replace(' ', '_').replace('-', '_') for x in ch_eeg]

    ecg = signals.get('ecg')
    ch_ecg = channels.get('ecg')
    fs_ecg = fs.get('ecg')
    if type(ch_ecg)==list and len(ch_ecg)>0:
        ch_ecg = [ch_ecg[0]]
        ecg = ecg[[0]]
        luna_cmd_path = _BA_LUNA_SCRIPT_ECG
    else:
        ch_ecg = []
        ecg = []
        luna_cmd_path = _BA_LUNA_SCRIPT_NO_ECG
    ch_ecg = [x.replace(' ', '_').replace('-', '_') for x in ch_ecg]

    if len(ch_ecg)>0:
        if _ecg_flip(ecg[0], fs_ecg):
            ecg = -ecg

    # save edf for Luna
    work_dir = kwargs.get('work_dir') or ''
    luna_edf_path = os.path.join(work_dir, f'luna_edf_{sid}_brain_age.edf')
    sigs = list(eeg)+list(ecg)
    fss = [fs_eeg]*len(ch_eeg)+[fs_ecg]*len(ch_ecg)
    chs = ch_eeg+ch_ecg
    sig_hdrs = [{
        'label': chs[x],
        'dimension': 'uV',
        'sample_frequency': fss[x],
        'physical_min': sigs[x].min(),
        'physical_max': sigs[x].max(),
        'digital_min': -32768,
        'digital_max': 32767,
        'transducer': '',
        'prefilter': ''
    } for x in range(len(chs))]
    write_edf(luna_edf_path, sigs, sig_hdrs, file_type=0)

    stages_txt = [_stage_to_txt(s) for s in sleep_stages]

    if len(ch_ecg)>0: ch_ecg = ch_ecg[0]
    notch_freq = kwargs.get('notch_freq')
    result = _ba_run_luna(luna_edf_path, luna_cmd_path, stages_txt, ch_eeg, ch_ecg,
                          actual_age, notch_freq)#, ecg_flip)
    if result is None:
        log("brain_age: Luna pipeline failed — skipping.")
        return {}, {}

    brain_age_v, feat_names, feat_vals = result
    feats = {
        'brain_age':       brain_age_v,
        'brain_age_index': brain_age_v - actual_age,
    }
    #for name, val in zip(feat_names, feat_vals):
    #    feats[f'brain_age_feat_{name}'] = val
    if os.path.exists(luna_edf_path): os.remove(luna_edf_path)
    log(f"Brain age is {brain_age_v:.2f} years.")
    return feats, {}


def arousal_burden(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute arousal burden (fraction of sleep time with arousals, arousal index, etc.).
    """
    #log(f"Arousal burden is {}%.")
    return {}, {}


def _ecg_flip(ecg_signal, fs):
    try:
        ecg = ecg_signal.astype(np.float64).flatten()
        if np.std(ecg) < 1e-2:
            ecg *= 1e6
        mid = len(ecg) // 2
        win = int(fs * 3600)
        segment = ecg[max(0, mid - win): min(len(ecg), mid + win)]
        if len(segment) < int(fs * 30):
            return False
        _, to_invert = nk.ecg_invert(segment, sampling_rate=int(fs))
        return bool(to_invert)
    except Exception:
        return False


def hrv(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute heart-rate variability: time-domain, frequency-domain, Poincaré, and sample entropy.

    Uses neurokit2 for ECG cleaning, polarity detection, and R-peak detection.
    Uses hrvanalysis for all HRV feature extraction.
    """
    ecg = signals.get('ecg')
    fs_ecg = fs.get('ecg')
    if ecg is None or fs_ecg is None:
        log("hrv: no ECG signal — skipping.")
        return {}, {}

    ecg = (ecg[0] if ecg.ndim > 1 else ecg).astype(float).copy()

    # Flip polarity if needed, then clean
    if _ecg_flip(ecg, fs_ecg):
        ecg = -ecg
    notch_freq = kwargs.get('notch_freq')
    ecg_clean = nk.ecg_clean(ecg, sampling_rate=int(fs_ecg), method='neurokit',
                              powerline=notch_freq)

    # Detect R-peaks
    try:
        _, rpeaks_info = nk.ecg_peaks(ecg_clean, sampling_rate=int(fs_ecg))
        rpeaks = rpeaks_info['ECG_R_Peaks']
    except Exception as e:
        log(f"hrv: R-peak detection failed — {e}")
        return {}, {}

    hr = len(rpeaks) / (len(ecg) / fs_ecg / 60)
    if hr<30 or hr>120:
        log(f"cardiopulmonary_coupling: invalid heart rate: {hr}")
        return {}, {}

    # NN intervals (ms), with ectopic beat removal via hrvanalysis
    rri_ms_raw = (np.diff(rpeaks) / fs_ecg * 1000).tolist()
    nn_intervals = [x for x in get_nn_intervals(rri_ms_raw, verbose=False)
                    if x is not None and not np.isnan(x)]
    if len(nn_intervals) < 50:
        log(f"hrv: too few valid NN intervals ({len(nn_intervals)}) — skipping.")
        return {}, {}

    feats = {}
    try:
        feats.update({'HRV_' + k: v for k, v in get_time_domain_features(nn_intervals).items()})
        feats.update({'HRV_' + k: v for k, v in get_frequency_domain_features(nn_intervals).items()})
        feats.update({'HRV_' + k: v for k, v in get_poincare_plot_features(nn_intervals).items()})
        #too slow: feats.update({'HRV_' + k: v for k, v in get_sampen(nn_intervals).items()})
    except Exception as e:
        log(f"hrv: feature extraction failed — {e}")

    sdnn = feats.get('HRV_sdnn', float('nan'))
    log(f"hrv: SDNN={sdnn:.1f} ms ({len(nn_intervals)} NN intervals used).")
    return feats, {}


def cardiopulmonary_coupling(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute cardiopulmonary coupling (CPC) sleep quality index.

    Uses neurokit2 for R-peak detection and ECG-derived respiration (EDR),
    and nitime MTCoherenceAnalyzer for cross-spectrum computation.
    Follows the algorithm of Thomas et al. (2005).
    """
    ecg = signals.get('ecg')
    fs_ecg = fs.get('ecg')
    if ecg is None or fs_ecg is None:
        log("cardiopulmonary_coupling: no ECG signal — skipping.")
        return {}, {}

    ecg = (ecg[0] if ecg.ndim > 1 else ecg).astype(float).copy()

    # Flip ECG polarity if needed
    if _ecg_flip(ecg, fs_ecg):
        ecg = -ecg
    notch_freq = kwargs.get('notch_freq')
    ecg = nk.ecg_clean(ecg, sampling_rate=fs_ecg, method='neurokit', powerline=notch_freq)

    try:
        df_rpeaks, info = nk.ecg_peaks(ecg, sampling_rate=fs_ecg)
        rpeaks = info['ECG_R_Peaks']
    except Exception as e:
        log(f"cardiopulmonary_coupling: R-peak detection failed — {e}")
        return {}, {}
    hr = len(rpeaks)/(len(ecg)/fs_ecg/60)
    if hr<30 or hr>120:
        log(f"cardiopulmonary_coupling: invalid heart rate: {hr}")
        return {}, {}

    # Compute NN-filtered RRI and interpolate to uniform sample grid
    try:
        rri_raw = np.diff(rpeaks)
        rri_nn = np.array(get_nn_intervals(rri_raw / fs_ecg * 1000, verbose=False), dtype=float) / 1000 * fs_ecg
        rri_ii = np.arange(int(rpeaks[0]), int(rpeaks[-2]) + 1)
        rri_uniform = interp1d(rpeaks[:-1], rri_nn)(rri_ii)
    except Exception as e:
        log(f"cardiopulmonary_coupling: RRI computation failed — {e}")
        return {}, {}

    # Compute EDR using neurokit2 (at full ECG sampling rate for alignment)
    try:
        ecg_rate = nk.ecg_rate(df_rpeaks, sampling_rate=fs_ecg, desired_length=len(ecg))
        edr_full = nk.ecg_rsp(ecg_rate, sampling_rate=fs_ecg)
    except Exception as e:
        log(f"cardiopulmonary_coupling: EDR computation failed — {e}")
        return {}, {}

    # Align EDR to the RRI sample grid
    start_idx = int(rpeaks[0])
    edr_aligned = edr_full[start_idx: start_idx + len(rri_uniform)]
    if len(edr_aligned) < len(rri_uniform):
        n = len(edr_aligned)
        rri_uniform = rri_uniform[:n]
        rri_ii = rri_ii[:n]
    else:
        edr_aligned = edr_aligned[:len(rri_uniform)]
    tt = rri_ii / fs_ecg

    # Resample both to 2 Hz
    newFs = 2.0
    rri_2hz = mne.filter.resample(rri_uniform, up=newFs / fs_ecg, down=1.0)
    edr_2hz = mne.filter.resample(edr_aligned, up=newFs / fs_ecg, down=1.0)
    tt_2hz = float(tt[0]) + np.arange(len(rri_2hz)) / newFs

    # Segment into 512-sample windows, step 256
    window_size = 512
    step_size   = 256
    start_ids = np.arange(0, len(rri_2hz) - window_size + 1, step_size)
    if len(start_ids) < 3:
        log("cardiopulmonary_coupling: signal too short for CPC — skipping.")
        return {}, {}

    tt_segs_mid = tt_2hz[start_ids]
    rri_segs = np.array([rri_2hz[s: s + window_size] for s in start_ids])
    edr_segs = np.array([edr_2hz[s: s + window_size] for s in start_ids])

    # Detrend each segment
    rri_segs = np.apply_along_axis(detrend, 1, rri_segs)
    edr_segs = np.apply_along_axis(detrend, 1, edr_segs)

    # Compute MTCoherenceAnalyzer per segment
    N = (window_size + 2) // 2
    cpc_list = []; freqs = None
    coh_list = []; csd_list = []
    for si in range(len(rri_segs)):
        rri_ = rri_segs[si]; edr_ = edr_segs[si]
        if np.isnan(rri_).any() or np.isnan(edr_).any():
            cpc_list.append(np.full(N, np.nan))
            coh_list.append(np.full(N, np.nan))
            csd_list.append(np.full(N, np.nan))
        else:
            res = MTCoherenceAnalyzer(input=TimeSeries(np.array([rri_, edr_]), sampling_rate=newFs))
            csd_ = np.abs(mtm_cross_spectrum(res.spectra[0], res.spectra[1],
                                              (res.weights[0], res.weights[1]),
                                              sides='onesided')) ** 2
            coh_ = res.coherence[0, 1]
            cpc_list.append(coh_ * csd_)
            coh_list.append(coh_)
            csd_list.append(csd_)
            if freqs is None:
                freqs = res.frequencies

    if freqs is None:
        log("cardiopulmonary_coupling: all windows were NaN — skipping.")
        return {}, {}

    cpc_arr = np.array(cpc_list)

    # Average over 3-window groups (matching reference)
    if len(cpc_arr) >= 3:
        cpc_arr     = np.array([np.nanmean(cpc_arr[si-1:si+2], axis=0) for si in range(1, len(cpc_arr) - 1)])
        tt_segs_mid = tt_segs_mid[1:-1]

    # Restrict to [0, 0.4 Hz]
    freq_mask = freqs <= 0.4
    freqs   = freqs[freq_mask]
    cpc_arr = cpc_arr[:, freq_mask]

    # Band powers
    vlf_mask = (freqs >= 0)    & (freqs < 0.01)
    lf_mask  = (freqs >= 0.01) & (freqs < 0.1)
    hf_mask  = (freqs >= 0.1)  & (freqs <= 0.4)

    vlfc = np.nansum(cpc_arr[:, vlf_mask], axis=1)
    lfc  = np.nansum(cpc_arr[:, lf_mask],  axis=1)
    hfc  = np.nansum(cpc_arr[:, hf_mask],  axis=1)

    feats = {
        'CPC_log_LF_power':     float(np.log(np.nanmean(lfc))),
        'CPC_log_HF_power':     float(np.log(np.nanmean(hfc))),
        'CPC_log_VLF_power':    float(np.log(np.nanmean(vlfc))),
        'CPC_LF_HF_ratio':  float(np.nanmean(lfc  / (hfc + 1e-12))),
        'CPC_VLF_LH_ratio': float(np.nanmean(vlfc / (lfc + hfc + 1e-12))),
    }

    """
    # Stage-stratified values
    if sleep_stages is not None and len(sleep_stages) > 0:
        epoch_sec = 30
        epoch_ids = np.clip(np.floor(tt_segs_mid / epoch_sec).astype(int), 0, len(sleep_stages) - 1)
        ss_at = np.array(sleep_stages)[epoch_ids]
        for stage_val, stage_name in [(4, 'REM'), (5, 'Wake'), (3, 'N1'), (2, 'N2'), (1, 'N3')]:
            mask = ss_at == stage_val
            if mask.any():
                lf_s  = np.nansum(cpc_arr[mask][:, lf_mask],  axis=1)
                hf_s  = np.nansum(cpc_arr[mask][:, hf_mask],  axis=1)
                vlf_s = np.nansum(cpc_arr[mask][:, vlf_mask], axis=1)
                feats[f'CPC_{stage_name}_LF_HF_ratio']  = float(np.nanmean(lf_s  / (hf_s + 1e-12)))
                feats[f'CPC_{stage_name}_VLF_LH_ratio'] = float(np.nanmean(vlf_s / (lf_s + hf_s + 1e-12)))
    """

    detects = {
        'cpc_t': tt_segs_mid,
        'cpc_freq': freqs,
        'cpc': cpc_arr,
    }
    return feats, detects


def ahi(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute apnea-hypopnea index (AHI) from respiratory signals.
    """
    #log(f"AHI is {}/hour.")
    return {}, {}



# FIR low-pass filter for SpO2 smoothing (from Chen et al.)
_HB_B = [
    0.000109398212241, 0.000514594526374, 0.001350397179936, 0.002341700062534,
    0.002485940327008, 0.000207543145171, -0.005659450344228, -0.014258087808069,
    -0.021415481383353, -0.019969417749860, -0.002425120103463, 0.034794452821365,
    0.087695691366900, 0.144171828095816, 0.187717212244959, 0.204101948813338,
    0.187717212244959, 0.144171828095816, 0.087695691366900, 0.034794452821365,
    -0.002425120103463, -0.019969417749860, -0.021415481383353, -0.014258087808069,
    -0.005659450344228, 0.000207543145171, 0.002485940327008, 0.002341700062534,
    0.001350397179936, 0.000514594526374, 0.000109398212241,
]
_HB_BAD_SPO2 = 60


def _hb_filter_spo2(arr, sfreq):
    """Resample to 1 Hz, replace bad values, apply FIR filter, round to 0.5 resolution."""
    arr = arr.copy().astype(float)
    good = arr[arr >= _HB_BAD_SPO2]
    arr[arr < _HB_BAD_SPO2] = good.mean() if len(good) else 95.0
    if sfreq != 1:
        arr = nk.signal_resample(arr, sampling_rate=sfreq, desired_sampling_rate=1)
    arr = filtfilt(_HB_B, 1, arr, axis=0, padtype='odd')
    arr = np.round(arr * 2) / 2
    return arr


def _hb_detect_desaturation(spo2, duration_min=5, duration_max=120):
    """Detect oxygen desaturation events from a 1-Hz SpO2 signal.
    Returns DataFrame with columns Start, Duration, Desat.
    Adapted from Chen et al. ODI.py.
    """
    spo2_max = spo2[0]
    spo2_max_index = 0
    spo2_min = 100.0
    des_onset_pred_set = np.array([], dtype=int)
    des_duration_pred_set = np.array([], dtype=int)
    des_level_set = np.array([])
    des_onset_pred_point = 0
    des_flag = 0
    ma_flag = 0
    prob_end = []

    for i, current_value in enumerate(spo2):
        des_percent = spo2_max - current_value

        if ma_flag and des_percent < 50:
            if des_flag and len(prob_end):
                des_onset_pred_set = np.append(des_onset_pred_set, des_onset_pred_point)
                des_duration_pred_set = np.append(des_duration_pred_set, prob_end[-1] - des_onset_pred_point)
                des_level_set = np.append(des_level_set, spo2_max - spo2_min)
            spo2_max = current_value; spo2_max_index = i
            ma_flag = 0; des_flag = 0; spo2_min = 100.0; prob_end = []
            continue

        if des_percent >= 2:
            if des_percent > 50:
                ma_flag = 1
            else:
                des_onset_pred_point = spo2_max_index
                des_flag = 1
                if current_value < spo2_min:
                    spo2_min = current_value

        if current_value >= spo2_max and not des_flag:
            spo2_max = current_value; spo2_max_index = i
        elif des_flag:
            if current_value > spo2_min:
                if current_value > spo2[i - 1]:
                    prob_end.append(i)
                if i >= 2 and current_value <= spo2[i - 1] < spo2[i - 2]:
                    dur = prob_end[-1] - spo2_max_index if prob_end else 0
                    if dur < duration_min:
                        spo2_max = spo2[i - 2]; spo2_max_index = i - 2
                        spo2_min = 100.0; des_flag = 0; prob_end = []
                    elif dur <= duration_max:
                        des_onset_pred_set = np.append(des_onset_pred_set, des_onset_pred_point)
                        des_duration_pred_set = np.append(des_duration_pred_set, dur)
                        des_level_set = np.append(des_level_set, spo2_max - spo2_min)
                        spo2_max = spo2[i - 2]; spo2_max_index = i - 2
                        spo2_min = 100.0; des_flag = 0; prob_end = []
                    else:
                        des_onset_pred_set = np.append(des_onset_pred_set, des_onset_pred_point)
                        des_duration_pred_set = np.append(des_duration_pred_set, prob_end[0] - des_onset_pred_point)
                        des_level_set = np.append(des_level_set, spo2_max - spo2_min)
                        remain = spo2[prob_end[0]:i + 1]
                        _o, _d, _l = _hb_detect_desaturation(remain, duration_min, duration_max)
                        des_onset_pred_set = np.append(des_onset_pred_set, _o + prob_end[0])
                        des_duration_pred_set = np.append(des_duration_pred_set, _d)
                        des_level_set = np.append(des_level_set, _l)
                        spo2_max = spo2[i - 2]; spo2_max_index = i - 2
                        spo2_min = 100.0; des_flag = 0; prob_end = []

    return des_onset_pred_set, des_duration_pred_set, des_level_set


def hypoxic_burden(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute hypoxic burden (HB) from SpO2.
    Features: HB_desat, HB_NREM_desat, HB_REM_desat (%·min/h).
    """
    spo2 = signals.get('spo2')
    fs_spo2 = fs.get('spo2')
    if spo2 is None or fs_spo2 is None:
        log("hypoxic_burden: no SpO2 signal found — skipping.")
        return {}, {}
    if sleep_stages is None or len(sleep_stages) == 0:
        log("hypoxic_burden: no sleep stages — skipping.")
        return {}, {}

    spo2 = spo2.flatten().astype(float)

    # Resample, filter, round
    spo2_1hz = _hb_filter_spo2(spo2, fs_spo2)

    # Detect desaturation events on rounded integer signal
    onsets, durations, _ = _hb_detect_desaturation(np.round(spo2_1hz))
    if len(onsets) < 2:
        log("hypoxic_burden: fewer than 2 desaturation events — skipping.")
        return {}, {}

    event_times = onsets + durations / 2.0   # midpoint of each event

    # Compute per-event HB
    time_span = 120
    all_curves = []
    good_ids = []
    for ei, et in enumerate(event_times):
        s, e = int(et - time_span), int(et + time_span)
        if s < 0 or e > len(spo2_1hz):
            continue
        window = spo2_1hz[s:e]
        if len(window) < 2 * time_span or np.mean(window < _HB_BAD_SPO2) > 0.3:
            continue
        all_curves.append(_hb_filter_spo2(window, 1))
        good_ids.append(ei)

    if len(all_curves) < 2:
        log("hypoxic_burden: not enough valid events for HB computation — skipping.")
        return {}, {}

    all_curves = np.array(all_curves)
    avg = filtfilt(_HB_B, 1, all_curves.mean(axis=0), axis=0, padtype='odd')
    peaks, _ = find_peaks(avg)
    before = peaks[peaks < time_span]
    after  = peaks[peaks > time_span]
    if len(before) == 0 or len(after) == 0:
        log("hypoxic_burden: cannot locate baseline peaks — skipping.")
        return {}, {}
    start_sec = before[-1]
    end_sec   = after[0]

    burdens = [
        float(np.sum(np.max(c[time_span - 100:time_span]) - c[start_sec:end_sec]) / 60)
        for c in all_curves ]

    df_res = pd.DataFrame({'EventTime': event_times, 'HB': np.nan})
    df_res.loc[good_ids, 'HB'] = burdens

    # Assign epoch stage to each event (our mapping: 1=N3,2=N2,3=N1,4=REM,5=W)
    epoch_ids = (df_res.EventTime // 30).astype(int).clip(0, len(sleep_stages) - 1)
    df_res['Stage'] = sleep_stages[epoch_ids.values]
    detects = {'desat_events':df_res}

    sleep_mask = np.in1d(sleep_stages, [1, 2, 3, 4])
    sleep_ids  = np.where(sleep_mask)[0]
    if len(sleep_ids) == 0:
        log("hypoxic_burden: no sleep epochs found — skipping.")
        return {}, {}

    sleep_start  = sleep_ids[0]  * 30
    sleep_end    = (sleep_ids[-1] + 1) * 30
    tst_h  = sleep_mask.sum() * 30 / 3600
    nrem_h = np.in1d(sleep_stages, [1, 2, 3]).sum() * 30 / 3600
    rem_h  = np.in1d(sleep_stages, [4]).sum() * 30 / 3600

    feats = {'HB_desat': float('nan'), 'HB_NREM_desat': float('nan'), 'HB_REM_desat': float('nan')}
    in_sleep = df_res[(df_res.EventTime >= sleep_start) & (df_res.EventTime < sleep_end)]
    if in_sleep.HB.notna().sum() > 0 and tst_h > 0:
        feats['HB_desat'] = float(in_sleep.HB.sum() / tst_h)
    nrem_mask = np.in1d(df_res.Stage, [1, 2, 3])
    if nrem_mask.sum() > 0 and nrem_h > 0:
        feats['HB_NREM_desat'] = float(df_res.HB[nrem_mask].sum() / nrem_h)
    rem_mask = np.in1d(df_res.Stage, [4])
    if rem_mask.sum() > 0 and rem_h > 0:
        feats['HB_REM_desat'] = float(df_res.HB[rem_mask].sum() / rem_h)

    log(f"Hypoxic burden: {feats.get('HB_desat', float('nan')):.2f} %min/h.")
    return feats, detects


_SS_FS        = 10     # analysis sampling rate
_SS_THRESHOLD = 0.80   # convolution score threshold


def _ss_find_events(signal):
    signal = np.asarray(signal, dtype=int)
    padded = np.concatenate(([0], signal, [0]))
    diff   = np.diff(padded)
    starts = np.where(diff ==  1)[0]
    ends   = np.where(diff == -1)[0]
    return list(zip(starts.tolist(), ends.tolist()))


def _ss_remove_short_events(arr, min_len):
    arr = arr.copy()
    for st, end in _ss_find_events(arr > 0):
        if end - st < min_len:
            arr[st:end] = 0
    return arr


def _ss_clip_normalize(signal):
    clipped = np.clip(signal, np.nanpercentile(signal, 5), np.nanpercentile(signal, 95))
    mean = np.nanmean(clipped); std = np.nanstd(clipped)
    if std < 1e-10: std = 1.0
    norm = (signal - mean) / std
    thresh = 10 * np.mean([np.abs(np.nanquantile(norm, 0.2)),
                            np.abs(np.nanquantile(norm, 0.8))])
    return np.clip(norm, -thresh, thresh)


def _ss_compute_envelopes(data, fs):
    signal = data['Ventilation_combined'].values
    pos_peaks, _ = find_peaks( signal, distance=int(fs*1.5), width=int(0.4*fs), rel_height=1)
    neg_peaks, _ = find_peaks(-signal, distance=int(fs*1.5), width=int(0.4*fs), rel_height=1)
    data['Ventilation_pos_envelope'] = np.nan
    data['Ventilation_neg_envelope'] = np.nan
    if len(pos_peaks) > 1:
        data.iloc[pos_peaks, data.columns.get_loc('Ventilation_pos_envelope')] = signal[pos_peaks]
    if len(neg_peaks) > 1:
        data.iloc[neg_peaks, data.columns.get_loc('Ventilation_neg_envelope')] = signal[neg_peaks]
    data['Ventilation_pos_envelope'] = data['Ventilation_pos_envelope'].interpolate(method='cubic', limit_area='inside')
    data['Ventilation_neg_envelope'] = data['Ventilation_neg_envelope'].interpolate(method='cubic', limit_area='inside')
    win = int(5 * fs)
    if win > 1:
        data['Ventilation_pos_envelope'] = data['Ventilation_pos_envelope'].rolling(win, center=True).median()
        data['Ventilation_neg_envelope'] = data['Ventilation_neg_envelope'].rolling(win, center=True).median()
    check = data['Ventilation_pos_envelope'] < data['Ventilation_neg_envelope']
    data.loc[check, 'Ventilation_pos_envelope'] = 0
    data.loc[check, 'Ventilation_neg_envelope'] = 0
    win_b = int(30 * fs)
    pos = data['Ventilation_pos_envelope'].rolling(win_b, center=True).mean()
    neg = data['Ventilation_neg_envelope'].rolling(win_b, center=True).mean()
    base1 = data['Ventilation_combined'].rolling(win_b, center=True).median().rolling(win_b, center=True).mean()
    base2 = ((pos + neg) / 2).rolling(win_b, center=True).mean()
    base_corr = (2 * base1 + base2) / 3
    data['Ventilation_baseline']         = base_corr.rolling(win_b, center=True).mean()
    data['Ventilation_default_baseline'] = base1
    return data


def _ss_assess_ventilation(data, fs, drop_hyp=0.40, drop_apnea=0.85):
    win   = int(60 * fs * 2)
    shift = int(60 * fs * 2)
    pos_exc = data['Ventilation_pos_envelope'].rolling(win).quantile(0.25).values.copy()
    neg_exc = data['Ventilation_neg_envelope'].rolling(win).quantile(0.75).values.copy()
    pos_exc[:-shift] = pos_exc[shift:]; neg_exc[:-shift] = neg_exc[shift:]
    baseline         = data['Ventilation_baseline'].values
    default_baseline = data['Ventilation_default_baseline'].values
    pos_dist = np.abs(pos_exc - baseline);         neg_dist = np.abs(neg_exc - baseline)
    data['pos_excursion_hyp'] = baseline + pos_dist * (1 - drop_hyp)
    data['neg_excursion_hyp'] = baseline - neg_dist * (1 - drop_hyp)
    pos_dist_a = np.abs(pos_exc - default_baseline); neg_dist_a = np.abs(neg_exc - default_baseline)
    avg_dist = np.mean([pos_dist_a, neg_dist_a], axis=0)
    data['pos_excursion_apnea'] = default_baseline + avg_dist * (1 - drop_apnea)
    data['neg_excursion_apnea'] = default_baseline - avg_dist * (1 - drop_apnea)
    sig = data['Ventilation_combined'].values
    apnea_drop = (sig < data['pos_excursion_apnea'].values) & (sig > data['neg_excursion_apnea'].values)
    hyp_drop   = ((sig < data['pos_excursion_hyp'].values) | (sig > data['neg_excursion_hyp'].values)) & ~apnea_drop
    data['Ventilation_drop_apnea']    = apnea_drop.astype(int)
    data['Ventilation_drop_hypopnea'] = hyp_drop.astype(int)
    return data


def _ss_combine_flow_reductions(data, fs):
    win_a = int(10 * fs); win_h = int(10 * fs)
    apnea_f = (pd.Series(data['Ventilation_drop_apnea'].values.astype(float))
               .rolling(win_a, center=True).mean().values > 0.75).astype(int)
    apnea_f = _ss_remove_short_events(apnea_f, int(4 * fs))
    hyp_f   = (pd.Series(data['Ventilation_drop_hypopnea'].values.astype(float))
               .rolling(win_h, center=True).mean().values > 0.5).astype(int)
    hyp_f   = _ss_remove_short_events(hyp_f, int(4 * fs))
    for st, end in _ss_find_events(apnea_f > 0):
        if end - st > 120 * fs: apnea_f[st:end] = 0
    for st, end in _ss_find_events(hyp_f > 0):
        if end - st > 150 * fs: hyp_f[st:end] = 0
    flow = np.zeros(len(data), dtype=float)
    flow[hyp_f > 0] = 2; flow[apnea_f > 0] = 1
    data['flow_reductions'] = flow
    return data


def _ss_tag_potential_spots(data, fs):
    data['potential_self_sim'] = 0
    labels     = (data['flow_reductions'].values > 0).astype(int)
    epoch_size = int(180 * fs); step = int(5 * fs)
    for start in np.arange(0, len(labels) - epoch_size + 1, step):
        if len(_ss_find_events(labels[start:start + epoch_size])) >= 3:
            data.iloc[start:start + epoch_size, data.columns.get_loc('potential_self_sim')] = 1
    return data


def _ss_compute_smooth_envelope(data, region):
    for new_col, src_col in [('Smooth_pos_envelope', 'Ventilation_pos_envelope'),
                               ('Smooth_neg_envelope', 'Ventilation_neg_envelope')]:
        sig = data.loc[region, src_col].copy().astype(float)
        if sig.isna().mean() < 0.10:
            sig = sig.interpolate(limit_direction='both')
        else:
            sig = sig.fillna(sig.median())
        n = len(sig)
        wl = min(51, n - 1 if (n - 1) % 2 == 1 else n - 2)
        if wl >= 5:
            data.loc[region, new_col] = savgol_filter(sig.values, wl, 1)
        else:
            data.loc[region, new_col] = sig.values
    return data


def _ss_find_cycle_spots(data, regions):
    if len(regions[0]) < 2 or len(regions[1]) < 2:
        return None
    cycle = [regions[0][len(regions[0])//2], regions[1][len(regions[1])//2]]
    if cycle[1] <= cycle[0]:
        return None
    local_range = list(range(cycle[0], cycle[1]))
    if len(local_range) < 2:
        return None
    local = data.loc[local_range]
    pos_v = local['Smooth_pos_envelope'].values; neg_v = local['Smooth_neg_envelope'].values
    if len(pos_v) > 0 and not np.all(np.isnan(pos_v)):
        top = int(np.nanargmax(pos_v)) + local.index[0]
        bot = int(np.nanargmin(neg_v)) + local.index[0]
        cycle.append(int(np.mean([top, bot])))
    else:
        cycle.append((cycle[0] + cycle[1]) // 2)
    return cycle


def _ss_convolve_envelope(data, cycle, fs):
    if cycle[1] <= cycle[0]: return 0.0
    region  = list(range(cycle[0], cycle[1]))
    if len(region) < 4: return 0.0
    baseline = data.loc[region, 'Ventilation_baseline'].values
    pos = data.loc[region, 'Smooth_pos_envelope'].values - baseline
    neg = baseline - data.loc[region, 'Smooth_neg_envelope'].values
    if np.all(np.isnan(pos)) or np.all(np.isnan(neg)): return 0.0
    ps = np.nanstd(pos); ns = np.nanstd(neg)
    if ps < 1e-6 or ns < 1e-6: return 0.0
    pos = (pos - np.nanmean(pos)) / (ps + 1e-6); pos[np.isnan(pos)] = 0
    neg = (neg - np.nanmean(neg)) / (ns + 1e-6); neg[np.isnan(neg)] = 0
    return float(np.nanmax(convolve(pos, neg, mode='same')) / len(pos))


def _ss_do_self_sim_tests(data, cycle, conv_score, fs):
    if not (10 < (cycle[1]-cycle[0])/fs < 120): return data
    sig = data.loc[list(range(cycle[0], cycle[1])), 'Ventilation_combined'].values
    if 'pos_excursion_hyp' in data.columns:
        if not np.any(sig > np.nanmean(data['pos_excursion_hyp'].values)): return data
    span = cycle[1] - cycle[0]
    if span > 0:
        p_t = (1 - abs((cycle[2]-cycle[0]) - (cycle[1]-cycle[2])) / span) * 100
    else:
        p_t = 0
    if p_t <= 50 or conv_score * 100 <= 50: return data
    if 0 <= cycle[2] < len(data):
        data.iloc[cycle[2], data.columns.get_loc('TAGGED')] = 1
    return data


def _ss_assess_potential_spots(data, fs):
    data['Smooth_pos_envelope'] = 0.0
    data['Smooth_neg_envelope'] = 0.0
    data['TAGGED'] = 0
    for ss_st, ss_end in _ss_find_events(data['potential_self_sim'].values > 0):
        region     = list(range(ss_st, ss_end))
        flow_lims  = _ss_find_events(data.loc[region, 'flow_reductions'].values > 0)
        for i in range(len(flow_lims) - 1):
            st         = ss_st + flow_lims[i][0];   end        = ss_st + flow_lims[i][1]
            next_start = ss_st + flow_lims[i+1][0]; next_end   = ss_st + flow_lims[i+1][1]
            r1 = list(range(st, end)); r2 = list(range(next_start, next_end))
            r_full = list(range(int(np.median([st, end])), int(np.median([next_start, next_end]))))
            if len(r_full) < 10 or len(r1) < 2 or len(r2) < 2: continue
            try:
                data = _ss_compute_smooth_envelope(data, r_full)
            except Exception:
                continue
            cycle = _ss_find_cycle_spots(data, [r1, r2])
            if cycle is None: continue
            conv  = _ss_convolve_envelope(data, cycle, fs)
            data  = _ss_do_self_sim_tests(data, cycle, conv, fs)
    return data


def _ss_window_correction(arr, window_size):
    half = window_size // 2; result = arr.copy()
    for st, end in _ss_find_events(arr > 0):
        result[max(0, st-half):min(len(result), end+half)] = arr[st]
    return result


def _ss_assess_three_oscillations(data, tags, fs):
    win = int(20 * fs); envelopes = []
    for t in range(3):
        loc   = tags[t][0]
        start = max(0, loc - win); end = min(len(data), loc + win)
        envelopes.append(data.iloc[start:end]['Smooth_pos_envelope'].values)
    if any(len(e) < 10 for e in envelopes): return 0.0
    scores = []
    for osc, ref in [(envelopes[1], envelopes[0]), (envelopes[1], envelopes[2])]:
        n = min(len(osc), len(ref)); osc = osc[:n]; ref = ref[:n]
        if n < 4: scores.append(0.0); continue
        os_ = np.std(osc); rs_ = np.std(ref)
        if os_ < 1e-6 or rs_ < 1e-6: scores.append(0.0); continue
        f = (osc - np.mean(osc)) / (os_ + 1e-6)
        s = (ref - np.mean(ref)) / (rs_ + 1e-6)
        scores.append(float(np.nanmax(convolve(f, s, mode='same')) / len(f)))
    return max(scores) if scores else 0.0


def _ss_post_process(data, fs, threshold):
    data['self similarity'] = 0; data['consecutive complexes'] = 0
    tagged = data['TAGGED'].values.astype(float)
    window = int(180 * fs)
    rolling_sum = pd.Series(tagged).rolling(window, center=True).sum()
    data.loc[rolling_sum >= 3, 'consecutive complexes'] = 2
    data['consecutive complexes'] = _ss_window_correction(
        data['consecutive complexes'].values, window_size=window)
    for st, end in _ss_find_events(data['consecutive complexes'].values > 0):
        region    = list(range(st, end))
        complexes = [(s + st, e + st) for s, e in
                     _ss_find_events(data.loc[region, 'TAGGED'].values > 0)]
        for t in range(len(complexes) - 2):
            tags = complexes[t:t+3]
            if _ss_assess_three_oscillations(data, tags, fs) >= threshold:
                data.iloc[tags[0][0]:tags[2][1],
                          data.columns.get_loc('self similarity')] = 1
    return data


def _ss_count_central_events(data):
    n_ap = 0; n_hy = 0
    ss_regions = data.get('self similarity', pd.Series(np.zeros(len(data))))
    for st, end in _ss_find_events(data['flow_reductions'].values > 0):
        if np.any(ss_regions.values[st:end] > 0):
            val = data['flow_reductions'].values[st]
            if val == 1: n_ap += 1
            elif val == 2: n_hy += 1
    return n_ap, n_hy


# ---------------------------------------------------------------------------

def self_similarity(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Detect self-similar (Cheyne-Stokes / periodic) breathing from respiratory effort.

    Ported from self_similarity.py. Uses signals['rip'] (abdominal/chest effort).
    """
    rip = signals.get('rip')
    ch_rip = channels.get('rip', [])
    fs_rip = fs.get('rip')
    if rip is None or fs_rip is None:
        log("self_similarity: no respiratory effort signal (rip) — skipping.")
        return {}, {}

    if 'ABD' in ch_rip:
        trace = (rip[ch_rip.index('ABD')] if rip.ndim > 1 else rip).astype(np.float64).copy()
    elif 'CHEST' in ch_rip:
        trace = (rip[ch_rip.index('CHEST')] if rip.ndim > 1 else rip).astype(np.float64).copy()
    else:
        log("self_similarity: no respiratory effort signal (rip) — skipping.")
        return {}, {}

    if len(trace) < fs_rip * 3600:
        log("self_similarity: signal too short (< 1 hour) — skipping.")
        return {}, {}

    # Filter: notch + bandpass 0–10 Hz
    notch_freq = kwargs.get('notch_freq')
    if notch_freq and notch_freq < fs_rip / 2:
        trace = mne.filter.notch_filter(trace, fs_rip, notch_freq, verbose=False)
    trace = detrend(trace)
    trace = mne.filter.filter_data(trace, fs_rip, None, 10, verbose=False)

    # Resample to _SS_FS (10 Hz)
    if int(fs_rip) != _SS_FS:
        trace = resample_poly(trace, _SS_FS, int(fs_rip))

    trace = _ss_clip_normalize(trace)

    data = pd.DataFrame({'Ventilation_combined': trace})
    data = _ss_compute_envelopes(data, _SS_FS)
    data = _ss_assess_ventilation(data, _SS_FS)
    data = _ss_combine_flow_reductions(data, _SS_FS)
    data = _ss_tag_potential_spots(data, _SS_FS)
    data = _ss_assess_potential_spots(data, _SS_FS)
    data = _ss_post_process(data, _SS_FS, _SS_THRESHOLD)
    n_central_apneas, n_central_hypopneas = _ss_count_central_events(data)
    duration_hours = len(trace) / _SS_FS / 3600
    ssr = data.get('self similarity', pd.Series(np.zeros(len(data)))).values

    feats = {
        'SS_self_sim_perc':         (ssr==1).mean()*100.,
        'SS_central_apneas':        n_central_apneas,
        'SS_central_hypopneas':     n_central_hypopneas,
        'SS_central_apnea_index':   n_central_apneas   / duration_hours if duration_hours > 0 else float('nan'),
        'SS_central_hypopnea_index':n_central_hypopneas / duration_hours if duration_hours > 0 else float('nan'),
    }

    detects = {
        'SS_ventilation': trace,
        'SS_flow_reductions': data['flow_reductions'].values,
        'SS_self_sim_regions': ssr,
        }
    log(f"self_similarity: self-similarity percent is {feats['SS_self_sim_perc']:.1f}%.")
    return feats, detects


def plmi(sid=None, signals=None, channels=None, fs=None, sleep_stages=None, log=print, n_jobs=1, **kwargs):
    """Compute periodic limb movement index (PLMI) from leg EMG.
    """
    #log(f"PLMI is {}/hour.")
    return {}, {}
