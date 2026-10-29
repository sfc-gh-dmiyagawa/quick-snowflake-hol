"""Generate the 5 HOL notebooks. Semantic view YAML comes from semantic_view_source.sql (verified original) and is patched below."""
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


# --- v2 の精度向上：社内 KPI（業務上の定義）を Semantic View に持たせる。
#     PDF レポートに書かれている基準（停滞＝40日超、推奨カバレッジ 1.6 倍 など）を指標として定義し、
#     Agent が毎回同じ定義で数えるようにする。
_OPEN = "CURRENT_STAGE NOT IN ('Closed Won', 'Closed Lost')"
_PIPE_METRICS = f"""      - name: OPEN_PIPELINE_VALUE
        synonyms: [open pipeline, active pipeline value, 進行中パイプライン, オープン商談金額]
        description: Total estimated value of open opportunities (excluding Closed Won / Closed Lost)
        expr: SUM(IFF({_OPEN}, ESTIMATED_VALUE, 0))
      - name: STALLED_DEAL_COUNT
        synonyms: [stalled deals, stuck deals, 停滞商談, 停滞している商談, 滞留商談]
        description: >
          Company definition of a stalled deal: an open opportunity that has been in its current stage
          for more than 40 days. 社内定義：未クローズで現ステージ滞留が40日超の商談。
        expr: COUNT_IF(DAYS_IN_CURRENT_STAGE > 40 AND {_OPEN})
      - name: AT_RISK_DEAL_COUNT
        synonyms: [at-risk deals, deals at risk, 失注リスク商談, リスク商談]
        description: >
          Company definition of an at-risk deal: an open opportunity with a competitor present and
          no decision maker engaged. 社内定義：未クローズ・競合あり・決裁者未接触の商談。
        expr: COUNT_IF(COMPETITOR_PRESENT AND NOT DECISION_MAKER_ENGAGED AND {_OPEN})
      - name: AT_RISK_PIPELINE_VALUE
        synonyms: [at-risk pipeline, 失注リスク金額, リスク商談の金額]
        description: Total estimated value of at-risk deals (open, competitor present, no decision maker engaged)
        expr: SUM(IFF(COMPETITOR_PRESENT AND NOT DECISION_MAKER_ENGAGED AND {_OPEN}, ESTIMATED_VALUE, 0))
      - name: WIN_RATE_PCT
        synonyms: [win rate, close rate, 勝率, 受注率]
        description: >
          Company definition of win rate: Closed Won / (Closed Won + Closed Lost) x 100, using pipeline stages.
          社内定義：受注 ÷（受注＋失注）× 100。
        expr: COUNT_IF(CURRENT_STAGE = 'Closed Won') * 100.0 / NULLIF(COUNT_IF(CURRENT_STAGE IN ('Closed Won', 'Closed Lost')), 0)
"""
_REP_METRICS = """      - name: REPS_ABOVE_QUOTA
        synonyms: [reps over quota, reps hitting quota, 目標達成者数, 目標を達成した営業担当の数]
        description: Number of sales reps whose quota attainment is above 100 percent
        expr: COUNT_IF(QUOTA_ATTAINMENT_PCT > 100)
      - name: REPS_BELOW_COVERAGE_TARGET
        synonyms: [coverage gap reps, カバレッジ不足の営業担当, 推奨カバレッジ未満]
        description: >
          Number of reps below the recommended minimum pipeline coverage of 1.6x
          (company target from the Sales Performance Analysis report). 推奨カバレッジ1.6倍未満の営業担当数。
        expr: COUNT_IF(PIPELINE_COVERAGE_RATIO < 1.6)
"""
_CUST_METRICS = """      - name: EXPANSION_TARGET_CUSTOMERS
        synonyms: [expansion targets, upsell targets, 拡大対象顧客, アップセル対象]
        description: >
          Customers with low churn risk (score below 30 on the 0-100 scale) and High or Medium expansion potential.
          解約リスク30未満かつ拡大余地 High/Medium の顧客数。
        expr: COUNT_IF(CHURN_RISK_SCORE < 30 AND EXPANSION_POTENTIAL IN ('High', 'Medium'))
"""


def _add_metrics(sv, after_metric_expr, block):
    i = sv.index(after_metric_expr) + len(after_metric_expr)
    i = sv.index("\n", i) + 1
    return sv[:i] + block + sv[i:]


SV_CELL = _add_metrics(SV_CELL, "expr: AVG(DAYS_IN_CURRENT_STAGE)", _PIPE_METRICS)
SV_CELL = _add_metrics(SV_CELL, "        description: Average days in current stage\n", "")  # anchor check
_m = SV_CELL.index("  - name: REPS")
_r = SV_CELL.index("    metrics:", _m)
SV_CELL = SV_CELL[:_r] + "    metrics:\n" + _REP_METRICS + SV_CELL[_r + len("    metrics:\n"):]
_c = SV_CELL.index("  - name: CUSTOMERS")
_cm = SV_CELL.index("    metrics:", _c)
SV_CELL = SV_CELL[:_cm] + "    metrics:\n" + _CUST_METRICS + SV_CELL[_cm + len("    metrics:\n"):]
SV_CELL = SV_CELL.replace("        description: Days in current stage\n",
                          "        description: Days in current stage (more than 40 days on an open deal = stalled)\n", 1)
SV_CELL = SV_CELL.replace("        description: Pipeline coverage ratio\n",
                          "        description: Pipeline coverage ratio (recommended minimum 1.6x)\n", 1)

_JP_VQ = """  - name: stalled_deals_jp
    question: 停滞している商談は何件？
    use_as_onboarding_question: true
    sql: |
      SELECT COUNT(*) AS STALLED_DEALS
      FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_PIPELINE_OPPORTUNITIES
      WHERE DAYS_IN_CURRENT_STAGE > 40 AND CURRENT_STAGE NOT IN ('Closed Won', 'Closed Lost')
  - name: win_rate_jp
    question: 商談の勝率は？
    use_as_onboarding_question: true
    sql: |
      SELECT COUNT_IF(CURRENT_STAGE = 'Closed Won') * 100.0
             / NULLIF(COUNT_IF(CURRENT_STAGE IN ('Closed Won', 'Closed Lost')), 0) AS WIN_RATE_PCT
      FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_PIPELINE_OPPORTUNITIES
  - name: revenue_by_tier_jp
    question: 製品ティア別の売上を教えて
    use_as_onboarding_question: true
    sql: |
      SELECT pr.PRODUCT_TIER, SUM(t.DEAL_SIZE_USD) AS TOTAL_REVENUE
      FROM CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_TRANSACTIONS_FACT_TABLE t
      JOIN CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.PRODUCT_PLAN_VIEW pr ON t.PRODUCT_SKU = pr.PRODUCT_SKU
      GROUP BY pr.PRODUCT_TIER ORDER BY TOTAL_REVENUE DESC
"""
SV_CELL = SV_CELL.replace("verified_queries:\n", "verified_queries:\n" + _JP_VQ, 1)


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


