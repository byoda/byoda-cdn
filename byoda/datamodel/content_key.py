'''
Class for modeling content keys

Content keys do not affect the content but are used to
restrict streaming & download access to the content.

This module is copied from byoda-python/byoda/datamodel/content_key.py
but all code around (SQL)Tables has been removed.

:maintainer : Steven Hessing <steven@byoda.org>
:copyright  : Copyright 2021, 2022, 2023
:license    : GPLv3
'''


import logging
from base64 import b64encode

from uuid import UUID
from enum import Enum
from datetime import datetime
from datetime import timezone
from datetime import timedelta

import orjson

from cryptography.hazmat.primitives import hashes


_LOGGER = logging.getLogger(__name__)

DEFAULT_KEY_START_DELAY: int = 86400
DEFAULT_KEY_EXPIRATION_DELAY: int = DEFAULT_KEY_START_DELAY + 86400


class ContentKeyStatus(Enum):
    # flake8: noqa=E221
    INACTIVE = 'inactive'
    ACTIVE   = 'active'
    EXPIRED  = 'expired'


class ContentKey:
    '''
    Manage keys under the /opt/byoda/keys directory
    '''

    def __init__(self, key: str, key_id: int, not_before: datetime,
                 not_after: datetime):
        '''
        Instantiate a ContentKey instance

        :param key: the key to sign tokens with
        :param key_id: the id of the key to sign/verify tokens
        :param not_before: what is the earliest date/time that the key can be
        used
        :param not after: what is the latest date/time that the key can be used
        '''

        self.key: str = key
        self.key_id: int = key_id
        if isinstance(not_before, str):
            self.not_before = datetime.fromisoformat(not_before)
        else:
            self.not_before: datetime = not_before

        if isinstance(not_after, str):
            self.not_after: datetime = datetime.fromisoformat(not_after)
        else:
            self.not_after: datetime = not_after

        self.table: None = None

        self.status = ContentKeyStatus.INACTIVE
        now = datetime.now(tz=timezone.utc)

        if self.not_before <= now:
            self.status: ContentKeyStatus = ContentKeyStatus.ACTIVE

        if self.not_after <= now:
            self.status: ContentKeyStatus = ContentKeyStatus.EXPIRED

    def __lt__(self, other):
        '''
        We give precedence to the active key that has become most
        recently 'active'. This allows us to initially create keys
        with really long expiration and once we've confirmed key
        distribution to CDN server is stable, we can start creating
        keys with shorter expiration.
        '''

        if self.status == other.status:
            return self.not_before < other.not_before

        if self.status == ContentKeyStatus.EXPIRED:
            return False
        elif self.status == ContentKeyStatus.INACTIVE:
            return True
        elif self.status == ContentKeyStatus.ACTIVE:
            if other.status == ContentKeyStatus.EXPIRED:
                return False
            else:
                return True
        else:
            raise NotImplementedError(f'Unknown status: {self.status}')

    def as_dict(self):
        return {
            'key': self.key,
            'key_id': self.key_id,
            'not_before': self.not_before,
            'not_after': self.not_after,
        }

    @staticmethod
    async def create(key: str = None, key_id: int = None, not_before: datetime = None,
               not_after: datetime = None):
        '''
        Creates a new ContentKey instance. I

        :param key:
        :param key_id
        :param not_before: what is the earliest date/time that the key can be
        used. If not specified, it defaults to 24 hours after the key is created
        :param not_after: what is the latest date/time that the key can be used.
        If not specified, it defaults to 48 hours after the key is created
        :returns: ContentKey
        '''

        if key_id is None:
            raise ValueError('key_id must be specified')

        if not_before is None:
            not_before: datetime = (
                datetime.now(tz=timezone.utc) +
                timedelta(seconds=DEFAULT_KEY_START_DELAY)
            )

        if not_after is None:
            not_after: datetime = (
                datetime.now(tz=timezone.utc) +
                timedelta(DEFAULT_KEY_EXPIRATION_DELAY)
            )

        return ContentKey(key, key_id, not_before, not_after)

    async def persist(self, table = None):
        '''
        Persist the key to the sql table
        '''

        raise NotImplementedError('persist() not implemented for the CDN')

    @staticmethod
    async def get_content_keys(filepath: str = None,
                               status: ContentKeyStatus = None) -> list:
        '''
        Gets the restricted content keys from the file and returns a
        list of ContentKey instances. The returned list is sorted
        based on most recent not_before timestamp.

        key: str, key_id: int, not_before: datetime, not_after: datetime
        :param status: optional ContentKeyStatus to filter the results
        :returns: list of ContentKey instances
        :raises: ValueError if an element of data does not contain the
        required fields
        '''

        if not filepath:
            raise ValueError('filepath must be specified')

        try:
            with open(filepath, 'rb') as file_desc:
                data = orjson.loads(file_desc.read())
        except FileNotFoundError:
            _LOGGER.debug(f'File {filepath} not found')
            return []

        _LOGGER.debug(
            f'Found {len(data or ())} keys for restricted content in '
            f'file {filepath}'
        )

        keys: list[ContentKey] = []
        for item in data or ():
            if ('key' not in item or 'key_id' not in item or 'not_before' not in item
                    or 'not_after' not in item):
                raise ValueError(
                    f'Incompatible data: {", ".join(item.keys())}'
                )

            content_key = ContentKey(
                item['key'], item['key_id'], item['not_before'], item['not_after']
            )
            if not status or status == content_key.status:
                keys.append(content_key)

        keys.sort(reverse=True)

        _LOGGER.debug(
            f'Still got {len(keys)} keys after filtering for status {status}'
        )


        return keys

    @staticmethod
    async def get_active_content_key(filepath: str):
        '''
        Returns the most recent active content key from the file

        :param filepath: file with an array of elements, each with the fields
        key: str, key_id: int, not_before: datetime, not_after: datetime
        :returns: ContentKey or None
        '''

        active_keys = await ContentKey.get_content_keys(
            filepath=filepath, status=ContentKeyStatus.ACTIVE
        )

        if not active_keys:
            return None

        return active_keys[0]

    def generate_token(self, service_id: int, member_id: UUID | str,
                       asset_id: UUID | str) -> bytes:
        '''
        Generates a token for the given service_id and asset_id.
        '''

        digest = hashes.Hash(hashes.SHA3_224())
        digest.update(str(service_id).encode('utf-8'))
        digest.update(str(member_id).encode('utf-8'))
        digest.update(str(asset_id).encode('utf-8'))
        digest.update(self.key.encode('utf-8'))
        token = digest.finalize()

        encoded_token = b64encode(token).decode('utf-8')
        _LOGGER.debug(
            f'Generated token with service_id {service_id}, member_id: {member_id} '
            f'and asset_id: {asset_id} for key_id {self.key_id}: {encoded_token}'
        )

        return encoded_token

    def generate_url_query_parameters(self, service_id: int, member_id: UUID | str,
                                      asset_id: UUID | str) -> str:
        data = '&'.join(
            [
                f'service_id={service_id}',
                f'member_id={member_id}',
                f'asset_id={asset_id}',
            ]
        )

        return data











