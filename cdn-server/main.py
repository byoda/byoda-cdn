'''
CDN server for Bring Your Own Data and Algorithms

The CDN server has limited functionality. Currently it only
supports checking whether a 'content token' is valid

It is expected that going forward it will also support
sending Common Media Client Data (CMCD) to send client stats
sent using query parameters in the request for a video chunk
to a message bus.
(https://github.com/cta-wave/common-media-client-data)

:maintainer : Steven Hessing <steven@byoda.org>
:copyright  : Copyright 2021, 2022, 2023
:license    : GPLv3
'''

import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.content_token import router as CdnRouter
from .routers.status import router as StatusRouter

from byoda.util.logger import Logger

from byoda import config

_LOGGER = None
LOG_FILE = '/var/log/byoda/cdn.log'


app = FastAPI(
    title='cdn server', description='BYODA CDN server', version='0.0.1',
    debug=True
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],,
    expose_headers=['*'],
    max_age=86400,
)

app.include_router(CdnRouter)
app.include_router(StatusRouter)


@app.on_event('startup')
async def setup():
    global _LOGGER
    _LOGGER = Logger.getLogger(
        sys.argv[0], json_out=False, debug=config.debug | True,
        loglevel='DEBUG', logfile=LOG_FILE
    )
