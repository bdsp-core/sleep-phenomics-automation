import os
import numpy as np
import pandas as pd
from datetime import datetime


def parse_annotation(
    file_path: str,
    separator: str = ',',
    onset_col: int = 1,
    onset_coding: str = 'seconds',
    use_duration: bool = True,
    duration_col: int = 2,
    use_end: bool = False,
    end_col: int = 3,
    stage_col: int = 4,
    data_start_line: int = 2,
    stage_map: dict = None,
    recording_start: datetime = None,
) -> pd.DataFrame:
    """
    Parse a sleep-stage annotation file into a standardised DataFrame.

    Parameters
    ----------
    file_path       : absolute path to the annotation file
    separator       : column delimiter (used only for .txt files)
    onset_col       : 1-based column index of the onset time
    onset_coding    : 'seconds'        – values already in seconds from recording start
                      'time_no_date'   – HH:MM:SS time strings (recording_start required)
                      'time_with_date' – full datetime strings   (recording_start required)
    use_duration    : if True, read epoch duration from duration_col
    duration_col    : 1-based column index of duration (seconds)
    use_end         : if True (and use_duration is False), duration = end_time - onset
    end_col         : 1-based column index of end time
    stage_col       : 1-based column index of the stage label
    data_start_line : first 1-based line number that contains data (preceding lines skipped)
    stage_map       : mapping from annotation labels → canonical stages (W/R/N1/N2/N3)
                      e.g. {'Wake': 'W', 'NREM1': 'N1', 'REM': 'R'}
    recording_start : datetime of recording start — required for time-based onset codings

    Returns
    -------
    pd.DataFrame with columns:
        Onset       (float) – seconds after recording start
        Duration    (float) – seconds
        Description (str)   – canonical stage label (W/R/N1/N2/N3) for stage rows,
                              raw annotation text for all other rows
    Rows with unparseable onsets or non-positive durations are dropped.
    """
    if stage_map is None:
        stage_map = {s: s for s in ('W', 'R', 'N1', 'N2', 'N3')}

    # --- time-conversion helpers (defined here so they are available for both
    #     onset and end columns regardless of which branch is active) ----------

    def _hms_to_sec(v):
        s = str(v).strip()
        for fmt in ('%H:%M:%S', '%H:%M:%S.%f'):
            try:
                t = datetime.strptime(s, fmt)
                return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6
            except ValueError:
                pass
        return np.nan

    def _dt_to_sec(v):
        if isinstance(v, datetime):
            dt = v
        else:
            try:
                dt = pd.to_datetime(str(v).strip()).to_pydatetime()
            except Exception:
                return np.nan
        if recording_start is None:
            return np.nan
        return (dt.replace(tzinfo=None) - recording_start.replace(tzinfo=None)).total_seconds()

    # --- load raw table -------------------------------------------------------

    ext = os.path.splitext(file_path)[1].lower()
    skiprows = data_start_line - 1

    if ext in ('.xlsx', '.xls'):
        raw = pd.read_excel(file_path, header=None, skiprows=skiprows)
        raw = raw.astype(str)
    elif ext == '.tsv':
        raw = pd.read_csv(file_path, header=None, skiprows=skiprows, sep='\t', dtype=str)
    elif ext == '.csv':
        raw = pd.read_csv(file_path, header=None, skiprows=skiprows, sep=',', dtype=str)
    else:  # .txt – user-supplied separator
        raw = pd.read_csv(file_path, header=None, skiprows=skiprows, sep=separator, dtype=str)

    # Convert 1-based column indices to 0-based
    oi = onset_col - 1
    di = duration_col - 1
    ei = end_col - 1
    si = stage_col - 1

    # --- onset ----------------------------------------------------------------

    raw_onset = raw.iloc[:, oi]

    if onset_coding == 'seconds':
        onset_sec = pd.to_numeric(raw_onset, errors='coerce')

    elif onset_coding == 'time_no_date':
        onset_sec = raw_onset.apply(_hms_to_sec)
        if recording_start is not None:
            rec_sec = (recording_start.hour * 3600
                       + recording_start.minute * 60
                       + recording_start.second
                       + getattr(recording_start, 'microsecond', 0) / 1e6)
            onset_sec = onset_sec - rec_sec

    elif onset_coding == 'time_with_date':
        onset_sec = raw_onset.apply(_dt_to_sec)

    else:
        raise ValueError(f"Unknown onset_coding: {onset_coding!r}")

    # --- duration -------------------------------------------------------------

    if use_duration:
        duration_sec = pd.to_numeric(raw.iloc[:, di], errors='coerce')

    elif use_end:
        raw_end = raw.iloc[:, ei]
        if onset_coding == 'seconds':
            end_sec = pd.to_numeric(raw_end, errors='coerce')
        elif onset_coding == 'time_no_date':
            end_sec = raw_end.apply(_hms_to_sec)
            if recording_start is not None:
                end_sec = end_sec - rec_sec
        else:  # time_with_date
            end_sec = raw_end.apply(_dt_to_sec)
        duration_sec = end_sec - onset_sec

    else:
        duration_sec = pd.Series(np.nan, index=raw.index)

    # --- stage / description --------------------------------------------------

    rev_map  = {str(k).strip(): v for k, v in stage_map.items()}
    raw_desc = raw.iloc[:, si].astype(str).str.strip()
    # For stage rows use the canonical label; for event rows keep raw text
    canonical = raw_desc.map(rev_map)
    description = canonical.where(canonical.notna(), raw_desc)

    # --- assemble & clean -----------------------------------------------------

    out = pd.DataFrame({
        'Onset':       onset_sec,
        'Duration':    duration_sec,
        'Description': description,
    })
    out = out.dropna(subset=['Onset'])
    out = out[out['Duration'].notna() & (out['Duration'] > 0)]
    out = out.reset_index(drop=True)
    return out
