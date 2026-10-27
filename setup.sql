-- ============================================================================
-- Amazon Quick × Snowflake ハンズオン  データ準備（setup.sql）
--   - ウェアハウス / DB / スキーマ / ロールの作成と権限設定
--   - 営業オペレーションのサンプルデータ（6テーブル）を公開S3から読み込み
--   - Cortex Search 用の PDF レポート（2本）を公開S3から社内ステージにコピー
--   実行方法: load.sql の後に、Snowsight の SQL ワークシートに貼り付けて「すべて実行」
--   所要時間: 約3分
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- ----------------------------------------------------------------------------
-- 1. ウェアハウス / データベース / スキーマ / ロール
-- ----------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS CORTEX_QUICK_HOL_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS CORTEX_QUICK_HOL_DB;
CREATE SCHEMA   IF NOT EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
CREATE ROLE     IF NOT EXISTS CORTEX_QUICK_HOL_ROLE;

-- 実行ユーザーにハンズオン用ロールを付与
SET HOL_USER = CURRENT_USER();
GRANT ROLE CORTEX_QUICK_HOL_ROLE TO USER IDENTIFIER($HOL_USER);

GRANT USAGE ON WAREHOUSE CORTEX_QUICK_HOL_WH TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT USAGE ON DATABASE  CORTEX_QUICK_HOL_DB TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA TO ROLE CORTEX_QUICK_HOL_ROLE;
-- Cortex Agent / Cortex Search などの AI 機能を使うためのデータベースロール
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER       TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE CORTEX_QUICK_HOL_ROLE;

USE WAREHOUSE CORTEX_QUICK_HOL_WH;
USE SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;

-- ----------------------------------------------------------------------------
-- 2. ファイルフォーマット
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FILE FORMAT CSV_FORMAT
  TYPE = 'CSV'
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  SKIP_HEADER = 1
  NULL_IF = ('', 'NULL');

-- ----------------------------------------------------------------------------
-- 3. テーブル作成（6テーブル）
-- ----------------------------------------------------------------------------
-- 3-1. 取引（ファクト）
CREATE OR REPLACE TABLE SALES_TRANSACTIONS_FACT_TABLE (
  TRANSACTION_ID             VARCHAR,
  TRANSACTION_DATE           DATE,
  CUSTOMER_ID                VARCHAR,
  PRODUCT_SKU                VARCHAR,
  SALES_REP_ID               VARCHAR,
  REGION                     VARCHAR,
  DEAL_SIZE_USD              NUMBER(12,2),
  QUANTITY                   NUMBER,
  DISCOUNT_PERCENTAGE        NUMBER(5,2),
  SALES_CYCLE_DAYS           NUMBER,
  LEAD_SOURCE                VARCHAR,
  CLOSE_PROBABILITY_AT_START NUMBER(5,2),
  FORECAST_CLOSE_DATE        DATE,
  ACTUAL_CLOSE_DATE          DATE
);

-- 3-2. 顧客
CREATE OR REPLACE TABLE CUSTOMER_DIMENSION_TABLE (
  CUSTOMER_ID             VARCHAR,
  COMPANY_NAME            VARCHAR,
  INDUSTRY                VARCHAR,
  COMPANY_SIZE            VARCHAR,
  ANNUAL_REVENUE_BAND     VARCHAR,
  FIRST_PURCHASE_DATE     DATE,
  CUSTOMER_LIFETIME_VALUE NUMBER(12,2),
  CHURN_RISK_SCORE        NUMBER(5,2),
  TOTAL_CONTRACTS_COUNT   NUMBER,
  EXPANSION_POTENTIAL     VARCHAR
);

-- 3-3. 製品カタログ
CREATE OR REPLACE TABLE PRODUCT_CATALOG_TABLE (
  PRODUCT_SKU                    VARCHAR,
  PRODUCT_NAME                   VARCHAR,
  PRODUCT_CATEGORY               VARCHAR,
  PRODUCT_FEATURE                VARCHAR,
  PRODUCT_TIER                   VARCHAR,
  BILLING_FREQUENCY              VARCHAR,
  LIST_PRICE_USD                 NUMBER(12,2),
  AVERAGE_CONTRACT_LENGTH_MONTHS NUMBER,
  RENEWAL_RATE_PCT               NUMBER(5,2),
  UPSELL_RATE_PCT                NUMBER(5,2),
  TYPICAL_DISCOUNT_RANGE         VARCHAR
);

