from telegram.ext import Application
from iex_cloud_api import IEXCloudAPI


class BotApplication(Application):
    def __init__(self, iex_cloud_api_client: IEXCloudAPI, **kwargs):
        super().__init__(**kwargs)
        self.iex_cloud_api_client = iex_cloud_api_client
