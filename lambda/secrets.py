import json
import os

import boto3

_secrets = None


def get_secrets() -> dict:
    """Fetch and cache API keys from AWS Secrets Manager.

    Returns the full secret as a dict. Cached after the first call so
    subsequent warm-invocation requests avoid an extra API call.
    """
    global _secrets
    if _secrets is None:
        client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION_NAME"])
        response = client.get_secret_value(SecretId=os.environ["SECRETS_ARN"])
        _secrets = json.loads(response["SecretString"])
    return _secrets
