'''
config

provides global variables

:maintainer : Steven Hessing <steven@byoda.org>
:copyright  : Copyright 2021, 2022, 2023
:license    : GPLv3
'''

from typing import TypeVar

import aiohttp
import requests

from ssl import SSLContext

HttpSession = TypeVar('HttpSession')

# Enable various debugging options in the pod, including
# whether the GraphQL web page should be enabled.
debug: bool = False

# Test cases set the value to True. Code may evaluate whether
# it is running as part of a test case to accept function parameters
test_case: bool = False

# Pool of aiohttp sessions, used by pods and service- and directory server:
client_pools: dict[str, aiohttp.ClientSession] = {}

# Pool of requests sessions, used by podworker as it can't use asyncio.
sync_client_pools: dict[str, requests.Session] = {}

# This cache avoids having to load cert/key for each request that uses
# client SSL auth
ssl_contexts: dict[str, SSLContext] = {}

MEMBER_KEY_FILE = '/opt/byoda/keys/service-{service_id}/{member_id}-keys.json'
