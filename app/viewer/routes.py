from flask import request, current_app, redirect, url_for, render_template, jsonify, send_file, make_response
from flask_login import current_user, login_required
from . import viewer_bp
from .data_processing import PSGDataManager
from ..models.user import PSGFile, PSGFileType, User, DerivedFile, ChannelMapping
from .. import db
import os
import numpy as np
import pandas as pd
import json
import shutil
import re
import mne
from werkzeug.datastructures import FileStorage
import tempfile
import io
import uuid
import queue
import threading
import logging
import pickle
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Response, stream_with_context
from .feature_extract import PSGFeatureComputation, FEATURE_RUNNING_TIMES
from .data_processing import MONTAGE_CHANNELS

# In-memory store for phenomics computation jobs: job_id -> dict
_phenotype_jobs = {}

MAX_CONCURRENT_JOBS = 3
_job_queue = []        # ordered list of queued job_ids
_jobs_lock = threading.Lock()

# Standard channels that are computed as (positive electrode) - (negative electrode)
REFERENTIAL_CHANNELS = {
    'F3-M2', 'F4-M1', 'C3-M2', 'C4-M1', 'O1-M2', 'O2-M1',
    'E1-M2', 'E2-M1', 'CHIN1-CHIN2',
}

# Maps each referential channel to its (positive, negative) electrode names
_referential_parts = {
    'F3-M2': ('F3', 'M2'), 'F4-M1': ('F4', 'M1'),
    'C3-M2': ('C3', 'M2'), 'C4-M1': ('C4', 'M1'),
    'O1-M2': ('O1', 'M2'), 'O2-M1': ('O2', 'M1'),
    'E1-M2': ('E1', 'M2'), 'E2-M1': ('E2', 'M1'),
    'CHIN1-CHIN2': ('CHIN1', 'CHIN2'),
}

ch_regex_patterns = {
    'F3-M2':      r'(EEG[:_\s-]*)*(?:F3[:_\s-]*[MA]|[MA]2[:_\s-]*F3)',
    'F4-M1':      r'(EEG[:_\s-]*)*(?:F4[:_\s-]*[MA]|[MA]1[:_\s-]*F4)',
    'C3-M2':      r'(EEG[:_\s-]*)*(?:C3[:_\s-]*[MA]|[MA]2[:_\s-]*C3)',
    'C4-M1':      r'(EEG[:_\s-]*)*(?:C4[:_\s-]*[MA]|[MA]1[:_\s-]*C4)',
    #'CZ-M1':      r'(EEG[:_\s-]*)*CZ[:_\s-]*[MA]',
    'O1-M2':      r'(EEG[:_\s-]*)*(?:O1[:_\s-]*[MA]|[MA]2[:_\s-]*O1)',
    'O2-M1':      r'(EEG[:_\s-]*)*(?:O2[:_\s-]*[MA]|[MA]1[:_\s-]*O2)',
    'E1-M2':      r'(?:E1[:_\s-]*[AM]|[AM]2[:_\s-]*E1|EOG[:_\s-]*1|EOG[:_\s(-]*L(EFT)?|LEOG)',
    'E2-M1':      r'(?:E2[:_\s-]*[AM]|[AM]1[:_\s-]*E2|EOG[:_\s-]*2|EOG[:_\s(-]*R(IGHT)?|REOG)',
    'CHIN1-CHIN2': r'(?:CHIN1[:_\s-]*CHIN2|EMG1[:_\s-]*EMG2|EMG[:_\s-]*CHIN|\bCHIN\b)',
    'ECG':        r'\bE[CK]G\d*\b',
    'SpO2':       r'(?:S[AP]O2|O2[:_\s-]*SAT|OXYGEN)',
    #'HR':         r'\b(HR|HEART[:_\s-]*RATE|PULSE|BPM)\b',
    'AIRFLOW':    r'(?:THERM|AIRFLOW|NASAL[-:_\s]*FLOW|(?<![A-Z\d\-_:\s])FLOW)',
    'CHEST':      r'(RIP)*[:_\s-]*(?:CHEST|THO)',
    'ABD':        r'(RIP)*[:_\s-]*ABD',
    'LAT':        r'(EMG[:_\s-]*)*(?:LAT|LEG[:_\s(-]*L(EFT)?|LEFT[:_\s-]*LEG)',
    'RAT':        r'(EMG[:_\s-]*)*(?:RAT|LEG[:_\s(-]*R(IGHT)?|RIGHT[:_\s-]*LEG)',
    'SNORE':      r'SNOR',
    'PTAF':       r'(?:NPT|PTAF|(?<![A-Z\d\-_:\s])PRES)',
}
       
