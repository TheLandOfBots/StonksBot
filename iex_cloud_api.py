import requests
from requests import HTTPError


class IEXCloudAPIError(Exception):
    pass


class IEXCloudAPI:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://cloud.iexapis.com/stable"

    def append_token(self, endpoint: str) -> str:
        return f"{endpoint}?token={self.token}"

    def get_stock_price(self, stock_symbol: str) -> float:
        endpoint = f"{self.base_url}/stock/{stock_symbol}/quote"
        url = self.append_token(endpoint)

        try:
            response = requests.get(url)
            response.raise_for_status()
            json_response = response.json()
            latest_price = float(json_response["latestPrice"])
            return round(latest_price, 2)
        except (HTTPError, KeyError):
            raise IEXCloudAPIError

    def get_crypto_price(self, crypto_symbol: str) -> float:
        endpoint = f"{self.base_url}/crypto/{crypto_symbol}USD/price"
        url = self.append_token(endpoint)
        try:
            response = requests.get(url)
            response.raise_for_status()
            price = float(response.json()["price"])
            return price
        except (HTTPError, KeyError):
            raise IEXCloudAPIError
