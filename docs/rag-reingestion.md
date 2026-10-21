# Ré-ingestion de la base de connaissances (RAG)

Le passage de la stratégie de découpe `HIERARCHICAL` à `FIXED_SIZE`
(`max_tokens=350`, `overlap_percentage=20`) **nécessite une ré-ingestion** de la
source de données. Tant que le job d'ingestion n'est pas terminé, la qualité de
la récupération ne change pas : les anciens chunks restent indexés.

## Étapes

1. Déployer la pile mise à jour :

   ```
   uv run cdk deploy KnowledgeBaseStack
   ```

2. Déclencher une synchronisation de la source de données, au choix :

   - **Console Bedrock** : sur la page de la Knowledge Base, bouton
     « Synchroniser » / « Sync » au niveau de la source de données.
   - **CLI** :

     ```
     aws bedrock-agent start-ingestion-job \
       --knowledge-base-id <KB_ID> \
       --data-source-id <DS_ID>
     ```

3. Retrouver les identifiants `<KB_ID>` et `<DS_ID>` :

   ```
   aws bedrock-agent list-knowledge-bases          # chercher le nom road-rule-kb
   aws bedrock-agent list-data-sources \
     --knowledge-base-id <KB_ID>                   # chercher le nom rule-s3-datasource
   ```

   Les identifiants sont aussi disponibles via les sorties CloudFormation ou la
   console Bedrock.

> La qualité de la récupération ne s'améliore qu'une fois le job d'ingestion
> terminé.
