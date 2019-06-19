#
# Copyright 2019 Ramble Lab
#

from flask import current_app
from google.cloud import firestore, exceptions
from datetime import datetime, timezone, timedelta
from tzlocal import get_localzone

db = firestore.Client()


class Mutex(object):
    def __init__(self, resource=None, team_id=None, locked=False, owner=None, channel=None, waiting='', reason=''):
        self.resource = resource
        self.team_id = team_id
        self.locked = locked
        self.owner = owner
        self.channel = channel
        self.waiting = waiting
        self.reason = reason
        self.expires = False
        self.expiration = datetime.now(timezone.utc)

    @staticmethod
    def from_dict(source):

        mutex = Mutex()

        mutex.resource = source[u'resource']
        mutex.team_id = source[u'team_id']

        
        if u'locked' in source:
            mutex.locked = source[u'locked']

        if u'owner' in source:
            mutex.owner = source[u'owner']

        if u'channel' in source:
            mutex.channel = source[u'channel']

        if u'waiting' in source:
            mutex.waiting = source[u'waiting']

        if u'reason' in source:
            mutex.reason = source[u'reason']

        if u'expires' in source:
            mutex.expires = source[u'expires']

        if u'expiration' in source:
            mutex.expiration = source[u'expiration']

        return mutex


    def to_dict(self):

        dest = {}

        dest[u'resource'] = self.resource
        dest[u'team_id'] = self.team_id
        
        if self.locked:
            dest[u'locked'] = self.locked

        if self.owner:
            dest[u'owner'] = self.owner

        if self.channel:
            dest[u'channel'] = self.channel

        if self.waiting:
            dest[u'waiting'] = self.waiting

        if self.reason:
            dest[u'reason'] = self.reason

        if self.expires:
            dest[u'expires'] = self.expires

        if self.expiration:
            dest[u'expiration'] = self.expiration

        return dest
        

    def __repr__(self):
        return(
            u'Mutex(resource={}, team_id={}, locked={}, owner={}, channel={}, waiting={}, reason={}, expires={}, expiration={})'
            .format(self.resource, self.team_id, self.locked, self.owner, self.channel, self.waiting,
                    self.reason, self.expires, self.expiration))


def lock_mutex(team_id, channel_id, resource, user_id, reason, duration):
    success = False
    response_text = ''
    details_text = ''
    time_text = ''

    mutex_ref, mutex = get_mutex(team_id, resource)

    if mutex.locked == True:
        if not mutex.owner == user_id:
            if user_id not in mutex.waiting.split(' '):
                mutex.waiting = mutex.waiting + user_id + ' '
                mutex_ref.update(mutex.to_dict())
            response_text = '<@' + user_id + '> unable to lock ' + resource + '.'
            if mutex.expires == True:
                offset_time = mutex.expiration - timedelta(hours=7)
                time_text = 'until: ' + offset_time.strftime("%b %d %Y %H:%M")
            details_text = 'It\'s currently locked by <@' + mutex.owner + '> ' + time_text
            return success, response_text, details_text

    mutex.locked = True
    mutex.owner = user_id
    mutex.channel = channel_id
    mutex.waiting = ''
    mutex.reason = reason
    if not duration or duration == 0:
        mutex.expires = False
    else:
        mutex.expires = True
    mutex.expiration = datetime.now(timezone.utc) + timedelta(seconds=(duration))

    mutex_ref.set(mutex.to_dict())

    success = True 
    response_text = '<@' + user_id + '> *locked* ' + resource
    if len(reason) > 1:
        details_text = 'Reason: ' + reason 
    if not duration == 0:
        offset_time = mutex.expiration - timedelta(hours=7)
        details_text +='\nUntil: ' + offset_time.strftime("%b %d %Y %H:%M")
    return success, response_text, details_text


def unlock_mutex(team_id, resource, user_id):
    success = False
    response_text = ''
    details_text = ''

    mutex_ref, mutex = get_mutex(team_id, resource)

    if mutex.locked == True:
        if not mutex.owner == user_id:
            response_text = '<@' + user_id + '> unable to unlock ' + resource + '.'
            details_text = 'It\'s currently locked by <@' + mutex.owner + '>'
            return success, response_text, details_text
    else:
        response_text = '<@' + user_id + '> unable to unlock ' + resource + '.'
        details_text = 'It\'s already unlocked.'
        return success, response_text, details_text

    for user in mutex.waiting.split(' '):
        if len(user) > 1:
            details_text += '<@' + user + '> '

    mutex.locked = False
    mutex.owner = ''
    mutex.channel = ''
    mutex.waiting = ''
    mutex.reason = ''
    mutex.expires = False
    mutex.expiration = datetime.now(timezone.utc)

    mutex_ref.set(mutex.to_dict())

    success = True 
    response_text = '<@' + user_id + '> *unlocked* ' + resource
    return success, response_text, details_text


def get_mutex(team_id, resource):
    mutex_dict = None
    mutex_doc = None
    
    try:
        mutex_ref = db.collection(u'Resources').where(u'resource', u'==', resource).where(u'team_id', u'==', team_id)
        mutex_doc = next(mutex_ref.get())
        mutex_dict = mutex_doc.to_dict()
        mutex_ref = db.collection(u'Resources').document(mutex_doc.id)
    except:
        print(u'Mutex does not exist in database!')

    if mutex_dict is None:
        mutex = Mutex(resource=resource, team_id=team_id)
        mutex_ref = db.collection(u'Resources').document()
        mutex_ref.set(mutex.to_dict())
        mutex_dict = mutex.to_dict()

    mutex = Mutex.from_dict(mutex_dict)

    return mutex_ref, mutex

