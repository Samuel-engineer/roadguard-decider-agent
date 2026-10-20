import boto3
from botocore.config import Config

_AWS_CONFIG = Config(retries={"max_attempts": 5, "mode": "adaptive"})
_S3 = boto3.client("s3", config=_AWS_CONFIG)
_BEDROCK_RUNTIME = boto3.client("bedrock-runtime", config=_AWS_CONFIG)
_BEDROCK_AGENT_RUNTIME = boto3.client("bedrock-agent-runtime", config=_AWS_CONFIG)
_SAGEMAKER_RUNTIME = boto3.client("sagemaker-runtime", config=_AWS_CONFIG)
