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


SETUP = '''from snowflake.snowpark.context import get_active_session
session = get_active_session()

DB, SCHEMA = "CORTEX_QUICK_HOL_DB", "CORTEX_QUICK_HOL_SCHEMA"
HOL_ROLE, HOL_WH = "CORTEX_QUICK_HOL_ROLE", "CORTEX_QUICK_HOL_WH"

session.use_role("ACCOUNTADMIN")
session.use_warehouse(HOL_WH)
session.use_schema(f"{DB}.{SCHEMA}")
print("ロール:", session.get_current_role(), "/ ウェアハウス:", session.get_current_warehouse())'''

PREFLIGHT_MD = '### 事前チェック：AI 機能とクロスリージョン推論\n\n後半（Agent / Quick 連携）で詰まらないよう、**最初に** AI 機能が使えるかを確かめます。\n\n- `CORTEX_ENABLED_CROSS_REGION` は、アカウントのリージョンに必要なモデルがないときに他リージョンで推論する設定です。アカウントのリージョンによっては Agent のモデルが見つからないため、`setup.sql` で `ANY_REGION` にしています（データ自体は移動しません）。ここでは値を確認するだけです。\n- `AI_COMPLETE` を1回だけ呼び、AI 機能が使えるかを確認します（数文字の応答なので消費はごくわずかです）。'
PREFLIGHT_PY = '''v = session.sql("SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT").collect()
print("CORTEX_ENABLED_CROSS_REGION:", v[0]["value"] if v else "(不明)", "（setup.sql で ANY_REGION に設定済み）")

try:
    r = session.sql("SELECT AI_COMPLETE('claude-sonnet-4-5', 'Reply with OK only.') AS R").collect()[0]["R"]
    print("OK: AI 機能が使えます（応答:", str(r).strip()[:20], "）")
except Exception as e:
    msg = str(e)
    print("⚠️ AI_COMPLETE の呼び出しに失敗しました。モデル名の問題の可能性があります（Agent の動作は 04 で確認します）:\\n", msg[:300])'''


ASK_AGENT = '''import json

def ask_agent(question: str, agent: str = "SALES_OPS_AGENT", show_sql: bool = True):
    """Agent に質問し、回答・使ったツール・生成 SQL・検索した文書を表示する"""
    payload = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
    raw = session.sql("SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS R",
                      params=[f"{DB}.{SCHEMA}.{agent}", payload]).collect()[0]["R"]
    resp = json.loads(raw) if isinstance(raw, str) else raw
    texts, sqls, tools, docs = [], [], [], []
    for c in resp.get("content", []):
        if c.get("type") == "text" and c.get("text", "").strip():
            texts.append(c["text"])
        elif c.get("type") == "tool_use":
            tools.append(c.get("tool_use", {}).get("name"))
        elif c.get("type") == "tool_result":
            for x in c.get("tool_result", {}).get("content", []):
                j = x.get("json", {})
                if j.get("sql"):
                    sqls.append(j["sql"])
                for r in j.get("search_results", []) or []:
                    if r.get("doc_title"):
                        docs.append(r["doc_title"])
    print(f"Q: {question}")
    print(f"（使ったツール: {', '.join(t for t in tools if t) or 'なし'}）\\n")
    print("\\n".join(texts))
    if show_sql:
        for s in sqls:
            print("\\n--- Cortex Analyst が生成した SQL ---\\n" + s)
    if docs:
        print("\\n--- 参照した文書 ---\\n" + "\\n".join(sorted(set(docs))))
    return resp'''

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

**前提**：`load.sql` と `setup.sql` を実行済みであること  
**所要時間**：約10分'''),
    md('''## シナリオ

あなたは SaaS 企業の**営業企画（Sales Operations）の担当者**です。
営業部長や現場のマネージャーから、毎日のようにこんな質問が届きます。

- 「今期の地域別の売上は？ Enterprise プランはどれくらい売れている？」
- 「**停滞している商談**は何件ある？」「**勝率**は？」
- 「レポートで推奨されている**パイプラインカバレッジ**を下回っている営業担当は誰？」

数字は Snowflake のテーブルに、**社内の基準や推奨アクションは PDF のレポート**に書かれています。
このハンズオンでは、両方をまたいで自然言語で答える **Cortex Agent** を作り、最後に **Amazon Quick** から使えるようにします。'''),
    md('''## Step 0. セッションの準備と事前チェック

