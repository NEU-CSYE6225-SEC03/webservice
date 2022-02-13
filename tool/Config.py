import yaml


class Config(object):
    with open('./config/config.yaml', encoding='utf-8') as f:
        __config = yaml.safe_load(f)

    @staticmethod
    def getInstance():
        return Config.__config
