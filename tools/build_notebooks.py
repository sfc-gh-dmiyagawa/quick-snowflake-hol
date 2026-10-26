"""Generate the 3 HOL notebooks. Semantic view YAML comes from semantic_view_source.sql (verified original) and is patched below."""
import json, uuid, pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "notebooks"
SV_CELL = (HERE / "semantic_view_source.sql").read_text()
META = json.loads((HERE / "notebook_metadata.json").read_text())

# --- データ修正: 取引の PRODUCT_SKU（ENT-ANNUAL 等）はカタログの SKU と形式が違い結合できないため、
#     プラン（ティア×請求サイクル）単位のビューを結合先にする。カタログ自体は独立した論理テーブルとして残す。
_i = SV_CELL.find("  - name: PRODUCTS")
_j = SV_CELL.find("  - name: REPS")
_products = SV_CELL[_i:_j]
_catalog = (_products.replace("  - name: PRODUCTS", "  - name: PRODUCT_CATALOG", 1)
            .replace("synonyms: [catalog, SKUs, product list, 製品, 商品]", "synonyms: [catalog, catalog SKUs, product list, 製品カタログ, 商品一覧]")
            .replace("synonyms: [SKU, product id, 製品ID]", "synonyms: [catalog SKU, product id, 製品ID]")
            .replace("      - name: PRODUCT_TIER\n        synonyms: [tier, pricing tier, plan, edition, ティア, プラン, エディション]",
                     "      - name: CATALOG_PRODUCT_TIER\n        synonyms: [catalog tier, カタログのティア]")
            .replace("      - name: BILLING_FREQUENCY\n", "      - name: CATALOG_BILLING_FREQUENCY\n", 1)
            .replace("Multi-Year]", "Multi-year]").replace("Monthly, Annual, Multi-Year\"", "Monthly, Annual, Multi-year\""))
_plans = """  - name: PRODUCT_PLANS
    description: >
      Subscription plans (tier x billing frequency) that each sales transaction is sold under.
      Join key PRODUCT_SKU matches SALES_TRANSACTIONS.PRODUCT_SKU (e.g. ENT-ANNUAL).
      取引が紐づく料金プラン（ティア×請求サイクル）。
    synonyms: [plan, product, product tier, subscription plan, プラン, 製品, 料金プラン]
    base_table:
      database: CORTEX_QUICK_HOL_DB
      schema: CORTEX_QUICK_HOL_SCHEMA
      table: PRODUCT_PLAN_VIEW
    primary_key:
      columns: [PRODUCT_SKU]
    dimensions:
      - name: PLAN_SKU
        synonyms: [plan SKU, プランSKU]
        description: Plan SKU used in transactions (e.g. ENT-ANNUAL)
        expr: PRODUCT_SKU
        data_type: TEXT
        sample_values: [ENT-ANNUAL, PRO-MONTHLY, STARTER-ANNUAL]
      - name: PRODUCT_TIER
        synonyms: [tier, pricing tier, plan tier, edition, ティア, プラン, エディション, 製品ティア]
        description: "Product tier: Starter, Professional, Enterprise"
        expr: PRODUCT_TIER
        data_type: TEXT
        sample_values: [Starter, Professional, Enterprise]
      - name: BILLING_FREQUENCY
        synonyms: [billing cycle, payment frequency, 請求サイクル, 支払サイクル]
        description: "Billing frequency of the plan: Annual or Monthly"
        expr: BILLING_FREQUENCY
        data_type: TEXT
        sample_values: [Annual, Monthly]
    facts:
      - name: PLAN_AVG_LIST_PRICE_USD
        synonyms: [plan list price, 平均定価]
        description: Average list price of catalog products in this plan (USD)
        expr: AVG_LIST_PRICE_USD
        data_type: NUMBER
      - name: PLAN_AVG_RENEWAL_RATE_PCT
        synonyms: [plan renewal rate, プラン更新率]
        description: Average renewal rate (percent, 0-100) of catalog products in this plan
        expr: AVG_RENEWAL_RATE_PCT
        data_type: NUMBER
      - name: PLAN_AVG_UPSELL_RATE_PCT
        synonyms: [plan upsell rate, プランのアップセル率]
        description: Average upsell rate (percent, 0-100) of catalog products in this plan
        expr: AVG_UPSELL_RATE_PCT
        data_type: NUMBER
      - name: PLAN_AVG_CONTRACT_LENGTH_MONTHS
        synonyms: [plan contract length, プランの平均契約期間]
        description: Average contract length in months of catalog products in this plan
        expr: AVG_CONTRACT_LENGTH_MONTHS
        data_type: NUMBER

"""
SV_CELL = SV_CELL[:_i] + _plans + _catalog + SV_CELL[_j:]
SV_CELL = SV_CELL.replace("right_table: PRODUCTS\n", "right_table: PRODUCT_PLANS\n")
# 解約リスクは 0-100 の尺度（元の Flow プロンプトは 0.3 と書いており 0 件になる）。説明に明記して Agent の誤解を防ぐ
assert "description: Churn risk score" in SV_CELL
SV_CELL = SV_CELL.replace("description: Churn risk score (0-100)", "description: Churn risk score on a 0-100 scale (not 0-1; higher = more likely to churn, below 30 = low risk)", 1)
SV_CELL = SV_CELL.replace("CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_CATALOG_TABLE pr",
                          "CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_PLAN_VIEW pr")
assert "right_table: PRODUCT_PLANS" in SV_CELL and "PRODUCT_PLAN_VIEW pr" in SV_CELL


def _lines(s):
    s = s.strip("\n")
    parts = s.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def md(s):
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": _lines(s)}


def py(s):
    return {"cell_type": "code", "id": uuid.uuid4().hex[:8], "execution_count": None,
            "metadata": {"codeCollapsed": False, "language": "python"}, "outputs": [], "source": _lines(s)}


def sql(name, s):
    return {"cell_type": "code", "id": uuid.uuid4().hex[:8], "execution_count": None,
            "metadata": {"codeCollapsed": False, "language": "sql", "name": name, "resultVariableName": name},
            "outputs": [], "source": _lines(f"%%sql -r {name}\n{s}")}


def fig(label, desc):
    return md(f"> 🖼️ **図の差し込み位置：{label}**  \n> {desc}  \n> （画像は `images/` に置き、`![{label}](../images/xxx.png)` で差し込んでください）")