このハンズオンで使う名前を変数にまとめ、AI 機能が使えるかを最初に確かめます。'''),
    py(SETUP + '''
info = session.sql("""SELECT CURRENT_USER() AS U, CURRENT_REGION() AS R,
  CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS A""").collect()[0]
print("実行ユーザー:", info["U"], "/ アカウント:", info["A"], "/ リージョン:", info["R"])'''),
    md(PREFLIGHT_MD),
    py(PREFLIGHT_PY),
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
| Sales Performance Analysis | 地域・営業担当の分析、**推奨パイプラインカバレッジ 1.6 倍**、値引きの上限の目安 |
| Customer Intelligence & Pipeline | 解約リスクの高い顧客、**停滞商談（40日超）**と推奨アクション、施策の優先順位 |'''),
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

**前提**：`01_explore_data.ipynb` を実行済みであること  
**所要時間**：約20分'''),
    md("## Step 0. セッションの準備"),
    py(SETUP),
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
    py('''def create_eval_agent(agent_name: str, sv_name: str):
    """指定した Semantic View だけをツールに持つ、評価用の Agent を作る"""
    session.sql(f"""
CREATE OR REPLACE AGENT {DB}.{SCHEMA}.{agent_name}
  COMMENT = 'Evaluation agent (Cortex Analyst only) for {sv_name}'
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
      semantic_view: {DB}.{SCHEMA}.{sv_name}
      execution_environment:
        type: warehouse
        warehouse: {HOL_WH}
  $$""").collect()
    print("OK:", agent_name, "→", sv_name)

create_eval_agent("EVAL_AGENT_V1", "SALES_OPS_SV_BASIC")'''),
    py(ASK_AGENT),
    py('_ = ask_agent("停滞している商談は何件？", agent="EVAL_AGENT_V1")'),
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

### 方法 A：GUI で作る（YAML をアップロード）

v2 は同義語・KPI・検証済みクエリが多く、画面で 1 つずつ入力すると時間がかかります。GUI では **できあがった YAML を読み込む**方法を使います。

1. GitHub の [`semantic_views/sales_ops_semantic_view.yaml`](../semantic_views/sales_ops_semantic_view.yaml) を PC にダウンロードする
   （Git 連携したワークスペースなら、左のファイル一覧の `semantic_views/` にもあります）
2. **「Workspaces」→「Add new」→「Semantic View」** を開き、保存先 `CORTEX_QUICK_HOL_DB` / `CORTEX_QUICK_HOL_SCHEMA` を選ぶ
3. 文脈の指定で **YAML specification のアップロード** を選び、ダウンロードした YAML を指定する
4. 作成されたら Semantic Studio で **Metrics**（`STALLED_DEAL_COUNT` など）と **Verified queries** が入っていることを確認する
5. （デモ）**Synonyms** に同義語を 1 つ追加する、**Verified queries** に質問を 1 つ追加するなど、GUI での編集を試す

> ⚠️ 名前は YAML の中で **`SALES_OPS_SEMANTIC_VIEW`** に決まっています。Step 4 の正答率はこの内容が前提なので、**GUI で大きく変更した場合は方法 B のセルを実行して元に戻してください。**

> ℹ️ GUI の手順は Snowflake 公式ドキュメントをもとに書いています。画面のラベルや順番が多少違う場合があります。\n> 迷ったら **方法 B（SQL）** のセルを実行すれば、同じ名前・同じ設定で作られます（GUI で作ったものは上書きされます）。

### 方法 B：SQL で作る（`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`）'''),
    sql("create_semantic_view", SV_CELL),
    md("作成できたか確認し、ハンズオン用ロールに参照権限を付けます。"),
    sql("show_semantic_views", "SHOW SEMANTIC VIEWS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA"),
    py('''for sv in ["SALES_OPS_SV_BASIC", "SALES_OPS_SEMANTIC_VIEW"]:
    session.sql(f"GRANT SELECT ON SEMANTIC VIEW {DB}.{SCHEMA}.{sv} TO ROLE {HOL_ROLE}").collect()
print("OK: Semantic View への SELECT を付与しました")'''),
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
3. **Logical tables / Relationships / Metrics / Verified queries** を開き、`SALES_OPS_SV_BASIC` と見比べる

> Semantic View の編集画面から、同義語や検証済みクエリを GUI で追加することもできます。'''),
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
    py('''import time
