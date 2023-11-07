"""Session handling code for the Tastytrade endpoints.
"""
__copyright__ = "Copyright (C) 2021  Martin Blais"
__license__ = "GNU GPLv2"

from functools import partial
from typing import Dict, List, Optional, Union
import datetime
import getpass
import logging
import shelve
import os
import re
import pprint
from os import path

import requests
from dateutil import parser


Json = Union[Dict[str, 'Json'], List['Json'], str, int, float]


API_URL = 'https://api.tastytrade.com'
SESSION_TOKEN_CACHE_FILENAME = '~/.tastytrade/scripts/token_cache'


class TastyApiError(Exception):
    """An error occurring due to authentications and/or token refresh."""
    def __init__(self, description, response):
        message = response.json()['error']['message']
        super().__init__(f'{description}: {message}')


class Session:
    """A simple requests session wrapper.
    This inserts the authentication token automatically.
    """
    def __init__(self, session_token):
        self.headers = {'Authorization': session_token}

    def __getattr__(self, name):
        """Delegate a call to requests, adding the auth token along the way."""
        func = getattr(requests, name)
        return partial(func, headers=self.headers)

    def relget(self, relative_url: str, *args, **kwargs):
        return self.get(f'{API_URL}{relative_url}', *args, **kwargs)

    def relpost(self, relative_url: str, *args, **kwargs):
        return self.post(f'{API_URL}{relative_url}', *args, **kwargs)


def get_session(username: Optional[str], password: Optional[str]) -> Session:
    """A simplistic one-off session getter with no storge nor refresh.
    (This will do for simple tasks.)"""

    cache_filename = path.expanduser(SESSION_TOKEN_CACHE_FILENAME)
    if path.exists(cache_filename):
        with open(cache_filename) as token_file:
            session_token = token_file.read().strip()
        logging.info(f'Reusing cached token "{session_token}" from "{cache_filename}"')

        # Attempt to validate the token.
        session = Session(session_token)
        resp = session.relpost('/sessions/validate')
        if resp.status_code == 201:
            return session
        else:
            logging.info('Expired session token; refreshing new token from credentials')
    else:
        logging.info('Invalid session cache; refreshing new token from credentials')

    # Get a new token from credentials.
    num_retry = 3
    orig_username = username
    orig_password = password
    for _ in range(num_retry):
        username = orig_username
        password = orig_password
        if username is None:
            username = os.getenv('TW_USER')
            if not username:
                username = getpass.getpass('Username: ')
        if password is None:
            password = os.getenv('TW_PASSWORD')
            if not password:
                password = getpass.getpass('Password: ')

        if not username.strip():
            raise TastyApiError(f'No username to acquire token')
        if not password.strip():
            raise TastyApiError(f'No password to acquire token for user {username}')

        resp = requests.post(f'{API_URL}/sessions', json={'login': username,
                                                          'password': password})
        if resp.status_code == 201:
            break
        logging.error(f'Failed to acquire token; try again?')
    else:
        raise TastyApiError(f'Could not log in after {num_retry} trials', resp)

    # Write out the new toklen
    session_token = get_data(resp)['session-token']
    os.makedirs(path.dirname(cache_filename), exist_ok=True)
    with open(cache_filename, 'w') as token_file:
        token_file.write(session_token)

    # Make sure it's valid.
    session = Session(session_token)
    resp = session.post(f'{API_URL}/sessions/validate')
    if resp.status_code != 201:
        raise TastyApiError(f'Could not validate session', resp)

    return session


def get_data(response: requests.Response) -> Json:
    """Get formatted response body with the right types."""
    return response.json(use_decimal=True)['data']


def get_approx_latest_time(db: shelve.Shelf) -> Optional[datetime.datetime]:
    """Return the approximately latest time."""
    # In order to do this, we find the largest id, and return the associated
    # date/time on that transaction. The ids are roughly, but not strictly,
    # incremental, so this should be good enough. The benefit of deriving the
    # latest time this way is that we don't have to do any housekeeping to keep
    # a special entry up-to-date, and we also don't have to parse any of the
    # values (this should scale a good amount).
    if len(db) == 0:
        return None
    max_id = max(db.keys())
    txn = db[max_id]
    return parser.parse(txn['executed-at'])
