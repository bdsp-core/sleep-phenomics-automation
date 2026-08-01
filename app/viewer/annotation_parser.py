import os
import numpy as np
import pandas as pd
from datetime import datetime
from xml.etree import ElementTree


class XDFAnnotationError(ValueError):
    """A user-readable XDF annotation validation error."""

    public_message = (
        "The uploaded XDF file does not contain usable sleep stages, events, or markers. "
        "Please confirm that it is a valid XDF annotation file and try again."
    )


def _xdf_first(value, default=""):
    while isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    return default if value is None else value


def _xdf_info(stream, key, default=""):
    if not isinstance(stream, dict):
        return default
    info = stream.get("info", {})
    if not isinstance(info, dict):
        return default
    return _xdf_first(info.get(key), default)


def _xdf_timestamps(stream):
    if not isinstance(stream, dict):
        return np.asarray([], dtype=float)
    try:
        return np.asarray(stream.get("time_stamps", []), dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return np.asarray([], dtype=float)


def _xdf_marker_payload(value):
    """Return (description, optional duration) from a marker sample."""
    if isinstance(value, np.ndarray):
        value = value.tolist()
    fields = value if isinstance(value, (list, tuple)) else [value]
    description = str(_xdf_first(fields[0] if fields else "", "")).strip()
    duration = np.nan
    if len(fields) > 1:
        try:
            candidate = float(_xdf_first(fields[1], np.nan))
            if np.isfinite(candidate) and candidate > 0:
                duration = candidate
        except (TypeError, ValueError):
            pass
    return description, duration


def _is_xdf_annotation_stream(stream):
    stream_type = str(_xdf_info(stream, "type", "")).strip().lower()
    stream_name = str(_xdf_info(stream, "name", "")).strip().lower()
    if any(token in stream_type or token in stream_name
           for token in ("marker", "event", "annotation")):
        return True
    try:
        nominal_rate = float(_xdf_info(stream, "nominal_srate", 0) or 0)
    except (TypeError, ValueError):
        nominal_rate = 0
    values = stream.get("time_series", []) if isinstance(stream, dict) else []
    try:
        is_empty = values is None or len(values) == 0
    except TypeError:
        is_empty = True
    if nominal_rate != 0 or is_empty:
        return False
    try:
        np.asarray(values, dtype=float)
        return False
    except (TypeError, ValueError):
        return True


def _xml_local_name(tag):
    return str(tag).rsplit("}", 1)[-1]


def _xml_child(element, name):
    return next((child for child in element if _xml_local_name(child.tag) == name), None)


def _xml_text(element, name, default=""):
    child = _xml_child(element, name)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _openxdf_datetime(value):
    try:
        # Polysmith OpenXDF commonly writes more than six fractional digits.
        # datetime.fromisoformat safely truncates the excess precision.
        return datetime.fromisoformat(str(value).strip()).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _openxdf_stage(value):
    stage = str(value or "").strip().upper().replace("STAGE", "").strip()
    return {
        "W": "W", "WAKE": "W", "0": "W",
        "R": "R", "REM": "R",
        "1": "N1", "N1": "N1",
        "2": "N2", "N2": "N2",
        "3": "N3", "4": "N3", "N3": "N3", "N4": "N3",
    }.get(stage)


def _openxdf_scorer_score(scorer):
    stages = _xml_child(scorer, "SleepStages")
    populated_stages = 0
    if stages is not None:
        populated_stages = sum(
            _openxdf_stage(_xml_text(record, "Stage")) is not None
            for record in stages
        )
    event_count = sum(
        len(container)
        for container in scorer
        if _xml_local_name(container.tag) in {
            "Apneas", "Hypopneas", "RERAs", "FlowLimitations",
            "Desaturations", "Microarousals", "Snores",
            "LegMovements1", "LegMovements2", "Arrhythmias",
            "PTTArousals", "NoteEvents", "CustomEvents",
        }
    )
    return populated_stages, event_count


def _select_openxdf_scorer(root):
    scorers = [element for element in root.iter()
               if _xml_local_name(element.tag) == "Scorer"]
    if not scorers:
        raise XDFAnnotationError("OpenXDF contains no scorers")
    default_id = _xml_text(root, "DefaultScorerID")
    if default_id:
        for index, scorer in enumerate(scorers):
            if _xml_text(scorer, "ScorerID") == default_id:
                return scorer, index, len(scorers), "default"
    index, scorer = max(enumerate(scorers), key=lambda item: _openxdf_scorer_score(item[1]))
    return scorer, index, len(scorers), "most_complete"


def _openxdf_event_description(container_name, record, custom_event_names):
    event_class = _xml_text(record, "Class").strip().lower()
    if container_name == "Apneas":
        return f"{event_class} apnea" if event_class else "apnea"
    if container_name == "Hypopneas":
        return "hypopnea"
    if container_name == "RERAs":
        return "RERA"
    if container_name in {"Microarousals", "PTTArousals"}:
        return "arousal"
    if container_name == "FlowLimitations":
        return "flow limitation"
    if container_name == "Desaturations":
        return "oxygen desaturation"
    if container_name == "Snores":
        return "snore"
    if container_name == "LegMovements1":
        return "left leg movement"
    if container_name == "LegMovements2":
        return "right leg movement"
    if container_name == "Arrhythmias":
        return event_class or "arrhythmia"
    if container_name == "NoteEvents":
        return _xml_text(record, "NoteText", "note") or "note"
    if container_name == "CustomEvents":
        try:
            event_type = int(_xml_text(record, "CEType"))
        except (TypeError, ValueError):
            event_type = -1
        return custom_event_names.get(event_type, "custom event")
    return _xml_local_name(record.tag).replace("_", " ").lower()


def _parse_openxdf_annotations(file_path, default_duration=30.0):
    # ElementTree does not fetch external entities, and the explicit declaration
    # check also rejects entity-expansion payloads before parsing clinical data.
    with open(file_path, "rb") as source:
        prefix = source.read(65536).upper()
    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
        raise XDFAnnotationError("Unsafe XML declarations are not supported")
    try:
        root = ElementTree.parse(file_path).getroot()
    except (ElementTree.ParseError, OSError, ValueError) as exc:
        raise XDFAnnotationError("OpenXDF XML parsing failed") from exc
    if _xml_local_name(root.tag) != "OpenXDF":
        raise XDFAnnotationError("XML file is not an OpenXDF annotation document")

    scorer, scorer_index, scorer_count, selection_reason = _select_openxdf_scorer(root)
    try:
        epoch_length = float(_xml_text(root, "EpochLength", default_duration))
    except (TypeError, ValueError):
        epoch_length = default_duration
    if not np.isfinite(epoch_length) or epoch_length <= 0:
        epoch_length = default_duration

    session_starts = []
    for session in root.iter():
        if _xml_local_name(session.tag) == "Session":
            start = _openxdf_datetime(_xml_text(session, "StartTime"))
            if start is not None:
                session_starts.append(start)
    recording_start = min(session_starts) if session_starts else None

    rows = []
    sleep_stages = _xml_child(scorer, "SleepStages")
    if sleep_stages is not None:
        for record in sleep_stages:
            stage = _openxdf_stage(_xml_text(record, "Stage"))
            try:
                epoch_number = int(_xml_text(record, "EpochNumber"))
            except (TypeError, ValueError):
                continue
            if stage is None or epoch_number < 1:
                continue
            rows.append({
                "Onset": (epoch_number - 1) * epoch_length,
                "Duration": epoch_length,
                "Description": stage,
            })

    custom_event_names = {}
    custom_configs = _xml_child(scorer, "CEConfigs")
    if custom_configs is not None:
        for index, config in enumerate(custom_configs):
            name = _xml_text(config, "CEName")
            if name:
                custom_event_names[index] = name[:256]

    event_containers = {
        "Apneas", "Hypopneas", "RERAs", "FlowLimitations",
        "Desaturations", "Microarousals", "Snores",
        "LegMovements1", "LegMovements2", "Arrhythmias",
        "PTTArousals", "NoteEvents", "CustomEvents",
    }
    pending_events = []
    for container in scorer:
        container_name = _xml_local_name(container.tag)
        if container_name not in event_containers:
            continue
        for record in container:
            event_time = _openxdf_datetime(_xml_text(record, "Time"))
            if event_time is None:
                continue
            try:
                duration = float(_xml_text(record, "Duration", "0"))
            except (TypeError, ValueError):
                duration = 0.0
            if not np.isfinite(duration) or duration <= 0:
                duration = 1.0
            description = _openxdf_event_description(
                container_name, record, custom_event_names
            ).strip()[:256]
            if description:
                pending_events.append((event_time, duration, description))

    if recording_start is None and pending_events:
        recording_start = min(event[0] for event in pending_events)
    if recording_start is not None:
        for event_time, duration, description in pending_events:
            onset = (event_time - recording_start).total_seconds()
            if np.isfinite(onset) and onset >= 0:
                rows.append({
                    "Onset": onset,
                    "Duration": duration,
                    "Description": description,
                })

    if not rows:
        raise XDFAnnotationError("OpenXDF contains no usable stages or events")
    result = pd.DataFrame(rows).sort_values("Onset", kind="stable").reset_index(drop=True)
    result.attrs["xdf_variant"] = "openxdf_xml"
    result.attrs["xdf_stream_count"] = scorer_count
    result.attrs["xdf_annotation_stream_count"] = 1
    result.attrs["xdf_selected_scorer_index"] = scorer_index
    result.attrs["xdf_scorer_selection"] = selection_reason
    return result


def parse_xdf_annotations(file_path: str, loader=None, default_duration: float = 30.0) -> pd.DataFrame:
    """Extract LSL XDF or OpenXDF XML annotations into SPA's table format.

    LSL signal streams may be present and are used only to establish the recording
    time origin; samples are never imported as PSG signals. OpenXDF files use the
    explicitly configured default scorer, or the most complete scorer as fallback.
    """
    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        raise XDFAnnotationError("Empty XDF annotation file")
    if loader is None:
        with open(file_path, "rb") as source:
            prefix = source.read(256).lstrip()
        if prefix.startswith(b"<?xml") or prefix.startswith(b"<"):
            return _parse_openxdf_annotations(file_path, default_duration)
    if loader is None:
        try:
            import pyxdf
        except ImportError as exc:  # pragma: no cover - deployment configuration
            raise XDFAnnotationError("pyxdf is not installed") from exc
        loader = pyxdf.load_xdf
    try:
        streams, _header = loader(file_path)
    except Exception as exc:
        raise XDFAnnotationError("XDF parsing failed") from exc
    if not streams:
        raise XDFAnnotationError("XDF contains no streams")

    annotation_streams = [stream for stream in streams if _is_xdf_annotation_stream(stream)]
    if not annotation_streams:
        raise XDFAnnotationError("XDF contains no marker or event streams")

    # Prefer the sleep-recording clock when a signal stream is present. For an
    # annotation-only XDF, use the first marker as time zero.
    signal_starts = []
    for stream in streams:
        if _is_xdf_annotation_stream(stream):
            continue
        stamps = _xdf_timestamps(stream)
        if stamps.size and np.isfinite(stamps[0]):
            signal_starts.append(float(stamps[0]))
    marker_starts = []
    for stream in annotation_streams:
        stamps = _xdf_timestamps(stream)
        if stamps.size and np.isfinite(stamps[0]):
            marker_starts.append(float(stamps[0]))
    if not marker_starts:
        raise XDFAnnotationError("XDF annotation timestamps are missing")
    time_origin = min(signal_starts) if signal_starts else min(marker_starts)

    rows = []
    for stream in annotation_streams:
        stamps = _xdf_timestamps(stream)
        try:
            samples = list(stream.get("time_series", [])) if isinstance(stream, dict) else []
        except TypeError:
            samples = []
        if stamps.size != len(samples):
            continue
        order = np.argsort(stamps)
        stamps = stamps[order]
        samples = [samples[index] for index in order]
        positive_gaps = np.diff(stamps)
        positive_gaps = positive_gaps[np.isfinite(positive_gaps) & (positive_gaps > 0)]
        fallback_duration = float(np.median(positive_gaps)) if positive_gaps.size else default_duration
        for index, (stamp, sample) in enumerate(zip(stamps, samples)):
            if not np.isfinite(stamp):
                continue
            description, duration = _xdf_marker_payload(sample)
            if not description:
                continue
            if not np.isfinite(duration):
                if index + 1 < len(stamps) and stamps[index + 1] > stamp:
                    duration = float(stamps[index + 1] - stamp)
                else:
                    duration = fallback_duration
            rows.append({
                "Onset": max(0.0, float(stamp) - time_origin),
                "Duration": float(duration),
                "Description": description[:256],
            })
    if not rows:
        raise XDFAnnotationError("XDF marker streams contain no usable annotations")
    result = pd.DataFrame(rows).sort_values("Onset", kind="stable").reset_index(drop=True)
    result.attrs["xdf_stream_count"] = len(streams)
    result.attrs["xdf_annotation_stream_count"] = len(annotation_streams)
    return result


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