from concurrent.futures import ThreadPoolExecutor

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
    py('''create_eval_agent("EVAL_AGENT_V2", "SALES_OPS_SEMANTIC_VIEW")

result_v1 = evaluate("EVAL_AGENT_V1")
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
    py('''for a in ["EVAL_AGENT_V1", "EVAL_AGENT_V2"]:
    session.sql(f"DROP AGENT IF EXISTS {DB}.{SCHEMA}.{a}").collect()
print("OK: 評価用 Agent を削除しました")'''),
    md('''✅ 02 はここまでです。次は `03_cortex_search.ipynb` に進みます。'''),
]

# ------------------------------------------------------------------ 03
nb_search = [
    md('''# 03. Cortex Search ― PDF レポートを検索できるようにする

02 の Cortex Analyst は「テーブルの数字」に答えます。一方、**「推奨カバレッジは？」「停滞商談にはどう対応すべき？」** のような答えは PDF のレポートにあります。
**Cortex Search** は、文書を意味で検索できるようにするサービスです。

```
PDF（DOCS_STAGE）
  ↓ ① AI_PARSE_DOCUMENT   … PDF からテキストを抽出（表は Markdown に）
  ↓ ② SPLIT_TEXT_RECURSIVE_CHARACTER … 検索しやすい長さ（チャンク）に分割
  ↓ ③ CREATE CORTEX SEARCH SERVICE  … ベクトル＋キーワードのハイブリッド検索インデックス
Cortex Search Service `SALES_DOCS_SEARCH` → 04 で Agent のツールにする
```

**前提**：`02_cortex_analyst.ipynb` を実行済みであること  
**所要時間**：約10分'''),
    md("## Step 0. セッションの準備"),
    py(SETUP),
    md('''## Step 1. PDF からテキストを取り出す

`AI_PARSE_DOCUMENT` の `LAYOUT` モードは、見出しや**表の構造を保ったまま** Markdown のテキストにします。'''),
    sql("parse_docs", f'''CREATE OR REPLACE TABLE {FQ}DOCS_PARSED AS
SELECT RELATIVE_PATH AS FILE_NAME,
       AI_PARSE_DOCUMENT(TO_FILE('@{FQ}DOCS_STAGE', RELATIVE_PATH), {{'mode': 'LAYOUT'}}):content::STRING AS CONTENT
FROM DIRECTORY(@{FQ}DOCS_STAGE)'''),
    sql("show_parsed", f'''SELECT FILE_NAME, LENGTH(CONTENT) AS CHARS, LEFT(CONTENT, 500) AS HEAD FROM {FQ}DOCS_PARSED'''),
    md('''## Step 2. チャンクに分割する

文書全体を 1 件として検索すると、関係ない部分まで混ざって精度が下がります。約 800 文字ずつ（前後 100 文字は重ねて）に分割します。
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

| 設定 | 値 | 意味 |
|---|---|---|
| `ON CHUNK` | 検索対象の列 | この列の中身で検索する |
| `ATTRIBUTES FILE_NAME` | 絞り込みに使える列 | 「このレポートだけ」で絞り込める |
| `EMBEDDING_MODEL` | `snowflake-arctic-embed-l-v2.0` | **多言語対応**のモデル。英語の PDF を日本語の質問で検索できる |
| `TARGET_LAG` | `1 day` | 元のテーブルが変わったときに追従する間隔 |

> 💡 既定のモデルは英語向けです。日本語で質問する場合は多言語モデルを指定してください（このハンズオンで実際に、既定モデルでは日本語の質問に対して関係の薄い表が上位に来ました）。
>
> 作成には 1〜2 分かかります。

### 方法 A：GUI（AI と ML → Cortex Search）で作る

Step 1・2 で作った `DOCS_CHUNKS` テーブルを、画面から検索サービスにします。

1. Snowsight 左メニュー **「AI と ML」→「Cortex Search」** を開き、**「Create」**
2. ロールは `ACCOUNTADMIN`、ウェアハウスは **`CORTEX_QUICK_HOL_WH`**
3. データベース / スキーマに `CORTEX_QUICK_HOL_DB` / `CORTEX_QUICK_HOL_SCHEMA`、サービス名に **`SALES_DOCS_SEARCH`**（**大文字のまま**）を入力し、**Next**
4. データの種類は **Table or view** → **`DOCS_CHUNKS`** を選び、**Next**
5. 検索結果に含める列：`CHUNK_ID` / `CHUNK` / `FILE_NAME` / `CHUNK_NO` → **Next**
6. 検索する列：**`CHUNK`** → **Next**
7. 絞り込みに使う列：**`FILE_NAME`** → **Next**
8. Target lag は **1 day** にして **Create**
9. 作成されたら同じ画面の **Playground** で「推奨されるパイプラインカバレッジの目安は？」と検索してみる

> ⚠️ **埋め込みモデル**：画面でモデルを選べない場合、既定の英語向けモデルで作られ、日本語の質問の精度が下がります。
> その場合は **方法 B のセルを実行**して、多言語モデル（`snowflake-arctic-embed-l-v2.0`）で作り直してください。
>
> ⚠️ GUI ではサービス名がダブルクォート付きで作られます。小文字が混じると SQL や Agent から `SALES_DOCS_SEARCH` で参照できなくなるため、**必ず大文字で入力**してください。

> ℹ️ GUI の手順は Snowflake 公式ドキュメントをもとに書いています。画面のラベルや順番が多少違う場合があります。\n> 迷ったら **方法 B（SQL）** のセルを実行すれば、同じ名前・同じ設定で作られます（GUI で作ったものは上書きされます）。

### 方法 B：SQL で作る（`CREATE CORTEX SEARCH SERVICE`）'''),
    sql("create_search_service", f'''CREATE OR REPLACE CORTEX SEARCH SERVICE {FQ}SALES_DOCS_SEARCH
  ON CHUNK
  ATTRIBUTES FILE_NAME
  WAREHOUSE = CORTEX_QUICK_HOL_WH
  TARGET_LAG = '1 day'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
  AS SELECT CHUNK_ID, CHUNK, FILE_NAME, CHUNK_NO FROM {FQ}DOCS_CHUNKS'''),
    md("GUI・SQL どちらで作った場合も、次のセルで権限を付けます。"),
    py('''session.sql(f"GRANT USAGE ON CORTEX SEARCH SERVICE {DB}.{SCHEMA}.SALES_DOCS_SEARCH TO ROLE {HOL_ROLE}").collect()
print("OK: Cortex Search Service への USAGE を付与しました")'''),
    md('''## Step 4. 検索してみる

`SEARCH_PREVIEW` で、質問に近いチャンクを上位から取り出します。英語の PDF に**日本語で**質問しています。'''),
    py('''def search_docs(query: str, limit: int = 3):
    req = json.dumps({"query": query, "columns": ["CHUNK", "FILE_NAME"], "limit": limit})
    res = json.loads(session.sql("SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(?, ?) AS R",
                                 params=[f"{DB}.{SCHEMA}.SALES_DOCS_SEARCH", req]).collect()[0]["R"])
    print(f"Q: {query}\\n")
    for i, r in enumerate(res["results"], 1):
        print(f"[{i}] {r['FILE_NAME']}\\n{' '.join(r['CHUNK'].split())[:300]}...\\n")

import json
search_docs("推奨されるパイプラインカバレッジの目安は？")'''),
    py('search_docs("停滞している商談にはどう対応すべき？")'),
    py('search_docs("解約リスクが高い顧客に共通する特徴は？")'),
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

**前提**：`03_cortex_search.ipynb` を実行済みであること  
**所要時間**：約15分'''),
    md("## Step 0. セッションの準備"),
    py(SETUP),
    md('''## Step 1. Agent を作る

| 設定（SQL の spec の項目） | 内容 |
|---|---|
| `models.orchestration` | 使うモデル。`auto` で Snowflake が自動選択 |
| `instructions.orchestration` | **ツールの使い分けの指示**。数字は Analyst、推奨・方針は Search、比較は両方 |
| `instructions.response` | 回答の書き方。日本語の質問には日本語で答える |
| `tools` / `tool_resources` | 2 つのツールと、それぞれの参照先（Semantic View、Search Service） |

> ⚠️ **ハマりどころ①：ウェアハウスの指定位置**
> Analyst の `execution_environment` は spec のトップではなく、**`tool_resources.<ツール名>` の中**に書きます。
> 位置が違うと、作成時に `unrecognized field execution_environment`、実行時に `missing an execution environment` になります。

> ⚠️ **ハマりどころ②：作り直すと権限が消える**
> `CREATE OR REPLACE` は既存の GRANT を引き継ぎません（検証したアカウントでは `CREATE AGENT ... COPY GRANTS` が構文エラーでした）。そのため作成直後に権限を付け直しています。

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
    md("GUI・SQL どちらで作った場合も、次のセルで権限を付けます（Quick からはハンズオン用ロールで実行されるため）。"),
    py('''session.sql(f"GRANT USAGE ON AGENT {DB}.{SCHEMA}.SALES_OPS_AGENT TO ROLE {HOL_ROLE}").collect()
print("OK: Agent への USAGE を付与しました")'''),
    sql("show_agent_grants", "SHOW GRANTS ON AGENT CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA.SALES_OPS_AGENT"),
    md('''## Step 2. Agent に質問する

Quick につなぐ前に、Snowflake 上で答えられるかを確認します。**ここで失敗する場合は、Quick からも同じエラーになります。**
各回答の上に「使ったツール」が表示されます。質問によって Agent がツールを使い分けていることを確かめてください。'''),
    py(ASK_AGENT),
    md('''| # | 質問 | 使うはずのツール | 期待される結果（目安） |
|---|---|---|---|
| 1 | 地域別の売上を教えて | Analyst | 北米 約 $5.95M が最大 |
| 2 | 停滞商談は何件で、金額はいくら？ | Analyst | 43 件、約 $4.37M |
| 3 | レポートで推奨されているパイプラインカバレッジは？ | Search | 1.6 倍（Sales Performance Analysis） |
| 4 | 推奨カバレッジを下回っている営業担当は何人？推奨値の根拠も教えて | **両方** | 63 人、1.6 倍の根拠 |
| 5 | 停滞商談への推奨アクションは？対象の件数と金額も | **両方** | 役員スポンサーの関与など＋43 件 |

> 💡 1 回の質問には 15〜40 秒ほどかかります。Quick から呼ぶ場合も同じです（60 秒を超えるとタイムアウト）。'''),
    py('_ = ask_agent("地域別の売上を教えて")'),
    py('_ = ask_agent("停滞商談は何件で、金額はいくら？")'),
    py('_ = ask_agent("レポートで推奨されているパイプラインカバレッジは？", show_sql=False)'),
    py('_ = ask_agent("推奨カバレッジを下回っている営業担当は何人？推奨値の根拠も教えて")'),
    py('_ = ask_agent("停滞商談への推奨アクションは？対象の件数と金額も", show_sql=False)'),
    md('''### ハンズオン用ロールで実行できるか確認する

Quick からはハンズオン用ロールで実行されます。ロールを切り替えて同じように答えられるか確かめます。'''),
    py('''session.use_role(HOL_ROLE)
try:
    _ = ask_agent("営業担当の目標達成率トップ3は？", show_sql=False)
    _ = ask_agent("レポートで推奨されているパイプラインカバレッジは？", show_sql=False)
finally:
    session.use_role("ACCOUNTADMIN")'''),
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
    md("## Step 0. セッションの準備"),
    py(SETUP + '''

# Quick のリージョン（OAuth のリダイレクト先と完全一致させる必要があります）
# us-west-2 / us-east-1 のどちらで Quick を作っても通るよう、両方を登録します
QUICK_REGIONS = ["us-west-2", "us-east-1"]
quick_redirect_uris = [f"https://{r}.quicksight.aws.amazon.com/sn/oauthcallback" for r in QUICK_REGIONS]
quick_redirect_uri = quick_redirect_uris[0]

row = session.sql("""SELECT CURRENT_USER() AS U,
  REPLACE(CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME(), '_', '-') AS H""").collect()[0]
hol_user, account_host = row["U"], row["H"]
print("ユーザー          :", hol_user)
print("アカウントホスト  :", f"{account_host}.snowflakecomputing.com")
print("OAuth リダイレクト:", ", ".join(quick_redirect_uris))'''),
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
ここでは MCP Server への USAGE を付け、3つがそろっているかをまとめて確認します。

> 💡 **元教材との違い**：AWS Workshop 5章 Step 6 では MCP Server への GRANT が2回書かれ、Agent への GRANT が抜けています。本ハンズオンでは 04 で Agent への GRANT を行っています。'''),
    py('''session.sql(f"GRANT USAGE ON MCP SERVER {DB}.{SCHEMA}.SALES_OPS_MCP_SERVER TO ROLE {HOL_ROLE}").collect()

for obj in ["MCP SERVER", "AGENT", "SEMANTIC VIEW", "CORTEX SEARCH SERVICE"]:
    name = {"MCP SERVER": "SALES_OPS_MCP_SERVER", "AGENT": "SALES_OPS_AGENT", "SEMANTIC VIEW": "SALES_OPS_SEMANTIC_VIEW", "CORTEX SEARCH SERVICE": "SALES_DOCS_SEARCH"}[obj]
    rows = session.sql(f"SHOW GRANTS ON {obj} {DB}.{SCHEMA}.{name}").collect()
    ok = any(r["grantee_name"] == HOL_ROLE for r in rows)
    print(f"{obj:<22} {name:<26} {HOL_ROLE} への付与: {'OK' if ok else '未付与'}")'''),
    sql("show_mcp_servers", '''SHOW MCP SERVERS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA'''),
    md('''## Step 3. 接続ユーザーの既定ロールを設定する

Quick から OAuth でログインしたとき、Snowflake は **そのユーザーのデフォルトロール／デフォルトウェアハウス** で処理します。

> ⚠️ **ハマりどころ③：既定ロールが ACCOUNTADMIN のままだと接続できない**
> - Quick からの処理は、セッションで切り替えたロールではなく **DEFAULT_ROLE** で行われます。
> - アカウント作成時の管理ユーザーは、DEFAULT_ROLE が **ACCOUNTADMIN** になっていることがあります。ACCOUNTADMIN / SECURITYADMIN / ORGADMIN は OAuth でのログインが**ブロック**されるため、このままでは Quick から接続できません。
> - そこで、Quick でログインするユーザー（＝今このNotebookを実行しているユーザー）の DEFAULT_ROLE を `CORTEX_QUICK_HOL_ROLE` に変えます。

> 💡 変更後も、Snowsight 右上のロール切り替えや `USE ROLE ACCOUNTADMIN` で管理者として作業できます（次回ログイン時の初期ロールが変わるだけです）。
> このNotebookも各セルで `ACCOUNTADMIN` に切り替えて実行しているので影響ありません。元に戻す方法は末尾のクリーンアップを参照してください。

> 💡 **ハマりどころ④：ALLOWED_INTERFACES**
> ユーザーの `ALLOWED_INTERFACES` が `SNOWFLAKE_INTELLIGENCE` などに制限されていると、Quick の OAuth ログイン自体は成功するのに MCP 呼び出しが 401（`395300 Not authorized to access interface ALL`）になり、**Quick がログイン画面を繰り返し表示**します。既定値（`ALL`）なら問題ありませんが、念のため下のセルで確認し、必要なら `ALL` に戻します。'''),
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
| `OAUTH_REDIRECT_URI` | Quick のコールバック URL（us-west-2） | ログイン後の戻り先。**Quick のリージョンと完全一致**が必要 |
| `OAUTH_ALTERNATE_REDIRECT_URIS` | 同（us-east-1） | 追加で受け付ける戻り先。これで us-west-2 / us-east-1 どちらの Quick でも接続できます |
| `OAUTH_ISSUE_REFRESH_TOKENS` | `TRUE` | 再ログインなしで使い続けられるようにする |
| `OAUTH_USE_SECONDARY_ROLES` | `NONE` | DEFAULT_ROLE の権限だけで動かす（MCP 向けの推奨設定）。ユーザーが ACCOUNTADMIN を持っていても、Quick 経由ではハンズオン用ロールの権限に限定されます |
| `BLOCKED_ROLES_LIST` | 既定（ACCOUNTADMIN 等） | 管理者ロールでの OAuth ログインを禁止 |
| `OAUTH_REFRESH_TOKEN_VALIDITY` | `86400` | リフレッシュトークンの有効期間（秒、1日） |

作成には ACCOUNTADMIN が必要です。

> ⚠️ このセルを再実行すると **Client ID / Secret が変わります**。Quick 側に登録した後で再実行した場合は、Quick のコネクタも作り直してください。'''),
    py('''alt_uris_sql = ", ".join("'" + u + "'" for u in quick_redirect_uris[1:])
session.sql(f"""
CREATE OR REPLACE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = '{quick_redirect_uris[0]}'
  OAUTH_ALTERNATE_REDIRECT_URIS = ({alt_uris_sql})
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_USE_SECONDARY_ROLES = 'NONE'
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400
""").collect()
print("OK: SALES_OPS_QUICK_SUITE_OAUTH を作成しました")'''),
    md('''## Step 5. Amazon Quick に入力する値を表示する

次のセルで、Quick のコネクタ設定に必要な値をまとめて表示します。手順は `docs/02_quick_setup_guide_ja.md` を参照してください。

> ⚠️ **Client Secret は画面共有で見せないよう注意してください。** 既定では伏せ字で表示し、`SHOW_SECRET = True` にしたときだけ全文を表示します。
> Quick に貼り付けるときだけ `True` にして実行し、貼り付け後は `False` に戻して再実行してください。

> 💡 Quick で OAuth ログイン画面が出たら、**この Snowflake アカウントのユーザー名とパスワード**でログインします（MFA を登録済みならその確認も求められます）。'''),
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
    "Redirect URL":        " または ".join(quick_redirect_uris) + "（Quick 側の表示と一致すれば OK）",
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
| OAuth で `mismatch in the given redirect uri` | Quick のリージョンが登録済み（us-west-2 / us-east-1）以外 | エラー画面の URL の `redirect_uri=` の値を `QUICK_REGIONS` に追加して Step 4 を再実行（Client ID / Secret が変わるので Quick も再入力） |
| Quick で 424 / タイムアウト | MCP の呼び出しは 60 秒で打ち切り | 質問を簡単にする、検証済みクエリを増やす |
| Quick がログイン画面を繰り返す（401） | ユーザーの `ALLOWED_INTERFACES` が制限されている | Step 3 のセルで `ALL` に戻す |
| Quick のログインで `invalid_client` | Client ID / Secret の貼り間違い、または OAuth 連携を作り直した | Step 5 の値を貼り直す |
| Quick で Snowflake の URL エラー | アカウント名の `_` をそのまま使っている | Step 5 で表示された URL（`-` に置換済み）を使う |'''),
    py('''print("=== OAuth 連携")
