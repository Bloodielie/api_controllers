import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.split(dir_path)[0])

import asyncio
from random import randint

import aiohttp
import sqlalchemy
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.configuration import config
from app.configuration.config_variables import writers
from app.core import urls
from app.core.middleware import FrontMiddleware
from app.utils.vk_api import VkApi
from app.utils.write_in_bd_data import Writer

app = FastAPI(title=config.TITLE, description=config.DESCRIPTION, version=config.VERSION, openapi_url=config.OPENAPI_URL)
app.include_router(urls.app, prefix='/api')
app.mount("/", StaticFiles(directory="./front"), name="static")

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], )


@app.on_event("startup")
async def startup() -> None:
    engine = sqlalchemy.create_engine(str(config.database.url))
    config.metadata.create_all(engine)
    await config.database.connect()

    loop = asyncio.get_running_loop()
    session = aiohttp.ClientSession(loop=loop)
    vk = VkApi(token=config.TOKEN_VK, session=session, loop=loop)

    bus_stop_writer = Writer(vk)
    for wr in writers:
        data = writers.get(wr)
        for info in data:
            await asyncio.sleep(randint(1, 3))
            asyncio.create_task(bus_stop_writer.write_in_database(info))

    app.add_middleware(FrontMiddleware,
                       static_directory=config.STATIC_DIRECTORY,
                       not_static_url=['api', app.docs_url, app.redoc_url], )


@app.on_event("shutdown")
async def shutdown() -> None:
    await config.database.disconnect()


if __name__ == "__main__":
    from os import environ

    port = environ.get('PORT')
    if port is None:
        uvicorn.run("main:app")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=int(port), log_level="info")
