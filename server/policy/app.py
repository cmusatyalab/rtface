#!env/bin/python

import glob
import os
import simplejson
from flask_wtf import Form
from flask import render_template, request
from wtforms.fields.html5 import DateField, DateTimeField, IntegerField
from wtforms.fields import  SelectField, StringField
from wtforms import validators
from flask import Flask, send_from_directory
import redis
r_server = redis.StrictRedis('localhost')
app = Flask(__name__)

@app.route('/reversedenature')
def reverse_denature():
   pk=request.args.get('key')
   trange=request.args.get('time')
   img_paths=get_encrypted_img_path()
   return 'Hello, World!'

@app.route('/encrypted/<string:img_name>')
def encrypted(img_name):
   return send_from_directory('../encrypted', img_name)

# @app.route('/decrypted/<string:img_name>')
# def encrypted(img_name):
#    return send_from_directory('../encrypted', img_name)
   
@app.route('/imagenames/<string:search_pattern>')    
def imagenames(search_pattern):
   encrypted_dir='../encrypted'
   filepaths=glob.glob(encrypted_dir+'/'+search_pattern)
   imagenames=[os.path.basename(filepath) for filepath in filepaths]
   return simplejson.dumps(imagenames)

mech = [
   'showFace',
   'blurFace'
]

class policyForm(Form):
   uid=StringField('uid')#, validators=[validators.Required()])
   policy=StringField('policy')#, validators=[validators.Required()])
   # dt = DateField('DatePicker', format='%Y-%m-%d', validators=[validators.Required()])
   # time = IntegerField('TimePicker', validators=[validators.Required(), validators.NumberRange(min=0, max=12)])
   # timeformat = SelectField('TimeFormat', choices=[('am', 'am'), ('pm', 'pm')], validators=[validators.Required()])
   # number = IntegerField('number', validators=[validators.Required(), validators.NumberRange(min=0)])

@app.route('/mechanism', methods=['GET'])
def mechanism():
   return simplejson.dumps(mech)

policies={}
@app.route('/policy', methods=['GET', 'POST'])
def policy():
   form=policyForm(csrf_enabled=False)
   if form.validate_on_submit():
      print request.data
      print request.form
      uid=str(form.uid.data)
      policy=str(form.policy.data)
      policies[uid]=policy
      whitelist=r_server.lrange('whitelist',0,-1)
      if policy == 'showFace':
         if uid not in whitelist:
            r_server.rpush('whitelist', uid)
      elif policy == 'blurFace':
         if uid in whitelist:
            r_server.lrem('whitelist', 0, uid)
      return simplejson.dumps(policies)
   return render_template('policy.html', form=form)

@app.route('/add/<string:uid>', methods=['GET'])
def add_person(uid):
   people=r_server.lrange('people',0,-1)
   if uid not in people:
      r_server.rpush('people',uid)
      r_server.set('update',1)      
   return simplejson.dumps(r_server.lrange('people',0,-1))

@app.route('/remove/<string:uid>', methods=['GET'])
def rm_person(uid):
   people=r_server.lrange('people',0,-1)
#   whitelist=r_server.lrange('whitelist',0,-1) 
   if uid in people:
      r_server.lrem('people',0, uid)
      r_server.set('update',1)
   # if uid in whitelist:
   #    r_server.lrem('whitelist',0, uid)
   return simplejson.dumps(r_server.lrange('people',0,-1))
   
# @app.route('/reversedenatureimg/<string:img_path>')   
# def reverse_denature(img_path):
#    pk=request.args.get('key')
#    trange=request.args.get('time')
#    img_paths=get_encrypted_img_path()
#    return 'Hello, World!'
   
if __name__ == '__main__':
    app.run(debug=True, port=4000, host='0.0.0.0')