ch_single_regex_patterns = {
    'F3':    r'(EEG[:_\s-]*)?F3(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'F4':    r'(EEG[:_\s-]*)?F4(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'C3':    r'(EEG[:_\s-]*)?C3(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'C4':    r'(EEG[:_\s-]*)?C4(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'O1':    r'(EEG[:_\s-]*)?O1(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'O2':    r'(EEG[:_\s-]*)?O2(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'M1':    r'^(EEG[:_\s-]*)?(M1|A1)(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'M2':    r'^(EEG[:_\s-]*)?(M2|A2)(?!\s*[-_:](?!\s*REF\b))(\s*[-_]?\s*REF)?\s*$',
    'E1':    r'(EOG\s*[-_]?\s*(L(?:EFT)?|1)|E1(\s*[-_]?\s*REF)?|LEOG)\s*$',
    'E2':    r'(EOG\s*[-_]?\s*(R(?:IGHT)?|2)|E2(\s*[-_]?\s*REF)?|REOG)\s*$',
    'CHIN1': r'(CHIN1|EMG\s*[-_]?\s*(1|CHIN)|\bCHIN\b)\s*$',
    'CHIN2': r'(CHIN2|EMG\s*[-_]?\s*2)\s*$',
}


@viewer_bp.route('/')
@login_required
def index():
    files = [x.original_filename for x in PSGFile.query.filter_by(user_id=current_user.id).all()]
    selected = request.args.get('selected', '')
    annotation_loaded = bool(request.args.get('annotation_loaded', ''))
    annot_file = request.args.get('annot_file', '') if annotation_loaded else ''
    return render_template('index.html', files=files, selected=selected,
                           annotation_loaded=annotation_loaded, annot_file=annot_file,
                           running_times=FEATURE_RUNNING_TIMES)

@viewer_bp.route('/docs/<feature>')
@login_required
def phenomics_docs(feature):
    """Serve a markdown documentation page for a phenomics feature."""
    allowed = {
        'sleep_staging_CAISR', 'band_power', 'spindle_slow_oscillation',
        'brain_age', 'eeg_connectivity', 'infraslow_oscillation',
        'arousal_burden', 'hrv', 'cardiopulmonary_coupling', 'plmi',
        'sleep_atonia_index', 'ahi', 'hypoxic_burden', 'self_similarity',
        'rrv', 'delta_hr', 'custom_phenotype',
    }
    if feature not in allowed:
        return "Documentation not found", 404
    md_url = url_for('static', filename=f'docs/phenomics/{feature}.md')
    return render_template('docs_viewer.html', title=feature.replace('_', ' ').title(), md_url=md_url)


@viewer_bp.route('/check_file_exists', methods=['POST'])
@login_required
def check_file_exists():
    """Check if a file with the same name already exists for the current user."""
    uploaded_file = request.files.get('file')
    if not uploaded_file:
        return jsonify({"error": "No file provided"}), 400
        
    # Get the original filename
    original_filename = uploaded_file.filename
    
    # Check if a file with this name already exists for the user
    existing_file = PSGFile.query.filter_by(
        original_filename=original_filename,
        user_id=current_user.id
    ).first()

    return jsonify({
        "exists": existing_file is not None,
        "filename": original_filename
    })

@viewer_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    uploaded_file = request.files.get('file')
    if not uploaded_file:
        return "No file provided", 400

    action = request.form.get('action', 'new')
    current_app.logger.debug(f"[upload] Request received: file='{uploaded_file.filename}' action='{action}'")

    try:
        original_filename = uploaded_file.filename

        current_app.logger.debug(f"[upload] Checking for existing file in DB")
        existing_file = PSGFile.query.filter_by(
            original_filename=original_filename,
            user_id=current_user.id
        ).first()

        if existing_file and action == 'replace':
            current_app.logger.debug(f"[upload] Existing file found — deleting before replace")
            delete_psg_file(existing_file)
            current_app.logger.debug(f"[upload] Saving uploaded file (replace)")
            psg_file = PSGDataManager.save_uploaded_file(uploaded_file, current_user)

        elif existing_file and action == 'rename':
            new_filename = generate_unique_filename(original_filename, current_user.id)
            current_app.logger.debug(f"[upload] Renaming to '{new_filename}'")
            file_content = uploaded_file.read()
            uploaded_file.seek(0)
            modified_file = FileStorage(
                stream=uploaded_file.stream,
                filename=new_filename,
                name=uploaded_file.name,
                content_type=uploaded_file.content_type,
                content_length=uploaded_file.content_length,
                headers=uploaded_file.headers
            )
            current_app.logger.debug(f"[upload] Saving uploaded file (rename)")
            psg_file = PSGDataManager.save_uploaded_file(modified_file, current_user)

        else:
            current_app.logger.debug(f"[upload] Saving uploaded file (new)")
            psg_file = PSGDataManager.save_uploaded_file(uploaded_file, current_user)

        current_app.logger.debug(f"[upload] File saved — redirecting to channel mapping")
        return redirect(url_for('viewer.channel_mapping', filename=psg_file.original_filename))

    except ValueError as e:
        return str(e), 400
    except Exception as e:
        current_app.logger.error(f"Error processing upload: {str(e)}")
        return "Error processing file", 500

_ANNOTATION_EXTS = {'.txt', '.csv', '.tsv', '.xlsx', '.xls'}

@viewer_bp.route('/use_example_annotation')
@login_required
def use_example_annotation():
    """Copy the bundled example annotation to the user's data directory and save parsed stages."""
    from .annotation_parser import parse_annotation
    example_path = os.path.join(current_app.root_path, 'static', 'example', 'example_annot.csv')
    user_dir = os.path.join(current_app.config['DATA_PATH'], str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    shutil.copy2(example_path, os.path.join(user_dir, 'example_annot.csv'))
    df = parse_annotation(file_path=example_path, separator=',', onset_col=1,
                          onset_coding='seconds', use_duration=True, duration_col=2,
                          use_end=False, end_col=3, stage_col=3, data_start_line=2)
    df.to_csv(os.path.join(user_dir, 'example_annot_stages.csv'), index=False)
    return jsonify({'annot_file': 'example_annot.csv'})


@viewer_bp.route('/upload_annotation', methods=['POST'])
@login_required
def upload_annotation():
    uploaded_file = request.files.get('annotation_file')
    edf_filename = request.form.get('edf_filename', '')
    if not uploaded_file:
        return jsonify({'error': 'No file provided'}), 400
    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    if ext not in _ANNOTATION_EXTS:
        return jsonify({'error': f'Unsupported format: {ext}'}), 400
    user_dir = os.path.join(current_app.config['DATA_PATH'], str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    uploaded_file.save(os.path.join(user_dir, uploaded_file.filename))
    return jsonify({'redirect': url_for('viewer.annotation_mapping',
                                        annot_file=uploaded_file.filename,
                                        edf_file=edf_filename)})


@viewer_bp.route('/annotation_mapping')
@login_required
def annotation_mapping():
    annot_file = request.args.get('annot_file', '')
    edf_file   = request.args.get('edf_file', '')
    ext = os.path.splitext(annot_file)[1].lower()
    return render_template('annotation_mapping.html',
                           annot_file=annot_file,
                           edf_file=edf_file,
                           is_txt=(ext == '.txt'))


@viewer_bp.route('/apply_annotation', methods=['POST'])
@login_required
def apply_annotation():
    from .annotation_parser import parse_annotation
    annot_file      = request.form.get('annot_file', '')
    edf_file        = request.form.get('edf_file', '')
    separator       = request.form.get('separator', ',')
    onset_col       = int(request.form.get('onset_col', 1))
    onset_coding    = request.form.get('onset_coding', 'seconds')
    use_duration    = 'use_duration' in request.form
    duration_col    = int(request.form.get('duration_col', 2))
    use_end         = 'use_end' in request.form
    end_col         = int(request.form.get('end_col', 3))
    stage_col       = int(request.form.get('stage_col', 4))
    data_start_line = int(request.form.get('data_start_line', 2))
    stage_map = {request.form.get(f'stage_{s}', s).strip(): s
                 for s in ('W', 'R', 'N1', 'N2', 'N3')
                 if request.form.get(f'stage_{s}', s).strip()}
    annot_path = os.path.join(current_app.config['DATA_PATH'],
                              str(current_user.id), annot_file)
    recording_start = None
    if onset_coding in ('time_no_date', 'time_with_date') and edf_file:
        psg = PSGFile.query.filter_by(original_filename=edf_file,
                                      user_id=current_user.id).first()
        if psg and psg.recording_date:
            recording_start = psg.recording_date
    df = parse_annotation(
        file_path=annot_path,
        separator=separator,
        onset_col=onset_col,
        onset_coding=onset_coding,
        use_duration=use_duration,
        duration_col=duration_col,
        use_end=use_end,
        end_col=end_col,
        stage_col=stage_col,
        data_start_line=data_start_line,
        stage_map=stage_map,
        recording_start=recording_start,
    )
    stages_path = os.path.join(current_app.config['DATA_PATH'], str(current_user.id),
                               os.path.splitext(annot_file)[0] + '_stages.csv')
    df.to_csv(stages_path, index=False)
    return jsonify({'stages': df.to_dict(orient='records'),
                    'count': len(df),
                    'edf_file': edf_file})


def generate_unique_filename(original_filename, user_id):
    """Generate a unique filename by adding a number suffix for files with duplicate names."""
    # Extract the base name and extension
    base_name, extension = os.path.splitext(original_filename)
    
    # Look for existing pattern of "name (n).ext"
    pattern = re.compile(r'^(.*?)(\s*\(\d+\))?$')
    match = pattern.match(base_name)
    if match:
        name_without_number = match.group(1)
    else:
        name_without_number = base_name
    
    # Find all existing files with similar names
    similar_files = PSGFile.query.filter(
        PSGFile.user_id == user_id,
        PSGFile.original_filename.like(f"{name_without_number}%{extension}")
    ).all()
    
    # If no similar files, just add (1)
    if not similar_files:
        return f"{base_name} (1){extension}"
    
    # Find the highest number currently in use
    max_number = 0
    pattern = re.compile(rf"^{re.escape(name_without_number)}\s*\((\d+)\){re.escape(extension)}$")
    
    for file in similar_files:
        match = pattern.match(file.original_filename)
        if match:
            number = int(match.group(1))
            max_number = max(max_number, number)
    
    # Create a new filename with the next number
    return f"{name_without_number} ({max_number + 1}){extension}"

def delete_psg_file(psg_file):
    """Delete a PSG file and all its associated derived files."""
    try:
        # Get the file's storage location
        main_file_path = psg_file.storage_path

        # Get all associated derived files
        derived_files = DerivedFile.query.filter_by(psg_file_id=psg_file.id).all()
        
        # Collect all file paths to remove
        file_paths_to_remove = [main_file_path]
        
        # Delete derived files from database and collect their paths
        for derived_file in derived_files:
            file_paths_to_remove.append(derived_file.storage_path)
            db.session.delete(derived_file)
        
        # Delete main PSG file record from database
        db.session.delete(psg_file)
        db.session.commit()
        
        # Delete physical files from storage
        for file_path in file_paths_to_remove:
            try:
                if os.path.exists(file_path):
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
            except Exception as e:
                current_app.logger.error(f"Error removing file {file_path}: {str(e)}")
                # Continue with other deletions even if one fails
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {str(e)}")
        db.session.rollback()
        return False

@viewer_bp.route('/load_psg', methods=['POST'])
@login_required
def load_psg():
    try:
        filename = request.form.get('filename')
        time_offset = float(request.form.get('offset', 0))
        duration = float(request.form.get('duration', 10))
        current_app.logger.debug(f"[load_psg] Request: file='{filename}' offset={time_offset}s duration={duration}s")

        current_app.logger.debug(f"[load_psg] Looking up file in DB")
        psg_file = PSGFile.query.filter_by(
            original_filename=filename,
            user_id=current_user.id
        ).first_or_404()

        # Gracefully ignore requests whose offset is at or beyond the recording end
        if time_offset >= psg_file.duration:
            current_app.logger.debug(f"[load_psg] Offset {time_offset}s >= recording length {psg_file.duration}s — returning empty")
            return json.dumps({
                'seg': [], 'channels': [], 'Fs': psg_file.sampling_rate,
                'num_samples': 0, 'index': int(time_offset / duration),
            }), 200, {'Content-Type': 'application/json'}

        current_app.logger.debug(f"[load_psg] Reading PSG segment from disk")
        seg, channel_1020, Fs, num_samples, eeg_start, recordingLength = \
            PSGDataManager.read_partial_edf(psg_file, time_offset, duration)
        current_app.logger.debug(f"[load_psg] Segment loaded: shape={seg.shape} channels={channel_1020} Fs={Fs}Hz")

        data = {
            'seg': seg.tolist(),
            'channels': channel_1020,
            'Fs': Fs,
            'num_samples': num_samples,
            'index': int(time_offset/duration),
        }

        if request.form.get('returnReport') == 'true':
            data['report'] = ""

        if request.form.get('initialRead') == 'true':
            current_app.logger.debug(f"[load_psg] Initial read — adding recording metadata")
            data.update({
                'max_ind': int(recordingLength/duration),
                'eeg_start': str(eeg_start),
                'recording_duration': recordingLength,
            })
            data['spikes'] = []

        current_app.logger.debug(f"[load_psg] Serializing response to JSON")
        try:
            if not isinstance(data.get('seg'), list):
                raise ValueError("Invalid seg data format")
            if not isinstance(data.get('channels'), list):
                raise ValueError("Invalid channels data format")

            json_response = json.dumps(data)
            response_size = len(json_response.encode('utf-8'))
            current_app.logger.debug(f"[load_psg] Response size: {response_size} bytes")

            if response_size > 10 * 1024 * 1024:
                current_app.logger.warning(f"[load_psg] Large response ({response_size} bytes) — downsampling")
                if len(data['seg']) > 0 and len(data['seg'][0]) > 10000:
                    downsample_factor = len(data['seg'][0]) // 10000
                    for i in range(len(data['seg'])):
                        data['seg'][i] = data['seg'][i][::downsample_factor]
                    data['Fs'] = data['Fs'] / downsample_factor
                    current_app.logger.debug(f"[load_psg] Downsampled by factor {downsample_factor}, effective Fs={data['Fs']:.1f}Hz")
                    json_response = json.dumps(data)

            current_app.logger.debug(f"[load_psg] Returning response")
            return json_response, 200, {'Content-Type': 'application/json'}

        except Exception as json_error:
            current_app.logger.error(f"JSON serialization error: {str(json_error)}")
            raise json_error
    
    except Exception as e:
        current_app.logger.error(f"Error loading PSG data: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_response = {
            'error': f"Failed to load PSG data: {str(e)}",
            'seg': [],
            'channels': [],
            'Fs': 256,
            'num_samples': 0,
            'index': 0
        }
        return json.dumps(error_response), 500, {'Content-Type': 'application/json'}

@viewer_bp.route('/delete_file', methods=['POST'])
@login_required
def delete_file():
    """Delete a PSG file and all its associated derived files."""
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "No filename provided"}), 400

        filename = data['filename']
        current_app.logger.debug(f"[delete_file] Request to delete file='{filename}'")

        current_app.logger.debug(f"[delete_file] Looking up file in DB")
        psg_file = PSGFile.query.filter_by(
            original_filename=filename,
            user_id=current_user.id
        ).first()

        if not psg_file:
            current_app.logger.debug(f"[delete_file] File not found in DB")
            return jsonify({"error": "File not found"}), 404

        current_app.logger.debug(f"[delete_file] Deleting file and derived records")
        if not delete_psg_file(psg_file):
            return jsonify({"error": "Error deleting file"}), 500

        # Also delete annotation files if provided
        annot_file = data.get('annot_file')
        if annot_file:
            user_dir = os.path.join(current_app.config['DATA_PATH'], str(current_user.id))
            for path in [
                os.path.join(user_dir, annot_file),
                os.path.join(user_dir, os.path.splitext(annot_file)[0] + '_stages.csv'),
            ]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        current_app.logger.error(f"Error removing annotation file {path}: {e}")

        current_app.logger.debug(f"[delete_file] Deletion successful")
        return jsonify({"success": True, "message": "File deleted successfully"}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@viewer_bp.route('/use_example')
@login_required
def use_example():
    """Copy the bundled example EDF into the user's account and go to channel mapping."""
    example_filename = 'example.edf'

    # If the user already has this file and it exists on disk, go straight to channel mapping
    existing = PSGFile.query.filter_by(
        original_filename=example_filename,
        user_id=current_user.id
    ).first()
    if existing:
        if os.path.exists(existing.storage_path):
            return redirect(url_for('viewer.channel_mapping', filename=example_filename))
        # Stale DB record — file was deleted from disk; remove the record and re-copy below
        delete_psg_file(existing)

    example_path = os.path.join(current_app.root_path, 'static', 'example', example_filename)
    if not os.path.exists(example_path):
        return f"Example file not found at {example_path}", 404

    with open(example_path, 'rb') as f:
        fs = FileStorage(stream=f, filename=example_filename)
        psg_file = PSGDataManager.save_uploaded_file(fs, current_user)

    return redirect(url_for('viewer.channel_mapping', filename=psg_file.original_filename))


@viewer_bp.route('/cancel_channel_mapping/<filename>')
@login_required
def cancel_channel_mapping(filename):
    """Delete a newly uploaded file when the user cancels channel mapping."""
    psg_file = PSGFile.query.filter_by(
        original_filename=filename,
        user_id=current_user.id
    ).first()
    if psg_file:
        delete_psg_file(psg_file)
    return redirect(url_for('viewer.index'))


@viewer_bp.route('/channel_mapping/<filename>')
@login_required
def channel_mapping(filename):
    """Display channel mapping screen for uploaded EDF file."""
    try:
        current_app.logger.debug(f"[channel_mapping] Request for file='{filename}'")

        current_app.logger.debug(f"[channel_mapping] Looking up file in DB")
        psg_file = PSGFile.query.filter_by(
            original_filename=filename,
            user_id=current_user.id
        ).first_or_404()

        current_app.logger.debug(f"[channel_mapping] Reading EDF channel list from disk")
        raw = mne.io.read_raw_edf(psg_file.storage_path, preload=False)
        edf_channels = raw.ch_names
        current_app.logger.debug(f"[channel_mapping] Found {len(edf_channels)} EDF channels")

        # Per-channel sampling rates
        try:
            import pyedflib
            edf_reader = pyedflib.EdfReader(psg_file.storage_path)
            raw_freqs = edf_reader.getSampleFrequencies()
            edf_reader._close()
            del edf_reader
            ch_freqs = {ch: int(raw_freqs[i]) for i, ch in enumerate(edf_channels)}
        except Exception:
            ch_freqs = {ch: int(raw.info['sfreq']) for ch in edf_channels}

        current_app.logger.debug(f"[channel_mapping] Loading existing mappings from DB")
        existing_mappings = psg_file.get_channel_mapping()

        current_app.logger.debug(f"[channel_mapping] Running auto-mapping")
        # Look up the most recently confirmed mapping from any other file belonging to this user
        previous_mapping = None
        if not existing_mappings:
            recent_file = (PSGFile.query
                           .filter(PSGFile.user_id == current_user.id,
                                   PSGFile.id != psg_file.id)
                           .order_by(PSGFile.id.desc())
                           .first())
            if recent_file:
                previous_mapping = recent_file.get_channel_mapping() or None
        auto_mappings = create_auto_mappings(MONTAGE_CHANNELS, edf_channels, existing_mappings, previous_mapping)
        current_app.logger.debug(f"[channel_mapping] Auto-mapped {len(auto_mappings)}/{len(MONTAGE_CHANNELS)} channels: {auto_mappings}")

        current_app.logger.debug(f"[channel_mapping] Rendering template")
        return render_template('channel_mapping.html',
                             filename=filename,
                             num_channels=len(edf_channels),
                             ch_freqs=ch_freqs,
                             edf_channels=edf_channels,
                             standard_channels=MONTAGE_CHANNELS,
                             auto_mappings=auto_mappings,
                             referential_channels=REFERENTIAL_CHANNELS)
                             
    except Exception as e:
        current_app.logger.error(f"Error in channel mapping: {str(e)}")
        return f"Error loading channel mapping: {str(e)}", 500


@viewer_bp.route('/save_channel_mapping', methods=['POST'])
@login_required
def save_channel_mapping():
    """Save the channel mapping and process the file."""
    try:
        filename = request.form.get('filename')
        current_app.logger.debug(f"[save_channel_mapping] Request for file='{filename}'")

        current_app.logger.debug(f"[save_channel_mapping] Looking up file in DB")
        psg_file = PSGFile.query.filter_by(
            original_filename=filename,
            user_id=current_user.id
        ).first_or_404()

        current_app.logger.debug(f"[save_channel_mapping] Parsing primary channel mappings from form")
        mapping_dict = {}
        for key, value in request.form.items():
            if key.startswith('mapping[') and key.endswith(']'):
                standard_channel = key[8:-1]
                if value:
                    mapping_dict[standard_channel] = value

        current_app.logger.debug(f"[save_channel_mapping] Merging reference (negative) electrode fields")
        for key, value in request.form.items():
            if key.startswith('mapping_ref[') and key.endswith(']'):
                standard_channel = key[12:-1]
                primary = mapping_dict.get(standard_channel, '')
                if value and primary and primary != 'DOES_NOT_EXIST':
                    mapping_dict[standard_channel] = f'{primary}|{value}'

        current_app.logger.debug(f"[save_channel_mapping] Final mapping ({len(mapping_dict)} channels): {mapping_dict}")
        current_app.logger.debug(f"[save_channel_mapping] Saving mapping to DB")
        psg_file.set_channel_mapping(mapping_dict)
        db.session.commit()
        current_app.logger.debug(f"[save_channel_mapping] Saved — redirecting to viewer")

        return redirect(url_for('viewer.index', selected=filename))
        
    except Exception as e:
        current_app.logger.error(f"Error saving channel mapping: {str(e)}")
        db.session.rollback()
        return f"Error saving channel mapping: {str(e)}", 500


def create_auto_mappings(standard_channels, edf_channels, existing_mappings=None, previous_mapping=None):
    """Create automatic channel mappings based on regex patterns.

    Priority order for each standard channel:
      1. existing_mappings (already confirmed for this file) — returned as-is
      2. previous_mapping: EDF channel name from last confirmed mapping, matched
         case-insensitively against this file's channel list
      3. Exact case-insensitive name match (standard channel name == EDF channel name)
      4. Regex match from ch_regex_patterns
      5. Referential electrode fallback (separate pos/neg electrode search)
    """
    if existing_mappings:
        return existing_mappings

    edf_channels_lower = {ch.lower(): ch for ch in edf_channels}

    auto_mappings = {}

    # Step 1: carry over previous mapping where the same EDF channel still exists
    if previous_mapping:
        for standard_ch, prev_edf_ch in previous_mapping.items():
            if standard_ch not in standard_channels:
                continue
            if '|' in prev_edf_ch:
                # Referential pair: both electrodes must be present
                pos, neg = prev_edf_ch.split('|', 1)
                if pos.lower() in edf_channels_lower and neg.lower() in edf_channels_lower:
                    auto_mappings[standard_ch] = (
                        f'{edf_channels_lower[pos.lower()]}|{edf_channels_lower[neg.lower()]}'
                    )
            elif prev_edf_ch.lower() in edf_channels_lower:
                auto_mappings[standard_ch] = edf_channels_lower[prev_edf_ch.lower()]

    # Step 2: for remaining channels, try exact match then regex
    for standard_ch in standard_channels:
        if standard_ch in auto_mappings:
            continue
        if standard_ch not in ch_regex_patterns:
            continue
        # Exact case-insensitive match takes priority over regex
        if standard_ch.lower() in edf_channels_lower:
            auto_mappings[standard_ch] = edf_channels_lower[standard_ch.lower()]
            continue
        pattern = re.compile(ch_regex_patterns[standard_ch], re.IGNORECASE)
        for edf_ch in edf_channels:
            if pattern.search(edf_ch):
                auto_mappings[standard_ch] = edf_ch
                break

    # Fallback for referential channels: if no pre-referenced channel was found,
    # try to find the positive and negative electrodes separately.
    compiled_electrode = {
        elec: re.compile(pat, re.IGNORECASE)
        for elec, pat in ch_single_regex_patterns.items()
    }
    for standard_ch in standard_channels:
        if standard_ch in auto_mappings:
            continue
        if standard_ch not in _referential_parts:
            continue
        pos_elec, neg_elec = _referential_parts[standard_ch]
        pos_ch = next((ch for ch in edf_channels
                       if compiled_electrode[pos_elec].search(ch)), None)
        neg_ch = next((ch for ch in edf_channels
                       if compiled_electrode[neg_elec].search(ch)), None)
        if pos_ch and neg_ch:
            auto_mappings[standard_ch] = f'{pos_ch}|{neg_ch}'

    return auto_mappings


def generate_hypno_png(pkl_bytes, recording_date_iso, stem, epoch_sec=30):
    """Generate a matplotlib PNG: hypnogram + optional event bars + optional EEG spectrogram."""
    from datetime import datetime, timedelta

    data = pickle.loads(pkl_bytes)

    rec_dt = None
    if recording_date_iso:
        try:
            rec_dt = datetime.fromisoformat(recording_date_iso)
        except Exception:
            pass

    # --- Determine which panels to include ---
    def load_events_pkl(key, exclude=None, include=None):
        df = data.get(key)
        if df is None or not hasattr(df, 'itertuples'):
            return []
        events = []
        for row in df.itertuples(index=False):
            desc = str(row.Description)
            if exclude and desc in exclude:
                continue
            if include and desc not in include:
                continue
            s = float(row.Onset)
            events.append((s / 3600, (s + float(row.Duration)) / 3600))
        return events

    _ss_raw     = data.get('sleep_stages_from_annotation', data.get('sleep_stages_CAISR', data.get('sleep_stages_USleep')))
    has_stages  = _ss_raw is not None
    has_spectro = 'psd_db' in data and 'psd_freq' in data
    apnea_evs   = (load_events_pkl('apnea_hypopnea_CAISR', exclude=['RERA']) or
                   load_events_pkl('apnea_hypopnea_from_annotation', exclude=['RERA']))
    arousal_evs = (load_events_pkl('arousal_CAISR') or
                   load_events_pkl('arousal_from_annotation'))
    plm_evs     = (load_events_pkl('limb_movement_CAISR', include=['periodic limb movement']) or
                   load_events_pkl('limb_movement_from_annotation', include=['periodic limb movement']))

    # Build panel list top→bottom: hypno, apnea?, arousal?, plm?, spectro?
    panels = [('hypno', 2.0)]
    if apnea_evs:   panels.append(('apnea',   0.5))
    if arousal_evs: panels.append(('arousal', 0.5))
    if plm_evs:     panels.append(('plm',     0.5))
    if has_spectro: panels.append(('spectro', 4.0))

    height_ratios = [h for _, h in panels]
    n_panels = len(panels)
    fig, axes = plt.subplots(n_panels, 1, figsize=(16, 2 + sum(height_ratios)),
                             gridspec_kw={'height_ratios': height_ratios, 'hspace': 0.08},
                             squeeze=False)
    axes = axes[:, 0]
    panel_axes = {name: axes[i] for i, (name, _) in enumerate(panels)}

    # --- Total hours ---
    total_hours = 8.0
    if has_stages:
        ss = _ss_raw.astype(float)
        total_hours = len(ss) * epoch_sec / 3600
    if has_spectro:
        n_ep = data['psd_db'].shape[0]
        total_hours = max(total_hours, n_ep * epoch_sec / 3600)

    # --- Hypnogram ---
    ax_hypno = panel_axes['hypno']
    if has_stages:
        t_hours = np.arange(len(ss)) * epoch_sec / 3600
        ax_hypno.step(t_hours, ss, where='post', color='black', linewidth=0.8)
        ax_hypno.set_ylim(0.5, 5.5)
        ax_hypno.set_yticks([1, 2, 3, 4, 5])
        ax_hypno.set_yticklabels(['N3', 'N2', 'N1', 'R', 'W'])
        ax_hypno.grid(axis='y', alpha=0.4)
    ax_hypno.set_ylabel('Stage')

    # --- Event bars ---
    def plot_event_ax(ax, events, label):
        for s, e in events:
            ax.axvspan(s, e, ymin=0.1, ymax=0.9, color='red', alpha=0.7)
        ax.set_ylim(-1, 1)
        ax.set_yticks([0])
        ax.set_yticklabels([label], fontsize=7)
        ax.tick_params(axis='y', length=0)

    if apnea_evs:   plot_event_ax(panel_axes['apnea'],   apnea_evs,   'Apnea')
    if arousal_evs: plot_event_ax(panel_axes['arousal'], arousal_evs, 'Arousal')
    if plm_evs:     plot_event_ax(panel_axes['plm'],     plm_evs,     'PLM')

    # --- Spectrogram ---
    if has_spectro:
        psd_db = data['psd_db']
        freq   = data['psd_freq']
        freq_mask = (freq >= 0.3) & (freq <= 25)
        psd_mean  = np.nanmean(psd_db, axis=1)[:, freq_mask]
        t_hours_sp = np.arange(psd_mean.shape[0]) * epoch_sec / 3600
        panel_axes['spectro'].pcolormesh(t_hours_sp, freq[freq_mask], psd_mean.T,
                                         vmin=-5, vmax=22, cmap='turbo', shading='auto')
        panel_axes['spectro'].set_ylim(0.3, 25)
        panel_axes['spectro'].set_ylabel('Freq (Hz)')

    # --- Shared x-axis ---
    tick_hours  = np.arange(0, total_hours + 0.001, 1.0)
    tick_labels = ([(rec_dt + timedelta(hours=h)).strftime('%H:%M') for h in tick_hours]
                   if rec_dt else [f'{int(h):02d}:00' for h in tick_hours])

    for ax in axes:
        ax.set_xlim(0, total_hours)
        ax.set_xticks(tick_hours)
        ax.set_xticklabels([])

    axes[-1].set_xticklabels(tick_labels, fontsize=8)
    axes[-1].set_xlabel('Time')

    fig.suptitle(f'PSG Summary: {stem}', fontsize=11)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def send_results_email(to_email, stem, csv_data, png_bytes, app):
    """Send phenomics results email with CSV and PNG attachments via SMTP."""
    _log = logging.getLogger(__name__)

    mail_server   = app.config.get('MAIL_SERVER')
    mail_port     = app.config.get('MAIL_PORT', 587)
    mail_use_tls  = app.config.get('MAIL_USE_TLS', True)
    mail_username = app.config.get('MAIL_USERNAME')
    mail_password = app.config.get('MAIL_PASSWORD')
    mail_from     = app.config.get('MAIL_FROM') or mail_username

    if not mail_server or not mail_username or not mail_password:
        _log.warning("Email not configured (MAIL_SERVER/MAIL_USERNAME/MAIL_PASSWORD missing) — skipping email")
        return

    msg = MIMEMultipart()
    msg['From']    = mail_from
    msg['To']      = to_email
    msg['Subject'] = f'SPA Sleep Phenomics Automation Results: {stem}'

    body = (
        f"Your SPA computation for '{stem}' is complete.\n\n"
        f"Attached files:\n"
        f"  • {stem}_phenotypes.csv  — computed phenomics\n"
        f"  • {stem}_hypnogram.png   — hypnogram and spectrogram\n"
    )
    msg.attach(MIMEText(body, 'plain'))

    # CSV attachment
    csv_part = MIMEBase('text', 'csv')
    csv_part.set_payload(csv_data.encode('utf-8') if isinstance(csv_data, str) else csv_data)
    encoders.encode_base64(csv_part)
    csv_part.add_header('Content-Disposition', f'attachment; filename="{stem}_phenotypes.csv"')
    msg.attach(csv_part)

    # PNG attachment
    png_part = MIMEBase('image', 'png')
    png_part.set_payload(png_bytes)
    encoders.encode_base64(png_part)
    png_part.add_header('Content-Disposition', f'attachment; filename="{stem}_hypnogram.png"')
    msg.attach(png_part)

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=60) as server:
            if mail_use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_from, to_email, msg.as_string())
        _log.info(f"Results email sent to {to_email}")
    except Exception as e:
        _log.error(f"Failed to send results email: {e}")


@viewer_bp.route('/start_phenotypes', methods=['POST'])
@login_required
def start_phenotypes():
    """Start a background phenomics computation job and return a job_id."""
    filename = request.form.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    psg_file = PSGFile.query.filter_by(
        original_filename=filename,
        user_id=current_user.id
    ).first()
    if not psg_file:
        return jsonify({'error': f"File '{filename}' not found"}), 404

    edf_path = psg_file.storage_path
    if not os.path.exists(edf_path):
        return jsonify({'error': 'EDF file not found on disk'}), 404

    channel_mapping = psg_file.get_channel_mapping()
    stem = os.path.splitext(filename)[0]
    notch_freq_raw = request.form.get('notch_freq', '60')
    notch_freq = None if notch_freq_raw == 'off' else float(notch_freq_raw)

    selected_features_raw = request.form.getlist('selected_features')
    selected_features = selected_features_raw if selected_features_raw else None

    annot_df = None
    annot_file = None
    if selected_features and 'from_annotation' in selected_features:
        annot_file = request.form.get('annot_file', '')
        if not annot_file:
            return jsonify({'error': 'Annotation file not specified.'}), 400
        stages_path = os.path.join(current_app.config['DATA_PATH'], str(current_user.id),
                                   os.path.splitext(annot_file)[0] + '_stages.csv')
        if not os.path.exists(stages_path):
            return jsonify({'error': 'Annotation stages not found. Please re-upload the annotation.'}), 400
        annot_df = pd.read_csv(stages_path)

    actual_age_raw = request.form.get('actual_age', '').strip()
    actual_age = float(actual_age_raw) if actual_age_raw else None

    quality_index_raw = request.form.get('quality_index', '').strip()
    quality_index = float(quality_index_raw) if quality_index_raw else None

    custom_code        = request.form.get('custom_code',        '').strip() or None
    custom_figure_code = request.form.get('custom_figure_code', '').strip() or None

    user_email = current_user.email
    user_id    = current_user.id
    flask_app  = current_app._get_current_object()
    data_path  = current_app.config['DATA_PATH']
    recording_date_iso = psg_file.recording_date.isoformat() if psg_file.recording_date else None

    job_id = str(uuid.uuid4())
    log_queue = queue.Queue()
    _phenotype_jobs[job_id] = {
        'log': log_queue,
        'csv': None,
        'pkl': None,
        'filename_stem': stem,
        'recording_date': recording_date_iso,
        'error': None,
        'done': False,
        'status': 'queued',
        'run_fn': None,
    }

    def run_job():
        _log = logging.getLogger(__name__)
        pkl_bytes = None
        csv_str = None
        result_dir = None
        try:
            def log_cb(msg):
                log_queue.put(('log', msg))

            pfc = PSGFeatureComputation(edf_path, channel_mapping, notch_freq=notch_freq, log_callback=log_cb,
                                        selected_features=selected_features, actual_age=actual_age,
                                        annot_df=annot_df, q=quality_index,
                                        custom_code=custom_code,
                                        custom_figure_code=custom_figure_code)
            df_feat, detections = pfc.run()

            buf = io.StringIO()
            df_feat.iloc[0].to_csv(buf, index=True, header=False)
            csv_str = buf.getvalue()
            _phenotype_jobs[job_id]['csv'] = csv_str

            pkl_bytes = pickle.dumps(detections)
            _phenotype_jobs[job_id]['pkl'] = pkl_bytes

            # Persist results to disk so they survive session closure / server restarts
            result_dir = os.path.join(data_path, str(user_id))
            os.makedirs(result_dir, exist_ok=True)
            csv_path = os.path.join(result_dir, f'{stem}_phenotypes.csv')
            pkl_path = os.path.join(result_dir, f'{stem}_detections.pkl')
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write(csv_str)
            with open(pkl_path, 'wb') as f:
                f.write(pkl_bytes)

        except Exception as e:
            import traceback
            _phenotype_jobs[job_id]['error'] = str(e)
            _log.error(f"Phenomics job {job_id} failed: {traceback.format_exc()}")
        finally:
            # Signal done immediately so the frontend can show the panel without
            # waiting for the email step, which may block if SMTP is unreachable.
            _phenotype_jobs[job_id]['done'] = True
            _phenotype_jobs[job_id]['status'] = 'done'
            log_queue.put(('done', None))
            _try_dequeue()

        # Send results email after signalling done so the UI is not blocked
        if not _phenotype_jobs[job_id]['error'] and user_email and pkl_bytes and result_dir:
            def log_cb(msg):  # redefine after finally block
                _log.info(msg)
            try:
                png_bytes = generate_hypno_png(pkl_bytes, recording_date_iso, stem)
                png_path = os.path.join(result_dir, f'{stem}_hypnogram.png')
                with open(png_path, 'wb') as f:
                    f.write(png_bytes)
                send_results_email(user_email, stem, csv_str, png_bytes, flask_app)
                _log.info(f"Results emailed to {user_email}.")
            except Exception as email_err:
                _log.error(f"Email step failed: {email_err}")

        # Clean up generated files, annotation files, and the source EDF from disk
        annot_paths = []
        if annot_file and result_dir:
            annot_paths = [
                os.path.join(result_dir, annot_file),
                os.path.join(result_dir, os.path.splitext(annot_file)[0] + '_stages.csv'),
            ]
        for path in [
            os.path.join(result_dir, f'{stem}_phenotypes.csv') if result_dir else None,
            os.path.join(result_dir, f'{stem}_detections.pkl') if result_dir else None,
            os.path.join(result_dir, f'{stem}_hypnogram.png') if result_dir else None,
            edf_path,
            *annot_paths,
        ]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as cleanup_err:
                    _log.error(f"Cleanup failed for {path}: {cleanup_err}")

    _phenotype_jobs[job_id]['run_fn'] = run_job

    with _jobs_lock:
        active = sum(1 for j in _phenotype_jobs.values() if j.get('status') == 'running')
        if active < MAX_CONCURRENT_JOBS:
            _phenotype_jobs[job_id]['status'] = 'running'
            threading.Thread(target=run_job, daemon=True).start()
            return jsonify({'job_id': job_id, 'queued': False})
        else:
            _job_queue.append(job_id)
            position = len(_job_queue)
            log_queue.put(('queued', position))
            return jsonify({'job_id': job_id, 'queued': True, 'position': position, 'max_jobs': MAX_CONCURRENT_JOBS})


def _try_dequeue():
    """Start the next queued job if a slot is available. Call after any job finishes."""
    with _jobs_lock:
        active = sum(1 for j in _phenotype_jobs.values() if j.get('status') == 'running')
        if active < MAX_CONCURRENT_JOBS and _job_queue:
            next_id = _job_queue.pop(0)
            _phenotype_jobs[next_id]['status'] = 'running'
            # notify remaining queued jobs of their new positions
            for i, jid in enumerate(_job_queue):
                _phenotype_jobs[jid]['log'].put(('queued', i + 1))
            threading.Thread(target=_phenotype_jobs[next_id]['run_fn'], daemon=True).start()


@viewer_bp.route('/phenotypes_progress/<job_id>')
@login_required
def phenotypes_progress(job_id):
    """SSE stream that forwards log lines from a phenomics job to the browser."""
    job = _phenotype_jobs.get(job_id)
    if not job:
        return "Job not found", 404

    def generate():
        log_queue = job['log']
        while True:
            try:
                msg_type, msg = log_queue.get(timeout=60)
                if msg_type == 'log':
                    lines = str(msg).strip().splitlines()
                    yield "".join(f"data: {line}\n" for line in lines) + "\n"
                elif msg_type == 'queued':
                    yield f"event: queued\ndata: {msg}\n\n"
                elif msg_type == 'done':
                    if job['error']:
                        yield f"event: error\ndata: {job['error']}\n\n"
                    else:
                        yield f"event: done\ndata: ok\n\n"
                    break
            except queue.Empty:
                yield ": heartbeat\n\n"  # keep connection alive

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@viewer_bp.route('/phenotypes_download/<job_id>')
@login_required
def phenotypes_download(job_id):
    """Return the computed CSV."""
    job = _phenotype_jobs.get(job_id)
    if not job or not job['csv']:
        return "Result not available", 404

    response = make_response(job['csv'])
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = (
        f'attachment; filename="{job["filename_stem"]}_phenotypes.csv"'
    )
    return response


@viewer_bp.route('/phenotypes_viz_data/<job_id>')
@login_required
def phenotypes_viz_data(job_id):
    """Return hypnogram and spectrogram data as JSON for frontend plotting."""
    job = _phenotype_jobs.get(job_id)
    if not job or not job['pkl']:
        return jsonify({'error': 'Result not available'}), 404

    data = pickle.loads(job['pkl'])
    result = {'epoch_sec': 30, 'recording_date': job.get('recording_date')}

    ss_raw = data.get('sleep_stages_from_annotation', data.get('sleep_stages_CAISR', data.get('sleep_stages_USleep')))
    if ss_raw is not None:
        ss = ss_raw.astype(float)
        result['sleep_stages'] = [None if np.isnan(x) else float(x) for x in ss]

    if 'sleep_stages_prob_CAISR' in data:
        ssp = data['sleep_stages_prob_CAISR']
        def _col(name):
            return [None if np.isnan(v) else float(v) for v in ssp[name].values]
        result['hypnodensity'] = {
            't':      (ssp['Onset'].values / 3600).tolist(),
            'prob_r':  _col('prob_r'),
            'prob_w':  _col('prob_w'),
            'prob_n1': _col('prob_n1'),
            'prob_n2': _col('prob_n2'),
            'prob_n3': _col('prob_n3'),
        }

    if 'psd_db' in data and 'psd_freq' in data:
        psd_db = data['psd_db']           # (n_epochs, n_channels, n_freqs)
        freq   = data['psd_freq']          # (n_freqs,)
        freq_mask = (freq >= 0.3) & (freq <= 25)
        psd_mean = np.nanmean(psd_db, axis=1)  # (n_epochs, n_freqs)
        # Plotly heatmap expects z[i][j] = y[i], x[j] → shape (n_freqs, n_epochs)
        result['psd_db'] = psd_mean[:, freq_mask].T.tolist()
        result['freq']   = freq[freq_mask].tolist()

    def load_events(key, exclude=None, include=None):
        df = data.get(key)
        if df is None or not hasattr(df, 'itertuples'):
            return []
        events = []
        for row in df.itertuples(index=False):
            desc = str(row.Description)
            if exclude and desc in exclude:
                continue
            if include and desc not in include:
                continue
            s = float(row.Onset)
            events.append({'s': s / 3600, 'e': (s + float(row.Duration)) / 3600})
        return events

    result['apnea']   = (load_events('apnea_hypopnea_CAISR', exclude=['RERA']) or
                         load_events('apnea_hypopnea_from_annotation', exclude=['RERA']))
    result['arousal'] = (load_events('arousal_CAISR') or
                         load_events('arousal_from_annotation'))
    result['plm']     = (load_events('limb_movement_CAISR', include=['periodic limb movement']) or
                         load_events('limb_movement_from_annotation', include=['periodic limb movement']))

    if 'cpc' in data and 'cpc_freq' in data and 'cpc_t' in data:
        cpc_arr = np.array(data['cpc'],      dtype=float)  # (n_windows, n_freqs)
        freqs_c = np.array(data['cpc_freq'], dtype=float)
        tt_c    = np.array(data['cpc_t'],    dtype=float)
        # Downsample frequencies by 2 for a less-dense mountain plot
        cpc_arr = cpc_arr[:, ::2]
        freqs_c = freqs_c[::2]
        # Per-frequency normalisation: scale 95th-pct → half the median freq spacing
        delta_f = float(np.median(np.diff(freqs_c))) if len(freqs_c) > 1 else 0.004
        for fi in range(cpc_arr.shape[1]):
            col = cpc_arr[:, fi]
            p95 = float(np.nanpercentile(col, 95))
            if p95 > 0:
                cpc_arr[:, fi] = col / p95 * delta_f * 0.6
        result['cpc_spectrogram'] = {
            'tt':   tt_c.tolist(),
            'freq': freqs_c.tolist(),
            'cpc':  cpc_arr.tolist(),
        }

    if 'custom_figure_json' in data:
        result['custom_figure_json'] = data['custom_figure_json']

    return jsonify(result)


@viewer_bp.route('/phenotypes_download_npz/<job_id>')
@login_required
def phenotypes_download_npz(job_id):
    """Return the detections as a pickle file."""
    job = _phenotype_jobs.get(job_id)
    if not job or not job['pkl']:
        return "Result not available", 404

    response = make_response(job['pkl'])
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = (
        f'attachment; filename="{job["filename_stem"]}_detections.pkl"'
    )
    return response

