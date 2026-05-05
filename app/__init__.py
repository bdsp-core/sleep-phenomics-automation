import os
from flask import Flask, session, redirect, url_for
from config import Config
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
from flask_login import LoginManager, login_required, current_user
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
from .models.user import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev', # will be overridden by config
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_object(Config)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)


    db.init_app(app)
    Session(app)
    login_manager.init_app(app)
    
    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .viewer import viewer_bp
    app.register_blueprint(viewer_bp)

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('viewer.index'))
        return redirect(url_for('auth.login'))

    with app.app_context():
        db.create_all()

    

    return app