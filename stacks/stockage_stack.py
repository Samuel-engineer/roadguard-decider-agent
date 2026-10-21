from aws_cdk import RemovalPolicy, Stack
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class StockageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.rule_bucket = s3.Bucket(
            self,
            "RoadBucket",
            bucket_name=f"road-rule-bucket-{self.account}-{self.region}",  # Remplacez par un nom unique
            removal_policy=RemovalPolicy.DESTROY,  # Supprime le bucket lors de la destruction du stack
            auto_delete_objects=True,  # Supprime les objets lors de la destruction du bucket*
        )

        self.media_bucket = s3.Bucket(
            self,
            "MediaBucket",
            bucket_name=f"media-bucket-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,  # Supprime le bucket lors de la destruction du stack
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.POST],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    exposed_headers=["ETag"],
                    max_age=36600,
                )
            ],
        )

        # Bucket for Bedrock Data Automation supplemental storage.
        # Fixed name so OpenSearchStack can grant the KB role access to it
        # without a cross-stack dependency.

        # self.supplemental_bucket = s3.Bucket(
        #     self,
        #     "SupplementalBucket",
        #     bucket_name=f"bedrock-kb-supplemental-{self.account}-{self.region}",
        #     removal_policy=RemovalPolicy.DESTROY,  # Supprime le bucket lors de la destruction du stack
        #     auto_delete_objects=True,  # Supprime les objets lors de la destruction du bucket*
        # )
