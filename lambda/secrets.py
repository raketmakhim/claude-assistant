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
        sa_value = params[os.environ["GOOGLE_SA_PATH"]]
        # Handle double-encoded JSON (value stored as a JSON string in SSM)
        sa_parsed = json.loads(sa_value)
        _secrets["GOOGLE_SERVICE_ACCOUNT"] = json.loads(sa_parsed) if isinstance(sa_parsed, str) else sa_parsed
    return _secrets

