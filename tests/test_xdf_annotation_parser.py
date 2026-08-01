import io
from pathlib import Path

import numpy as np
import pytest

from spa_annotation_parser import XDFAnnotationError, parse_xdf_annotations


ROOT = Path(__file__).parents[1]


def _signal(start=100.0, samples=100, rate=100.0):
    timestamps = start + np.arange(samples) / rate
    return {
        "info": {
            "name": ["EEG"],
            "type": ["EEG"],
            "nominal_srate": [str(rate)],
        },
        "time_stamps": timestamps,
        "time_series": np.zeros((samples, 2)),
    }


def _markers(stamps=(100.0, 130.0), values=(("W",), ("N1",)),
             name="Sleep stages", stream_type="Markers"):
    return {
        "info": {
            "name": [name],
            "type": [stream_type],
            "nominal_srate": ["0"],
        },
        "time_stamps": np.asarray(stamps, dtype=float),
        "time_series": list(values),
    }


def _parse(tmp_path, streams, payload=b"mock xdf payload"):
    source = tmp_path / "annotations.xdf"
    source.write_bytes(payload)
    return parse_xdf_annotations(str(source), loader=lambda _path: (streams, {}))


def _openxdf_xml():
    return b"""<?xml version='1.0' encoding='utf-8'?>
<xdf:OpenXDF xmlns:xdf='http://www.openxdf.org/xdf'>
  <EpochLength>30</EpochLength>
  <Sessions><Session><StartTime>2024-01-01T22:00:00.0000000</StartTime></Session></Sessions>
  <DefaultScorerID>preferred</DefaultScorerID>
  <ScoringResults><Scorers>
    <Scorer>
      <ScorerID>other</ScorerID>
      <SleepStages>
        <SleepStage><EpochNumber>1</EpochNumber><Stage>W</Stage></SleepStage>
        <SleepStage><EpochNumber>2</EpochNumber><Stage>2</Stage></SleepStage>
      </SleepStages>
      <Apneas />
    </Scorer>
    <Scorer>
      <ScorerID>preferred</ScorerID>
      <SleepStages>
        <SleepStage><EpochNumber>2</EpochNumber><Stage>1</Stage></SleepStage>
        <SleepStage><EpochNumber>3</EpochNumber><Stage>3</Stage></SleepStage>
        <SleepStage><EpochNumber>4</EpochNumber><Stage>R</Stage></SleepStage>
      </SleepStages>
      <Apneas>
        <Apnea><Time>2024-01-01T22:00:35.0000000</Time><Duration>12</Duration><Class>central</Class></Apnea>
      </Apneas>
      <Microarousals>
        <Microarousal><Time>2024-01-01T22:01:05.0000000</Time><Duration>0</Duration></Microarousal>
      </Microarousals>
    </Scorer>
  </Scorers></ScoringResults>
</xdf:OpenXDF>"""


def test_eeg_samples_are_ignored_and_markers_align_to_signal_clock(tmp_path):
    result = _parse(tmp_path, [_signal(start=100.0), _markers((105.0, 135.0))])

    assert list(result.columns) == ["Onset", "Duration", "Description"]
    assert result.to_dict("records") == [
        {"Onset": 5.0, "Duration": 30.0, "Description": "W"},
        {"Onset": 35.0, "Duration": 30.0, "Description": "N1"},
    ]


def test_annotation_only_xdf_uses_first_marker_as_time_zero(tmp_path):
    result = _parse(tmp_path, [_markers((250.0, 280.0))])

    assert result["Onset"].tolist() == [0.0, 30.0]


def test_multiple_annotation_streams_are_combined_and_sorted(tmp_path):
    stages = _markers((100.0, 130.0), (("W",), ("N2",)))
    events = _markers((115.0,), (("Arousal",),), name="Events", stream_type="Events")
    result = _parse(tmp_path, [_signal(), stages, events])

    assert result["Description"].tolist() == ["W", "Arousal", "N2"]
    assert result["Onset"].tolist() == [0.0, 15.0, 30.0]


def test_explicit_marker_duration_is_retained(tmp_path):
    stream = _markers((100.0,), (("REM", "45"),))
    result = _parse(tmp_path, [stream])

    assert result.iloc[0].to_dict() == {
        "Onset": 0.0,
        "Duration": 45.0,
        "Description": "REM",
    }


