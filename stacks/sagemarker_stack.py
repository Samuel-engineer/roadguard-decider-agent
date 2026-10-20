from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from constructs import Construct
from config import Settings

class SageMakerInferenceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        cfg = Settings()

        # 1. Build et Push automatique de l'image Docker via CDK
        # Assurez-vous que le paramètre `directory` pointe vers le dossier contenant votre Dockerfile
        docker_image = ecr_assets.DockerImageAsset(
            self,
            "StrandsDeciderImage",
            directory="./stacks/code",
            file="Dockerfile"
        )

        # 2. Rôle IAM pour SageMaker
        sagemaker_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ],
        )

        # 3. Autoriser spécifiquement SageMaker à télécharger cette image gérée par CDK
        docker_image.repository.grant_pull(sagemaker_role)

        # 4. Définition du Modèle (Utilise l'URI générée dynamiquement par DockerImageAsset)
        
        model = sagemaker.CfnModel(
            self,
            "StrandsDeciderModel",
            model_name="strands-decider-model",
            execution_role_arn=sagemaker_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                image=docker_image.image_uri,
                environment={
                    "MODEL_ID": "StrandsAgents/strands-decider-2B-hobson-v21",
                    "HF_TOKEN": cfg.hf_token
                },
            ),
        )


        # 5. Configuration de l'Endpoint
        endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "StrandsDeciderEndpointConfig",
            endpoint_config_name="strands-decider-config",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    model_name=model.attr_model_name,
                    variant_name="AllTraffic",
                    initial_instance_count=1,
                    instance_type="ml.g5.xlarge",
                    initial_variant_weight=1.0,
                    container_startup_health_check_timeout_in_seconds=900
                )
            ],
        )
        endpoint_config.add_resource_dependency(model)

        # 6. Création de l'Endpoint
        self.endpoint = sagemaker.CfnEndpoint(
            self,
            "StrandsDeciderEndpoint",
            endpoint_name="strands-decider-endpoint",
            endpoint_config_name=endpoint_config.attr_endpoint_config_name,
        )
        self.endpoint.add_resource_dependency(endpoint_config)

        CfnOutput(
            self,
            "SageMakerEndpointName",
            value=self.endpoint.attr_endpoint_name,
            description="Nom de l'Endpoint SageMaker",
        )

        CfnOutput(
            self,
            "DockerImageUri",
            value=docker_image.image_uri,
            description="URI de l'image Docker poussée sur ECR",
        )
