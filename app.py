import aws_cdk as cdk

from config import get_environment_account
from stacks.api_stack import ApiStack
from stacks.knowledge_base_stack import KnowledgeBaseStack
from stacks.opensearch_stack import OpenSearchStack
from stacks.sagemarker_stack import SageMakerInferenceStack
from stacks.stockage_stack import StockageStack

env = cdk.Environment(**get_environment_account())

app = cdk.App()


decider_stack = SageMakerInferenceStack(app, "DeciderStack", env=env)
aoss_stack = OpenSearchStack(app, "OpenSearchStack", env=env)
stockage_stack = StockageStack(app, "StockageStack", env=env)

knowledge_base_stack = KnowledgeBaseStack(
    app,
    "KnowledgeBaseStack",
    collection=aoss_stack.collection,
    rule_bucket=stockage_stack.rule_bucket,
    supplemental_bucket=stockage_stack.supplemental_bucket,
    env=env,
)

api_stack = ApiStack(
    app,
    "ApiStack",
    knowledge_base_id=knowledge_base_stack.knowledge_base.attr_knowledge_base_id,
    media_bucket=stockage_stack.media_bucket,
    decider_endpoint=decider_stack.endpoint.attr_endpoint_name,
    env=env,
)

app.synth()
