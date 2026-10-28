# トラブルシュート

ハンズオンで起きやすい問題と対処です。上から順に「どこで止まったか」で探してください。

## トライアルアカウント

| 症状 | 原因 | 対処 |
|---|---|---|
| `AI function ... is not available for trial accounts` / `Access denied for trial accounts`（399504） | 通常のセルフサービストライアルでは AI 機能（Cortex Agent・AI 関数など）が既定で無効 | Snowsight の **Admin » Billing » Payment method** でクレジットカードを登録し、01 の Step 0 を再実行。カードを登録しても残りの無償クレジットはそのまま使え、トライアル期間も終わりません。イベント用のサインアップ URL で作ったアカウントでは発生しません |
| Notebook の接続でコンピュートプールを作れない | トライアルでは新規作成できない | 既定の **`SYSTEM_COMPUTE_POOL_CPU`** を選ぶ |
| Notebook の起動が遅い（数分かかる） | コンピュートプールは5分使わないと停止し、次回起動に時間がかかる | 起動を待つ。ハンズオン中は Notebook を開いたままにする |
| `Your free trial has ended` | トライアル期限切れ（30日）またはクレジット切れ | 新しいトライアルを作る、またはカードを登録 |

## Notebook（Snowflake 側）

| 症状 | 原因 | 対処 |
|---|---|---|
| `Object does not exist` / `Database ... does not exist` | 前の Notebook を最後まで実行していない、または途中のセルを飛ばした | load.sql → setup.sql → 01 → 02 → 03 → 04 → 05 の順に、上から全セル実行（Run all） |
| `Warehouse 'CORTEX_QUICK_HOL_WH' does not exist` | `setup.sql` を実行していない | `setup.sql` を「すべて実行」してから Notebook を実行 |
| `DIRECTORY(@...DOCS_STAGE)` が 0 件・`AI_PARSE_DOCUMENT` が失敗 | PDF のコピーに失敗した | `setup.sql` の 4-3 を再実行（`COPY FILES` → `ALTER STAGE ... REFRESH`） |
| 日本語で検索すると関係ない段落が返る | 英語向けの既定の埋め込みモデルを使っている | 05 のとおり `EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'` で作る |
| 02 の正答率が毎回少し変わる | AI の回答は実行ごとに揺れる（特に v1） | 想定どおり。v2 が安定して高いことを確認する |
| `COPY INTO` の status が `LOAD_SKIPPED` | 同じファイルを読み込み済み | 問題なし。テーブルを作り直した場合は再度 `LOADED` になる |
| 製品の結合が 0 件（`TXN_TO_PRODUCT_CATALOG = 0`） | 元データの SKU の形式が違う（既知） | 想定どおり。Step 6 のプランビュー（`TXN_TO_PLAN = 200`）を使います |
| `CREATE AGENT` で `unrecognized field execution_environment` | spec のトップに書いている | `tool_resources.<ツール名>` の中に入れる |
| Agent 実行で `missing an execution environment` | ツールにウェアハウスが紐付いていない | 上と同じ |
| Agent を作り直したら Quick から使えなくなった | `CREATE OR REPLACE` は GRANT を引き継がない | 04 の GRANT セルを再実行 |
| Agent Studio で編集した内容が消えた | 04 の `create_agent` セルを再実行して上書きした | GUI で編集した後は、SQL のセルを再実行しない |
| `CREATE AGENT ... COPY GRANTS` で構文エラー | 2026年10月時点で確認した挙動 | `COPY GRANTS` を付けず、作成後に GRANT する（04 のとおり） |
| Agent の回答で「製品カテゴリ別」が答えられない | 元データに取引と製品の対応がない | ティア別・請求サイクル別で質問する |

## OAuth ログイン

| 症状 | 原因 | 対処 |
|---|---|---|
| Snowflake のログイン後に `invalid_scope` / ロールが ACCOUNTADMIN と表示されて拒否 | DEFAULT_ROLE が ACCOUNTADMIN のまま（トライアルの初期値）。管理者ロールは OAuth でブロックされる | 05 の Step 3 を `APPLY_DEFAULT_ROLE = True` で実行 |
| ログイン後にリダイレクトエラー（`redirect_uri` が不一致） | Quick のリージョンが登録済み（us-west-2 / us-east-1）以外、または OAuth 連携が旧版（us-west-2 のみ） | すぐ直すなら `ALTER SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH SET OAUTH_ALTERNATE_REDIRECT_URIS = ('https://<Quickのリージョン>.quicksight.aws.amazon.com/sn/oauthcallback');`（Client ID / Secret は変わらない）。エラー画面の URL の `redirect_uri=` で実際の値を確認できる |
| `invalid_client` | Client ID / Secret の貼り間違い（前後の空白を含む）、または OAuth 連携を作り直した | 05 の Step 5 を `SHOW_SECRET = True` で再表示して貼り直す |
| **ログイン画面が何度も出る（ループする）** | ユーザーの `ALLOWED_INTERFACES` が `SNOWFLAKE_INTELLIGENCE` などに制限されており、MCP 呼び出しが 401（`395300 Not authorized to access interface ALL`）になる | 05 の Step 3 のセルで `('ALL')` に戻す（トライアルの既定値は ALL） |
| MFA の画面で止まる | MFA を登録済みのユーザー | 登録した認証アプリで承認する |
| ネットワークポリシーで拒否 | アカウントにネットワークポリシーがある（トライアルでは通常なし） | Quick（AWS us-west-2 / us-east-1）からのアクセスを許可する |

## Quick のコネクタ・チャット

| 症状 | 原因 | 対処 |
|---|---|---|
| コネクタが `Creation in progress` のまま | 作成直後 | 数分待って画面を更新する |
| `sales_ops_agent` がツールに出ない | HOL ロールに MCP Server の USAGE がない | 05 の Step 2 を再実行 |
| 「権限がない」「Object does not exist」 | DEFAULT_ROLE に Agent / Semantic View / Cortex Search / ウェアハウスの権限がない | 05 の Step 6 の最後のチェック（`CORTEX_QUICK_HOL_ROLE で ... OK`）を確認 |
| 424 / タイムアウト | MCP の呼び出しは60秒で打ち切り。複雑な質問は時間がかかる | 質問を単純にする。Flow はガイドのプロンプト（自然言語の質問1回＋Flow 側で計算）を使う |
| Flow がエラーで止まる・SQL を送ろうとする | プロンプトが Agent に SQL を送らせている | ガイドのプロンプト（`Do NOT write or send SQL`）を使う |
| Flow のレポートが空・0件 | 元教材のプロンプトの `CHURN_RISK_SCORE < 0.3`（スコアは0〜100） | ガイドの修正版プロンプト（`< 30`）を使う |
| 英語で返ってくる | Chat Agent のプロンプトに言語指定がない | ガイドのプロンプト（`Always reply in the same language as the user`）を使う |

## 状態をまとめて確認する SQL

```sql
USE ROLE ACCOUNTADMIN;
SHOW SEMANTIC VIEWS IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
SHOW AGENTS        IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
SHOW CORTEX SEARCH SERVICES IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
SHOW MCP SERVERS   IN SCHEMA CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA;
SHOW GRANTS TO ROLE CORTEX_QUICK_HOL_ROLE;
DESC SECURITY INTEGRATION SALES_OPS_QUICK_SUITE_OAUTH;
DESC USER IDENTIFIER(CURRENT_USER());   -- DEFAULT_ROLE / DEFAULT_WAREHOUSE / ALLOWED_INTERFACES
```