-- 3-4. 営業担当の実績
CREATE OR REPLACE TABLE SALES_REP_PERFORMANCE_TABLE (
  SALES_REP_ID               VARCHAR,
  REP_NAME                   VARCHAR,
  TERRITORY                  VARCHAR,
  HIRE_DATE                  DATE,
  QUOTA_USD                  NUMBER(12,2),
  QUOTA_ATTAINMENT_PCT       NUMBER(5,2),
  AVG_DEAL_SIZE              NUMBER(12,2),
  WIN_RATE_PCT               NUMBER(5,2),
  AVG_SALES_CYCLE_DAYS       NUMBER(5,2),
  PIPELINE_COVERAGE_RATIO    NUMBER(5,2),
  ACTIVE_OPPORTUNITIES_COUNT NUMBER
);

-- 3-5. 商談パイプライン
CREATE OR REPLACE TABLE SALES_PIPELINE_OPPORTUNITIES (
  OPPORTUNITY_ID              VARCHAR,
  OPPORTUNITY_NAME            VARCHAR,
  CURRENT_STAGE               VARCHAR,
  ESTIMATED_VALUE             NUMBER(12,2),
  WEIGHTED_FORECAST_VALUE     NUMBER(12,2),
  CLOSE_PROBABILITY           NUMBER(5,2),
  CREATED_DATE                DATE,
  EXPECTED_CLOSE_DATE         DATE,
  STAGE_ENTRY_DATE            DATE,
  LAST_ACTIVITY_DATE          DATE,
  DAYS_IN_CURRENT_STAGE       NUMBER,
  COMPETITOR_PRESENT          BOOLEAN,
  DECISION_MAKER_ENGAGED      BOOLEAN,
  ACTIVITY_COUNT_LAST_30_DAYS NUMBER
);

-- 3-6. マーケティング施策
CREATE OR REPLACE TABLE MARKETING_ATTRIBUTION_TABLE (
  LEAD_ID                   VARCHAR,
  LEAD_SOURCE_DETAIL        VARCHAR,
  CAMPAIGN_NAME             VARCHAR,
  FIRST_TOUCH_CHANNEL       VARCHAR,
  LAST_TOUCH_CHANNEL        VARCHAR,
  LEAD_SCORE                NUMBER(5,2),
  LEAD_TO_OPPORTUNITY_DAYS  NUMBER,
  MARKETING_SPEND_ALLOCATED NUMBER(12,2)
);

-- ----------------------------------------------------------------------------
-- 4. 公開S3からデータを読み込み
-- ----------------------------------------------------------------------------
COPY INTO SALES_TRANSACTIONS_FACT_TABLE
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/sales_transactions_fact_table.csv'
  FILE_FORMAT = CSV_FORMAT;

COPY INTO CUSTOMER_DIMENSION_TABLE
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/customer_dimension_table.csv'
  FILE_FORMAT = CSV_FORMAT;

COPY INTO PRODUCT_CATALOG_TABLE
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/product_catalog_table.csv'
  FILE_FORMAT = CSV_FORMAT;

COPY INTO SALES_REP_PERFORMANCE_TABLE
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/sales_rep_performance_table.csv'
  FILE_FORMAT = CSV_FORMAT;

COPY INTO SALES_PIPELINE_OPPORTUNITIES
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/sales_pipeline_opportunities.csv'
  FILE_FORMAT = CSV_FORMAT;

COPY INTO MARKETING_ATTRIBUTION_TABLE
  FROM 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs/marketing_attribution_table.csv'
  FILE_FORMAT = CSV_FORMAT;

-- 既存テーブルにもSELECTを付与（FUTURE GRANTは作成後のテーブルには効かないため）
GRANT SELECT ON ALL TABLES IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA TO ROLE CORTEX_QUICK_HOL_ROLE;

-- ----------------------------------------------------------------------------
-- 4-2. 取引と製品をつなぐプランビュー
--   取引の PRODUCT_SKU（ENT-ANNUAL 等）は製品カタログの SKU（ENT-ANN-011 等）と形式が違い、
--   そのままでは結合できない（元データの問題）。ティア×請求サイクル単位のビューで結合する。
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW PRODUCT_PLAN_VIEW
  COMMENT = 'Plan (tier x billing) level product view joinable to SALES_TRANSACTIONS_FACT_TABLE.PRODUCT_SKU'
