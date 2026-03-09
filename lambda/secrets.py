import json
import os

import boto3

_secrets = None


def get_secrets() -> dict:
    """Fetch and cache API keys from SSM Parameter Store.

    Fetches two parameters: the main API keys JSON and the Google service account
    JSON (stored separately to avoid nesting issues). Cached after the first call.
    """
    global _secrets
    if _secrets is None:
        client = boto3.client("ssm", region_name=os.environ["AWS_REGION_NAME"])
        response = client.get_parameters(
            Names=[os.environ["SECRETS_PATH"], os.environ["GOOGLE_SA_PATH"]],
            WithDecryption=True,
        )
        params = {p["Name"]: p["Value"] for p in response["Parameters"]}
        _secrets = json.loads(params[os.environ["SECRETS_PATH"]])
        _secrets["GOOGLE_SERVICE_ACCOUNT"] = params[os.environ["GOOGLE_SA_PATH"]]
    return _secrets
