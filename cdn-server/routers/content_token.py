'''
/api/v1/content_auth API

:maintainer : Steven Hessing <steven@byoda.org>
:copyright  : Copyright 2021, 2022, 2023
:license    : GPLv3
'''

from logging import getLogger

from uuid import UUID
from urllib.parse import urlparse
from urllib.parse import ParseResult

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

from byoda.datamodel.content_key import ContentKey
from byoda.datamodel.content_key import ContentKeyStatus

from byoda import config

_LOGGER = getLogger(__name__)

router = APIRouter(prefix='/api/v1/cdn/content', dependencies=[])

# This HTTP header is set by the nginx config of the nginx server
ORIGNAL_URL_HEADER = 'original-url'

# test curl:
# curl 'http://localhost/restricted/index.html?service_id=1&member_id=66e41ad6-c295-4843-833c-5e523d34cce1&asset_id=066a050a-03e6-43d5-8d77-9e14fba0ed3b&key_id=1' --header 'Authorization: 1234567890      # noqa: E501


@router.get('/asset')
async def content_token(request: Request, service_id: int = None,
                        member_id: UUID = None,
                        asset_id: UUID = None, key_id: int = None):
    '''
    This is an internal API called by a sub-request in nginx. It is
    not accessible externally
    '''

    _LOGGER.debug(
        f'Received request for token check, service_id={service_id}, '
        f'key_id={key_id}, member_id={member_id}, asset_id={asset_id}, '
        f'token={request.headers.get("Authorization")}'
    )

    if not service_id or not member_id or not asset_id or not key_id:
        _LOGGER.debug('Missing query parameters')
        raise HTTPException(
            403, 'Must specify service_id, member_id, asset_id, and key_id'
        )

    token: str = request.headers.get('Authorization')

    if not token:
        _LOGGER.debug('No token provided in Authorization header')
        raise HTTPException(403, 'No token provided')

    if token.startswith('Bearer ') or token.startswith('bearer '):
        token = token[7:]
        _LOGGER.debug(f'Extracted token: {token}')

    # Original URL header is set by nginx when it performs the sub-request
    # to authenticate the request
    original_url: str = request.headers.get(ORIGNAL_URL_HEADER)
    parsed_url: ParseResult = urlparse(original_url)
    if not parsed_url.path:
        _LOGGER.debug(f'Missing asset_id in URL: {original_url}')
        raise HTTPException(403, f'Missing asset_id in URL: {original_url}')

    # Here we check that the requested file is under a folder with as
    # name the asset_id. This is to prevent that a user can request
    # all restricted content with just one content token.
    path_elems = parsed_url.path.split('/')
    if not path_elems or str(asset_id) != path_elems[2]:
        _LOGGER.debug(f'Invalid asset_id in URL: {original_url}')
        raise HTTPException(403, f'Invalid asset_id in URL: {original_url}')

    keys = await ContentKey.get_content_keys(
        filepath=config.MEMBER_KEY_FILE.format(
            service_id=service_id, member_id=member_id
        ), status=ContentKeyStatus.ACTIVE
    )

    if not keys:
        _LOGGER.debug(f'No active keys found for member {member_id}')
        raise HTTPException(400, f'No keys found for member {member_id}')

    key_dict = {key.key_id: key for key in keys}

    key: ContentKey = key_dict.get(key_id)
    if not key:
        _LOGGER.debug(
            f'Key_id {key_id} specified in request for '
            f'member {member_id} does not exist'
        )
        raise HTTPException(
            400, f'No key found for key_id {key_id} of member {member_id}'
        )

    generated_token = key.generate_token(
        service_id=service_id, member_id=member_id, asset_id=asset_id
    )

    _LOGGER.debug(f'Looking for match with token: {generated_token}')

    if generated_token != token:
        _LOGGER.debug(
            f'Token mismatch for member {member_id}: '
            f'{token} != {generated_token}'
        )
        raise HTTPException(403, 'Invalid token')

    return None