AS
WITH plans AS (
  SELECT DISTINCT PRODUCT_SKU,
    CASE SPLIT_PART(PRODUCT_SKU, '-', 1)
      WHEN 'ENT' THEN 'Enterprise' WHEN 'PRO' THEN 'Professional' WHEN 'STARTER' THEN 'Starter'
    END AS PRODUCT_TIER,
    INITCAP(SPLIT_PART(PRODUCT_SKU, '-', 2)) AS BILLING_FREQUENCY
  FROM SALES_TRANSACTIONS_FACT_TABLE
)
SELECT p.PRODUCT_SKU, p.PRODUCT_TIER, p.BILLING_FREQUENCY,
  COUNT(c.PRODUCT_SKU)              AS CATALOG_PRODUCT_COUNT,
  ROUND(AVG(c.LIST_PRICE_USD), 2)   AS AVG_LIST_PRICE_USD,
  ROUND(AVG(c.RENEWAL_RATE_PCT), 2) AS AVG_RENEWAL_RATE_PCT,
  ROUND(AVG(c.UPSELL_RATE_PCT), 2)  AS AVG_UPSELL_RATE_PCT,
  ROUND(AVG(c.AVERAGE_CONTRACT_LENGTH_MONTHS), 1) AS AVG_CONTRACT_LENGTH_MONTHS
FROM plans p
LEFT JOIN PRODUCT_CATALOG_TABLE c
  ON c.PRODUCT_TIER = p.PRODUCT_TIER AND c.BILLING_FREQUENCY = p.BILLING_FREQUENCY
GROUP BY 1, 2, 3;

GRANT SELECT ON VIEW PRODUCT_PLAN_VIEW TO ROLE CORTEX_QUICK_HOL_ROLE;

-- ----------------------------------------------------------------------------
-- 4-3. Cortex Search 用の PDF レポート（非構造化データ）
--   公開 S3 の PDF 2本を、AI_PARSE_DOCUMENT で読める社内ステージ（SSE 暗号化・ディレクトリ有効）にコピー
-- ----------------------------------------------------------------------------
CREATE OR REPLACE STAGE HOL_S3_PDF_STAGE
  URL = 's3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/pdfs/';
CREATE STAGE IF NOT EXISTS DOCS_STAGE
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
  DIRECTORY  = (ENABLE = TRUE);
COPY FILES INTO @DOCS_STAGE FROM @HOL_S3_PDF_STAGE;
ALTER STAGE DOCS_STAGE REFRESH;
GRANT READ ON STAGE DOCS_STAGE TO ROLE CORTEX_QUICK_HOL_ROLE;

-- Agent が使うモデルがアカウントのリージョンにない場合に備えてクロスリージョン推論を許可
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- ----------------------------------------------------------------------------
-- 5. 確認（テーブルは各200件、プラン結合200件、PDF 2件ならOK）
-- ----------------------------------------------------------------------------
SELECT 'SALES_TRANSACTIONS_FACT_TABLE' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM SALES_TRANSACTIONS_FACT_TABLE
UNION ALL SELECT 'CUSTOMER_DIMENSION_TABLE',     COUNT(*) FROM CUSTOMER_DIMENSION_TABLE
UNION ALL SELECT 'PRODUCT_CATALOG_TABLE',        COUNT(*) FROM PRODUCT_CATALOG_TABLE
UNION ALL SELECT 'SALES_REP_PERFORMANCE_TABLE',  COUNT(*) FROM SALES_REP_PERFORMANCE_TABLE
UNION ALL SELECT 'SALES_PIPELINE_OPPORTUNITIES', COUNT(*) FROM SALES_PIPELINE_OPPORTUNITIES
UNION ALL SELECT 'MARKETING_ATTRIBUTION_TABLE',  COUNT(*) FROM MARKETING_ATTRIBUTION_TABLE
UNION ALL SELECT 'TXN_JOINED_TO_PRODUCT_PLAN (=200)', COUNT(*)
  FROM SALES_TRANSACTIONS_FACT_TABLE t JOIN PRODUCT_PLAN_VIEW p ON t.PRODUCT_SKU = p.PRODUCT_SKU
UNION ALL SELECT 'PDF_FILES_ON_DOCS_STAGE (=2)', COUNT(*) FROM DIRECTORY(@DOCS_STAGE);
