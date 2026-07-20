"""XDF ingestion and conversion to the EDF representation used by SPA."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pyedflib


class XDFError(ValueError):
    code = "XDF_PARSE_FAILED"
    public_message = (
        "The uploaded XDF file could not be parsed. Please confirm that the file "
        "is valid and try again."
    )


class XDFEmptyError(XDFError):
    code = "XDF_EMPTY"
    public_message = "The uploaded XDF file does not contain a usable time-series stream."


class XDFStreamSelectionRequired(XDFError):
    code = "XDF_STREAM_SELECTION_REQUIRED"
    public_message = "This XDF file contains multiple signal streams. Please select one."

    def __init__(self, streams):
        super().__init__(self.public_message)
        self.streams = streams


def _first(value: Any, default=""):
    while isinstance(value, list):
        if not value:
            return default
        value = value[0]
    return default if value is None else value


def _info(stream, key, default=""):
    return _first(stream.get("info", {}).get(key), default)


def _channel_metadata(stream, count):
    channels = stream.get("info", {}).get("desc", [])
    try:
        channels = channels[0]["channels"][0]["channel"]
    except (IndexError, KeyError, TypeError):
        channels = []
    labels, units = [], []
    for index in range(count):
        channel = channels[index] if index < len(channels) and isinstance(channels[index], dict) else {}
        labels.append(str(_first(channel.get("label"), f"Channel {index + 1}")))
        units.append(str(_first(channel.get("unit"), "uV")))
    # EDF labels have a 16-character limit and must be unique.
    seen = set()
    for index, label in enumerate(labels):
        candidate = label.strip() or f"Channel {index + 1}"
        candidate = candidate[:16]
        if candidate in seen:
            suffix = f"_{index + 1}"
            candidate = candidate[: 16 - len(suffix)] + suffix
        seen.add(candidate)
        labels[index] = candidate
    return labels, units


def _numeric_matrix(stream):
    values = np.asarray(stream.get("time_series", []))
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 1:
        return None
    try:
        values = values.astype(float)
    except (TypeError, ValueError):
        return None
    return values if np.isfinite(values).any() else None


def describe_streams(streams):
    result = []
    for index, stream in enumerate(streams):
        values = np.asarray(stream.get("time_series", []))
        count = values.shape[1] if values.ndim == 2 else (1 if values.ndim == 1 and values.size else 0)
        timestamps = np.asarray(stream.get("time_stamps", []), dtype=float)
        nominal = _as_rate(_info(stream, "nominal_srate", 0))
        stream_type = str(_info(stream, "type", ""))
        marker_like = stream_type.strip().lower() in {"marker", "markers", "event", "events"}
        result.append({
            "id": index,
            "name": str(_info(stream, "name", f"Stream {index + 1}")),
            "type": stream_type,
            "channel_count": int(count),
            "sample_count": int(values.shape[0]) if values.ndim else 0,
            "nominal_sampling_rate": nominal,
            "is_regular": bool(nominal > 0 and timestamps.size > 1),
            "is_signal": _numeric_matrix(stream) is not None and not marker_like,
        })
    return result


def _as_rate(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rate_and_regular_data(stream, values, warnings):
    timestamps = np.asarray(stream.get("time_stamps", []), dtype=float)
    if timestamps.size != values.shape[0] or timestamps.size < 2 or not np.all(np.isfinite(timestamps)):
        raise XDFError("Signal timestamps are missing or malformed")
    order = np.argsort(timestamps)
    timestamps, values = timestamps[order], values[order]
    unique = np.r_[True, np.diff(timestamps) > 0]
    timestamps, values = timestamps[unique], values[unique]
    if timestamps.size < 2:
        raise XDFError("Signal timestamps do not span a usable interval")
    inferred = 1.0 / float(np.median(np.diff(timestamps)))
    rate = _as_rate(_info(stream, "nominal_srate", 0))
    if not rate:
        rate = inferred
        warnings.append(f"Sampling rate was inferred from timestamps ({rate:.3f} Hz).")
    if not math.isfinite(rate) or rate <= 0 or rate > 100000:
        raise XDFError("Signal sampling rate is invalid")
    target_count = int(round((timestamps[-1] - timestamps[0]) * rate)) + 1
    if target_count <= 1 or target_count > 100_000_000 or target_count > timestamps.size * 100:
        raise XDFError("Signal timestamps imply an unsupported recording size")
    target = timestamps[0] + np.arange(target_count) / rate
    jitter = np.max(np.abs(timestamps - (timestamps[0] + np.arange(timestamps.size) / rate)))
    if timestamps.size != target.size or jitter > max(1e-6, 0.01 / rate):
        values = np.column_stack([np.interp(target, timestamps, values[:, i]) for i in range(values.shape[1])])
        warnings.append("Irregular timestamps were resampled onto a regular timeline for SPA.")
    return rate, values, float(timestamps[0])


def _unit_scale(unit):
    normalized = unit.strip().lower().replace("µ", "u").replace("μ", "u")
    return {"v": 1e6, "mv": 1e3, "uv": 1.0, "nv": 1e-3}.get(normalized, 1.0)


@dataclass
class XDFConversion:
    streams: list[dict]
    selected_stream_id: int
    warnings: list[str]
    marker_count: int


def convert_xdf_to_edf(source_path, destination_path, selected_stream_id=None, loader=None):
    """Parse XDF, choose a numeric stream, and atomically create an SPA-compatible EDF."""
    if not os.path.isfile(source_path) or os.path.getsize(source_path) == 0:
        raise XDFEmptyError()
    if loader is None:
        try:
            import pyxdf
        except ImportError as exc:  # pragma: no cover - deployment configuration
            raise XDFError("pyxdf is not installed") from exc
        loader = pyxdf.load_xdf
    try:
        streams, _header = loader(source_path)
    except Exception as exc:
        raise XDFError(str(exc)) from exc
    if not streams:
        raise XDFEmptyError()

    descriptions = describe_streams(streams)
    candidates = [item["id"] for item in descriptions if item["is_signal"]]
    if not candidates:
        raise XDFEmptyError()
    if selected_stream_id is None and len(candidates) > 1:
        raise XDFStreamSelectionRequired(descriptions)
    try:
        selected = candidates[0] if selected_stream_id is None else int(selected_stream_id)
    except (TypeError, ValueError) as exc:
        raise XDFError("Invalid stream selection") from exc
    if selected not in candidates:
        raise XDFError("The selected XDF stream is not a usable signal stream")

    warnings = []
    signal_stream = streams[selected]
    values = _numeric_matrix(signal_stream)
    rate, values, signal_start = _rate_and_regular_data(signal_stream, values, warnings)
    labels, units = _channel_metadata(signal_stream, values.shape[1])
    signals_uv = [values[:, i] * _unit_scale(units[i]) for i in range(values.shape[1])]
    known_units = {"v", "mv", "uv", "nv", "µv", "μv"}
    unknown_units = sorted({unit for unit in units if unit.strip().lower() not in known_units})
    if unknown_units:
        warnings.append("Unknown channel units were treated as microvolts.")
    headers = []
    for label, signal in zip(labels, signals_uv):
        finite = signal[np.isfinite(signal)]
        if finite.size == 0:
            signal[:] = 0
            finite = signal
        elif finite.size != signal.size:
            valid = np.isfinite(signal)
            signal[~valid] = np.interp(np.flatnonzero(~valid), np.flatnonzero(valid), signal[valid])
            warnings.append(f"Non-finite samples in channel {label} were interpolated.")
        max_abs = max(1.0, float(np.max(np.abs(finite))))
        # Symmetric power-of-two bounds are safe, compact EDF header values and
        # avoid silently clipping extrema during digital conversion.
        bound = 2.0 ** math.ceil(math.log2(max_abs * 1.01))
        headers.append(pyedflib.highlevel.make_signal_header(
            label, sample_frequency=rate, physical_min=-bound, physical_max=bound,
            dimension="uV",
        ))

    annotations = []
    for index, stream in enumerate(streams):
        stream_type = str(_info(stream, "type", "")).strip().lower()
        if index == selected or stream_type not in {"marker", "markers", "event", "events"}:
            continue
        stamps = np.asarray(stream.get("time_stamps", []), dtype=float)
        series = stream.get("time_series", [])
        for stamp, marker in zip(stamps, series):
            text = str(_first(marker, ""))[:80]
            if text and math.isfinite(float(stamp)):
                annotations.append((max(0.0, float(stamp) - signal_start), -1, text))

    tmp_path = destination_path + ".part.edf"
    try:
        header = pyedflib.highlevel.make_header(startdate=datetime.now())
        header["annotations"] = annotations
        pyedflib.highlevel.write_edf(tmp_path, signals_uv, headers, header=header)
        os.replace(tmp_path, destination_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return XDFConversion(descriptions, selected, warnings, len(annotations))
