import importlib.util
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
CAISR_ROOT = ROOT / "app/ml_models/CAISR-App"
SETUP_SCRIPT = CAISR_ROOT / "create_caisr_dockers.py"
README = ROOT / "README.md"


def load_setup_module():
    spec = importlib.util.spec_from_file_location("create_caisr_dockers", SETUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_model_builds_request_amd64_on_apple_silicon():
    setup = load_setup_module()

    with (
        patch.object(setup.platform, "machine", return_value="arm64"),
        patch.object(setup.platform, "system", return_value="Darwin"),
        patch.object(setup.subprocess, "check_call") as check_call,
    ):
        setup.create_docker("stage/Dockerfile", "stage")

    check_call.assert_called_once_with(
        ["docker", "build", "--platform", "linux/amd64", "-t", "caisr_stage", "."]
    )


def test_native_model_builds_stay_on_the_host_platform():
    setup = load_setup_module()

    with (
        patch.object(setup.platform, "machine", return_value="arm64"),
        patch.object(setup.platform, "system", return_value="Darwin"),
        patch.object(setup.subprocess, "check_call") as check_call,
    ):
        setup.create_docker("preprocess/Dockerfile", "preprocess")

    check_call.assert_called_once_with(
        ["docker", "build", "-t", "caisr_preprocess", "."]
    )


def test_headless_preprocess_and_report_do_not_install_pyqt():
    preprocess_requirements = (
        CAISR_ROOT / "preprocess/requirements_preprocess.txt"
    ).read_text()
    report_requirements = (CAISR_ROOT / "report/requirements_report.txt").read_text()

    assert "PyQt5" not in preprocess_requirements
    assert "PyQt5" not in report_requirements


def test_native_arm_images_use_h5py_release_with_python_wheels():
    requirement_files = [
        CAISR_ROOT / "preprocess/requirements_preprocess.txt",
        CAISR_ROOT / "resp/resp_requirements.txt",
        CAISR_ROOT / "report/requirements_report.txt",
    ]

    for requirements in requirement_files:
        assert "h5py==3.12.1" in requirements.read_text()


def test_mac_setup_enables_rosetta_and_runs_setup_from_caisr_context():
    readme = README.read_text()

    assert "--vm-type vz --vz-rosetta" in readme
    assert "cd app/ml_models/CAISR-App" in readme
