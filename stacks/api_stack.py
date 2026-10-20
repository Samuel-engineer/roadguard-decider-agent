# stacks/api_stack.py

from typing import cast

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from constructs import Construct

from .config import Settings


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        knowledge_base_id: str,
        media_bucket: s3.Bucket,
        decider_endpoint: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = Settings()

        # 1. Lambda d'inférence
        self.query_lambda = cast(
            _lambda.IFunction,
            _lambda.Function(
                self,
                "QueryHandler",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="main.lambda_handler",
                code=_lambda.Code.from_asset("functions"),
                timeout=Duration.seconds(60),  # Inférieur aux 30s max d'API Gateway
                memory_size=512,
                environment={
                    "KNOWLEDGE_BASE_ID": knowledge_base_id,
                    "MEDIA_BUCKET": media_bucket.bucket_name,
                    "DECIDER_ENDPOINT": decider_endpoint,
                    "VISION_MODEL_ID": cfg.vision_model_id,
                },
            ),
        )
        self.query_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:PutObject"],
                resources=[media_bucket.arn_for_objects("requests/*")],
            )
        )

        # 2. Permissions IAM for Bedrock retrieval/inference and SageMaker decisioning
        self.query_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:Retrieve"],
                resources=[
                    f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{knowledge_base_id}"
                ],
            )
        )
        self.query_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{cfg.vision_model_id}",
                    f"arn:aws:bedrock:*::foundation-model/{cfg.vision_model_id.removeprefix('us.')}",
                ],
            )
        )
        self.query_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sagemaker:InvokeEndpoint"],
                resources=["*"],
            )
        )

        media_bucket.grant_read_write(self.query_lambda)

        # 3. HTTP API Gateway v2
        http_api = apigw.HttpApi(
            self,
            "RoadHttpApi",
            api_name="EnterpriseRagHttpApi",
            description="Point d'entrée HTTP pour interroger le RAG",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.POST],
                allow_headers=["content-type"],
                max_age=Duration.hours(1),
            ),
        )

        # 4. Route POST /query liée à la Lambda
        lambda_integration = integrations.HttpLambdaIntegration(
            "LambdaInferenceIntegration",
            handler=self.query_lambda,
            timeout=Duration.seconds(29),
        )
        http_api.add_routes(
            path="/query",
            methods=[apigw.HttpMethod.POST],
            integration=lambda_integration,
        )
        http_api.add_routes(
            path="/uploads",
            methods=[apigw.HttpMethod.POST],
            integration=lambda_integration,
        )

        # 5. Output affichant l'URL utilisable après cdk deploy
        CfnOutput(
            self,
            "ApiEndpointUrl",
            value=f"{http_api.url}query",
            description="URL pour tester les requêtes POST",
        )
        CfnOutput(
            self,
            "UploadEndpointUrl",
            value=f"{http_api.url}uploads",
            description="URL pour obtenir une autorisation temporaire de téléversement S3",
        )
