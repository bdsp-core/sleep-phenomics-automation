import os, timeit
import tempfile
import numpy as np
import pandas as pd
import mne
import pyedflib
try:
    from .spa_phenotypes import *
except ImportError:
    from spa_phenotypes import *


FEATURE_RUNNING_TIMES = {
    'from_annotation':          '1 second',
    'sleep_staging_CAISR':      '10 minutes',
    'sleep_staging_USleep':     '5 minutes',
    'band_power':               '10 seconds',
    'spindle_slow_oscillation': '15 minutes',
    'brain_age':                '2 minutes',
    'arousal_burden':           '1 second',
    'hrv':                      '1 minute',
    'cardiopulmonary_coupling': '1 minute',
    'ahi':                      '1 second',
    'hypoxic_burden':           '10 seconds',
    'self_similarity':          '2 minutes',
    'plmi':                     '1 second',
}


ALL_FEATURE_LABELS = {
    'from_annotation':          ('Sleep stages from annotation file', sleep_staging_from_annotation),
    'sleep_staging_CAISR':      ('Complete AI Sleep Report (CAISR, Nasiri et al.) for sleep stages, arousals, apneas, and limb movements', sleep_staging_CAISR),
    'sleep_staging_USleep':      ('U-Sleep for high-frequency sleep staging (Perslev et al.)', sleep_staging_USleep),
    'band_power':               ('EEG band powers by bands, sleep stages, and channels', band_power),
    'spindle_slow_oscillation': ('Sleep spindle and slow oscillation detection', spindle_slow_oscillation),
    'brain_age':                ('EEG brain age estimation', brain_age),
    #'eeg_connectivity':         ('EEG inter-channel connectivity', eeg_connectivity),
    #'infraslow_oscillation':    ('Infraslow EEG oscillations (<0.1 Hz)', infraslow_oscillation),
    'arousal_burden':           ('Arousal burden', arousal_burden),
    'hrv':                      ('Heart-rate variability (HRV)', hrv),
    'cardiopulmonary_coupling': ('Cardiopulmonary coupling', cardiopulmonary_coupling),
    'ahi':                      ('Apnea-hypopnea index (AHI)', ahi),
    'hypoxic_burden':           ('Hypoxic burden', hypoxic_burden),
    'self_similarity':          ('Respiratory self-similarity', self_similarity),
    #'rrv':                      ('Respiratory rate variability (RRV)', rrv),
    'plmi':                     ('Periodic limb movement index (PLMI)', plmi),
    #'sleep_atonia_index':       ('Sleep atonia index', sleep_atonia_index),
    #'delta_hr':                 ('Delta-HR cross-channel coupling', delta_hr),
}


