import json
import subprocess
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "app/static/script.js"


def run_go_right(*, current_index, next_index, recording_duration, max_index):
    harness = r"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(process.argv[1], "utf8");
const sandbox = {
    Chart: {defaults: {plugins: {tooltip: {}}}},
    console: {log() {}, error() {}},
    document: {},
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);

const result = vm.runInContext(`
    dur = 30;
    recordingDuration = ${RECORDING_DURATION};
    max_ind = ${MAX_INDEX};
    readPointer = 0;
    buffer = new Array(30).fill(null);
    buffer[0] = {index: ${CURRENT_INDEX}};
    buffer[1] = {index: ${NEXT_INDEX}};

    var alerts = [];
    var displayed = [];
    alert = message => alerts.push(message);
    display_segment = segment => displayed.push(segment.index);

    go_right();
    JSON.stringify({alerts, displayed, readPointer});
`, sandbox);
process.stdout.write(result);
"""
    harness = (
        harness.replace("${RECORDING_DURATION}", str(recording_duration))
        .replace("${MAX_INDEX}", str(max_index))
        .replace("${CURRENT_INDEX}", str(current_index))
        .replace("${NEXT_INDEX}", "null" if next_index is None else str(next_index))
    )
    completed = subprocess.run(
        ["node", "-e", harness, str(SCRIPT_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_go_to_end(*, current_index, recording_duration):
    harness = r"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(process.argv[1], "utf8");
const sandbox = {
    Chart: {defaults: {plugins: {tooltip: {}}}},
    console: {log() {}, error() {}},
    document: {},
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);

const result = vm.runInContext(`
    dur = 30;
    recordingDuration = ${RECORDING_DURATION};
    readPointer = 0;
    buffer = new Array(30).fill(null);
    buffer[0] = {index: ${CURRENT_INDEX}};

    var alerts = [];
    var jumpTimes = [];
    alert = message => alerts.push(message);
    jumpToTime = time => jumpTimes.push(time);

    go_to_end();
    JSON.stringify({alerts, jumpTimes});
`, sandbox);
process.stdout.write(result);
"""
    harness = (
        harness.replace("${RECORDING_DURATION}", str(recording_duration))
        .replace("${CURRENT_INDEX}", str(current_index))
    )
    completed = subprocess.run(
        ["node", "-e", harness, str(SCRIPT_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_forward_navigation_shows_popup_on_last_full_segment():
    result = run_go_right(
        current_index=3,
        next_index=None,
        recording_duration=120,
        max_index=4,
    )

    assert result == {
        "alerts": ["You have reached the end of the sleep study."],
        "displayed": [],
        "readPointer": 0,
    }


def test_forward_navigation_shows_popup_on_last_partial_segment():
    result = run_go_right(
        current_index=3,
        next_index=None,
        recording_duration=100,
        max_index=3,
    )

    assert result["alerts"] == ["You have reached the end of the sleep study."]
    assert result["readPointer"] == 0


def test_forward_navigation_still_advances_before_end():
    result = run_go_right(
        current_index=2,
        next_index=3,
        recording_duration=120,
        max_index=4,
    )

    assert result == {"alerts": [], "displayed": [3], "readPointer": 1}


def test_move_to_end_jumps_silently_when_before_last_page():
    result = run_go_to_end(current_index=1, recording_duration=120)

    assert result == {"alerts": [], "jumpTimes": [90]}


def test_move_to_end_shows_popup_only_when_already_on_last_page():
    result = run_go_to_end(current_index=3, recording_duration=120)

    assert result == {
        "alerts": ["You have reached the end of the sleep study."],
        "jumpTimes": [],
    }
