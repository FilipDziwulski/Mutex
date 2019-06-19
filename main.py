#
# Copyright 2019 Ramble Lab
#

# [START gae_python37_app]
import os
import json
import slack
from datetime import datetime, timezone
from mutex import lock_mutex, unlock_mutex, get_mutex
from flask import Flask, Response, request, jsonify
from google.auth.transport import requests
import google.oauth2.id_token
from google.cloud import firestore, exceptions
from util import is_number


# Load Env Vars from firestore
db = firestore.Client()
env_vars_ref = db.collection(u'SlackApp').document(u'env_variables')
env_vars = env_vars_ref.get().to_dict()

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)


@app.route('/slack/install', methods=['GET'])
def install():
    return '''
        <a href="https://slack.com/oauth/authorize?scope={0}&client_id={1}">
          Add to Slack
        </a>
    '''.format(env_vars["SLACK_BOT_SCOPE"], env_vars["SLACK_CLIENT_ID"])


@app.route('/slack/auth', methods=['GET', 'POST'])
def auth():

    # Retrieve the auth code from the request params
    auth_code = request.args['code']

    # An empty string is a valid token for this request
    client = slack.WebClient(token="")

    # Request the auth tokens from Slack
    response = client.oauth_access(
        client_id=env_vars["SLACK_CLIENT_ID"],
        client_secret=env_vars["SLACK_CLIENT_SECRET"],
        code=auth_code
    )

    tokens = {
        'access_token': response['access_token']
    }

    # Saving the token in association with the TeamID
    db = firestore.Client()
    settings_ref = db.collection(u'Settings').document(response['team_id'])
    settings_ref.set(tokens)

    # Let the user know that auth has succeeded!
    return "Auth complete!"


@app.route('/slack/tasks/check_expired', methods=['GET'])
def check_expired():
    
    # For every team, go through all of it's resources.
    # If a resource is locked and expired, unlock it and
    # notify the team

    print('Running periodic check_expired task.')

    resources_ref = db.collection(u'Resources')
    resources = resources_ref.get()

    for resource in resources:
        mutex_ref, mutex = get_mutex(resource.to_dict()[u'team_id'], resource.to_dict()[u'resource'])
        if mutex.locked == True:
            print('MUTEX EXPIRATION: ' + mutex.expiration.strftime("%b %d %Y %H:%M"))
            print('TIME NOW: ' + datetime.now(timezone.utc).strftime("%b %d %Y %H:%M"))
            if mutex.expires and datetime.now(timezone.utc) > mutex.expiration:
                send_exp_msg(resource.to_dict()[u'team_id'], resource.to_dict()[u'resource'], mutex)

                mutex.locked = False
                mutex.owner = ''
                mutex.channel = ''
                mutex.waiting = ''
                mutex.reason = ''
                mutex.expires = False
                mutex.expiration = datetime.now(timezone.utc)

                mutex_ref.set(mutex.to_dict())

    return "ok"

def send_exp_msg(team, resource, mutex):

    details_text = ''

    db = firestore.Client()
    settings_ref = db.collection(u'Settings').document(team)
    settings_dict = settings_ref.get().to_dict()

    client = slack.WebClient(token=settings_dict['access_token'])

    for user in mutex.waiting.split(' '):
        if len(user) > 1:
            details_text += '<@' + user + '> '

    details_json = json.dumps([{'text': details_text}])

    response = client.chat_postMessage(
    channel=mutex.channel,
    text="<@" + mutex.owner + "> Your lock of " + resource + " has expired!",
    attachments=details_json)


@app.route('/slack/lock', methods=['POST'])
def lock():
    team_id = request.values.get("team_id")
    user_name = request.values.get("user_name")
    user_id = request.values.get("user_id")
    channel_name = request.values.get("channel_name")
    channel_id = request.values.get("channel_id")
    text = request.values.get("text")

    if not team_id or not user_id or not channel_id or not channel_name:
        return 'Poorly formed request!', 400

    resource = channel_name
    duration = 0
    reason = ''

    if text:
        param_list = text.split(',', 2)
        if len(param_list) > 0:
            res = param_list[0].strip()
            if len(res) > 1:
                resource = res
        if len(param_list) > 1:
            if is_number(param_list[1].strip()):
                duration = int(float(param_list[1].strip())*60*60)
        if len(param_list) > 2:
            reas = param_list[2].strip()
            if len(reas) > 1:
                reason = reas
            

    success, response_text, details_text = lock_mutex(team_id, channel_id, resource, user_id, reason, duration)

    if success == True:
        response = {
            'response_type': 'in_channel',
            'as_user': False,
            'icon_url': 'https://image.flaticon.com/icons/svg/149/149462.svg',
            'channel': channel_id,
            'text': response_text,
            'attachments': [
                {
                    'text': details_text
                }
            ]
        }
    else:
        response = response = {
            'response_type': 'in_channel',
            'as_user': False,
            'icon_url': 'https://image.flaticon.com/icons/svg/149/149147.svg',
            'channel': channel_id,
            'text': response_text,
            'attachments': [
                {
                    'text': details_text
                }
            ]
        }

    return jsonify(response)



@app.route('/slack/unlock', methods=['POST'])
def unlock():
    team_id = request.values.get("team_id")
    user_name = request.values.get("user_name")
    user_id = request.values.get("user_id")
    channel_name = request.values.get("channel_name")
    channel_id = request.values.get("channel_id")
    text = request.values.get("text")

    if not team_id or not user_id or not channel_id or not channel_name:
        return 'Poorly formed request!', 400

    
    resource = channel_name
    
    if text:
        res = text.split(',', 1)[0].strip()
        if len(res) > 1:
            resource = res

    success, response_text, details_text = unlock_mutex(team_id, resource, user_id)

    if success == True:
        response = {
            'response_type': 'in_channel',
            'as_user': False,
            'icon_url': 'https://image.flaticon.com/icons/svg/149/149463.svg',
            'channel': channel_id,
            'text': response_text,
            'attachments': [
                {
                    'text': details_text
                }
            ]
        }
    else:
        response = {
            'response_type': 'in_channel',
            'as_user': False,
            'icon_url': 'https://image.flaticon.com/icons/svg/149/149147.svg',
            'channel': channel_id,
            'text': response_text, 
            'attachments': [
                {
                    'text': details_text
                }
            ]
        }

    return jsonify(response)


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
