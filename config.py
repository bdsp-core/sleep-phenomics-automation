import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-for-development'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    DATA_PATH = 'app/data/' # will probably need to change? Or migrate to AWS
    # PHI-bearing processing artifacts live outside app/static and are purged after
    # every run. This short fallback window covers abrupt process/host termination.
    SPA_JOB_CACHE_ROOT = os.environ.get('SPA_JOB_CACHE_ROOT') or os.path.join(basedir, 'instance', 'spa_jobs')
    SPA_JOB_RETENTION_SECONDS = int(os.environ.get('SPA_JOB_RETENTION_SECONDS', 3600))
    SPA_JOB_TIMEOUT_SECONDS = int(os.environ.get('SPA_JOB_TIMEOUT_SECONDS', 7200))
    SPA_RESULT_RETENTION_SECONDS = int(os.environ.get('SPA_RESULT_RETENTION_SECONDS', 3600))
    # Email (SMTP) settings — set these in .env
    MAIL_SERVER   = os.environ.get('MAIL_SERVER')    # e.g. 'smtp.gmail.com'
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # sender address
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_FROM     = os.environ.get('MAIL_FROM') or os.environ.get('MAIL_USERNAME')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
