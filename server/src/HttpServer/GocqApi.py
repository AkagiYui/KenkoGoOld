import asyncio
import logging
import sys
from fastapi import Request
import requests
from fastapi import APIRouter
import Utils
from Utils import HttpResult as Result

Logger = Utils.get_logger(' Redirect')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


class GocqApi:

    def refresh_config(self):
        self.r.headers.update({
            'Authorization': f'Bearer {self.config["access_token"]}',
            'Content-Type': 'application/json',
        })
        self.base_url = 'http://127.0.0.1:'
        for _server in self.gocq_config['servers']:
            if 'http' not in _server.keys():
                continue
            self.base_url += str(_server['http']['port'])
            break
        Logger.debug(f'go-cqhttp Api URL: {self.base_url}')

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_config = shared_objects['gocq_config']
        self.server_config = shared_objects['server_config']

        self.r = requests.Session()
        self.base_url = ''
        self.refresh_config()

        self.router = APIRouter()

        @self.router.get('/{api_name}')
        @self.router.post('/{api_name}')
        def api_redirect(api_name: str, request: Request):
            body = asyncio.run(request.body())
            method = request.method
            if method == 'POST':
                response = self.r.post(f'{self.base_url}/{api_name}', data=body)
            elif method == 'GET':
                response = self.r.get(f'{self.base_url}/{api_name}', data=body)
            else:
                return Result.error(f'{method} is not supported')
            return Result.success(response.json())
