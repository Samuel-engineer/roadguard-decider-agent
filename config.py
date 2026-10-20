import os

from dotenv import load_dotenv

load_dotenv()

account = os.getenv("CDK_DEFAULT_ACCOUNT")
region = os.getenv("CDK_DEFAULT_REGION")


def get_environment_account():
    return {"account": account, "region": region}
