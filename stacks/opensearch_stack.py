import json

from aws_cdk import (
    Stack,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_opensearchserverless as oss,
)
from constructs import Construct

from .config import Settings


class OpenSearchStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        collection_name = "road-rule-col"
        index_name = "road-rule-col-index"
        cfg = Settings

        # 1. Encryption policy
        self.encryption_policy = oss.CfnSecurityPolicy(
            self,
            "AossEncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "Resource": [f"collection/{collection_name}"],
                            "ResourceType": "collection",
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        # 2. Network policy
        self.network_policy = oss.CfnSecurityPolicy(
            self,
            "AossNetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "ResourceType": "collection",
                            },
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "ResourceType": "dashboard",
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        # 3. Collection
        self.collection = oss.CfnCollection(
            self,
            "AossCollection",
            name=collection_name,
            type="VECTORSEARCH",
            description="Vector collection for Bedrock Knowledge Base",
        )

        self.collection.add_resource_dependency(self.encryption_policy)
        self.collection.add_resource_dependency(self.network_policy)

        # The default CDK bootstrap role executes CloudFormation resource handlers.
        cfn_execution_role_arn = self.format_arn(
            service="iam",
            region="",
            resource="role",
            resource_name=(f"cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}"),
        )
        self.data_access_policy = oss.CfnAccessPolicy(
            self,
            "AossIndexCreationAccessPolicy",
            name=f"{collection_name}-cfn-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/{index_name}"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DeleteIndex",
                                ],
                            }
                        ],
                        "Principal": [cfn_execution_role_arn],
                    }
                ]
            ),
        )

        self.index = oss.CfnIndex(
            self,
            "AossVectorIndex",
            collection_endpoint=self.collection.attr_collection_endpoint,
            index_name=index_name,
            settings=oss.CfnIndex.IndexSettingsProperty(
                index=oss.CfnIndex.IndexProperty(
                    knn=True, knn_algo_param_ef_search=100
                ),
                analysis=oss.CfnIndex.AnalysisProperty(
                    analyzer={
                        "analyser_key": oss.CfnIndex.AnalyzerItemsProperty(
                            filter=["lowercase", "asciifolding"],
                            tokenizer="standard",
                            type="custom",
                        )
                    }
                ),
            ),
            mappings=oss.CfnIndex.MappingsProperty(
                properties={
                    "vector": oss.CfnIndex.PropertyMappingProperty(
                        type="knn_vector",
                        dimension=cfg.embedding_dimension,
                        method=oss.CfnIndex.MethodProperty(
                            name="hnsw",
                            engine="faiss",
                            space_type="cosinesimil",
                        ),
                    ),
                    "text": oss.CfnIndex.PropertyMappingProperty(
                        type="text", analyzer="analyser_key"
                    ),
                    "metadata": oss.CfnIndex.PropertyMappingProperty(
                        type="text",
                        index=False,
                    ),
                }
            ),
        )

        # Collection must exist before index
        self.index.add_resource_dependency(self.collection)
        # The index data-plane API requires a policy before CloudFormation creates it.
        self.index.add_resource_dependency(self.data_access_policy)

        # ------------------------------------------------------------------ #
        # Bedrock Knowledge Base execution role + AOSS data access policy     #
        # Must live here (before KnowledgeBaseStack) so the policy is fully   #
        # propagated by the time Bedrock validates the KB storage config.     #
        # ------------------------------------------------------------------ #

        # Fixed role name so KnowledgeBaseStack can reference it by ARN
        # without creating a cross-stack CDK dependency.
        kb_role_name = "BedrockKBExecutionRole"

        self.kb_role = iam.Role(
            self,
            "BedrockKBExecutionRole",
            role_name=kb_role_name,
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        )

        # IAM permission to call AOSS data-plane APIs
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll", "aoss:DashboardsAccessAll"],
                resources=[self.collection.attr_arn],
            )
        )

        # IAM permission to invoke the embedding model
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:*::foundation-model/{cfg.embedding_model_id}",
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/us.{cfg.embedding_model_id}",
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/global.{cfg.embedding_model_id}",
                ],
            )
        )

        # IAM permission for Bedrock Data Automation (parsing)
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeDataAutomationAsync",
                    "bedrock:GetDataAutomationStatus",
                ],
                resources=["*"],
            )
        )

        # S3 permissions on the raw bucket (deterministic name — defined in IngestionStack).
        # We use the ARN directly to avoid a cross-stack CDK dependency.
        rule_bucket_arn = f"arn:aws:s3:::road-rule-bucket-{self.account}-{self.region}"
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject*", "s3:GetBucket*", "s3:List*"],
                resources=[rule_bucket_arn, f"{rule_bucket_arn}/*"],
            )
        )

        # S3 permissions on the supplemental bucket (deterministic name).
        # KnowledgeBaseStack creates this bucket with this fixed name.
        supplemental_bucket_arn = (
            f"arn:aws:s3:::bedrock-kb-supplemental-{self.account}-{self.region}"
        )
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject*",
                    "s3:GetBucket*",
                    "s3:List*",
                    "s3:PutObject*",
                    "s3:DeleteObject*",
                    "s3:Abort*",
                ],
                resources=[supplemental_bucket_arn, f"{supplemental_bucket_arn}/*"],
            )
        )

        # AOSS data access policy for the KB role — created here so it
        # propagates before KnowledgeBaseStack deploys the CfnKnowledgeBase.
        self.kb_data_access_policy = oss.CfnAccessPolicy(
            self,
            "KbAossAccessPolicy",
            name=f"{collection_name}-kb-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                ],
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                    "aoss:DeleteIndex",
                                ],
                            },
                        ],
                        "Principal": [
                            self.kb_role.role_arn,
                            f"arn:aws:iam::{self.account}:root",
                        ],
                    }
                ]
            ),
        )
