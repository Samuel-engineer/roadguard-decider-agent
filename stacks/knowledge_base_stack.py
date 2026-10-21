from aws_cdk import Stack
from aws_cdk import (
    aws_bedrock as bedrock,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_opensearchserverless as oss,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct

from .config import Settings


class KnowledgeBaseStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        collection: oss.CfnCollection,
        rule_bucket: s3.Bucket,
        supplemental_bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        collection_name = collection.name
        collection_arn = collection.attr_arn
        cfg = Settings()

        # Import the KB role by ARN to avoid a cross-stack CDK dependency cycle.
        # The role is created (with a fixed name) in OpenSearchStack, which
        # deploys before this stack, so the role exists by the time CDK
        # evaluates this reference.
        kb_role_arn = f"arn:aws:iam::{self.account}:role/BedrockKBExecutionRole"
        kb_role = iam.Role.from_role_arn(self, "BedrockKBExecutionRole", kb_role_arn)

        # Knowledge Base Bedrock
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "RoadRuleKnowledgeBase",
            name="road-rule-kb",
            role_arn=kb_role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/{cfg.embedding_model_id}",
                    supplemental_data_storage_configuration=bedrock.CfnKnowledgeBase.SupplementalDataStorageConfigurationProperty(
                        supplemental_data_storage_locations=[
                            bedrock.CfnKnowledgeBase.SupplementalDataStorageLocationProperty(
                                supplemental_data_storage_location_type="S3",
                                s3_location=bedrock.CfnKnowledgeBase.S3LocationProperty(
                                    uri=f"s3://{supplemental_bucket.bucket_name}/"
                                ),
                            )
                        ]
                    ),
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=collection_arn,
                    vector_index_name=f"{collection_name}-index",
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="vector",
                        text_field="text",
                        metadata_field="metadata",
                    ),
                ),
            ),
        )

        # Utilise try_find_child pour éviter un crash si l'ID interne change ou n'est pas encore instancié
        default_policy = kb_role.node.try_find_child("DefaultPolicy")
        if default_policy:
            self.knowledge_base.node.add_dependency(default_policy)

        # Source de données rattachée au bucket S3
        self.data_source = bedrock.CfnDataSource(
            self,
            "S3DataSource",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            name="rule-s3-datasource",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=rule_bucket.bucket_arn
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                parsing_configuration=bedrock.CfnDataSource.ParsingConfigurationProperty(
                    parsing_strategy="BEDROCK_DATA_AUTOMATION",
                    bedrock_data_automation_configuration=bedrock.CfnDataSource.BedrockDataAutomationConfigurationProperty(
                        parsing_modality="MULTIMODAL"
                    ),
                ),
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=350,
                        overlap_percentage=20,
                    ),
                ),
            ),
        )
