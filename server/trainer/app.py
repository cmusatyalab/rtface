#! /usr/bin/env python2
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, request, jsonify
from flask_oauthlib.client import OAuth
import pdb
import os

app = Flask(__name__)
app.config['GOOGLE_ID'] = os.environ.get('GOOGLE_ID')
app.config['GOOGLE_SECRET'] = os.environ.get('GOOGLE_SECRET')
app.debug = True
app.secret_key = os.environ.get('VIDEO_TRAINER_SECRET')
oauth = OAuth(app)

google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_ID'),
    consumer_secret=app.config.get('GOOGLE_SECRET'),
    request_token_params={
        'scope': 'email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

@app.route('/')
@app.route('/index.html')
def index():
    if 'google_token' in session:
        uid=str(google.get('userinfo').data['email'])
        print('uid: {}'.format(uid))
        return render_template('index.html', uid=uid, authorized=True)
    return render_template('index.html', authorized=False)

@app.route('/js/<path:path>')
def send_js(path):
    print path
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/vendor/<path:path>')
def send_vendor(path):
    print path
    return send_from_directory('vendor', path)

@app.route('/images/<path:path>')
def send_images(path):
    return send_from_directory('images', path)
    
# @app.before_request
# def before_request():
#     if request.url.startswith('http://'):
#         url = request.url.replace('http://', 'https://', 1)
#         code = 301
#         return redirect(url, code=code)

@app.route('/login')
def login():
    return google.authorize(callback=url_for('authorized', _external=True))

@app.route('/logout')
def logout():
    session.pop('google_token', None)
    return redirect(url_for('index'))

@app.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')
    return redirect('/index.html', code=301)    

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')
    
if __name__ == '__main__':
    app.run(host='0.0.0.0',
            port=10002,
            debug=True,
    )