def save(name, cells):
    nb = {"cells": cells, "metadata": META, "nbformat": 4, "nbformat_minor": 5}
    (OUT / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("wrote", name, len(cells), "cells")


SETUP = '''from snowflake.snowpark.context import get_active_session
session = get_active_session()

DB, SCHEMA = "CORTEX_QUICK_HOL_DB", "CORTEX_QUICK_HOL_SCHEMA"
HOL_ROLE, HOL_WH = "CORTEX_QUICK_HOL_ROLE", "CORTEX_QUICK_HOL_WH"

session.use_role("ACCOUNTADMIN")
session.use_warehouse(HOL_WH)
session.use_schema(f"{DB}.{SCHEMA}")
print("ロール:", session.get_current_role(), "/ ウェアハウス:", session.get_current_warehouse())'''

PREFLIGHT_MD = '### 事前チェック：AI 機能とクロスリージョン推論\n\n後半（Agent / Quick 連携）で詰まらないよう、**最初に** AI 機能が使えるかを確かめます。\n\n- `CORTEX_ENABLED_CROSS_REGION` は、アカウントのリージョンに必要なモデルがないときに他リージョンで推論する設定です。トライアルのリージョンによっては Agent のモデルが見つからないため、`ANY_REGION` にします（データ自体は移動しません）。\n- `AI_COMPLETE` を1回だけ呼び、トライアルの AI 制限にかかっていないかを確認します（数文字の応答なので消費はごくわずかです）。\n\n> ❌ `not available for trial accounts` / `Access denied for trial accounts` が出た場合、この先の Agent は動きません。\n> 上の「トライアルアカウントの注意」のとおりクレジットカードを登録し、このセルを再実行してください。'
PREFLIGHT_PY = 'session.sql("ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = \'ANY_REGION\'").collect()\nprint("OK: CORTEX_ENABLED_CROSS_REGION = ANY_REGION")\n\ntry:\n    r = session.sql("SELECT AI_COMPLETE(\'claude-sonnet-4-5\', \'Reply with OK only.\') AS R").collect()[0]["R"]\n    print("OK: AI 機能が使えます（応答:", str(r).strip()[:20], "）")\nexcept Exception as e:\n    msg = str(e)\n    if "trial" in msg.lower():\n        raise RuntimeError(\n            "このトライアルアカウントでは AI 機能が無効です。Admin » Billing » Payment method でクレジットカードを登録してから、"\n            "このセルを再実行してください。（イベント用 URL で作ったアカウントでは通常発生しません）") from None\n    print("⚠️ AI_COMPLETE の呼び出しに失敗しました。モデル名の問題の可能性があります（Agent の動作は 02 で確認します）:\\n", msg[:300])'

# ------------------------------------------------------------------ 01
nb1 = [
    md('''# 01. データ準備 ― ウェアハウス・DB・ロールと6テーブル

Amazon Quick × Snowflake ハンズオン（Snowflake編）の **1本目** です。
元教材では SQL ワークシートに貼り付けて一括実行していた部分を、1ステップずつ実行しながら確認します。

| Notebook | 内容 |
|---|---|
| **01（このNotebook）** | ウェアハウス・DB・ロールの作成、S3 から 6 テーブルをロード |
| 02 | Semantic View と Cortex Agent の作成・動作確認 |
| 03 | MCP Server と OAuth の作成、Amazon Quick に入力する値の取得 |

**前提**：Snowflake の **トライアルアカウント**（Enterprise エディション、**AWS** リージョン推奨）。サインアップしたユーザーは ACCOUNTADMIN を持っています。  
**所要時間**：約10分

### Notebook を開く前に（トライアルアカウントの注意）

| 確認すること | 理由 |
|---|---|
| **AI 機能が有効なトライアルか** | 通常のセルフサービストライアルでは Cortex Agent などの AI 機能が**既定で無効**です（`not available for trial accounts`）。イベント用のサインアップ URL で作ったアカウントか、**Admin » Billing でクレジットカードを登録**したアカウントを使ってください（カード登録後も残りの無償クレジットはそのまま使えます）。Step 0 で自動チェックします。 |
| **コンピュートプールは `SYSTEM_COMPUTE_POOL_CPU`** | トライアルではコンピュートプールを新規作成できません。Notebook の接続時に既定の CPU プールを選んでください（GPU は不要です）。 |
| **クエリウェアハウスは既定の `COMPUTE_WH` でよい** | Step 1 で専用ウェアハウスを作り、以降はそちらに切り替えます。 |'''),
    fig("全体アーキテクチャ", "6テーブル → Semantic View → Cortex Agent → MCP Server → OAuth → Amazon Quick の全体図（このNotebookは左端の「データ」部分）"),
    md('''## Step 0. セッションの準備

このNotebookで使う名前（DB・スキーマ・ロール・ウェアハウス）を変数にまとめます。
作成系の操作は ACCOUNTADMIN で行い、最後にハンズオン用ロールで参照できることを確認します。

> ウェアハウス `CORTEX_QUICK_HOL_WH` はまだ存在しないため、このセルは Step 1 の後でもう一度実行しても構いません。'''),
    py('''from snowflake.snowpark.context import get_active_session
session = get_active_session()

DB, SCHEMA = "CORTEX_QUICK_HOL_DB", "CORTEX_QUICK_HOL_SCHEMA"
HOL_ROLE, HOL_WH = "CORTEX_QUICK_HOL_ROLE", "CORTEX_QUICK_HOL_WH"

session.use_role("ACCOUNTADMIN")
info = session.sql("""SELECT CURRENT_USER() AS U, CURRENT_REGION() AS R,
  CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS A""").collect()[0]
hol_user = info["U"]
print("実行ユーザー:", hol_user, "/ ロール:", session.get_current_role())
print("アカウント  :", info["A"], "/ リージョン:", info["R"])'''),
    md(PREFLIGHT_MD),
    py(PREFLIGHT_PY),
    md('''## Step 1. ウェアハウス・データベース・スキーマ・ロールを作る

| オブジェクト | 名前 | 役割 |
|---|---|---|
| ウェアハウス | `CORTEX_QUICK_HOL_WH` | SQL を実行する計算資源（XSMALL、60秒で自動停止） |
| データベース / スキーマ | `CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA` | テーブルや Agent の置き場所 |
| ロール | `CORTEX_QUICK_HOL_ROLE` | Amazon Quick から接続するときに使う権限のまとまり |

> 💡 **元教材との違い**：元教材では `SNOWFLAKE_USER` を自分のユーザー名に書き換えて実行します。
> ここでは `CURRENT_USER()` で取得した値を使うので、書き換えは不要です。'''),
    py('''stmts = [
    f"CREATE WAREHOUSE IF NOT EXISTS {HOL_WH} WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE INITIALLY_SUSPENDED=TRUE",
    f"CREATE DATABASE IF NOT EXISTS {DB}",
    f"CREATE SCHEMA IF NOT EXISTS {DB}.{SCHEMA}",
    f"CREATE ROLE IF NOT EXISTS {HOL_ROLE}",
    f'GRANT ROLE {HOL_ROLE} TO USER "{hol_user}"',
]
for s in stmts:
    session.sql(s).collect()
    print("OK:", s)

session.use_warehouse(HOL_WH)
session.use_schema(f"{DB}.{SCHEMA}")'''),
    md('''### ロールに権限を付ける

Snowflake では「誰が何をできるか」をロールに付けた権限で管理します（RBAC）。
Quick から OAuth でログインしたユーザーも、このロールの権限の範囲でしかデータに触れません。

| 権限 | 意味 |
|---|---|
| `USAGE ON WAREHOUSE` | ウェアハウスで SQL を実行できる |
| `USAGE ON DATABASE` | データベースの中を見られる |
| `ALL ON SCHEMA` | スキーマ内にオブジェクトを作ったり使ったりできる |
| `SELECT ON FUTURE TABLES` | **これから作る**テーブルを自動的に参照できる |
| `SNOWFLAKE.CORTEX_AGENT_USER` | Cortex Agent を呼び出せる（データベースロール） |'''),
    py('''stmts = [
    f"GRANT USAGE ON WAREHOUSE {HOL_WH} TO ROLE {HOL_ROLE}",
    f"GRANT USAGE ON DATABASE {DB} TO ROLE {HOL_ROLE}",
    f"GRANT ALL PRIVILEGES ON SCHEMA {DB}.{SCHEMA} TO ROLE {HOL_ROLE}",
    f"GRANT SELECT ON FUTURE TABLES IN SCHEMA {DB}.{SCHEMA} TO ROLE {HOL_ROLE}",
    f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE {HOL_ROLE}",
]
for s in stmts:
    session.sql(s).collect()
    print("OK:", s)'''),
    md('''## Step 2. CSV のファイルフォーマットを作る

S3 にある CSV ファイルの読み方（区切り文字・ヘッダー行・NULL の扱い）を定義します。'''),
    sql("create_file_format", '''CREATE OR REPLACE FILE FORMAT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.CSV_FORMAT
  TYPE = 'CSV'
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  SKIP_HEADER = 1
  NULL_IF = ('', 'NULL')'''),
    md('''## Step 3. 6つのテーブルを作る

営業オペレーションのサンプルデータです。取引（ファクト）を中心に、顧客・製品・営業担当が紐づきます。

| テーブル | 内容 | 主なカラム |
|---|---|---|
| `SALES_TRANSACTIONS_FACT_TABLE` | 受注した取引（ファクト） | 地域、金額、割引率、営業期間 |
| `CUSTOMER_DIMENSION_TABLE` | 顧客 | 業種、規模、LTV、解約リスク |
| `PRODUCT_CATALOG_TABLE` | 製品カタログ | カテゴリ、ティア、定価、更新率 |
| `SALES_REP_PERFORMANCE_TABLE` | 営業担当の実績 | テリトリー、目標、達成率、勝率 |
| `SALES_PIPELINE_OPPORTUNITIES` | 商談パイプライン | ステージ、見込み金額、競合有無 |
| `MARKETING_ATTRIBUTION_TABLE` | マーケティング施策 | キャンペーン、チャネル、リードスコア |'''),
    fig("テーブル関係図（ER図）", "取引テーブルが CUSTOMER_ID / PRODUCT_SKU / SALES_REP_ID で顧客・製品・営業担当につながる図。パイプラインとマーケティングは独立"),
    sql("create_tables", '''CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE (
  TRANSACTION_ID VARCHAR, TRANSACTION_DATE DATE, CUSTOMER_ID VARCHAR, PRODUCT_SKU VARCHAR,
  SALES_REP_ID VARCHAR, REGION VARCHAR, DEAL_SIZE_USD NUMBER(12,2), QUANTITY NUMBER,
  DISCOUNT_PERCENTAGE NUMBER(5,2), SALES_CYCLE_DAYS NUMBER, LEAD_SOURCE VARCHAR,
  CLOSE_PROBABILITY_AT_START NUMBER(5,2), FORECAST_CLOSE_DATE DATE, ACTUAL_CLOSE_DATE DATE
);
CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.CUSTOMER_DIMENSION_TABLE (
  CUSTOMER_ID VARCHAR, COMPANY_NAME VARCHAR, INDUSTRY VARCHAR, COMPANY_SIZE VARCHAR,
  ANNUAL_REVENUE_BAND VARCHAR, FIRST_PURCHASE_DATE DATE, CUSTOMER_LIFETIME_VALUE NUMBER(12,2),
  CHURN_RISK_SCORE NUMBER(5,2), TOTAL_CONTRACTS_COUNT NUMBER, EXPANSION_POTENTIAL VARCHAR
);
CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_CATALOG_TABLE (
  PRODUCT_SKU VARCHAR, PRODUCT_NAME VARCHAR, PRODUCT_CATEGORY VARCHAR, PRODUCT_FEATURE VARCHAR,
  PRODUCT_TIER VARCHAR, BILLING_FREQUENCY VARCHAR, LIST_PRICE_USD NUMBER(12,2),
  AVERAGE_CONTRACT_LENGTH_MONTHS NUMBER, RENEWAL_RATE_PCT NUMBER(5,2), UPSELL_RATE_PCT NUMBER(5,2),
  TYPICAL_DISCOUNT_RANGE VARCHAR
);
CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_REP_PERFORMANCE_TABLE (
  SALES_REP_ID VARCHAR, REP_NAME VARCHAR, TERRITORY VARCHAR, HIRE_DATE DATE, QUOTA_USD NUMBER(12,2),
  QUOTA_ATTAINMENT_PCT NUMBER(5,2), AVG_DEAL_SIZE NUMBER(12,2), WIN_RATE_PCT NUMBER(5,2),
  AVG_SALES_CYCLE_DAYS NUMBER(5,2), PIPELINE_COVERAGE_RATIO NUMBER(5,2), ACTIVE_OPPORTUNITIES_COUNT NUMBER
);
CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_PIPELINE_OPPORTUNITIES (
  OPPORTUNITY_ID VARCHAR, OPPORTUNITY_NAME VARCHAR, CURRENT_STAGE VARCHAR, ESTIMATED_VALUE NUMBER(12,2),
  WEIGHTED_FORECAST_VALUE NUMBER(12,2), CLOSE_PROBABILITY NUMBER(5,2), CREATED_DATE DATE,
  EXPECTED_CLOSE_DATE DATE, STAGE_ENTRY_DATE DATE, LAST_ACTIVITY_DATE DATE, DAYS_IN_CURRENT_STAGE NUMBER,
  COMPETITOR_PRESENT BOOLEAN, DECISION_MAKER_ENGAGED BOOLEAN, ACTIVITY_COUNT_LAST_30_DAYS NUMBER
);
CREATE OR REPLACE TABLE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.MARKETING_ATTRIBUTION_TABLE (
  LEAD_ID VARCHAR, LEAD_SOURCE_DETAIL VARCHAR, CAMPAIGN_NAME VARCHAR, FIRST_TOUCH_CHANNEL VARCHAR,
  LAST_TOUCH_CHANNEL VARCHAR, LEAD_SCORE NUMBER(5,2), LEAD_TO_OPPORTUNITY_DAYS NUMBER,
  MARKETING_SPEND_ALLOCATED NUMBER(12,2)
)'''),
    md('''## Step 4. S3 からデータをロードする

`COPY INTO` で、公開 S3 バケットの CSV を各テーブルに読み込みます。認証情報は不要です（トライアルアカウントでもそのまま動きます）。
結果の `status` が `LOADED`、`rows_loaded` が 200 になっていれば成功です。

> 💡 同じセルを2回実行すると `LOAD_SKIPPED`（読み込み済み）になります。テーブルを作り直した（Step 3 を再実行した）場合は再度 `LOADED` になります。'''),
    py('''S3 = "s3://snowflake-corp-se-workshop/summit26-coco-mcp-aws-quick-hol/csvs"
tables = ["SALES_TRANSACTIONS_FACT_TABLE", "CUSTOMER_DIMENSION_TABLE", "PRODUCT_CATALOG_TABLE",
          "SALES_REP_PERFORMANCE_TABLE", "SALES_PIPELINE_OPPORTUNITIES", "MARKETING_ATTRIBUTION_TABLE"]
for t in tables:
    r = session.sql(f"COPY INTO {DB}.{SCHEMA}.{t} FROM '{S3}/{t.lower()}.csv' FILE_FORMAT = {DB}.{SCHEMA}.CSV_FORMAT").collect()[0]
    print(f"{t:<32} {r['status']:<8} rows_loaded={r['rows_loaded']}")
    assert r["status"] in ("LOADED", "LOAD_SKIPPED"), f"{t} のロードに失敗しました: {r}"'''),
    md('''### 既存テーブルにも SELECT 権限を付ける

Step 1 の `FUTURE TABLES` の付与は、**付与した後に作ったテーブル**に効きます。
念のため、作成済みのテーブルにも明示的に付与します。

> 💡 **元教材との違い**：元教材ではテーブル作成前に `GRANT SELECT ON ALL TABLES` を実行しているため、
> その時点で存在しないテーブルには権限が付きません。ここではロード後に付与しています。'''),
    py('''session.sql(f"GRANT SELECT ON ALL TABLES IN SCHEMA {DB}.{SCHEMA} TO ROLE {HOL_ROLE}").collect()
print("OK: 既存テーブルへの SELECT を付与しました")'''),
    md('''## Step 5. 確認する

6テーブルすべてに **200件** ずつ入っていれば準備完了です。'''),
    sql("row_counts", '''SELECT 'SALES_TRANSACTIONS_FACT_TABLE' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE
UNION ALL SELECT 'CUSTOMER_DIMENSION_TABLE',     COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.CUSTOMER_DIMENSION_TABLE
UNION ALL SELECT 'PRODUCT_CATALOG_TABLE',        COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_CATALOG_TABLE
UNION ALL SELECT 'SALES_REP_PERFORMANCE_TABLE',  COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_REP_PERFORMANCE_TABLE
UNION ALL SELECT 'SALES_PIPELINE_OPPORTUNITIES', COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_PIPELINE_OPPORTUNITIES
UNION ALL SELECT 'MARKETING_ATTRIBUTION_TABLE',  COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.MARKETING_ATTRIBUTION_TABLE'''),
    md('''### テーブル同士がつながるか確認する

Semantic View では、取引テーブルを顧客・製品・営業担当とキーで結合します。実際に一致する行数を見ておきます。'''),
    sql("join_check", '''SELECT
  (SELECT COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE t JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.CUSTOMER_DIMENSION_TABLE c ON t.CUSTOMER_ID = c.CUSTOMER_ID)     AS TXN_TO_CUSTOMER,
  (SELECT COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE t JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_REP_PERFORMANCE_TABLE r ON t.SALES_REP_ID = r.SALES_REP_ID) AS TXN_TO_REP,
  (SELECT COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE t JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_CATALOG_TABLE p ON t.PRODUCT_SKU = p.PRODUCT_SKU)        AS TXN_TO_PRODUCT_CATALOG'''),
    md('''> ⚠️ **元データの問題：取引と製品カタログが結合できない**
> 顧客・営業担当は 200 件すべて一致しますが、**製品カタログとは 0 件**です。
> 取引の `PRODUCT_SKU` は `ENT-ANNUAL` のような「ティア＋請求サイクル」（6種類）、製品カタログは `ENT-ANN-011` のような個別製品（200種類）で、値の形式が違うためです（元教材のデータのままです）。
> このままだと「ティア別の売上は？」という Semantic View の検証済みクエリも 0 件になってしまいます。

## Step 6. 取引と製品をつなぐ「プラン」ビューを作る

取引の SKU を分解すると、ティア（`ENT` → Enterprise など）と請求サイクル（`ANNUAL` → Annual）が取り出せます。
製品カタログにも同じ2つのカラムがあるので、**プラン（ティア×請求サイクル）単位**のビューを作れば両者をつなげられます。

| ビューのカラム | 意味 |
|---|---|
| `PRODUCT_SKU` | 取引と同じ SKU（`ENT-ANNUAL` など）→ **取引と 1対多 で結合できる** |
| `PRODUCT_TIER` / `BILLING_FREQUENCY` | Enterprise / Professional / Starter、Annual / Monthly |
| `CATALOG_PRODUCT_COUNT` / `AVG_LIST_PRICE_USD` / `AVG_RENEWAL_RATE_PCT` / `AVG_UPSELL_RATE_PCT` / `AVG_CONTRACT_LENGTH_MONTHS` | そのプランに属するカタログ製品の数・平均定価・平均更新率・平均アップセル率・平均契約期間 |

> 💡 **元教材との違い**：Semantic View の製品テーブルをこのビューに差し替えています。これで「ティア別」「請求サイクル別」の売上に答えられます。
> 個別製品やカテゴリ単位の売上は、元データに情報がないため答えられません（製品カタログ単体の質問には答えられます）。'''),
    fig("プランビューによる結合", "取引 PRODUCT_SKU（ENT-ANNUAL）→ PRODUCT_PLAN_VIEW（Enterprise × Annual）← 製品カタログ（ティア＋請求サイクルで集約）の図"),
    sql("create_product_plan_view", '''CREATE OR REPLACE VIEW CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_PLAN_VIEW
  COMMENT = 'Plan (tier x billing) level product view joinable to SALES_TRANSACTIONS_FACT_TABLE.PRODUCT_SKU'
AS
WITH plans AS (
  SELECT DISTINCT PRODUCT_SKU,
    CASE SPLIT_PART(PRODUCT_SKU, '-', 1)
      WHEN 'ENT' THEN 'Enterprise' WHEN 'PRO' THEN 'Professional' WHEN 'STARTER' THEN 'Starter'
    END AS PRODUCT_TIER,
    INITCAP(SPLIT_PART(PRODUCT_SKU, '-', 2)) AS BILLING_FREQUENCY
  FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE
)
SELECT p.PRODUCT_SKU, p.PRODUCT_TIER, p.BILLING_FREQUENCY,
  COUNT(c.PRODUCT_SKU)              AS CATALOG_PRODUCT_COUNT,
  ROUND(AVG(c.LIST_PRICE_USD), 2)   AS AVG_LIST_PRICE_USD,
  ROUND(AVG(c.RENEWAL_RATE_PCT), 2) AS AVG_RENEWAL_RATE_PCT,
  ROUND(AVG(c.UPSELL_RATE_PCT), 2)  AS AVG_UPSELL_RATE_PCT,
  ROUND(AVG(c.AVERAGE_CONTRACT_LENGTH_MONTHS), 1) AS AVG_CONTRACT_LENGTH_MONTHS
FROM plans p
LEFT JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_CATALOG_TABLE c
  ON c.PRODUCT_TIER = p.PRODUCT_TIER AND c.BILLING_FREQUENCY = p.BILLING_FREQUENCY
GROUP BY 1, 2, 3'''),
    py('''session.sql(f"GRANT SELECT ON VIEW {DB}.{SCHEMA}.PRODUCT_PLAN_VIEW TO ROLE {HOL_ROLE}").collect()
print("OK: PRODUCT_PLAN_VIEW への SELECT を付与しました")'''),
    md('''6行（3ティア × 2請求サイクル）が表示され、`CATALOG_PRODUCT_COUNT` がすべて 1 以上なら成功です。
取引 200 件すべてがプランに結合できることも確認します（`TXN_TO_PLAN = 200`）。'''),
    sql("check_product_plan_view", '''SELECT v.*,
  (SELECT COUNT(*) FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE t
     JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_PLAN_VIEW p ON t.PRODUCT_SKU = p.PRODUCT_SKU) AS TXN_TO_PLAN
FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_PLAN_VIEW v
ORDER BY v.PRODUCT_SKU'''),
    md('''✅ 01 はここまでです。次は `02_semantic_view_and_agent.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 02
nb2 = [
    md('''# 02. Semantic View と Cortex Agent

2本目では、テーブルに **ビジネス上の意味** を与える Semantic View と、それを使って自然言語の質問に答える Cortex Agent を作ります。

元教材では Cortex Code スキルの Step 2〜4 が自動で行っている部分です。

**前提**：`01_data_setup.ipynb` を最後まで実行済みであること'''),
    fig("Semantic View と Agent の関係", "ユーザーの質問 → Cortex Agent → Cortex Analyst（Semantic View を参照して SQL 生成）→ ウェアハウスで実行 → 回答、の流れ"),
    md("## Step 0. セッションの準備"),
    py(SETUP),
    md('''## Step 1. Semantic View とは

AI にテーブルだけを渡すと、「売上」がどのカラムのどんな計算なのかを列名から**推測**します。
推測がぶれると、同じ質問でも答えが変わったり、部門ごとに数字が合わなくなったりします。

Semantic View は、その推測をなくすための「データの辞書」です。

| 要素 | 意味 | 例 |
|---|---|---|
| 論理テーブル | 物理テーブルに分かりやすい名前を付けたもの | `TRANSACTIONS` = `SALES_TRANSACTIONS_FACT_TABLE` |
| ディメンション | 切り口（GROUP BY に使う項目） | 地域、業種、商談ステージ |
| ファクト | 行ごとの数値 | 取引金額、目標額 |
| メトリクス | 集計の定義（KPI） | 売上 = `SUM(DEAL_SIZE_USD)` |
| リレーション | テーブル同士のつなぎ方 | 取引 → 顧客（CUSTOMER_ID） |
| 同義語 | 言い換え | 売上 / revenue / 総売上 |
| 検証済みクエリ | よくある質問と正解 SQL のペア | 「地域別の売上は？」 |

> 💡 **元教材との違い**
> - 日本語の同義語（売上、地域、営業担当 など）を追加し、日本語の質問でも定義に沿った SQL が生成されるようにしています。
> - 取引の結合先を製品カタログから **`PRODUCT_PLANS`（`PRODUCT_PLAN_VIEW`）** に変えています。元のままだと製品の結合が 0 件になり、「ティア別売上」が答えられません。製品カタログ（`PRODUCT_CATALOG`）は単独の論理テーブルとして残しています。'''),
    fig("Semantic View の構成", "7つの論理テーブルと3本のリレーション（取引→顧客・製品プラン・営業担当）。製品カタログ・パイプライン・マーケティングは独立、主なメトリクスを示した図"),
    md('''## Step 2. Semantic View を作る

YAML で定義を書き、`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` で作成します。
最後の引数 `FALSE` は「検証だけでなく実際に作成する」という意味です（`TRUE` にすると検証のみ）。

定義は長いですが、ポイントは次の3つです。
- **メトリクスを明示**（`TOTAL_REVENUE: SUM(DEAL_SIZE_USD)` など）
- **リレーション**で取引を顧客・**製品プラン**（01 の Step 6 で作ったビュー）・営業担当に結合
- **verified_queries** に6つの代表的な質問を登録

> 補足：verified_queries を物理テーブル名で書くと警告が出ますが、論理名に自動変換されるため動作に影響はありません。'''),
    sql("create_semantic_view", SV_CELL),
    md("作成できたか確認し、ハンズオン用ロールに参照権限を付けます。"),
    sql("show_semantic_views", f"SHOW SEMANTIC VIEWS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA"),
    py('''session.sql(f"GRANT SELECT ON SEMANTIC VIEW {DB}.{SCHEMA}.SALES_OPS_SEMANTIC_VIEW TO ROLE {HOL_ROLE}").collect()
print("OK: Semantic View への SELECT を付与しました")'''),
    md('''### 定義の中身を見る

`DESCRIBE SEMANTIC VIEW` で、登録されたディメンション・メトリクスなどを一覧できます。'''),
    sql("describe_semantic_view", '''DESCRIBE SEMANTIC VIEW CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW'''),
    md('''## Step 3. Semantic View を SQL で直接クエリする

Agent を作る前に、Semantic View だけで正しく集計できるかを確かめます。
`SEMANTIC_VIEW()` 関数は、**ディメンションとメトリクスを指定するだけ**で、結合や集計は定義に従って Snowflake が組み立てます。

期待される結果：North America が最大（約 $5.95M）、続いて EMEA（約 $4.20M）。2つ目のクエリはプラン別で、Enterprise / Annual が最大（約 $5.07M）です。'''),
    sql("sv_revenue_by_region", '''SELECT * FROM SEMANTIC_VIEW(
  CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
  DIMENSIONS TRANSACTIONS.REGION
  METRICS TRANSACTIONS.TOTAL_REVENUE
)
ORDER BY TOTAL_REVENUE DESC'''),
    sql("sv_revenue_by_plan", '''SELECT * FROM SEMANTIC_VIEW(
  CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
  DIMENSIONS PRODUCT_PLANS.PRODUCT_TIER, PRODUCT_PLANS.BILLING_FREQUENCY
  METRICS TRANSACTIONS.TOTAL_REVENUE
)
ORDER BY TOTAL_REVENUE DESC'''),
    md('''## Step 4. Cortex Agent を作る

Cortex Agent は、質問を理解して適切なツールを選び、結果を回答にまとめる AI エージェントです。
今回のツールは **Cortex Analyst**（自然言語 → SQL）1つで、参照先は Step 2 の Semantic View です。

| spec の項目 | 内容 |
|---|---|
| `models.orchestration` | 使うモデル。`auto` で Snowflake が自動選択 |
| `instructions` | 振る舞いの指示。日本語の質問には日本語で答えるよう追記 |
| `tools` | 使えるツール（`cortex_analyst_text_to_sql`） |
| `tool_resources` | ツールごとの設定（Semantic View、実行ウェアハウス） |

> ⚠️ **ハマりどころ①：ウェアハウスの指定位置**
> `execution_environment` は spec のトップではなく、**`tool_resources.<ツール名>` の中**に書きます。
> 位置が違うと、作成時に `unrecognized field execution_environment`、実行時に `missing an execution environment` になります。
> `USE WAREHOUSE` やユーザーのデフォルトウェアハウスでは代わりになりません（Quick 経由でも Agent の spec が使われます）。

> ⚠️ **ハマりどころ②：作り直すと権限が消える**
> `CREATE OR REPLACE` は既存の GRANT を引き継ぎません。ドキュメントには `COPY GRANTS` がありますが、
> 検証したアカウント（2026年10月時点）では `CREATE AGENT ... COPY GRANTS` が構文エラーになりました。
> そのため、ここでは作成直後に権限を付け直しています。'''),
    sql("create_agent", '''CREATE OR REPLACE AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT
  COMMENT = 'Sales Operations analytics agent'
  FROM SPECIFICATION $$
  models:
    orchestration: auto

  instructions:
    system: >
      You are a Sales Operations analyst. Help users explore revenue trends,
      pipeline health, sales rep performance, customer segmentation, product mix,
      and marketing attribution. Provide clear, data-driven answers. When presenting
      numbers, use appropriate formatting (currency for USD values, percentages for rates).
      Always include relevant context.
    response: >
      Provide concise, actionable answers about sales operations data. Include
      relevant numbers and comparisons when helpful. Always reply in the same
      language as the user's question (reply in Japanese if the question is in Japanese).

  tools:
    - tool_spec:
        type: cortex_analyst_text_to_sql
        name: sales_ops_analyst
        description: >
          Analyzes sales operations data including revenue, pipeline, rep performance,
          customer health, product catalog, and marketing attribution.

  tool_resources:
    sales_ops_analyst:
      semantic_view: CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
      execution_environment:
        type: warehouse
        warehouse: CORTEX_QUICK_HOL_WH
  $$'''),
    py('''session.sql(f"GRANT USAGE ON AGENT {DB}.{SCHEMA}.SALES_OPS_AGENT TO ROLE {HOL_ROLE}").collect()
print("OK: Agent への USAGE を付与しました")'''),
    sql("show_agent_grants", '''SHOW GRANTS ON AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT'''),
    md('''## Step 5. Agent に質問する

Quick につなぐ前に、Snowflake 上で Agent が正しく答えるかを確認します。**ここで失敗する場合は、Quick からも同じエラーになります。**

`SNOWFLAKE.CORTEX.DATA_AGENT_RUN` で Agent を呼び出します。下の関数は、回答の文章と Cortex Analyst が生成した SQL を取り出して表示します。'''),
    fig("Agent の処理の流れ", "質問 → Agent が意図を判断 → Cortex Analyst が Semantic View から SQL 生成 → 実行 → 結果を文章・表にまとめる"),
    py('''import json

AGENT_FQN = f"{DB}.{SCHEMA}.SALES_OPS_AGENT"

def ask_agent(question: str, show_sql: bool = True):
    payload = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
    raw = session.sql("SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS R", params=[AGENT_FQN, payload]).collect()[0]["R"]
    resp = json.loads(raw) if isinstance(raw, str) else raw
    texts, sqls = [], []
    for c in resp.get("content", []):
        if c.get("type") == "text" and c.get("text", "").strip():
            texts.append(c["text"])
        elif c.get("type") == "tool_result":
            for x in c.get("tool_result", {}).get("content", []):
                if x.get("json", {}).get("sql"):
                    sqls.append(x["json"]["sql"])
    print(f"Q: {question}\\n")
    print("\\n".join(texts))
    if show_sql:
        for s in sqls:
            print("\\n--- Cortex Analyst が生成した SQL ---\\n" + s)
    return resp'''),
    md('''| # | 質問 | 期待される結果（目安） |
|---|---|---|
| 1 | What is total revenue by region? | North America が最大（約 $5.95M）、続いて EMEA |
| 2 | Which 5 reps have the highest quota attainment? | Steven Moore（約 129.9%）がトップ |
| 3 | What is pipeline value by stage and how many deals have competitors? | 総額 約 $19.4M、競合ありは 90 件、Proposal が最大 |
| 4 | 地域別の売上を教えて | 1 と同じ数字が日本語で返る |
| 5 | 商談ステージ別のパイプライン金額を教えて | 3 と同じ数字が日本語で返る |
| 6 | 製品ティア別の売上を教えて | Enterprise が最大（約 $7.82M）、Professional 約 $3.58M、Starter 約 $0.95M |

> 💡 1回の質問には 10〜30 秒ほどかかります。Quick から呼ぶ場合も同じ時間がかかります（60 秒を超えるとタイムアウト）。'''),
    py('_ = ask_agent("What is total revenue by region?")'),
    py('_ = ask_agent("Which 5 reps have the highest quota attainment?")'),
    py('_ = ask_agent("What is pipeline value by stage and how many deals have competitors?")'),
    py('_ = ask_agent("地域別の売上を教えて")'),
    py('_ = ask_agent("商談ステージ別のパイプライン金額を教えて")'),
    py('_ = ask_agent("製品ティア別の売上を教えて")'),
    md('''### ハンズオン用ロールで実行できるか確認する

Quick からはハンズオン用ロールで実行されます。ロールを切り替えて同じように答えられるか確かめます。'''),
    py('''session.use_role(HOL_ROLE)
_ = ask_agent("営業担当の目標達成率トップ3は？", show_sql=False)
session.use_role("ACCOUNTADMIN")'''),
    md('''> ✅ すべての質問に、数字の入った回答と生成 SQL が返れば成功です。
> 個別製品・製品カテゴリ別の売上は、元データに情報がないため答えられません（01 の Step 6 を参照）。
>
> ❌ `Access denied for trial accounts`（399504）が出た場合は、トライアルの AI 制限です。01 の「トライアルアカウントの注意」を参照してください。

次は `03_mcp_and_oauth.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 03
nb3 = [
    md('''# 03. MCP Server と OAuth ― Amazon Quick から呼べるようにする

3本目では、02 で作った Agent を **外部（Amazon Quick）から呼べるように公開** します。
元教材では Cortex Code スキルの Step 5〜7 にあたる部分です。

| 作るもの | 役割 |
|---|---|
| MCP Server `SALES_OPS_MCP_SERVER` | Agent を MCP（標準プロトコル）のツールとして公開する窓口 |
| OAuth 連携 `SALES_OPS_QUICK_SUITE_OAUTH` | Quick のユーザーが Snowflake にログインするための仕組み |

**前提**：`02_semantic_view_and_agent.ipynb` を最後まで実行済みであること'''),
    fig("Quick から Snowflake への接続の流れ", "Quick（Chat Agent / Flow）→ OAuth ログイン → MCP Server → Cortex Agent → Cortex Analyst → Semantic View → テーブル。返るのは結果のみ"),
    md("## Step 0. セッションの準備"),
    py(SETUP + '''

# Quick を使うリージョン（OAuth のリダイレクト先と完全一致させる必要があります）
QUICK_REGION = "us-west-2"
quick_redirect_uri = f"https://{QUICK_REGION}.quicksight.aws.amazon.com/sn/oauthcallback"

row = session.sql("""SELECT CURRENT_USER() AS U,
  REPLACE(CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME(), '_', '-') AS H""").collect()[0]
hol_user, account_host = row["U"], row["H"]
print("ユーザー          :", hol_user)
print("アカウントホスト  :", f"{account_host}.snowflakecomputing.com")
print("OAuth リダイレクト:", quick_redirect_uri)'''),
    md('''> 💡 **アカウントホストについて**：MCP エンドポイントや OAuth の URL は `<組織名>-<アカウント名>.snowflakecomputing.com` で組み立てます。
> アカウント名に `_` が含まれる場合は `-` に置き換えます（URL で使えないため）。'''),
    md('''## Step 1. MCP Server を作る

MCP（Model Context Protocol）は、AI エージェントと外部ツールをつなぐ標準プロトコルです。
Snowflake Managed MCP Server を使うと、**サーバーを自前で立てずに** Agent を外部へ公開できます。

- ツールの種類 `CORTEX_AGENT_RUN` で Agent を1つ公開します（外部には Agent だけを見せ、どのツールを使うかは Agent に任せる構成）
- Semantic View を直接公開する `CORTEX_ANALYST_MESSAGE` などの種類もあります'''),
    sql("create_mcp_server", '''CREATE OR REPLACE MCP SERVER CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_MCP_SERVER
  COMMENT = 'MCP Server exposing Sales Ops Agent for Amazon Quick'
  FROM SPECIFICATION $$
    tools:
      - title: "Sales Ops Agent"
        name: "sales_ops_agent"
        type: "CORTEX_AGENT_RUN"
        identifier: "CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT"
        description: "Ask questions about sales operations data including revenue, pipeline, rep performance, customers, products, and marketing."
  $$'''),
    md('''## Step 2. 権限を付ける

MCP Server の USAGE だけでは、配下のツールは使えません。**Agent と Semantic View の権限も必要**です（02 で付与済み）。
ここでは MCP Server への USAGE を付け、3つがそろっているかをまとめて確認します。

> 💡 **元教材との違い**：AWS Workshop 5章 Step 6 では MCP Server への GRANT が2回書かれ、Agent への GRANT が抜けています。本 Notebook では 02 で Agent への GRANT を行っています。'''),
    py('''session.sql(f"GRANT USAGE ON MCP SERVER {DB}.{SCHEMA}.SALES_OPS_MCP_SERVER TO ROLE {HOL_ROLE}").collect()

for obj in ["MCP SERVER", "AGENT", "SEMANTIC VIEW"]:
    name = {"MCP SERVER": "SALES_OPS_MCP_SERVER", "AGENT": "SALES_OPS_AGENT", "SEMANTIC VIEW": "SALES_OPS_SEMANTIC_VIEW"}[obj]
    rows = session.sql(f"SHOW GRANTS ON {obj} {DB}.{SCHEMA}.{name}").collect()
    ok = any(r["grantee_name"] == HOL_ROLE for r in rows)
    print(f"{obj:<14} {name:<26} {HOL_ROLE} への付与: {'OK' if ok else '未付与'}")'''),
    sql("show_mcp_servers", '''SHOW MCP SERVERS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA'''),
    md('''## Step 3. 接続ユーザーの既定ロールを設定する

Quick から OAuth でログインしたとき、Snowflake は **そのユーザーのデフォルトロール／デフォルトウェアハウス** で処理します。

> ⚠️ **ハマりどころ③：トライアルのユーザーは既定ロールが ACCOUNTADMIN**
> - Quick からの処理は、セッションで切り替えたロールではなく **DEFAULT_ROLE** で行われます。
> - トライアルでサインアップしたユーザーの DEFAULT_ROLE は **ACCOUNTADMIN** です。ACCOUNTADMIN / SECURITYADMIN / ORGADMIN は OAuth でのログインが**ブロック**されるため、このままでは Quick から接続できません。
> - そこで、Quick でログインするユーザー（＝今このNotebookを実行しているユーザー）の DEFAULT_ROLE を `CORTEX_QUICK_HOL_ROLE` に変えます。

> 💡 変更後も、Snowsight 右上のロール切り替えや `USE ROLE ACCOUNTADMIN` で管理者として作業できます（次回ログイン時の初期ロールが変わるだけです）。
> このNotebookも各セルで `ACCOUNTADMIN` に切り替えて実行しているので影響ありません。元に戻す方法は末尾のクリーンアップを参照してください。

> 💡 **ハマりどころ④：ALLOWED_INTERFACES**
> ユーザーの `ALLOWED_INTERFACES` が `SNOWFLAKE_INTELLIGENCE` などに制限されていると、Quick の OAuth ログイン自体は成功するのに MCP 呼び出しが 401（`395300 Not authorized to access interface ALL`）になり、**Quick がログイン画面を繰り返し表示**します。トライアルの既定値（`ALL`）なら問題ありませんが、念のため下のセルで確認し、必要なら `ALL` に戻します。'''),
    py('''before = {r["property"]: r["value"] for r in session.sql(f'DESC USER "{hol_user}"').collect()
          if r["property"] in ("DEFAULT_ROLE", "DEFAULT_WAREHOUSE")}
print("変更前:", before)

APPLY_DEFAULT_ROLE = True   # 既定ロールを変えたくない場合は False（その場合 Quick からは接続できません）
if APPLY_DEFAULT_ROLE:
    session.sql(f'ALTER USER "{hol_user}" SET DEFAULT_ROLE = \\'{HOL_ROLE}\\'').collect()
    session.sql(f'ALTER USER "{hol_user}" SET DEFAULT_WAREHOUSE = \\'{HOL_WH}\\'').collect()
    print("変更後: DEFAULT_ROLE =", HOL_ROLE, "/ DEFAULT_WAREHOUSE =", HOL_WH)

# ALLOWED_INTERFACES の確認（SNOWFLAKE_INTELLIGENCE のみだと Quick が OAuth ループになる）
props = {r["property"]: r["value"] for r in session.sql(f'DESC USER "{hol_user}"').collect()}
cur = (props.get("ALLOWED_INTERFACES") or "[ALL]")
print("ALLOWED_INTERFACES:", cur)
if "ALL" not in cur.upper().replace("[", " ").replace("]", " ").replace(",", " ").split():
    session.sql(f"ALTER USER \\"{hol_user}\\" SET ALLOWED_INTERFACES = ('ALL')").collect()
    print("→ ('ALL') に戻しました（Quick の MCP 接続に必要）")'''),
    md('''## Step 4. OAuth 連携を作る

Amazon Quick のユーザーは OAuth で Snowflake にログインします。ログイン後の処理は、そのユーザーのロールの権限内で行われます（**RBAC がそのまま効く**）。

| 設定 | 値 | 意味 |
|---|---|---|
| `OAUTH_CLIENT_TYPE` | `CONFIDENTIAL` | Client Secret を使う方式 |
| `OAUTH_REDIRECT_URI` | Quick のコールバック URL | ログイン後の戻り先。**Quick のリージョンと完全一致**させる |
| `OAUTH_ISSUE_REFRESH_TOKENS` | `TRUE` | 再ログインなしで使い続けられるようにする |
| `OAUTH_USE_SECONDARY_ROLES` | `NONE` | DEFAULT_ROLE の権限だけで動かす（MCP 向けの推奨設定）。ユーザーが ACCOUNTADMIN を持っていても、Quick 経由ではハンズオン用ロールの権限に限定されます |
| `BLOCKED_ROLES_LIST` | 既定（ACCOUNTADMIN 等） | 管理者ロールでの OAuth ログインを禁止 |
| `OAUTH_REFRESH_TOKEN_VALIDITY` | `86400` | リフレッシュトークンの有効期間（秒、1日） |

作成には ACCOUNTADMIN が必要です。

> ⚠️ このセルを再実行すると **Client ID / Secret が変わります**。Quick 側に登録した後で再実行した場合は、Quick のコネクタも作り直してください。'''),
    py('''session.sql(f"""
CREATE OR REPLACE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = '{quick_redirect_uri}'
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_USE_SECONDARY_ROLES = 'NONE'
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400
""").collect()
print("OK: SALES_OPS_QUICK_SUITE_OAUTH を作成しました")'''),
    md('''## Step 5. Amazon Quick に入力する値を表示する

次のセルで、Quick のコネクタ設定に必要な値をまとめて表示します。手順は `docs/02_quick_setup_guide_ja.md` を参照してください。

> ⚠️ **Client Secret は画面共有で見せないよう注意してください。** 既定では伏せ字で表示し、`SHOW_SECRET = True` にしたときだけ全文を表示します。
> Quick に貼り付けるときだけ `True` にして実行し、貼り付け後は `False` に戻して再実行してください。

> 💡 Quick で OAuth ログイン画面が出たら、**このトライアルアカウントのユーザー名とパスワード**でログインします（MFA を登録済みならその確認も求められます）。'''),
    py('''import json
SHOW_SECRET = False

sec = json.loads(session.sql("SELECT SYSTEM$SHOW_OAUTH_CLIENT_SECRETS('SALES_OPS_QUICK_SUITE_OAUTH') AS S").collect()[0]["S"])
base = f"https://{account_host}.snowflakecomputing.com"
secret = sec["OAUTH_CLIENT_SECRET"]

quick_settings = {
    "MCP server endpoint": f"{base}/api/v2/databases/{DB}/schemas/{SCHEMA}/mcp-servers/SALES_OPS_MCP_SERVER",
    "Client ID":           sec["OAUTH_CLIENT_ID"],
    "Client secret":       secret if SHOW_SECRET else secret[:4] + "*" * (len(secret) - 4),
    "Token URL":           f"{base}/oauth/token-request",
    "Authorization URL":   f"{base}/oauth/authorize",
    "Redirect URL":        quick_redirect_uri,
}
for k, v in quick_settings.items():
    print(f"{k:<20}: {v}")'''),
    md('''## Step 6. 設定をまとめて確認する（トラブル時にも使えます）

| 症状 | 原因 | 対処 |
|---|---|---|
| `CREATE AGENT` で `unrecognized field execution_environment` | spec のトップに書いている | `tool_resources.<ツール名>` の中に入れる |
| Agent 実行で `missing an execution environment` | ツールにウェアハウスが紐付いていない | 上と同じ |
| Agent を作り直したら権限が消えた | `CREATE OR REPLACE` は GRANT を引き継がない | GRANT をやり直す |
| Quick から「権限がない」 | DEFAULT_ROLE に権限がない | Step 2・3 を確認 |
| OAuth ログインで拒否される | ACCOUNTADMIN 等は既定でブロック | 既定ロールを `CORTEX_QUICK_HOL_ROLE` に |
| OAuth のリダイレクトエラー | `OAUTH_REDIRECT_URI` と Quick のリージョンが不一致 | `QUICK_REGION` を合わせて Step 4 を再実行 |
| Quick で 424 / タイムアウト | MCP の呼び出しは 60 秒で打ち切り | 質問を簡単にする、検証済みクエリを増やす |
| Quick がログイン画面を繰り返す（401） | ユーザーの `ALLOWED_INTERFACES` が制限されている | Step 3 のセルで `ALL` に戻す |
| Quick のログインで `invalid_client` | Client ID / Secret の貼り間違い、または OAuth 連携を作り直した | Step 5 の値を貼り直す |
| `Access denied for trial accounts` | トライアルの AI 機能が無効 | クレジットカードを登録（01 冒頭参照） |
| Quick で Snowflake の URL エラー | アカウント名の `_` をそのまま使っている | Step 5 で表示された URL（`-` に置換済み）を使う |'''),
    py('''print("=== OAuth 連携")
for r in session.sql("DESCRIBE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH").collect():
    if r["property"] in ("ENABLED", "OAUTH_REDIRECT_URI", "OAUTH_CLIENT_TYPE", "OAUTH_USE_SECONDARY_ROLES", "BLOCKED_ROLES_LIST"):
        print(f"  {r['property']:<28} {r['property_value']}")

print("\\n=== 接続ユーザーの既定設定")
for r in session.sql(f'DESC USER "{hol_user}"').collect():
    if r["property"] in ("DEFAULT_ROLE", "DEFAULT_WAREHOUSE"):
        print(f"  {r['property']:<28} {r['value']}")

print("\\n=== Quick と同じロール（DEFAULT_ROLE）で MCP / Agent / Semantic View を使えるか")
session.use_role(HOL_ROLE)
try:
    for obj, name in [("MCP SERVER", "SALES_OPS_MCP_SERVER"), ("AGENT", "SALES_OPS_AGENT")]:
        session.sql(f"DESCRIBE {obj} {DB}.{SCHEMA}.{name}").collect()
        print(f"  {HOL_ROLE} で {obj} {name} を参照: OK")
    n = session.sql(f"SELECT COUNT(*) AS N FROM SEMANTIC_VIEW({DB}.{SCHEMA}.SALES_OPS_SEMANTIC_VIEW METRICS TRANSACTIONS.TOTAL_REVENUE)").collect()[0]["N"]
    print(f"  {HOL_ROLE} で Semantic View をクエリ: OK")
finally:
    session.use_role("ACCOUNTADMIN")'''),
    md('''✅ Snowflake 側の準備はここまでです。続きは `docs/02_quick_setup_guide_ja.md` に沿って Amazon Quick 側を設定してください。

---

## クリーンアップ（ハンズオン終了後）

作成したオブジェクトを削除します。誤って実行しないよう、`RUN_CLEANUP = True` にしたときだけ実行されます。
DB・ウェアハウス・ロールまで消す場合は `DROP_BASE_OBJECTS = True` にしてください。
既定ロールを変更した場合は、`RESTORE_DEFAULT_ROLE` に元のロール名を入れると戻せます。'''),
    py('''RUN_CLEANUP = False
DROP_BASE_OBJECTS = False
RESTORE_DEFAULT_ROLE = None   # 例: "ACCOUNTADMIN"（トライアルの初期値）

if RUN_CLEANUP:
    session.use_role("ACCOUNTADMIN")
    stmts = [
        f"DROP MCP SERVER IF EXISTS {DB}.{SCHEMA}.SALES_OPS_MCP_SERVER",
        f"DROP AGENT IF EXISTS {DB}.{SCHEMA}.SALES_OPS_AGENT",
        f"DROP SEMANTIC VIEW IF EXISTS {DB}.{SCHEMA}.SALES_OPS_SEMANTIC_VIEW",
        "DROP SECURITY INTEGRATION IF EXISTS SALES_OPS_QUICK_SUITE_OAUTH",
    ]
    if RESTORE_DEFAULT_ROLE:
        stmts.append(f'ALTER USER "{hol_user}" SET DEFAULT_ROLE = \\'{RESTORE_DEFAULT_ROLE}\\'')
    if DROP_BASE_OBJECTS:
        stmts += [f"DROP DATABASE IF EXISTS {DB}", f"DROP WAREHOUSE IF EXISTS {HOL_WH}", f"DROP ROLE IF EXISTS {HOL_ROLE}"]
    for s in stmts:
        session.sql(s).collect()
        print("OK:", s)
else:
    print("RUN_CLEANUP = False のため何もしていません")'''),
]

OUT.mkdir(parents=True, exist_ok=True)
save("01_data_setup.ipynb", nb1)
save("02_semantic_view_and_agent.ipynb", nb2)
save("03_mcp_and_oauth.ipynb", nb3)