for r in session.sql("DESCRIBE SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH").collect():
    if r["property"] in ("ENABLED", "OAUTH_REDIRECT_URI", "OAUTH_ALTERNATE_REDIRECT_URIS", "OAUTH_CLIENT_TYPE", "OAUTH_USE_SECONDARY_ROLES", "BLOCKED_ROLES_LIST"):
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
RESTORE_DEFAULT_ROLE = None   # 例: "ACCOUNTADMIN"（変更前のロール）

if RUN_CLEANUP:
    session.use_role("ACCOUNTADMIN")
    stmts = [
        f"DROP MCP SERVER IF EXISTS {DB}.{SCHEMA}.SALES_OPS_MCP_SERVER",
        f"DROP AGENT IF EXISTS {DB}.{SCHEMA}.SALES_OPS_AGENT",
        f"DROP SEMANTIC VIEW IF EXISTS {DB}.{SCHEMA}.SALES_OPS_SEMANTIC_VIEW",
        f"DROP SEMANTIC VIEW IF EXISTS {DB}.{SCHEMA}.SALES_OPS_SV_BASIC",
        f"DROP CORTEX SEARCH SERVICE IF EXISTS {DB}.{SCHEMA}.SALES_DOCS_SEARCH",
        "DROP SECURITY INTEGRATION IF EXISTS SALES_OPS_QUICK_SUITE_OAUTH",
    ]
    if RESTORE_DEFAULT_ROLE:
        stmts.append(f'ALTER USER "{hol_user}" SET DEFAULT_ROLE = \\'{RESTORE_DEFAULT_ROLE}\\'')
    if DROP_BASE_OBJECTS:
        stmts += [f"DROP DATABASE IF EXISTS {DB}", f"DROP WAREHOUSE IF EXISTS {HOL_WH}", f"DROP ROLE IF EXISTS {HOL_ROLE}",
                  # load.sql で作った Git 連携（ワークスペースを Git から作った場合、先にワークスペースを削除してください）
                  "DROP DATABASE IF EXISTS QUICK_HOL_GIT_DB", "DROP API INTEGRATION IF EXISTS QUICK_HOL_GIT_INTEGRATION"]
    for s in stmts:
        session.sql(s).collect()
        print("OK:", s)
else:
    print("RUN_CLEANUP = False のため何もしていません")'''),
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
