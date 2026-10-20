import boto3
import json

client = boto3.client("sagemaker-runtime", region_name="us-east-1")

payload = {"state": "healthcheck",
            "questions": {
                "check": {
                    "type": "choice",
                    "instructions": "Is the system operational?",
                    "criteria": {
                        "ok": "System is functioning normally",
                        "error": "System has encountered an issue",
                    },
                }
            },
        }

response = client.invoke_endpoint(
    EndpointName="strands-decider-endpoint",
    ContentType="application/json",
    Body=json.dumps(payload),
)

result = json.loads(response["Body"].read())
print(result)