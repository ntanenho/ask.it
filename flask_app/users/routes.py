from flask import render_template, url_for, redirect, request, Blueprint, session
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Mail, Message
from flask_app import db, bcrypt
from flask_app.models import User, Question
from flask_app.users.forms import RegistrationForm, LoginForm, UpdateUsernameForm, UpdateEmailForm, UpdatePasswordForm

import qrcode
import qrcode.image.svg as svg
import pyotp

from io import BytesIO

users = Blueprint("users", __name__)
mail = Mail()

@users.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed)
        db.session.add(user)
        db.session.commit()
        session['reg_username'] = user.username

        msg = Message("Welcome to Ask.it!",
            recipients=[user.email],
            body = "Hello " + user.username + ", thank you for registering to join the Ask.it community! We have attached the QR code " + "for you to download the authenticator app to obtain a login passcode each time you log back in."
        + "\nIf you did not set up an account with our community, please contact us at ask.itsender@gmail.com.")
        mail.send(msg)

        return redirect(url_for('users.tfa'))

    return render_template('register.html', form=form)

@users.route("/tfa")
def tfa():
    if 'reg_username' not in session:
        return redirect(url_for('main.index'))

    headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0' # Expire immediately, so browser has to reverify everytime
    }

    return render_template('tfa.html'), headers

@users.route("/qr_code")
def qr_code():
    if 'reg_username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['reg_username']).first()
    session.pop('reg_username')
    img = qrcode.make(user.get_auth_uri(), image_factory=svg.SvgPathImage)
    stream = BytesIO()
    img.save(stream)

    headers = {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0' # Expire immediately, so browser has to reverify everytime
    }

    return stream.getvalue(), headers

@users.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        print(user)

        if user is not None and bcrypt.check_password_hash(user.password, form.password.data) and form.otp.data == pyotp.TOTP(user.otp_secret).now():
            login_user(user)
            return redirect(url_for('main.index', username=form.username.data))

    return render_template('login.html', form=form)


@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@users.route("/account", methods=["GET", "POST"])
@login_required
def account():
    session['reg_username'] = current_user.username
    userForm = UpdateUsernameForm()
    emailForm = UpdateEmailForm()
    passwordForm = UpdatePasswordForm()
    print(request.form)
    if request.method == 'POST':
        if userForm.validate_on_submit():
            current_user.username = userForm.username.data
            db.session.commit()
            msg = Message("Updated Account Username",
                recipients=[current_user.email],
                body="Hello user at " + current_user.email + ", you have chosen to change your username to " + current_user.username + "."
                + "\nIf this was not you, please login to your account to change your account information.")
            mail.send(msg)
            return redirect(url_for('main.user_detail', username=current_user.username))
        elif emailForm.is_submitted() and emailForm.validate_on_submit():
            current_user.email = emailForm.email.data
            db.session.commit()
            msg = Message("Updated Account Email address",
                recipients=[current_user.email],
                body="Hello " + current_user.username + ", you have chosen to change your email." +
                "\nIf this was not you, please login to your account to change your account information.")
            mail.send(msg)
            return redirect(url_for('main.user_detail', username=current_user.username))
        elif passwordForm.is_submitted() and passwordForm.validate_on_submit():
            hashed = bcrypt.generate_password_hash(passwordForm.new_password.data).decode('utf-8')
            user = User.query.filter_by(username=current_user.username).first()
            user.password = hashed
            db.session.commit()
            msg = Message("Updated Account Password",
                recipients=[current_user.email],
                body="Hello " + current_user.username + ", you have chosen to change your password." +
                "\nIf this was not you, please contact us to recover your account information.")
            mail.send(msg)
            logout_user()
            return redirect(url_for('users.login'))

    userForm.username.data = current_user.username
    emailForm.email.data = current_user.email
    return render_template('account.html', title='Account', userForm=userForm, emailForm=emailForm, passwordForm=passwordForm)