class PSGFeatureComputation:
    def __init__(self, edf_path, channel_mapping, notch_freq=60, log_callback=None,
                 selected_features=None, actual_age=None, annot_df=None, q=None,
                 custom_code=None, custom_figure_code=None):
        self.annot_df = annot_df
        self.q = q
        self.custom_code        = custom_code
        self.custom_figure_code = custom_figure_code
        # Determine staging method and remaining features
        if selected_features is None:
            steps = ['sleep_staging_CAISR']
        elif 'from_annotation' in selected_features:
            steps = ['from_annotation'] + [f for f in selected_features
                                       if f not in ('sleep_staging_CAISR', 'from_annotation')]
        else:
            steps = ['sleep_staging_CAISR'] + [f for f in selected_features
                                                if f != 'sleep_staging_CAISR']

        self.feature_steps = steps
        self.feature_steps_txt = [ALL_FEATURE_LABELS.get(f, [f])[0] for f in steps]
        self.actual_age = actual_age

        self.edf_path = edf_path
        self.sid = os.path.splitext(os.path.basename(self.edf_path))[0]
        self.channel_mapping = channel_mapping
        self.notch_freq = notch_freq
        self._log_callback = log_callback
        self.edf_ch_names = mne.io.read_raw_edf(edf_path, verbose=False, preload=False).ch_names

        self.channel_group_names = ['eeg', 'eog', 'ecg', 'chin_emg', 'limb_emg', 'rip', 'nasalpressure', 'airflow', 'spo2']
        self.channel_group2names_all = {
            'eeg':['F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1'],
            'eog':['E1-M2', 'E2-M1'],
            'ecg':['ECG'],
            'chin_emg':['CHIN1-CHIN2'],
            'limb_emg':['LAT', 'RAT'],
            'rip':['CHEST', 'ABD'],
            'nasalpressure':['PTAF'],
            'airflow':['AIRFLOW'],
            'spo2':['SpO2'], }

    def _log(self, msg):
        if self._log_callback:
            self._log_callback(msg)
        print(msg)

    def _get_sleep_stages(self):
        """Return the sleep-stage array from detections, or None if not available."""
        ss_names = [x for x in self.detections if 'sleep_stag' in x.lower()]
        if not ss_names:
            return None
        return self.detections[ss_names[0]]

    def run(self):
        #self._log(str(self.channel_mapping))
        self._log("Starting feature extraction...")

        self._log('Getting signals...')
        self.get_signals()
        self._log('Preprocessing...')
        self.preprocess_signals()

        self.feats = {}       # single-value features
        self.detections = {}  # non-scalar detections

        for feat, feat_txt in zip(self.feature_steps, self.feature_steps_txt):
            self._log(f'\nGetting {feat_txt}...')
            start_time = timeit.default_timer()

            if feat == 'from_annotation':
                if self.annot_df is None or len(self.annot_df) == 0:
                    self._log('No annotation stages provided — skipping.')
                    continue
                f, d = sleep_staging_from_annotation(annot=self.annot_df, signal_len_seconds=self.signal_len_seconds,
                        log=self._log, fs=self.fs,)

            elif feat == 'sleep_staging_CAISR':
                folder = self.prepare_EDF_for_CAISR()
                f, d = sleep_staging_CAISR(sid=self.sid, signals=self.signals, folder=folder, signal_len_seconds=self.signal_len_seconds,
                        log=self._log, fs=self.fs,)
                #self._log(', '.join([f'{k}: {v}' for k, v in f.items()]))

            elif feat == 'custom_phenotype':
                if not self.custom_code:
                    self._log('custom_phenotype: no code provided — skipping.')
                    continue
                try:
                    import types as _types
                    ns = {}
                    exec(compile(self.custom_code, '<custom_phenotype>', 'exec'), ns)
                    # Only pick functions actually defined in this code block (not imported ones)
                    fn = next((v for k, v in ns.items()
                               if isinstance(v, _types.FunctionType)
                               and v.__code__.co_filename == '<custom_phenotype>'
                               and not k.startswith('_')), None)
                    if fn is None:
                        self._log('custom_phenotype: no callable function found — skipping.')
                        continue
                    sleep_stages = self._get_sleep_stages()
                    f, d = fn(
                        sid=self.sid,
                        signals=self.signals,
                        fs=self.fs,
                        channels=self.channel_group2names,
                        sleep_stages=sleep_stages,
                        log=self._log,
                        n_jobs=1,
                        notch_freq=self.notch_freq,
                    )
                except Exception:
                    import traceback
                    self._log(f'custom_phenotype failed:\n{traceback.format_exc()}')
                    continue
                # Run optional figure function
                if self.custom_figure_code:
                    try:
                        ns_fig = {}
                        exec(compile(self.custom_figure_code, '<custom_figure>', 'exec'), ns_fig)
                        fig_fn = next((v for k, v in ns_fig.items()
                                       if isinstance(v, _types.FunctionType)
                                       and v.__code__.co_filename == '<custom_figure>'
                                       and not k.startswith('_')), None)
                        if fig_fn is not None:
                            fig = fig_fn(f, d)
                            if fig is not None:
                                d['custom_figure_json'] = fig.to_json()
                    except Exception:
                        import traceback
                        self._log(f'custom_figure failed:\n{traceback.format_exc()}')

            elif feat in ALL_FEATURE_LABELS:
                fn = ALL_FEATURE_LABELS[feat][1]
                sleep_stages = self._get_sleep_stages()
                if sleep_stages is None:
                    self._log(f'No sleep stage detected — skipping {feat}.')
                    continue
                input_args = dict(
                    sid=self.sid,
                    signals=self.signals,
                    fs=self.fs,
                    channels=self.channel_group2names,
                    sleep_stages=sleep_stages,
                    log=self._log,
                    n_jobs=1,
                )
                if feat=='brain_age':
                    input_args['actual_age'] = self.actual_age
                    input_args['notch_freq'] = self.notch_freq
                    input_args['work_dir'] = os.path.dirname(self.edf_path)
                if feat=='spindle_slow_oscillation':
                    input_args['q'] = self.q
                    input_args['work_dir'] = os.path.dirname(self.edf_path)
                if feat=='cardiopulmonary_coupling':
                    input_args['notch_freq'] = self.notch_freq
                if feat=='hrv':
                    input_args['notch_freq'] = self.notch_freq
                if feat=='self_similarity':
                    input_args['notch_freq'] = self.notch_freq
                f, d = fn(**input_args)
                if len(f)==0:
                    self._log(f'{feat} has empty features.')

            else:
                self._log(f'{feat} is not recognised — skipping.')
                continue

            self.feats |= f
            self.detections |= d
            end_time = timeit.default_timer()
            self._log(f'{feat} finished in {end_time-start_time:.2f} seconds.')

        df_feat = pd.DataFrame(data={k: [v] for k, v in self.feats.items()})
        #self._log(df_feat.iloc[0].to_string())
        self._log("\nPhenomics computation is complete.")
        return df_feat, self.detections

    #def _get_signals_pyedflib(self, channels, scale=1.):
    #def _get_signals_pyedfio(self, channels, scale=1.):
    def _get_signals_mne(self, channels, scale=1.):
        actual_chs = []
        channel_plan = {}
        for ch in channels:
            mapped = self.channel_mapping.get(ch, '')
            if not mapped or mapped == 'DOES_NOT_EXIST':
                continue
            if '|' in mapped:
                ch1, ch2 = mapped.split('|', 1)
                if ch1 in self.edf_ch_names and ch2 in self.edf_ch_names:
                    actual_chs.append(ch1)
                    actual_chs.append(ch2)
                    channel_plan[ch] = ('diff', ch1, ch2)
            elif mapped in self.edf_ch_names:
                actual_chs.append(mapped)
                channel_plan[ch] = ('direct', mapped)

        actual_chs = pd.unique(np.array(actual_chs))
        if len(actual_chs)==0:
            found_signals = None
            found_channels = []
            fs = np.nan
        else:
            raw = mne.io.read_raw_edf(
                self.edf_path, verbose=False, preload=True,
                exclude=[x for x in self.edf_ch_names if x not in actual_chs])
            fs = raw.info['sfreq']

            found_signals = []
            found_channels = []
            for ch in channels:
                if ch in channel_plan:
                    cp = channel_plan[ch]
                    if cp[0]=='direct':
                        found_signals.append(raw.get_data(picks=cp[1]).flatten())
                    else:
                        s = raw.get_data(picks=cp[1:])
                        found_signals.append(s[0]-s[1])
                    found_channels.append(ch)
            found_signals = np.array(found_signals)*scale
        return found_signals, found_channels, fs

    def get_signals(self):
        """Load signals from the EDF, using the channel mapping.
        The mapping value can be:
          - A single EDF channel name  (pre-referenced, use directly)
          - 'pos|neg'                  (compute pos − neg)
          - 'DOES_NOT_EXIST' or ''     (skip)
        Get self.signals = {'eeg':, 'ecg':, ...}
        """
        self.signals = {}
        self.channel_group2names = {}
        self.fs = {}
        self.signal_len_seconds = None

        for chg in self.channel_group_names:
            sig_, ch_, fs_ = self._get_signals_mne(self.channel_group2names_all[chg])
            if sig_ is not None:
                self.signals[chg], self.channel_group2names[chg], self.fs[chg] = sig_, ch_, fs_
                self._log(f'    Found {len(self.channel_group2names[chg])} {chg} channels: {self.channel_group2names[chg]}.')
                if chg == 'spo2':
                    spo2_median = np.median(self.signals[chg])
                    cc = 0
                    while True:
                        if spo2_median<10.5:
                            spo2_median *= 10.
                            self.signals[chg] *= 10.
                        elif spo2_median>105:
                            spo2_median /= 10.
                            self.signals[chg] /= 10.
                        else:
                            break
                        cc += 1
                        if cc>50:
                            self.signals.pop('spo2')
                            self.channel_group2names.pop('spo2')
                            self.fs.pop('spo2')
                            break
                else:
                    if (self.signals[chg].std(axis=1)<1e-3).all():
                        self.signals[chg] *= 1e6
                if self.signal_len_seconds is None:
                    self.signal_len_seconds = self.signals[chg].shape[1] / self.fs[chg]
            else:
                self._log(f'CANNOT find {chg} channels based on {self.channel_group2names_all[chg]}!')

        self._log(f"Recording length: {self.signal_len_seconds/3600:.2f} h")

    def preprocess_signals(self):
        if 'eeg' in self.signals:
            if self.notch_freq is not None and self.notch_freq < self.fs['eeg'] / 2:
                self.signals['eeg'] = mne.filter.notch_filter(
                    self.signals['eeg'], self.fs['eeg'], self.notch_freq, verbose=False)
            high = 35 if 35 < self.fs['eeg'] / 2 else None
            self.signals['eeg'] = mne.filter.filter_data(
                self.signals['eeg'], self.fs['eeg'], 0.3, high, verbose=False)

        if 'eog' in self.signals:
            if self.notch_freq is not None and self.notch_freq < self.fs['eog'] / 2:
                self.signals['eog'] = mne.filter.notch_filter(
                    self.signals['eog'], self.fs['eog'], self.notch_freq, verbose=False)
            high = 35 if 35 < self.fs['eog'] / 2 else None
            self.signals['eog'] = mne.filter.filter_data(
                self.signals['eog'], self.fs['eog'], 0.3, high, verbose=False)

        if 'ecg' in self.signals:
            if self.notch_freq is not None and self.notch_freq < self.fs['ecg'] / 2:
                self.signals['ecg'] = mne.filter.notch_filter(
                    self.signals['ecg'], self.fs['ecg'], self.notch_freq, verbose=False)
            high = 100 if 100 < self.fs['ecg'] / 2 else None
            self.signals['ecg'] = mne.filter.filter_data(
                self.signals['ecg'], self.fs['ecg'], 0.3, high, verbose=False)

        if 'chin_emg' in self.signals:
            if self.notch_freq is not None and self.notch_freq < self.fs['chin_emg'] / 2:
                self.signals['chin_emg'] = mne.filter.notch_filter(
                    self.signals['chin_emg'], self.fs['chin_emg'], self.notch_freq, verbose=False)
            high = 100 if 100 < self.fs['chin_emg'] / 2 else None
            self.signals['chin_emg'] = mne.filter.filter_data(
                self.signals['chin_emg'], self.fs['chin_emg'], 10, high, verbose=False)

        if 'limb_emg' in self.signals:
            if self.notch_freq is not None and self.notch_freq < self.fs['limb_emg'] / 2:
                self.signals['limb_emg'] = mne.filter.notch_filter(
                    self.signals['limb_emg'], self.fs['limb_emg'], self.notch_freq, verbose=False)
            high = 100 if 100 < self.fs['limb_emg'] / 2 else None
            self.signals['limb_emg'] = mne.filter.filter_data(
                self.signals['limb_emg'], self.fs['limb_emg'], 10, high, verbose=False)

        if 'rip' in self.signals:
            high = 15 if 15 < self.fs['rip'] / 2 else None
            self.signals['rip'] = mne.filter.filter_data(
                self.signals['rip'], self.fs['rip'], 0.1, high, verbose=False)

        if 'airflow' in self.signals:
            high = 15 if 15 < self.fs['airflow'] / 2 else None
            self.signals['airflow'] = mne.filter.filter_data(
            self.signals['airflow'], self.fs['airflow'], 0.1, high, verbose=False)

        if 'nasalpressure' in self.signals:
            high = 100 if 100 < self.fs['nasalpressure'] / 2 else None
            self.signals['nasalpressure'] = mne.filter.filter_data(
                self.signals['nasalpressure'], self.fs['nasalpressure'], 0.03, high, verbose=False)


    def prepare_EDF_for_CAISR(self):
        # Each job gets its own temp dir so concurrent users don't share data/output paths.
        # /var/folders (macOS default tmpdir) is not shared with Docker Desktop by default.
        # Use the EDF file's parent directory instead, which is always under /Users/... and
        # is guaranteed to be in Docker Desktop's file-sharing list.
        job_dir = tempfile.mkdtemp(prefix='spa_caisr_', dir=os.path.dirname(self.edf_path))

        base = os.path.splitext(os.path.basename(self.edf_path))[0]
        out_path = os.path.join(job_dir, 'data', 'raw', base + '.edf')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        signal_groups = []
        for ch in self.channel_group_names:
            if ch not in self.signals: continue
            sig = self.signals[ch]
            # expand to all since CAISR requires all
            if set(self.channel_group2names[ch])==set(self.channel_group2names_all[ch]):
                sig2 = sig
            else:
                sig2 = np.zeros((len(self.channel_group2names_all[ch]), sig.shape[1]))+sig[0]
                sig2[[self.channel_group2names_all[ch].index(x) for x in self.channel_group2names[ch]]] = sig

            signal_groups.append((sig2, self.channel_group2names_all[ch], self.fs[ch], '%' if ch=='spo2' else 'uV'))

        all_signals, all_headers = [], []
        for signals, ch_names, fs, unit in signal_groups:
            for i, ch in enumerate(ch_names):
                sig = signals[i].astype(np.float64)
                pmin = float(np.min(sig))
                pmax = float(np.max(sig))
                if pmin == pmax:
                    pmax = pmin + 1.0
                hdr = pyedflib.highlevel.make_signal_header(
                    ch, dimension=unit, sample_frequency=fs,
                    physical_min=pmin, physical_max=pmax)
                all_signals.append(sig)
                all_headers.append(hdr)

        pyedflib.highlevel.write_edf(out_path, all_signals, all_headers)
        self._log(f"Saved EDF for CAISR at {out_path}")
        return job_dir


