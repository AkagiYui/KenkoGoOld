import requests


class GocqApi:

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.base_url = config['server_base_url'] + '/api'
        self.r: requests = shared_objects['r']

    def send_group_msg(self, group_id: int, message: str, auto_escape: bool = False):
        response = self.r.post(f'{self.base_url}/send_group_msg', json={'group_id': group_id, 'message': message, 'auto_escape': auto_escape})

        return response.json()
