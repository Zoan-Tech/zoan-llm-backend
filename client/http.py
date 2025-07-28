import requests
import re


class HTTPClient:
    def __init__(self, base_url: str):
        # Initialize the HTTP client
        self.base_url = base_url

    def make_request(
        self,
        method: str,
        uri: str,
        json_data=None,
        headers=None,
        params=None,
        var=None,
        file=None,
        timeout_seconds=20
    ):
        """
        Make an HTTP request.
        """
        url = self.base_url + uri
        response = None
        # Process GET request
        if method == "GET":
            if ":var_" in url:
                url = self.replace_var_placeholder(url, var)

            # Make the GET request with the updated URL
            response = requests.get(url, headers=headers, params=params, timeout=timeout_seconds)
        # Process POST request
        elif method == "POST":
            response = requests.post(url, json=json_data, headers=headers, files=file, timeout=timeout_seconds)
        # Process PUT request
        elif method == "PUT":
            if ":var_" in url:
                url = self.replace_var_placeholder(url, var)
            response = requests.put(url, json=json_data, headers=headers, params=params, files=file,
                                    timeout=timeout_seconds)
        # Process DELETE request
        elif method == "DELETE":
            if ":var_" in url:
                url = self.replace_var_placeholder(url, var)
            response = requests.delete(url, headers=headers, params=params, timeout=timeout_seconds)

        resp = response.json()
        response.close()
        return resp

    def replace_var_placeholder(self, url: str, var: dict) -> str:
        # Extract all :var_ placeholders from the URL
        placeholders = re.findall(r":var_\w+", url)

        # Loop through each placeholder and replace it with the corresponding value from the var dictionary
        for placeholder in placeholders:
            var_key = placeholder[5:]
            if var_key in var:
                url = url.replace(placeholder, str(var[var_key]))

        return url