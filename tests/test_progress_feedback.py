import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
PROGRESS_SCRIPT = ROOT / "app/static/progress.js"
INDEX_TEMPLATE = ROOT / "app/templates/index.html"


def run_progress_expression(expression):
    harness = """
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2], sandbox)));
"""
    completed = subprocess.run(
        ["node", "-e", harness, str(PROGRESS_SCRIPT), expression],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_upload_progress_reports_percent_and_estimated_time_remaining():
    result = run_progress_expression("SPAProgress.uploadSnapshot(50, 100, 5)")

    assert result == {"percent": 50, "remainingSeconds": 5}


def test_computation_progress_updates_but_waits_for_completion_to_reach_100():
    halfway = run_progress_expression("SPAProgress.computationSnapshot(60, 120)")
    overdue = run_progress_expression("SPAProgress.computationSnapshot(180, 120)")

    assert halfway == {"percent": 50, "remainingSeconds": 60}
    assert overdue == {"percent": 95, "remainingSeconds": 0}


def test_computation_estimate_includes_required_staging_without_double_counting():
    running_times = json.dumps(
        {
            "sleep_staging_CAISR": "10 minutes",
            "from_annotation": "1 second",
            "band_power": "10 seconds",
        }
    )
    caisr_result = run_progress_expression(
        f"SPAProgress.selectedFeatureEstimate(['sleep_staging_CAISR', 'band_power'], {running_times})"
    )
    annotation_result = run_progress_expression(
        f"SPAProgress.selectedFeatureEstimate(['from_annotation', 'band_power'], {running_times})"
    )

    assert caisr_result == 610
    assert annotation_result == 11


def test_existing_upload_and_computation_requests_keep_their_original_endpoints():
    source = INDEX_TEMPLATE.read_text()

    assert "xhr.open('POST', '/viewer/upload')" in source
    assert "xhr.send(formData)" in source
    assert "fetch('/viewer/start_phenotypes', { method: 'POST', body: formData })" in source
    assert "new EventSource('/viewer/phenotypes_progress/' + job_id)" in source
    assert "window.location.href = '/viewer/phenotypes_download/'" in source


def test_progress_windows_continue_updating_during_server_work():
    source = INDEX_TEMPLATE.read_text()

    assert "uploadProgressTimer = setInterval" in source
    assert "computationProgressTimer = setInterval" in source
    assert 'id="uploadProgressDetail"' in source
    assert 'id="phenomicsProgressStatus"' in source


def test_terminal_computation_error_does_not_trigger_reconnect_message():
    source = INDEX_TEMPLATE.read_text()

    assert "let terminalEventReceived = false" in source
    assert source.count("terminalEventReceived = true") == 2
    assert "if (terminalEventReceived) return" in source