if __name__=='__main__':
    #edf_path = '../static/example/example.edf'
    #annot_path = '../static/example/example_annot.csv'
    channel_mapping = {
        'C4-M1':'EEG',
        #'F3-M2':'F3-M2', 'F4-M1':'F4-M1',
        #'C3-M2':'C3-M2', 'C4-M1':'C4-M1',
        #'O1-M2':'O1-M2', 'O2-M1':'O2-M1',
        #'E1-M2':'E1', 'E2-M1':'E2',
        #'CHIN1-CHIN2':'CHIN',
        #'AIRFLOW':'THERM', 'CHEST':'CHEST',
        #'ABD':'ABDOMINAL', 'ECG':'EKG', 'SpO2':'SaO2'}
        }
    #annot_df = pd.read_csv(annot_path)
    #annot_df = annot_df.rename(columns={'onset':'Onset', 'duration':'Duration', 'sleep stage':'Description'})
    import glob
    mapping = {'Wake':'W','REM sleep':'R','Stage 1 sleep':'N1','Stage 2 sleep':'N2','Stage 3 sleep':'N3'}
    df_res = []
    for folder in ['age40-45_m', 'age50-55_m', 'age60-65_m', 'age70-75_m', 'age80-85_m']:
        files = glob.glob(os.path.join('/Users/hs635/Downloads/saurons_eye/shhs', folder, '*.edf'))
        for edf_path in files:
            sid = os.path.basename(edf_path).replace('.edf','')
            print(f'\n\n\n\n====== {sid} ======\n\n\n')
            annot_path = edf_path.replace('.edf','-nsrr.csv')
            annot_df = pd.read_csv(annot_path)
            annot_df['Description'] = annot_df['Description'].apply(lambda x:mapping.get(x,''))
            a = PSGFeatureComputation(edf_path, channel_mapping, notch_freq=60, selected_features=['from_annotation', 'band_power'], annot_df= annot_df, actual_age=60, q=0.5)
            df_feat, detections = a.run()
            #print(df_feat)
            #print(detections.keys())
            df_feat.insert(0,'nsrrid',int(sid[6:]))
            df_feat.insert(0,'AgeGroup',folder)
            df_res.append(df_feat[['AgeGroup','nsrrid','BP_abs_delta_C4-M1_N3','BP_rel_delta_C4-M1_N3', 'BP_abs_sigma_C4-M1_N2','BP_rel_sigma_C4-M1_N2']])
    df_res = pd.concat(df_res)
    df_ = pd.read_csv('/Users/hs635/Downloads/saurons_eye/shhs/shhs1-dataset-0.21.0.csv')
    df_res=df_res.merge(df_[['nsrrid','age_s1']],on='nsrrid',how='inner', validate='1:1')
    df_res.to_csv('shhs_SPA_band_powers.csv', index=False)

    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_style('ticks')
    import pingouin as pg

    df_corr = pg.partial_corr(data=df_res, x="age_s1", y="BP_abs_delta_C4-M1_N3")
    print(df_corr)
    corr = df_corr.loc['pearson','r']
    ci = df_corr.loc['pearson','CI95']
    p_val = df_corr.loc['pearson','p_val']

    plt.close()
    fig = plt.figure(figsize=(6,3.6))
    ax = fig.add_subplot(111)
    sns.regplot(data=df_res, x="age_s1", y="BP_abs_delta_C4-M1_N3", color='k', scatter_kws={'alpha': 0.5})
    ax.text(0.98,0.95,f'Person\'s correlation = {corr:.2f} [{ci[0]:.2f} - {ci[1]:.2f}], p < 0.05', ha='right',va='top',transform=ax.transAxes)
    ax.set_xlabel('Age (year)')
    ax.set_ylabel('Delta band power at C4-M1 during N3 (dB)')
    sns.despine()
    plt.grid()
    plt.tight_layout()
    plt.savefig('updated_delta_power_scatterplot2.pdf', bbox_inches='tight')



