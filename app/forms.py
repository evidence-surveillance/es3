from flask_wtf import FlaskForm as Form
from wtforms import StringField, PasswordField, RadioField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo


class EmailPasswordForm(Form):
    """
    Login form
    """
    login_email = StringField('Email', validators=[DataRequired(message='Email address is required'), Email()])
    password = PasswordField('Password', validators=[DataRequired(message='Password is required')])
    submit = SubmitField(label='Login')


class PasswordForm(Form):
    """
    Reset password form
    """
    password = PasswordField('New password',
                             validators=[DataRequired(), EqualTo('password_conf', message='Passwords do not match')])
    password_conf = PasswordField('Confirm password')


class NewUserForm(Form):
    """
    Register new user form
    """
    new_email = StringField('Email', validators=[DataRequired(message='Email address is required'), Email()])
    nickname = StringField('Nickname', validators=[DataRequired(message='Nickname is required')])
    password = StringField('Initial Password', validators=[DataRequired(message='Password is required')])

    type = RadioField(label='Permissions',
                      validators=[DataRequired(message='Please specify the permission level of the new user')],
                      choices=[('admin', 'Admin'), ('standard', 'Standard')])
    submit = SubmitField(label='Create User')


class ForgotPasswordForm(Form):
    """
    Forgot password form
    """
    forgot_email = StringField('Email', validators=[DataRequired(message='Email address is required'), Email()])
    submit = SubmitField(label='Reset Password')


class ChangePasswordForm(Form):
    """
    Change password form
    """
    current_password = PasswordField('Current password',
                                     validators=[DataRequired(message='Current password is required')])
    new_password = PasswordField('New password', validators=[DataRequired(message='Current password is required')])
    confirm_password = PasswordField('Confirm new password',
                                     validators=[DataRequired(message='Current password is required')])
    submit = SubmitField(label='Change Password')


class RequestRegisterForm(Form):
    """
    Request account creation form
    """
    email = StringField('Email', validators=[DataRequired(message='Email address is required'), Email()])
    nickname = StringField('Name', validators=[DataRequired(message='Name is required')])
    submit = SubmitField(label='Request Access')
