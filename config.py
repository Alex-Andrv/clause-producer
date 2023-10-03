import configparser

VERSION = '0.0.1'

import os
print(os.getcwd())

CONFIG_INI_PATH = os.environ.get('CONFIG_PATH', f'{os.path.dirname(__file__)}/../config.ini')

config = configparser.ConfigParser()
config.read(CONFIG_INI_PATH)

REDIS_HOST = config['redis']['host']
REDIS_PORT = config['redis']['port']
REDIS_DECODE_RESPONSES = config['redis']['decode_responses']