def test_irregular_string_stream_is_inferred_as_annotations(tmp_path):
    stream = _markers(name="LSL stream", stream_type="", values=(("lights off",), ("lights on",)))
    result = _parse(tmp_path, [stream])

    assert result["Description"].tolist() == ["lights off", "lights on"]


def test_signal_only_xdf_is_not_accepted_as_an_annotation(tmp_path):
    with pytest.raises(XDFAnnotationError):
        _parse(tmp_path, [_signal()])


def test_malformed_timestamps_return_a_validation_error(tmp_path):
    stream = _markers()
    stream["time_stamps"] = ["not-a-timestamp"]

    with pytest.raises(XDFAnnotationError):
        _parse(tmp_path, [stream])


def test_openxdf_uses_default_scorer_and_normalizes_stages_and_events(tmp_path):
    source = tmp_path / "polysmith.xdf"
    source.write_bytes(_openxdf_xml())

    result = parse_xdf_annotations(str(source))

    assert result.attrs["xdf_variant"] == "openxdf_xml"
    assert result.attrs["xdf_selected_scorer_index"] == 1
    assert result.attrs["xdf_scorer_selection"] == "default"
    assert result.to_dict("records") == [
        {"Onset": 30.0, "Duration": 30.0, "Description": "N1"},
        {"Onset": 35.0, "Duration": 12.0, "Description": "central apnea"},
        {"Onset": 60.0, "Duration": 30.0, "Description": "N3"},
        {"Onset": 65.0, "Duration": 1.0, "Description": "arousal"},
        {"Onset": 90.0, "Duration": 30.0, "Description": "R"},
    ]


def test_openxdf_rejects_entity_declarations(tmp_path):
    source = tmp_path / "unsafe.xdf"
    source.write_bytes(b"<!DOCTYPE x [<!ENTITY bad 'value'>]><OpenXDF />")

    with pytest.raises(XDFAnnotationError):
        parse_xdf_annotations(str(source))


@pytest.mark.parametrize(
    "payload,loader",
    [
        (b"", lambda _path: ([], {})),
        (b"not an xdf", lambda _path: (_ for _ in ()).throw(RuntimeError("bad magic"))),
        (b"mock", lambda _path: ([], {})),
    ],
)
def test_empty_corrupt_and_streamless_xdf_files_are_rejected(tmp_path, payload, loader):
    source = tmp_path / "renamed.xdf"
    source.write_bytes(payload)

    with pytest.raises(XDFAnnotationError) as error:
        parse_xdf_annotations(str(source), loader=loader)

    assert "usable sleep stages, events, or markers" in error.value.public_message


def test_frontend_and_routes_assign_xdf_to_annotations_only():
    template = (ROOT / "app/templates/index.html").read_text()
    routes = (ROOT / "app/viewer/routes.py").read_text()

    assert 'id="fileUpload" name="file" accept=".edf,.EDF"' in template
    assert 'id="annotationUpload" accept=".txt,.TXT,.csv,.CSV,.tsv,.TSV,.xlsx,.XLSX,.xls,.XLS,.xdf,.XDF"' in template
    assert "'.xdf'" in routes.split("_ANNOTATION_EXTS", 1)[1].split("}", 1)[0]
    assert "xdfStreamModal" not in template


def test_xdf_annotation_upload_is_converted_and_original_is_removed(tmp_path, monkeypatch):
    import pyxdf
    from app import create_app, db
    from app.models.user import User

    upload_root = tmp_path / "uploads"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "DATA_PATH": str(upload_root),
        "SPA_JOB_CACHE_ROOT": str(tmp_path / "jobs"),
        "SESSION_TYPE": "filesystem",
    })
    with app.app_context():
        user = User(email="xdf-annotation@example.invalid")
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    monkeypatch.setattr(
        pyxdf,
        "load_xdf",
        lambda _path: ([_signal(), _markers()], {}),
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post(
        "/viewer/upload_annotation",
        data={
            "annotation_file": (io.BytesIO(b"mock xdf payload"), "stages.xdf"),
            "edf_filename": "recording.edf",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "stages_xdf_annotations.csv" in response.get_json()["redirect"]
    user_dir = upload_root / str(user_id)
    assert not (user_dir / "stages.xdf").exists()
    converted = user_dir / "stages_xdf_annotations.csv"
    assert converted.exists()
    assert converted.read_text().splitlines()[0] == "Onset,Duration,Description"