def save(name, cells):
    nb = {"cells": cells, "metadata": META, "nbformat": 4, "nbformat_minor": 5}
    (OUT / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("wrote", name, len(cells), "cells")


SETUP_SQL = """USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CORTEX_QUICK_HOL_WH;
USE SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
SELECT CURRENT_ROLE() AS "ロール", CURRENT_WAREHOUSE() AS "ウェアハウス", CURRENT_SCHEMA() AS "スキーマ\""""

SETUP_MD = """## Step 0. 実行環境をそろえる

使うロール・ウェアハウス・スキーマを指定します。Notebook はそれぞれ独立して動くため、各 Notebook の最初に実行します。"""

PREFLIGHT_MD = '### 事前チェック：AI 機能とクロスリージョン推論\n\n後半（Agent / Quick 連携）で詰まらないよう、**最初に** AI 機能が使えるかを確かめます。\n\n- `CORTEX_ENABLED_CROSS_REGION` は、アカウントのリージョンに必要なモデルがないときに他リージョンで推論する設定です。アカウントのリージョンによっては Agent のモデルが見つからないため、`setup.sql` で `ANY_REGION` にしています（データ自体は移動しません）。ここでは値を確認するだけです。\n- `AI_COMPLETE` を1回だけ呼び、AI 機能が使えるかを確認します（数文字の応答なので消費はごくわずかです）。'
PREFLIGHT_SQL_1 = "SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT"
PREFLIGHT_SQL_2 = "SELECT AI_COMPLETE('claude-sonnet-4-5', 'Reply with OK only.') AS \"AI の応答\""


ASK_AGENT_SQL = """-- Agent に質問し、「使ったツール」「生成した SQL」「参照した文書」「回答」を表に整形して返す
CREATE OR REPLACE PROCEDURE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.ASK_AGENT(
  QUESTION STRING, AGENT STRING DEFAULT 'SALES_OPS_AGENT')
RETURNS TABLE ("種別" STRING, "内容" STRING)
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
  agent_fqn STRING DEFAULT 'CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.' || AGENT;
  body STRING DEFAULT OBJECT_CONSTRUCT('messages', ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(
         'role', 'user', 'content', ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('type', 'text', 'text', QUESTION)))))::STRING;
  res RESULTSET;
BEGIN
  res := (
    WITH r AS (SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(:agent_fqn, :body)) AS J),
         c AS (SELECT f.index AS N, f.value AS V FROM r, LATERAL FLATTEN(J:content) f)
    SELECT CASE V:type::STRING WHEN 'text' THEN '回答' WHEN 'tool_use' THEN 'ツール' ELSE '参照文書' END,
           CASE V:type::STRING
             WHEN 'text'     THEN V:text::STRING
             WHEN 'tool_use' THEN V:tool_use:name::STRING || IFF(V:tool_use:input:sql IS NULL, '', CHR(10) || V:tool_use:input:sql::STRING)
             ELSE ARRAY_TO_STRING(ARRAY_DISTINCT(TRANSFORM(V:tool_result:content[0]:json:search_results, x -> x:doc_title::STRING)), ', ')
           END
    FROM c
    WHERE V:type::STRING IN ('text', 'tool_use')
       OR (V:type::STRING = 'tool_result' AND V:tool_result:content[0]:json:search_results IS NOT NULL)
    ORDER BY N
  );
  RETURN TABLE(res);
END;
$$;
GRANT USAGE ON PROCEDURE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.ASK_AGENT(STRING, STRING) TO ROLE CORTEX_QUICK_HOL_ROLE"""

ASK_AGENT_MD = """`ASK_AGENT` は、Agent を呼び出す関数 `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` の結果（JSON）を、読みやすい表に整形するだけの SQL プロシージャです。
以降は `CALL ASK_AGENT('質問');` の 1 行で Agent に質問できます。表の「種別」で、Agent がどのツールを使い、どんな SQL を作り、どの文書を参照したかが分かります。"""


def eval_agent_sql(agent, sv):
    return f"""CREATE OR REPLACE AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.{agent}
  COMMENT = 'Evaluation agent (Cortex Analyst only) for {sv}'
  FROM SPECIFICATION $$
  models:
    orchestration: auto
  instructions:
    response: Answer briefly with the number. Reply in the same language as the question.
  tools:
    - tool_spec:
        type: cortex_analyst_text_to_sql
        name: analyst
        description: Sales operations data
  tool_resources:
    analyst:
      semantic_view: CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.{sv}
      execution_environment:
        type: warehouse
        warehouse: CORTEX_QUICK_HOL_WH
  $$"""


def search_sql(q):
    return f"""SELECT r.index + 1 AS "順位",
       r.value:FILE_NAME::STRING AS "ファイル",
       LEFT(REGEXP_REPLACE(r.value:CHUNK::STRING, '\\\\s+', ' '), 300) AS "本文（先頭 300 文字）"
FROM TABLE(FLATTEN(PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_DOCS_SEARCH',
  '{{"query": "{q}", "columns": ["CHUNK", "FILE_NAME"], "limit": 3}}'
)):results)) r"""


def ask(q, agent=None):
    a = f", '{agent}'" if agent else ""
    return f"CALL CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.ASK_AGENT('{q}'{a})"

FQ = "CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA."

INTRO_TABLE = '''| Notebook | 内容 |
|---|---|
| 01 | 取り込んだデータの確認と、このハンズオンで作るもの |
| 02 | **Cortex Analyst**：Semantic View を作り、改善前後の正答率を比べる |
| 03 | **Cortex Search**：PDF レポートを検索できるようにする |
| 04 | **Cortex Agent**：Analyst と Search を組み合わせた Agent を作る |
| 05 | MCP Server と OAuth：Amazon Quick から Agent を呼べるようにする |'''

# ------------------------------------------------------------------ 01
nb1 = [
    md(f'''# 01. データを確認する ― 何があって、何を作るのか

Amazon Quick × Snowflake ハンズオン（Snowflake 編）の 1 本目です。
`setup.sql` で取り込んだデータを確認し、このハンズオンで作るものを整理します。**このNotebookでは何も作りません**（確認だけです）。

{INTRO_TABLE}

**前提**：`load.sql` と `setup.sql` を実行済みであること'''),
    md('''## シナリオ

あなたは SaaS 企業の**営業企画（Sales Operations）の担当者**です。
営業部長や現場のマネージャーから、毎日のようにこんな質問が届きます。

- 「今期の地域別の売上は？ Enterprise プランはどれくらい売れている？」
- 「**停滞している商談**は何件ある？」「**勝率**は？」
- 「レポートで推奨されている**パイプラインカバレッジ**を下回っている営業担当は誰？」

数字は Snowflake のテーブルに、**社内の基準や推奨アクションは PDF のレポート**に書かれています。
このハンズオンでは、両方をまたいで自然言語で答える **Cortex Agent** を作り、最後に **Amazon Quick** から使えるようにします。'''),
    md(SETUP_MD),
    sql("setup", SETUP_SQL + """;
SELECT CURRENT_USER() AS "実行ユーザー", CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS "アカウント", CURRENT_REGION() AS "リージョン\""""),
    md(PREFLIGHT_MD),
    sql("check_cross_region", PREFLIGHT_SQL_1),
    md("`value` が `ANY_REGION` になっていれば OK です。続けて、AI 関数を 1 回だけ呼んでみます。"),
    sql("check_ai", PREFLIGHT_SQL_2),
    md("> ✅ 「AI の応答」に `OK` と返れば、AI 機能が使えます。"),
    md('''## Step 1. 構造化データ：6 つのテーブル

`setup.sql` で公開 S3 から読み込んだ、営業オペレーションのサンプルデータです。まず件数を確認します（各 200 件）。

| テーブル | 内容 | 主なカラム |
|---|---|---|
| `SALES_TRANSACTIONS_FACT_TABLE` | 受注した取引（ファクト） | 地域、金額、割引率、プラン SKU |
| `CUSTOMER_DIMENSION_TABLE` | 顧客 | 業種、規模、LTV、解約リスク（0〜100）、拡大余地 |
| `PRODUCT_CATALOG_TABLE` | 製品カタログ | カテゴリ、ティア、定価、更新率、アップセル率 |
| `SALES_REP_PERFORMANCE_TABLE` | 営業担当の実績 | テリトリー、目標達成率、勝率、パイプラインカバレッジ |
| `SALES_PIPELINE_OPPORTUNITIES` | 商談パイプライン | ステージ、見込金額、滞留日数、競合有無、決裁者接触 |
| `MARKETING_ATTRIBUTION_TABLE` | マーケティング施策 | キャンペーン、チャネル、リードスコア、費用 |'''),
    sql("row_counts", f'''SELECT 'SALES_TRANSACTIONS_FACT_TABLE' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE
UNION ALL SELECT 'CUSTOMER_DIMENSION_TABLE',     COUNT(*) FROM {FQ}CUSTOMER_DIMENSION_TABLE
UNION ALL SELECT 'PRODUCT_CATALOG_TABLE',        COUNT(*) FROM {FQ}PRODUCT_CATALOG_TABLE
UNION ALL SELECT 'SALES_REP_PERFORMANCE_TABLE',  COUNT(*) FROM {FQ}SALES_REP_PERFORMANCE_TABLE
UNION ALL SELECT 'SALES_PIPELINE_OPPORTUNITIES', COUNT(*) FROM {FQ}SALES_PIPELINE_OPPORTUNITIES
UNION ALL SELECT 'MARKETING_ATTRIBUTION_TABLE',  COUNT(*) FROM {FQ}MARKETING_ATTRIBUTION_TABLE'''),
    md('''### 中身を見てみる

取引と商談を数行ずつ表示します。どんなカラムにどんな値が入っているかを眺めてください。'''),
    sql("sample_transactions", f'''SELECT * FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE ORDER BY TRANSACTION_DATE LIMIT 5'''),
    sql("sample_pipeline", f'''SELECT OPPORTUNITY_ID, CURRENT_STAGE, ESTIMATED_VALUE, DAYS_IN_CURRENT_STAGE,
       COMPETITOR_PRESENT, DECISION_MAKER_ENGAGED
FROM {FQ}SALES_PIPELINE_OPPORTUNITIES ORDER BY ESTIMATED_VALUE DESC LIMIT 5'''),
    md('''### ざっくり集計してみる

あとで Agent に聞く質問の「正解」を、SQL で先に確かめておきます。'''),
    sql("revenue_by_region", f'''SELECT REGION, COUNT(*) AS DEALS, SUM(DEAL_SIZE_USD) AS REVENUE
FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE GROUP BY REGION ORDER BY REVENUE DESC'''),
    sql("pipeline_by_stage", f'''SELECT CURRENT_STAGE, COUNT(*) AS OPPS, SUM(ESTIMATED_VALUE) AS VALUE,
       ROUND(AVG(DAYS_IN_CURRENT_STAGE), 1) AS AVG_DAYS_IN_STAGE
FROM {FQ}SALES_PIPELINE_OPPORTUNITIES GROUP BY CURRENT_STAGE ORDER BY VALUE DESC'''),
    md('''> 💡 **気づいてほしいこと**
> - 解約リスク `CHURN_RISK_SCORE` は **0〜100** の値です（0〜1 ではありません）。
> - 商談名 `OPPORTUNITY_NAME` は、元データの時点で全件が空です。商談は `OPPORTUNITY_ID` で区別します。
> - 「停滞商談」「勝率」「推奨カバレッジ」といった**社内用語は、どのテーブルにもカラムとして存在しません**。
>   人間は「あの基準のことだな」と分かりますが、AI は分かりません。これを教えるのが 02 の Semantic View です。'''),
    md(f'''## Step 2. データの落とし穴：取引と製品がつながらない

取引の `PRODUCT_SKU` と製品カタログの `PRODUCT_SKU` で結合してみます。'''),
    sql("join_check", f'''SELECT
  (SELECT COUNT(*) FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE t JOIN {FQ}CUSTOMER_DIMENSION_TABLE c ON t.CUSTOMER_ID = c.CUSTOMER_ID)     AS TXN_TO_CUSTOMER,
  (SELECT COUNT(*) FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE t JOIN {FQ}SALES_REP_PERFORMANCE_TABLE r ON t.SALES_REP_ID = r.SALES_REP_ID) AS TXN_TO_REP,
  (SELECT COUNT(*) FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE t JOIN {FQ}PRODUCT_CATALOG_TABLE p ON t.PRODUCT_SKU = p.PRODUCT_SKU)        AS TXN_TO_PRODUCT_CATALOG,
  (SELECT COUNT(*) FROM {FQ}SALES_TRANSACTIONS_FACT_TABLE t JOIN {FQ}PRODUCT_PLAN_VIEW p ON t.PRODUCT_SKU = p.PRODUCT_SKU)            AS TXN_TO_PRODUCT_PLAN'''),
    md('''顧客・営業担当は 200 件すべて結合できますが、**製品カタログとは 0 件**です。
取引の SKU は `ENT-ANNUAL` のような「ティア＋請求サイクル」（6種類）、カタログは `ENT-ANN-011` のような個別製品（200種類）で、形式が違うためです（元教材のデータのままです）。

そこで `setup.sql` では、**プラン（ティア×請求サイクル）単位のビュー `PRODUCT_PLAN_VIEW`** を作っています。これなら 200 件すべて結合できます（`TXN_TO_PRODUCT_PLAN = 200`）。
このように「AI に渡す前にデータのつながりを確かめる」ことが、精度の土台になります。'''),
    sql("product_plan_view", f'''SELECT * FROM {FQ}PRODUCT_PLAN_VIEW ORDER BY PRODUCT_SKU'''),
    md('''## Step 3. 非構造化データ：PDF レポート 2 本

数字以外の「社内の基準」や「推奨アクション」は、PDF のレポートに書かれています。`setup.sql` で社内ステージ `DOCS_STAGE` にコピー済みです。

| PDF | 主な内容 |
|---|---|
| [Sales Performance Analysis](../data/pdfs/Sales%20Performance%20Analysis.pdf) | 地域・営業担当の分析、**推奨パイプラインカバレッジ 1.6 倍**、値引きの上限の目安 |
| [Customer Intelligence & Pipeline](../data/pdfs/Customer%20Intelligence%20%26%20Pipeline.pdf) | 解約リスクの高い顧客、**停滞商談（40日超）**と推奨アクション、施策の優先順位 |

> 💡 PDF の中身は GitHub の [`data/pdfs/`](../data/pdfs/) でそのまま開けます（Snowflake に取り込んでいるものと同じファイルです）。'''),
    sql("list_docs", f'''SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED FROM DIRECTORY(@{FQ}DOCS_STAGE)'''),
    md('''## このハンズオンで作るもの

| 種類 | 名前 | 役割 | 作る Notebook |
|---|---|---|---|
| Semantic View（改善前） | `SALES_OPS_SV_BASIC` | テーブルを並べただけの最小構成 | 02 |
| Semantic View（改善版） | `SALES_OPS_SEMANTIC_VIEW` | 説明・同義語・社内 KPI・検証済みクエリ入り | 02 |
| Cortex Search Service | `SALES_DOCS_SEARCH` | PDF レポートの意味検索 | 03 |
| Cortex Agent | `SALES_OPS_AGENT` | Analyst（数字）と Search（文書）を使い分けて答える | 04 |
| MCP Server / OAuth | `SALES_OPS_MCP_SERVER` / `SALES_OPS_QUICK_SUITE_OAUTH` | Amazon Quick から呼ぶ窓口 | 05 |

✅ 01 はここまでです。次は `02_cortex_analyst.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 02
nb2 = [
    md(f'''# 02. Cortex Analyst ― Semantic View を作り、精度を上げる

**Cortex Analyst** は、自然言語の質問を SQL に変換して実行する機能です。
その「辞書」になるのが **Semantic View** です。このNotebookでは、

1. テーブルを並べただけの **最小構成（v1）** を作り、
2. 説明・同義語・社内 KPI・検証済みクエリを入れた **改善版（v2）** を作り、
3. **同じ 9 問の質問で正答率を自動採点**して、改善の効果を数字で確かめます。

**前提**：`01_explore_data.ipynb` を実行済みであること'''),
    md(SETUP_MD),
    sql("setup", SETUP_SQL),
    md('''## Step 1. Semantic View とは

AI にテーブルだけを渡すと、「売上」「停滞商談」がどのカラムのどんな計算なのかを列名から**推測**します。
推測がぶれると、同じ質問でも答えが変わったり、社内の数字と合わなくなったりします。Semantic View は、その推測をなくすための「データの辞書」です。

| 要素 | 意味 | 例 |
|---|---|---|
| 論理テーブル | 物理テーブルに分かりやすい名前を付けたもの | `TRANSACTIONS` = `SALES_TRANSACTIONS_FACT_TABLE` |
| ディメンション | 切り口（GROUP BY に使う項目） | 地域、業種、商談ステージ |
| ファクト | 行ごとの数値 | 取引金額、滞留日数 |
| メトリクス | 集計の定義（**社内 KPI**） | 停滞商談数 = 未クローズかつ滞留40日超の件数 |
| リレーション | テーブル同士のつなぎ方 | 取引 → 顧客（CUSTOMER_ID） |
| 説明・同義語 | 意味や言い換え | 「勝率」= win rate、「解約リスクは 0〜100」 |
| 検証済みクエリ | よくある質問と正解 SQL のペア | 「停滞している商談は何件？」 |'''),
    md('''## Step 2. 最小構成の Semantic View（v1）を作る

まずは **テーブルとカラムを並べただけ** の Semantic View を作ります。
説明・同義語・社内 KPI・検証済みクエリは入れていません。製品は、元教材と同じく取引の SKU でカタログに結合しています。

### 方法 A：GUI（Semantic View Autopilot）で作る

1. Snowsight 左メニュー **「Workspaces」** を開き、**「Add new」→「Semantic View」** を選ぶ（Autopilot のウィザードが開きます）
2. 保存先に `CORTEX_QUICK_HOL_DB` / `CORTEX_QUICK_HOL_SCHEMA`、名前に **`SALES_OPS_SV_BASIC`** を入力し、**Next**
3. **SQL Queries（文脈）は空のまま**にする（v1 は「何も教えていない状態」にしたいため）
4. **Select tables** で次の 5 つを選び、**Next**
   - `SALES_TRANSACTIONS_FACT_TABLE` / `CUSTOMER_DIMENSION_TABLE` / `PRODUCT_CATALOG_TABLE` / `SALES_REP_PERFORMANCE_TABLE` / `SALES_PIPELINE_OPPORTUNITIES`
5. **Select columns** はすべて選び、**サンプル値の追加** と **AI による説明の自動生成** は **オフ**にする
6. **Create and save** → **Save and run**。数分で作成されます
7. 作成後、Semantic Studio で **Logical tables / Relationships** を開き、どんな内容が自動で作られたかを見る

> ⚠️ Autopilot はリレーションや説明を自動で推測するため、GUI 版の v1 は下の SQL 版と完全には一致しません。
> **Step 4 の正答率比較を SQL 版と同じ条件で行うため、デモの後は方法 B のセルを実行して v1 を SQL 版にそろえてください。**

> ℹ️ GUI の手順は Snowflake 公式ドキュメントをもとに書いています。画面のラベルや順番が多少違う場合があります。\n> 迷ったら **方法 B（SQL）** のセルを実行すれば、同じ名前・同じ設定で作られます（GUI で作ったものは上書きされます）。

### 方法 B：SQL で作る（`CREATE SEMANTIC VIEW`）'''),
    sql("create_sv_basic", (HERE / "semantic_view_basic.sql").read_text().strip().rstrip(";")),
    md('''### v1 で質問してみる

Cortex Analyst だけを持つ評価用の Agent を作り、質問してみます（Agent については 04 で詳しく扱います。ここでは「Analyst を呼ぶための入れ物」と考えてください）。'''),
    sql("create_eval_agent_v1", eval_agent_sql("EVAL_AGENT_V1", "SALES_OPS_SV_BASIC")),
    md(ASK_AGENT_MD),
    sql("create_ask_agent", ASK_AGENT_SQL),
    sql("ask_v1_stalled", ask("停滞している商談は何件？", "EVAL_AGENT_V1")),
    md('''> 💡 回答の数字と、生成された SQL の条件を見てください。「停滞」の定義（40日超・未クローズ）を知らないため、
> Agent は自分で条件を推測するか、答えられないと返します。01 で確かめた正解は **43 件** です。'''),
    md('''## Step 3. 改善版の Semantic View（v2）を作る

v1 に次を加えた改善版を、YAML 形式で作ります（`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`）。

| # | 追加するもの | 解決する問題 |
|---|---|---|
| 1 | **説明（description）と同義語（synonyms）**（日本語含む） | 「解約リスクは 0〜100」「勝率＝win rate」などカラム名だけでは伝わらない意味を補う |
| 2 | **リレーションの修正**（取引 → `PRODUCT_PLAN_VIEW`） | v1 では製品の結合が 0 件。プラン単位でつなぎ直す |
| 3 | **社内 KPI のメトリクス** | 停滞商談・失注リスク商談・勝率・推奨カバレッジ未満の人数などを、PDF レポートの基準どおりに定義 |
| 4 | **検証済みクエリ（verified_queries）** | よく聞かれる質問に「お墨付きの SQL」を用意。`use_as_onboarding_question: true` で Snowflake Intelligence の質問候補にも出る |

追加した社内 KPI の例：

| メトリクス | 定義 | 根拠 |
|---|---|---|
| `STALLED_DEAL_COUNT` | 未クローズで現ステージ滞留が **40日超** の件数 | Customer Intelligence レポート |
| `AT_RISK_DEAL_COUNT` / `AT_RISK_PIPELINE_VALUE` | 未クローズ・**競合あり・決裁者未接触** の件数／金額 | 同上 |
| `WIN_RATE_PCT` | 受注 ÷（受注＋失注）× 100 | 社内の定義 |
| `REPS_BELOW_COVERAGE_TARGET` | パイプラインカバレッジ **1.6 倍未満** の営業担当数 | Sales Performance レポート |
| `EXPANSION_TARGET_CUSTOMERS` | 解約リスク **30 未満** かつ拡大余地 High/Medium の顧客数 | 社内の定義 |

### YAML を取り込んで作る

v2 は同義語・KPI・検証済みクエリが多く、画面で 1 つずつ入力すると時間がかかります。そこで、**用意済みの YAML（定義書）を SQL 1 本で取り込み**、中身の確認と追加の編集は GUI で行います。
YAML の中身は GitHub の [`semantic_views/sales_ops_semantic_view.yaml`](../semantic_views/sales_ops_semantic_view.yaml) と同じです（ダウンロードは不要です）。'''),
    sql("create_semantic_view", SV_CELL),
    md("作成できたか確認し、ハンズオン用ロールに参照権限を付けます。"),
    sql("show_semantic_views", "SHOW SEMANTIC VIEWS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA"),
    sql("grant_sv", """GRANT SELECT ON SEMANTIC VIEW CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SV_BASIC TO ROLE CORTEX_QUICK_HOL_ROLE;
GRANT SELECT ON SEMANTIC VIEW CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW TO ROLE CORTEX_QUICK_HOL_ROLE"""),
    md('''### SQL で直接クエリしてみる

`SEMANTIC_VIEW()` 関数を使うと、**メトリクス名を指定するだけ**で、定義どおりの集計を SQL から使えます。
社内 KPI が Semantic View の中に「部品」として入ったことが分かります。'''),
    sql("sv_kpis", '''SELECT * FROM SEMANTIC_VIEW(
  CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
  METRICS PIPELINE.STALLED_DEAL_COUNT, PIPELINE.AT_RISK_DEAL_COUNT, PIPELINE.WIN_RATE_PCT,
          REPS.REPS_BELOW_COVERAGE_TARGET
)'''),
    sql("sv_revenue_by_plan", '''SELECT * FROM SEMANTIC_VIEW(
  CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
  DIMENSIONS PRODUCT_PLANS.PRODUCT_TIER
  METRICS TRANSACTIONS.TOTAL_REVENUE
)
ORDER BY TOTAL_REVENUE DESC'''),
    md('''### Snowsight で中身を見る（GUI）

1. Snowsight 左メニュー **「AI と ML」→「Cortex Analyst」**（または **「Workspaces」の Semantic Studio**）を開く
2. `CORTEX_QUICK_HOL_DB` の `SALES_OPS_SEMANTIC_VIEW` をクリック
3. **Logical tables / Relationships / Metrics / Verified queries** を開き、`SALES_OPS_SV_BASIC` と見比べる（`STALLED_DEAL_COUNT` などの社内 KPI や、9 件の検証済みクエリが入っています）
4. （デモ）GUI で編集してみる：たとえば **Synonyms** に同義語を 1 つ追加する、**Verified queries** に質問と SQL を 1 つ追加する → **Save**

> ⚠️ Step 4 の正答率はこの内容が前提です。GUI で大きく変更した場合は、上の `create_semantic_view` セルを再実行すれば元の定義に戻ります。
>
> ℹ️ GUI の画面ラベルは公式ドキュメントをもとに書いています。実際の表記と多少違う場合があります。'''),
    md('''## Step 4. 正答率を比べる（v1 vs v2）

同じ 9 問を v1・v2 それぞれに投げ、**Analyst が生成した SQL を実行して、結果に正解の値が含まれるか**で自動採点します。
正解は 01 で SQL を使って確かめた値です。

| # | 質問 | 正解 | ポイント |
|---|---|---|---|
| 1 | 北米の売上合計は？ | $5,947,306.61 | 基本の集計 |
| 2 | Enterprise ティアの売上合計は？ | $7,816,021.78 | 製品の結合（データの落とし穴） |
| 3 | 売上が最も大きい業種はどこ？ | Technology | テーブルをまたぐ集計 |
| 4 | 停滞している商談は何件？ | 43 件 | 社内 KPI |
| 5 | 目標を達成している営業担当は何人？ | 87 人 | 基本の集計 |
| 6 | 解約リスクが低く、拡大余地が High の顧客は何社？ | 25 社 | 「低い」＝30 未満（0〜100 の尺度） |
| 7 | 失注リスクのある商談の金額合計は？ | $3,629,041.99 | 社内 KPI |
| 8 | パイプラインカバレッジが推奨水準を下回る営業担当は何人？ | 63 人 | PDF に書かれた基準（1.6 倍） |
| 9 | 商談の勝率は？ | 69.7% | 社内 KPI |

> 9 問を 5 並列で投げるので、1 回の採点は 30〜60 秒ほどです。AI の回答は毎回少しずつ変わるため、v1 の点数は実行ごとに前後します。'''),
    sql("create_eval_agent_v2", eval_agent_sql("EVAL_AGENT_V2", "SALES_OPS_SEMANTIC_VIEW")),
    md('''採点は、9 問を並列で投げて結果を照合する処理なので、ここだけ Python で書いています（`session` は Python から SQL を実行するための接続です）。'''),
    py('''import json, time
from concurrent.futures import ThreadPoolExecutor
from snowflake.snowpark.context import get_active_session
session = get_active_session()
DB, SCHEMA = "CORTEX_QUICK_HOL_DB", "CORTEX_QUICK_HOL_SCHEMA"

EVAL_SET = [
    ("北米の売上合計は？",                                     5947306.61),
    ("Enterprise ティアの売上合計は？",                         7816021.78),
    ("売上が最も大きい業種はどこ？",                            "Technology"),
    ("停滞している商談は何件？",                                43),
    ("目標を達成している営業担当は何人？",                      87),
    ("解約リスクが低く、拡大余地が High の顧客は何社？",        25),
    ("失注リスクのある商談の金額合計は？",                      3629041.99),
    ("パイプラインカバレッジが推奨水準を下回る営業担当は何人？", 63),
    ("商談の勝率は？",                                          69.7),
]

def _matches(expected, values):
    for v in values:
        if v is None:
            continue
        if isinstance(expected, str):
            if expected.lower() in str(v).lower():
                return True
        else:
            try:
                if abs(float(v) - expected) <= max(0.5, abs(expected) * 0.005):
                    return True
            except (TypeError, ValueError):
                pass
    return False

def _grade(agent_fqn, question, expected):
    t = time.time()
    payload = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
    try:
        raw = session.sql("SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS R", params=[agent_fqn, payload]).collect()[0]["R"]
        resp = json.loads(raw) if isinstance(raw, str) else raw
        sqls = [x["json"]["sql"] for c in resp.get("content", []) if c.get("type") == "tool_result"
                for x in c.get("tool_result", {}).get("content", []) if x.get("json", {}).get("sql")]
        values = [v for row in session.sql(sqls[-1]).collect()[:50] for v in row] if sqls else []
        return {"QUESTION": question, "OK": _matches(expected, values), "SEC": round(time.time() - t)}
    except Exception as e:
        return {"QUESTION": question, "OK": False, "SEC": round(time.time() - t), "ERROR": str(e)[:100]}

def evaluate(agent_name: str):
    fqn = f"{DB}.{SCHEMA}.{agent_name}"
    with ThreadPoolExecutor(max_workers=5) as ex:
        rows = list(ex.map(lambda qa: _grade(fqn, *qa), EVAL_SET))
    print(f"=== {agent_name}: {sum(r['OK'] for r in rows)} / {len(rows)} 正解")
    for r in rows:
        print(f"  {'○' if r['OK'] else '×'}  {r['QUESTION']}")
    return rows'''),
    py('''result_v1 = evaluate("EVAL_AGENT_V1")
result_v2 = evaluate("EVAL_AGENT_V2")'''),
    md('''### 結果を並べる'''),
    py('''import pandas as pd

df = pd.DataFrame({
    "質問": [r["QUESTION"] for r in result_v1],
    "v1（最小構成）": ["○" if r["OK"] else "×" for r in result_v1],
    "v2（改善版）": ["○" if r["OK"] else "×" for r in result_v2],
})
print(f"正答率  v1: {sum(r['OK'] for r in result_v1)}/{len(result_v1)}  →  v2: {sum(r['OK'] for r in result_v2)}/{len(result_v2)}")
df'''),
    md('''> ✅ 検証したアカウント（2026年10月）では **v1: 4/9 → v2: 9/9** でした。
>
> v1 が間違えた質問を見ると、**「データのつながり（製品）」「社内用語（停滞・失注リスク・勝率）」「社外の基準（推奨カバレッジ）」** の 3 種類に分かれます。
> どれもモデルを賢くするのではなく、**Semantic View にビジネスの定義を書く**ことで解決しています。
>
> 💡 **自分でも試してみましょう**：v2 で間違える質問を見つけたら、同義語・説明・検証済みクエリを足して `create_semantic_view` を再実行し、もう一度採点します。
> この「評価セットで測る → 定義を足す → もう一度測る」の繰り返しが、本番運用での精度向上の基本です。'''),
    md('''### 後片付け（評価用 Agent）

評価用の Agent は以降使わないので削除します（Semantic View v1 は比較用に残しておきます）。'''),
    sql("drop_eval_agents", """DROP AGENT IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.EVAL_AGENT_V1;
DROP AGENT IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.EVAL_AGENT_V2"""),
    md('''✅ 02 はここまでです。次は `03_cortex_search.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 03
nb_search = [
    md('''# 03. Cortex Search ― PDF レポートを検索できるようにする

02 の Cortex Analyst は「テーブルの数字」に答えます。一方、**「推奨カバレッジは？」「停滞商談にはどう対応すべき？」** のような答えは PDF のレポートにあります。
**Cortex Search** は、文書を意味で検索できるようにするサービスです。

```
PDF（DOCS_STAGE。中身は GitHub の data/pdfs/ で見られます）
  ↓ ① AI_PARSE_DOCUMENT   … PDF からテキストを抽出（表は Markdown に）
  ↓ ② SPLIT_TEXT_RECURSIVE_CHARACTER … 検索しやすい長さ（チャンク）に分割
  ↓ ③ CREATE CORTEX SEARCH SERVICE  … ベクトル＋キーワードのハイブリッド検索インデックス
Cortex Search Service `SALES_DOCS_SEARCH` → 04 で Agent のツールにする
```

**前提**：`02_cortex_analyst.ipynb` を実行済みであること'''),
    md(SETUP_MD),
    sql("setup", SETUP_SQL),
    md('''## Step 1. PDF からテキストを取り出す

`AI_PARSE_DOCUMENT` の `LAYOUT` モードは、見出しや**表の構造を保ったまま** Markdown のテキストにします。'''),
    sql("parse_docs", f'''CREATE OR REPLACE TABLE {FQ}DOCS_PARSED AS
SELECT RELATIVE_PATH AS FILE_NAME,
       AI_PARSE_DOCUMENT(TO_FILE('@{FQ}DOCS_STAGE', RELATIVE_PATH), {{'mode': 'LAYOUT'}}):content::STRING AS CONTENT
FROM DIRECTORY(@{FQ}DOCS_STAGE)'''),
    sql("show_parsed", f'''SELECT FILE_NAME, LENGTH(CONTENT) AS CHARS, LEFT(CONTENT, 500) AS HEAD FROM {FQ}DOCS_PARSED'''),
    md('''## Step 2. チャンクに分割する

PDF 1 本を丸ごと 1 件として登録せず、短い「チャンク」に分けてから検索サービスに入れます。理由は 3 つです。

| 理由 | 内容 |
|---|---|
| ベクトル化できる長さに上限がある | 一度に読める長さは埋め込みモデルによって違い、今回使う `snowflake-arctic-embed-l-v2.0` は **512 トークン**です（`-8k` 版は 8,192、`voyage-multilingual-2` は 32,000）。上限を超えた部分は**ベクトル検索では使われません**（キーワード検索では全文が使われます）。長く読めるモデルでも、Snowflake は 1 チャンク 512 トークン以下を推奨しています |
| 検索の精度が上がる | 1 件の中に話題がたくさん混ざると、質問との「意味の近さ」がぼやけます。話題ごとに分けると、関係する段落だけが上位に来ます |
| Agent に渡す量が適切になる | Agent は検索結果を読んで回答を作ります。PDF 全体ではなく関係する段落だけを渡すほうが、回答が正確で速くなります |

ここでは約 800 文字ずつ（前後 100 文字は重ねて、文の途中で切れても前後の文脈が残るように）分割します。
`'markdown'` を指定すると、見出しや段落の切れ目を優先して分割します。'''),
    sql("chunk_docs", f'''CREATE OR REPLACE TABLE {FQ}DOCS_CHUNKS AS
SELECT d.FILE_NAME || '#' || c.INDEX AS CHUNK_ID,
       d.FILE_NAME,
       c.INDEX        AS CHUNK_NO,
       c.VALUE::STRING AS CHUNK
FROM {FQ}DOCS_PARSED d,
     LATERAL FLATTEN(SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER(d.CONTENT, 'markdown', 800, 100)) c'''),
    sql("chunk_counts", f'''SELECT FILE_NAME, COUNT(*) AS CHUNKS, ROUND(AVG(LENGTH(CHUNK))) AS AVG_CHARS
FROM {FQ}DOCS_CHUNKS GROUP BY FILE_NAME'''),
    md('''## Step 3. Cortex Search Service を作る

Step 2 の `DOCS_CHUNKS` を検索サービスにします。決めることは次の 5 つで、GUI の各ステップと SQL の各句は 1 対 1 で対応しています。

| GUI のステップ | SQL | 今回の値 | 何のために決めるか |
|---|---|---|---|
| データを選択 | `AS SELECT ... FROM` | `DOCS_CHUNKS` テーブル | 検索対象にする文書（1 行 = 1 チャンク）を決める |
| 検索列を選択 | `ON` | `CHUNK` | **質問と照らし合わせる本文**。この列がベクトル化され、意味とキーワードの両方で検索されます |
| 属性を選択 | `ATTRIBUTES` | `FILE_NAME` | **絞り込みに使う列**。「Sales Performance Analysis だけから探す」のように、検索時にフィルタをかけられます |
| 列を選択 | `AS SELECT` の列 | `CHUNK_ID` / `CHUNK` / `FILE_NAME` / `CHUNK_NO` | **検索結果として返す列**。04 の Agent は `CHUNK_ID` を出典の ID、`FILE_NAME` を出典名として使うので、必ず含めます |
| インデックス作成を構成 | `WAREHOUSE` / `TARGET_LAG` / `EMBEDDING_MODEL` | `CORTEX_QUICK_HOL_WH` / `1 day` / `snowflake-arctic-embed-l-v2.0` | 索引を作るウェアハウス、元データの変更に追従する間隔、ベクトル化に使うモデル |

> 💡 **埋め込みモデルは多言語のものを選びます。** 既定のモデルは英語向けで、このハンズオンで試したところ、日本語の質問に対して関係の薄い表が上位に来ました。`snowflake-arctic-embed-l-v2.0` なら、英語の PDF を日本語の質問で検索できます。
>
> 作成には 1〜2 分かかります。

### 方法 A：GUI（AI と ML → Cortex Search）で作る

1. Snowsight 左メニュー **「AI と ML」→「Cortex Search」** を開き、**「作成」**
2. **新しいサービス**：ロール `ACCOUNTADMIN`、ウェアハウス `CORTEX_QUICK_HOL_WH`、データベース / スキーマ `CORTEX_QUICK_HOL_DB` / `CORTEX_QUICK_HOL_SCHEMA`、サービス名 **`SALES_DOCS_SEARCH`**（**大文字のまま**）
3. **データを選択**：テーブル **`DOCS_CHUNKS`**
4. **検索列を選択**：**`CHUNK`**
5. **属性を選択**：**`FILE_NAME`**
6. **列を選択**：`CHUNK_ID` / `CHUNK` / `FILE_NAME` / `CHUNK_NO` の 4 つ
7. **インデックス作成を構成**：ターゲットラグ **1 day**。埋め込みモデルを選べる場合は **`snowflake-arctic-embed-l-v2.0`** → **作成**
8. 作成されたら同じ画面の **Playground** で「推奨されるパイプラインカバレッジの目安は？」と検索し、1.6 倍が書かれた段落が上位に来ることを確かめる

> ⚠️ 埋め込みモデルを選べなかった場合は英語向けのモデルで作られるため、**方法 B のセルを実行して作り直してください**（同じ名前で上書きされます）。
>
> ⚠️ GUI ではサービス名がダブルクォート付きで作られます。小文字が混じると SQL や Agent から `SALES_DOCS_SEARCH` で参照できなくなるため、**必ず大文字で入力**してください。

### 方法 B：SQL で作る（`CREATE CORTEX SEARCH SERVICE`）'''),
    sql("create_search_service", f'''CREATE OR REPLACE CORTEX SEARCH SERVICE {FQ}SALES_DOCS_SEARCH
  ON CHUNK
  ATTRIBUTES FILE_NAME
  WAREHOUSE = CORTEX_QUICK_HOL_WH
  TARGET_LAG = '1 day'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
  AS SELECT CHUNK_ID, CHUNK, FILE_NAME, CHUNK_NO FROM {FQ}DOCS_CHUNKS'''),
    md("GUI・SQL どちらで作った場合も、次のセルで権限を付けます。"),
    sql("grant_search", "GRANT USAGE ON CORTEX SEARCH SERVICE CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_DOCS_SEARCH TO ROLE CORTEX_QUICK_HOL_ROLE"),
    md('''## Step 4. 検索してみる

`SEARCH_PREVIEW` で、質問に近いチャンクを上位から取り出します。英語の PDF に**日本語で**質問しています。
質問を変えて試す場合は、SQL の `query` の部分を書き換えて実行してください。'''),
    sql("search_coverage", search_sql("推奨されるパイプラインカバレッジの目安は？")),
    sql("search_stalled", search_sql("停滞している商談にはどう対応すべき？")),
    sql("search_churn", search_sql("解約リスクが高い顧客に共通する特徴は？")),
    md('''> ✅ それぞれの質問に、関係する段落（推奨 1.6 倍、役員スポンサーの関与、技術的なエスカレーションなど）が上位に返れば成功です。
'''),
    md('''✅ 03 はここまでです。次は `04_cortex_agent.ipynb` で、Analyst と Search を 1 つの Agent にまとめます。'''),
]

# ------------------------------------------------------------------ 04
nb_agent = [
    md('''# 04. Cortex Agent ― Analyst と Search を組み合わせる

**Cortex Agent** は、質問を理解して**どのツールを使うかを自分で判断し**、結果を回答にまとめる AI エージェントです。

| ツール | 中身 | 得意な質問 |
|---|---|---|
| `sales_ops_analyst`（Cortex Analyst） | 02 の Semantic View v2 | 「何件？」「いくら？」「誰？」 |
| `sales_docs_search`（Cortex Search） | 03 の PDF 検索 | 「推奨は？」「どう対応すべき？」「なぜ？」 |

**両方を使うと**、「レポートの推奨値を、実際のデータが満たしているか」のような質問に 1 回で答えられます。

**前提**：`03_cortex_search.ipynb` を実行済みであること'''),
    md(SETUP_MD),
    sql("setup", SETUP_SQL),
    md('''## Step 1. Agent を作る

| 設定（SQL の spec の項目） | 内容 |
|---|---|
| `models.orchestration` | 使うモデル。`auto` で Snowflake が自動選択 |
| `instructions.orchestration` | **ツールの使い分けの指示**。数字は Analyst、推奨・方針は Search、比較は両方 |
| `instructions.response` | 回答の書き方。日本語の質問には日本語で答える |
| `tools` / `tool_resources` | 2 つのツールと、それぞれの参照先（Semantic View、Search Service） |

### 方法 A：GUI（AI と ML → Agents）で作る

1. Snowsight 左メニュー **「AI と ML」→「Agents」** を開き、**「Create agent」**
2. データベース / スキーマに `CORTEX_QUICK_HOL_DB` / `CORTEX_QUICK_HOL_SCHEMA`、**Agent object name** に **`SALES_OPS_AGENT`**、**Display name** に `Sales Ops Agent` を入力し、**Create agent**
3. 作成した Agent を開き、**「Edit」**
4. **Tools** → **Cortex Analyst** の **「+ Add」**
   - Name：`sales_ops_analyst`
   - Semantic view：**`SALES_OPS_SEMANTIC_VIEW`**（02 の v2）
   - Warehouse：**`CORTEX_QUICK_HOL_WH`**
   - Description：下の SQL の `sales_ops_analyst` の description を貼り付け → **Add**
5. **Tools** → **Cortex Search Services** の **「+ Add」**
   - Name：`sales_docs_search`
   - Search service：**`SALES_DOCS_SEARCH`**（03）
   - ID column：`CHUNK_ID`、Title column：`FILE_NAME`
   - Description：下の SQL の `sales_docs_search` の description を貼り付け → **Add**
6. **Orchestration**
   - Orchestration model：`auto`
   - Planning instructions：下の SQL の `orchestration:` の文章を貼り付け
   - Response instruction：下の SQL の `response:` の文章を貼り付け（**日本語で答える指示**が入っています）
7. **Save**。右側のチャット欄で「停滞商談は何件？」と聞いて、回答が返ることを確認する

> 💡 ここで画面に入力した内容は、下の SQL の spec と 1 対 1 で対応しています。SQL を見比べると「GUI の設定＝spec の YAML」であることが分かります。

> ℹ️ GUI の手順は Snowflake 公式ドキュメントをもとに書いています。画面のラベルや順番が多少違う場合があります。\n> 迷ったら **方法 B（SQL）** のセルを実行すれば、同じ名前・同じ設定で作られます（GUI で作ったものは上書きされます）。

### 方法 B：SQL で作る（`CREATE AGENT`）'''),
    sql("create_agent", '''CREATE OR REPLACE AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT
  COMMENT = 'Sales Operations agent (Cortex Analyst + Cortex Search)'
  FROM SPECIFICATION $$
  models:
    orchestration: auto

  instructions:
    system: >
      You are a Sales Operations analyst. Help users explore revenue, pipeline health,
      sales rep performance, customer segmentation, product mix, and marketing attribution.
    orchestration: >
      Use sales_ops_analyst for numbers from the sales data (revenue, pipeline, reps, customers,
      products, marketing). Use sales_docs_search for recommendations, benchmarks, policies and
      qualitative insights in the internal PDF reports. When a question compares the data with a
      recommendation in the reports, use both tools.
    response: >
      Provide concise, actionable answers. Format USD values as currency and rates as percentages.
      When you use the reports, mention the report name. Always reply in the same language as the
      user's question (reply in Japanese if the question is in Japanese).

  tools:
    - tool_spec:
        type: cortex_analyst_text_to_sql
        name: sales_ops_analyst
        description: >
          Structured sales operations data: revenue, pipeline, rep performance, customers,
          product plans, and marketing attribution. Includes company KPIs such as stalled deals,
          at-risk deals, win rate and pipeline coverage target.
    - tool_spec:
        type: cortex_search
        name: sales_docs_search
        description: >
          Internal PDF reports (Sales Performance Analysis, Customer Intelligence & Pipeline) with
          benchmarks, recommendations, and qualitative insights.

  tool_resources:
    sales_ops_analyst:
      semantic_view: CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW
      execution_environment:
        type: warehouse
        warehouse: CORTEX_QUICK_HOL_WH
    sales_docs_search:
      name: CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_DOCS_SEARCH
      max_results: 4
      title_column: FILE_NAME
      id_column: CHUNK_ID
  $$'''),
    md("GUI・SQL どちらで作った場合も、次のセルで権限を付けます（Quick からはハンズオン用ロールで実行されるため）。Agent を作り直すと権限は消えるので、そのたびに実行してください。"),
    sql("grant_agent", "GRANT USAGE ON AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT TO ROLE CORTEX_QUICK_HOL_ROLE"),
    sql("show_agent_grants", "SHOW GRANTS ON AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT"),
    md('''## Step 2. Agent に質問する

Quick につなぐ前に、Snowflake 上で答えられるかを確認します。**ここで失敗する場合は、Quick からも同じエラーになります。**
各回答の上に「使ったツール」が表示されます。質問によって Agent がツールを使い分けていることを確かめてください。'''),
    md(ASK_AGENT_MD + "（02 で作ったものと同じです。02 を飛ばした場合に備えて、ここでも作成します）"),
    sql("create_ask_agent", ASK_AGENT_SQL),
    md('''| # | 質問 | 使うはずのツール | 期待される結果（目安） |
|---|---|---|---|
| 1 | 地域別の売上を教えて | Analyst | 北米 約 $5.95M が最大 |
| 2 | 停滞商談は何件で、金額はいくら？ | Analyst | 43 件、約 $4.37M |
| 3 | レポートで推奨されているパイプラインカバレッジは？ | Search | 1.6 倍（Sales Performance Analysis） |
| 4 | 推奨カバレッジを下回っている営業担当は何人？推奨値の根拠も教えて | **両方** | 63 人、1.6 倍の根拠 |
| 5 | 停滞商談への推奨アクションは？対象の件数と金額も | **両方** | 役員スポンサーの関与など＋43 件 |

> 💡 1 回の質問には 15〜40 秒ほどかかります。Quick から呼ぶ場合も同じです（60 秒を超えるとタイムアウト）。'''),
    sql("ask_q1", ask("地域別の売上を教えて")),
    sql("ask_q2", ask("停滞商談は何件で、金額はいくら？")),
    sql("ask_q3", ask("レポートで推奨されているパイプラインカバレッジは？")),
    sql("ask_q4", ask("推奨カバレッジを下回っている営業担当は何人？推奨値の根拠も教えて")),
    sql("ask_q5", ask("停滞商談への推奨アクションは？対象の件数と金額も")),
    md('''### ハンズオン用ロールで実行できるか確認する

Quick からはハンズオン用ロールで実行されます。ロールを切り替えて同じように答えられるか確かめます。'''),
    sql("ask_as_hol_role_1", "USE ROLE CORTEX_QUICK_HOL_ROLE;\n" + ask("営業担当の目標達成率トップ3は？")),
    sql("ask_as_hol_role_2", ask("レポートで推奨されているパイプラインカバレッジは？")),
    md("確認できたら、ロールを ACCOUNTADMIN に戻します。"),
    sql("back_to_admin", "USE ROLE ACCOUNTADMIN"),
    md('''## Step 3. Agent Studio で確認・編集する（GUI）

作った Agent は、Snowsight の画面から確認・編集できます（方法 A で作った場合は、作成時の画面と同じです）。

1. Snowsight 左メニュー **「AI と ML」→「Agents」**（Agent Studio）を開く
2. `SALES_OPS_AGENT` をクリック
3. **「Configuration」** タブで次を確認する
   - **Tools**：`sales_ops_analyst`（Semantic View）と `sales_docs_search`（Cortex Search）の 2 つ
   - **Instructions**：ツールの使い分けの指示
4. 右側のチャット欄で、上の質問を試す。回答の下の **「思考過程（Thinking）」** を開くと、どのツールをどの順に呼んだかが分かります
5. （任意）**Sample questions** に質問例を追加し、右上の **「Save」** をクリック

> ⚠️ GUI で編集した後に、このNotebookの `create_agent` セルを再実行すると、**GUI の変更は上書きされます**。

> 💡 **Snowflake Intelligence でも使えます**：Snowsight 左メニュー **「AI と ML」→「Snowflake Intelligence」** で `SALES_OPS_AGENT` を選ぶと、チャット画面から同じ Agent に質問できます（02 で `use_as_onboarding_question: true` にした質問が候補に出ます）。'''),
    md('''> ✅ すべての質問に回答が返り、質問 4・5 で 2 つのツールが使われていれば成功です。

次は `05_mcp_and_oauth.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 05
nb5 = [
    md('''# 05. MCP Server と OAuth ― Amazon Quick から呼べるようにする

5本目では、04 で作った Agent を **外部（Amazon Quick）から呼べるように公開** します。
元教材では Cortex Code スキルの Step 5〜7 にあたる部分です。

| 作るもの | 役割 |
|---|---|
| MCP Server `SALES_OPS_MCP_SERVER` | Agent を MCP（標準プロトコル）のツールとして公開する窓口 |
| OAuth 連携 `SALES_OPS_QUICK_SUITE_OAUTH` | Quick のユーザーが Snowflake にログインするための仕組み |

**前提**：`04_cortex_agent.ipynb` を最後まで実行済みであること'''),
    md(SETUP_MD),
    sql("setup", SETUP_SQL + """;
SELECT CURRENT_USER() AS "ユーザー",
       REPLACE(CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME(), '_', '-') || '.snowflakecomputing.com' AS "アカウントホスト\""""),
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
        description: "Ask questions about sales operations data (revenue, pipeline, reps, customers, products, marketing) and the internal sales reports (recommendations, benchmarks)."
  $$'''),
    md('''## Step 2. 権限を付ける

MCP Server の USAGE だけでは、配下のツールは使えません。**Agent・Semantic View・Cortex Search の権限も必要**です（02〜04 で付与済み）。
ここでは MCP Server への USAGE を付け、ハンズオン用ロールにそろっているかをまとめて確認します（一覧の `CORTEX_AGENT_SERVER` が MCP Server です）。

> 💡 **元教材との違い**：AWS Workshop 5章 Step 6 では MCP Server への GRANT が2回書かれ、Agent への GRANT が抜けています。本ハンズオンでは 04 で Agent への GRANT を行っています。'''),
    sql("grant_mcp", """GRANT USAGE ON MCP SERVER CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_MCP_SERVER TO ROLE CORTEX_QUICK_HOL_ROLE;
-- ハンズオン用ロールに付いている権限を一覧（MCP Server・Agent・Semantic View・Cortex Search の 4 つがあれば OK）
SHOW GRANTS TO ROLE CORTEX_QUICK_HOL_ROLE
  ->> SELECT "privilege", "granted_on", "name" FROM $1
      WHERE "granted_on" IN ('CORTEX_AGENT_SERVER', 'CORTEX_AGENT', 'SEMANTIC_VIEW', 'CORTEX_SEARCH_SERVICE')
      ORDER BY "granted_on", "name\""""),
    sql("show_mcp_servers", '''SHOW MCP SERVERS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA'''),
    md('''## Step 3. 接続ユーザーの既定ロールを設定する

Quick から OAuth でログインしたとき、Snowflake は **そのユーザーのデフォルトロール／デフォルトウェアハウス** で処理します。

- Quick からの処理は、セッションで切り替えたロールではなく **DEFAULT_ROLE** で行われます。
- ACCOUNTADMIN / SECURITYADMIN / ORGADMIN は OAuth でのログインが**ブロック**されるため、DEFAULT_ROLE が ACCOUNTADMIN のままだと Quick から接続できません。
- そこで、Quick でログインするユーザー（＝今このNotebookを実行しているユーザー）の DEFAULT_ROLE を `CORTEX_QUICK_HOL_ROLE` に変えます。

> 💡 変更後も、Snowsight 右上のロール切り替えや `USE ROLE ACCOUNTADMIN` で管理者として作業できます（次回ログイン時の初期ロールが変わるだけです）。
> このNotebookも Step 0 で `USE ROLE ACCOUNTADMIN` を実行しているので影響ありません。元に戻す方法は末尾のクリーンアップを参照してください。

> 💡 あわせて、ユーザーの `ALLOWED_INTERFACES` を `ALL` にします（制限されていると Quick がログイン画面を繰り返し表示します。既定値は `ALL` なので、通常は変化しません）。
>
> 既定ロールを変えたくない場合は、このセルを実行しないでください（その場合 Quick からは接続できません）。'''),
    sql("set_default_role", """SET HOL_USER = CURRENT_USER();
ALTER USER IDENTIFIER($HOL_USER) SET DEFAULT_ROLE = CORTEX_QUICK_HOL_ROLE;
ALTER USER IDENTIFIER($HOL_USER) SET DEFAULT_WAREHOUSE = CORTEX_QUICK_HOL_WH;
ALTER USER IDENTIFIER($HOL_USER) SET ALLOWED_INTERFACES = ('ALL');
DESC USER IDENTIFIER($HOL_USER)
  ->> SELECT "property", "value" FROM $1 WHERE "property" IN ('DEFAULT_ROLE', 'DEFAULT_WAREHOUSE', 'ALLOWED_INTERFACES')"""),
    md('''## Step 4. OAuth 連携を作る

Amazon Quick のユーザーは OAuth で Snowflake にログインします。ログイン後の処理は、そのユーザーのロールの権限内で行われます（**RBAC がそのまま効く**）。

| 設定 | 値 | 意味 |
|---|---|---|
| `OAUTH_CLIENT_TYPE` | `CONFIDENTIAL` | Client Secret を使う方式 |
| `OAUTH_REDIRECT_URI` | Quick のコールバック URL（us-west-2） | ログイン後の戻り先。**Quick のリージョンと完全一致**が必要 |
| `OAUTH_ALTERNATE_REDIRECT_URIS` | 同（us-east-1） | 追加で受け付ける戻り先。これで us-west-2 / us-east-1 どちらの Quick でも接続できます |
| `OAUTH_ISSUE_REFRESH_TOKENS` | `TRUE` | 再ログインなしで使い続けられるようにする |
| `OAUTH_USE_SECONDARY_ROLES` | `NONE` | DEFAULT_ROLE の権限だけで動かす（MCP 向けの推奨設定）。ユーザーが ACCOUNTADMIN を持っていても、Quick 経由ではハンズオン用ロールの権限に限定されます |
| `BLOCKED_ROLES_LIST` | 既定（ACCOUNTADMIN 等） | 管理者ロールでの OAuth ログインを禁止 |
| `OAUTH_REFRESH_TOKEN_VALIDITY` | `86400` | リフレッシュトークンの有効期間（秒、1日） |

作成には ACCOUNTADMIN が必要です。

> ⚠️ このセルを再実行すると **Client ID / Secret が変わります**。Quick 側に登録した後で再実行した場合は、Quick のコネクタも作り直してください。'''),
    sql("create_oauth", """CREATE OR REPLACE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = 'https://us-west-2.quicksight.aws.amazon.com/sn/oauthcallback'
  OAUTH_ALTERNATE_REDIRECT_URIS = ('https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback')
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_USE_SECONDARY_ROLES = 'NONE'
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400"""),
    md('''## Step 5. Amazon Quick に入力する値を表示する

次のセルで、Quick のコネクタ設定に必要な値をまとめて表示します。手順は `docs/02_quick_setup_guide_ja.md` を参照してください。

> ⚠️ **Client Secret は画面共有で見せないよう注意してください。** 既定では伏せ字で表示し、1 行目を `SET SHOW_SECRET = TRUE;` にしたときだけ全文を表示します。
> Quick に貼り付けるときだけ `TRUE` にして実行し、貼り付け後は `FALSE` に戻して再実行してください。

> 💡 Quick で OAuth ログイン画面が出たら、**この Snowflake アカウントのユーザー名とパスワード**でログインします（MFA を登録済みならその確認も求められます）。'''),
    sql("quick_settings", """-- Quick に Client secret を貼り付けるときだけ TRUE にする（貼り付けたら FALSE に戻す）
SET SHOW_SECRET = FALSE;
WITH s AS (SELECT PARSE_JSON(SYSTEM$SHOW_OAUTH_CLIENT_SECRETS('SALES_OPS_QUICK_SUITE_OAUTH')) AS J),
     h AS (SELECT 'https://' || REPLACE(CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME(), '_', '-') || '.snowflakecomputing.com' AS B)
SELECT "項目", "値" FROM (
            SELECT 1 AS O, 'MCP server endpoint' AS "項目",
                   B || '/api/v2/databases/CORTEX_QUICK_HOL_DB/schemas/CORTEX_QUICK_HOL_SCHEMA/mcp-servers/SALES_OPS_MCP_SERVER' AS "値" FROM h
  UNION ALL SELECT 2, 'Client ID', J:OAUTH_CLIENT_ID::STRING FROM s
  UNION ALL SELECT 3, 'Client secret', IFF($SHOW_SECRET, J:OAUTH_CLIENT_SECRET::STRING,
                   LEFT(J:OAUTH_CLIENT_SECRET::STRING, 4) || REPEAT('*', LENGTH(J:OAUTH_CLIENT_SECRET::STRING) - 4)) FROM s
  UNION ALL SELECT 4, 'Token URL', B || '/oauth/token-request' FROM h
  UNION ALL SELECT 5, 'Authorization URL', B || '/oauth/authorize' FROM h
  UNION ALL SELECT 6, 'Redirect URL', 'https://us-west-2.quicksight.aws.amazon.com/sn/oauthcallback または https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback（Quick 側の表示と一致すれば OK）'
)
ORDER BY O"""),
    md('''## Step 6. 設定をまとめて確認する（トラブル時にも使えます）

| 症状 | 原因 | 対処 |
|---|---|---|
| `CREATE AGENT` で `unrecognized field execution_environment` | spec のトップに書いている | `tool_resources.<ツール名>` の中に入れる |
| Agent 実行で `missing an execution environment` | ツールにウェアハウスが紐付いていない | 上と同じ |
| Agent を作り直したら権限が消えた | `CREATE OR REPLACE` は GRANT を引き継がない | GRANT をやり直す |
| Quick から「権限がない」 | DEFAULT_ROLE に権限がない | Step 2・3 を確認 |
| OAuth ログインで拒否される | ACCOUNTADMIN 等は既定でブロック | 既定ロールを `CORTEX_QUICK_HOL_ROLE` に |
| OAuth で `mismatch in the given redirect uri` | Quick のリージョンが登録済み（us-west-2 / us-east-1）以外 | エラー画面の URL の `redirect_uri=` の値を、`ALTER SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH SET OAUTH_ALTERNATE_REDIRECT_URIS = ('<その値>')` で追加（Client ID / Secret は変わりません） |
| Quick で 424 / タイムアウト | MCP の呼び出しは 60 秒で打ち切り | 質問を簡単にする、検証済みクエリを増やす |
| Quick がログイン画面を繰り返す（401） | ユーザーの `ALLOWED_INTERFACES` が制限されている | Step 3 のセルで `ALL` に戻す |
| Quick のログインで `invalid_client` | Client ID / Secret の貼り間違い、または OAuth 連携を作り直した | Step 5 の値を貼り直す |
| Quick で Snowflake の URL エラー | アカウント名の `_` をそのまま使っている | Step 5 で表示された URL（`-` に置換済み）を使う |'''),
    sql("check_oauth", """DESCRIBE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH
  ->> SELECT "property", "property_value" FROM $1
      WHERE "property" IN ('ENABLED', 'OAUTH_REDIRECT_URI', 'OAUTH_ALTERNATE_REDIRECT_URIS',
                           'OAUTH_CLIENT_TYPE', 'OAUTH_USE_SECONDARY_ROLES', 'BLOCKED_ROLES_LIST')"""),
    sql("check_user", """SET HOL_USER = CURRENT_USER();
DESC USER IDENTIFIER($HOL_USER)
  ->> SELECT "property", "value" FROM $1 WHERE "property" IN ('DEFAULT_ROLE', 'DEFAULT_WAREHOUSE', 'ALLOWED_INTERFACES')"""),
    md("Quick と同じロール（`CORTEX_QUICK_HOL_ROLE`）で、MCP Server・Agent・Semantic View を使えるか確かめます。エラーにならず金額が表示されれば OK です。"),
    sql("check_as_hol_role", """USE ROLE CORTEX_QUICK_HOL_ROLE;
DESCRIBE MCP SERVER CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_MCP_SERVER;
DESCRIBE AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT;
SELECT * FROM SEMANTIC_VIEW(CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW METRICS TRANSACTIONS.TOTAL_REVENUE)"""),
    sql("back_to_admin", "USE ROLE ACCOUNTADMIN"),
    md('''✅ Snowflake 側の準備はここまでです。続きは `docs/02_quick_setup_guide_ja.md` に沿って Amazon Quick 側を設定してください。

---

## クリーンアップ（ハンズオン終了後）

作成したオブジェクトを削除します。誤って実行しないよう、**すべてコメントアウト**してあります。消したい行の先頭の `-- ` を外して実行してください。'''),
    sql("cleanup", """-- ① ハンズオンで作ったもの
-- DROP MCP SERVER IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_MCP_SERVER;
-- DROP AGENT IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT;
-- DROP SEMANTIC VIEW IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SEMANTIC_VIEW;
-- DROP SEMANTIC VIEW IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_SV_BASIC;
-- DROP CORTEX SEARCH SERVICE IF EXISTS CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_DOCS_SEARCH;
-- DROP SECURITY INTEGRATION IF EXISTS SALES_OPS_QUICK_SUITE_OAUTH;

-- ② 既定ロールを元に戻す（例：ACCOUNTADMIN）
-- SET HOL_USER = CURRENT_USER();
-- ALTER USER IDENTIFIER($HOL_USER) SET DEFAULT_ROLE = ACCOUNTADMIN;

-- ③ DB・ウェアハウス・ロール・Git 連携まで消す場合（Git から作ったワークスペースは先に削除してください）
-- DROP DATABASE IF EXISTS CORTEX_QUICK_HOL_DB;
-- DROP WAREHOUSE IF EXISTS CORTEX_QUICK_HOL_WH;
-- DROP ROLE IF EXISTS CORTEX_QUICK_HOL_ROLE;
-- DROP DATABASE IF EXISTS QUICK_HOL_GIT_DB;
-- DROP API INTEGRATION IF EXISTS QUICK_HOL_GIT_INTEGRATION;
SELECT 'コメントを外した行だけが実行されます' AS "メモ\""""),
]


OUT.mkdir(parents=True, exist_ok=True)

# GUI（Semantic View Autopilot）でアップロードする用に、v2 の YAML を書き出す
_yaml = SV_CELL.split("$$")[1].strip() + "\n"
_sv_dir = HERE.parent / "semantic_views"
_sv_dir.mkdir(exist_ok=True)
(_sv_dir / "sales_ops_semantic_view.yaml").write_text(_yaml)
print("wrote semantic_views/sales_ops_semantic_view.yaml", len(_yaml.splitlines()), "lines")
for old in ["01_data_setup.ipynb", "02_semantic_view_and_agent.ipynb", "03_mcp_and_oauth.ipynb"]:
    (OUT / old).unlink(missing_ok=True)
save("01_explore_data.ipynb", nb1)
save("02_cortex_analyst.ipynb", nb2)
save("03_cortex_search.ipynb", nb_search)
save("04_cortex_agent.ipynb", nb_agent)
save("05_mcp_and_oauth.ipynb", nb5)
