"""Simple utilities on top of the API.
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

from goodkids.session import Json, Session, TastyApiError, get_data


def paginated_get(session: Session, url: str, *args, **kwargs) -> List[Json]:
    """Do a paginated GET request and accumulate all 'items' field in a list."""
    per_page = 1024

    page_offset = 0
    total_pages = None
    total_items = 0
    all_items = []
    while total_pages is None or page_offset < total_pages:
        logging.info(f"Getting page {page_offset} for {url}")
        params = kwargs.pop('params', {})
        params.update({'per-page': per_page,
                       'page-offset': page_offset})
        kwargs['params'] = params
        resp = session.relget(url, *args, **kwargs)
        if resp.status_code != 200:
            raise TastyApiError(f'Error in paginated requets at {url}', resp)

        page_offset += 1
        json = resp.json(use_decimal=True)
        if total_pages is None:
            pagination = json['pagination']
            total_pages = pagination['total-pages']
            total_items = pagination['total-items']

        items = json['data']['items']
        if items:
            all_items.extend(items)

    assert len(all_items) == total_items, (
        "Could not fetch some items in paginated request.")
    return all_items


def get_accounts(session: Session) -> List[Json]:
    """Return a list of active accounts."""
    resp = session.relget(f'/customers/me/accounts')
    if resp.status_code != 200:
        raise TastyApiError('Could not get trading accounts info', resp)
    items = get_data(resp)['items']
    accounts = [item['account'] for item in items if item['authority-level'] == 'owner']

    return [acc for acc in accounts if not acc['is-closed']]


def filter_matching_account(accounts: List[Json], regexp: Optional[str]) -> Json:
    """Filter down the list of accounts to those matching a single regexp."""
    if regexp:
        accounts = [account
                    for account in accounts
                    if any(re.search(regexp, account[field], flags=re.I)
                           for field in ['account-number', 'account-type-name',
                                         'nickname', 'external-id', 'margin-or-cash'])]
    if len(accounts) != 1:
        raise ValueError(f"More than a single account matches pattern '{regexp}': \n"
                         "{}".format(pprint.pformat(accounts)))
    return next(iter(accounts))
