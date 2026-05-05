from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models.user import User
from .forms import LoginForm, RegistrationForm, ForgotPasswordForm
from datetime import datetime
from . import auth_bp

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('auth.login'))
        except ValueError as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred, please try again later', 'error')
            print(f"Registration error: {str(e)}")
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST']) #TODO: add flask_limiter?
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'error')
            return redirect(url_for('auth.login'))
        
        # Update last login time
        user.last_login = datetime.now()
        db.session.commit()
        
        # Log the user in
        login_user(user, remember=form.remember_me.data)
        
        return redirect(url_for('viewer.index'))
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('viewer.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            try:
                db.session.delete(user)
                db.session.commit()
                flash('Your account has been deleted. Please register again.', 'info')
                return redirect(url_for('auth.register'))
            except Exception as e:
                db.session.rollback()
                flash('An unexpected error occurred. Please try again.', 'error')
        else:
            flash('No account found with that email address.', 'error')

    return render_template('auth/forgot_password.html', form=ForgotPasswordForm())