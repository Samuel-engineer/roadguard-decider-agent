# stacks/web_stack.py

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

# Prérequis : exécuter `npm run build` dans web/ AVANT `cdk synth`/`cdk deploy`.
# Le build n'est PAS lancé pendant la synthèse pour garder celle-ci hermétique ;
# WEB_DIST_DIR doit déjà contenir le bundle produit par Vite.
WEB_DIST_DIR = "web/dist"


class WebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Bucket privé : tout accès public est bloqué, CloudFront y accède via OAC.
        # Style de construction aligné sur stacks/stockage_stack.py.
        self.site_bucket = s3.Bucket(
            self,
            "WebBucket",
            bucket_name=f"roadguard-web-{self.account}-{self.region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,  # Supprime le bucket lors de la destruction du stack
            auto_delete_objects=True,  # Supprime les objets lors de la destruction du bucket
        )

        # Distribution CloudFront avec Origin Access Control vers le bucket privé.
        # Les erreurs 403/404 sont réécrites vers /index.html (200) pour le routage
        # côté client de la SPA React.
        self.distribution = cloudfront.Distribution(
            self,
            "WebDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.site_bucket
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        # Déploiement du bundle prébuild (web/dist) vers le bucket, avec
        # invalidation du cache CloudFront.
        s3deploy.BucketDeployment(
            self,
            "WebDeployment",
            sources=[s3deploy.Source.asset(WEB_DIST_DIR)],
            destination_bucket=self.site_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(
            self,
            "WebDistributionDomain",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="URL CloudFront de l'application React (définir VITE_API_URL au build)",
        )
