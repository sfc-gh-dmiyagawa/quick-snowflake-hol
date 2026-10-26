# スキル版 ↔ Notebook版 対応表

元教材（Snowflakeクイックスタート / AWS Workshop Studio f2443d19）では、Snowflake側の構築を
Cortex Code スキル `sales-ops-cortex-agent-mcp-quick`（SKILL.md）が自動実行します。
本リポジトリではその処理を分解し、Notebook を上から実行して「何が起きているか」を確認できるようにしています。

## 全体対応

| 元教材 | 処理内容 | 本リポジトリ |
|---|---|---|
| Workshop 4章（SQLワークシート） | WH / DB / スキーマ / ロール作成、ロール付与、DEFAULT_ROLE設定 | `01_data_setup.ipynb` Step 1 |
| （トライアル向けに追加） | AI 機能の利用可否チェック、クロスリージョン推論の有効化 | `01_data_setup.ipynb` Step 0 |
| Workshop 4章 | CSVファイルフォーマット作成、6テーブル作成、S3からCOPY INTO、件数確認 | `01_data_setup.ipynb` Step 2〜5 |
| （データ修正として追加） | 取引と製品をつなぐ `PRODUCT_PLAN_VIEW` の作成 | `01_data_setup.ipynb` Step 6 |
| スキル Step 1 | ACCOUNT_HOST取得、6テーブルの存在確認 | `01_data_setup.ipynb` Step 5 / `03` 冒頭 |
| スキル Step 2 | `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` で SALES_OPS_SEMANTIC_VIEW 作成 | `02_semantic_view_and_agent.ipynb` Step 1〜2 |
| （スキルには無し） | `SEMANTIC_VIEW()` で直接クエリして中身を理解 | `02` Step 3（追加） |
| スキル Step 3 | `CREATE AGENT` で SALES_OPS_AGENT 作成（Cortex Analyst ツール） | `02` Step 4 |
| スキル Step 4 | `DATA_AGENT_RUN` で3つのテスト質問 | `02` Step 5（日本語の質問を追加） |
| スキル Step 5 / Workshop 5章 Step 6 | `CREATE MCP SERVER`（CORTEX_AGENT_RUN）、権限付与 | `03_mcp_and_oauth.ipynb` Step 1〜2 |
| スキル Step 6 / Workshop 5章 Step 7 | ACCOUNTADMINで `SECURITY INTEGRATION`（OAuth）作成、Client Secret取得 | `03` Step 3〜4 |
| スキル Step 7 | Quickに入力する値の表示と手順 | `03` Step 5 → `docs/02_quick_setup_guide_ja.md` |
| スキル Troubleshooting | SHOW/DESCRIBE/直接テスト | `03` Step 6・`docs/troubleshooting_ja.md` |
| スキル Cleanup / Workshop 9章 | DROP 一式 | `03` 末尾（既定は実行しない） |

## 元教材から変えている点

| 項目 | 元教材 | 本リポジトリ | 理由 |
|---|---|---|---|
| ユーザー名 | `SNOWFLAKE_USER` を手で書き換え | `CURRENT_USER()` を変数で使用 | 書き換えミス防止 |
| テーブルへのSELECT付与 | テーブル作成前に `GRANT SELECT ON ALL TABLES` | ロード後に付与（＋FUTURE GRANTS） | 作成前の付与は後から作ったテーブルに効かない |
| Semantic View | 英語の同義語のみ | 日本語の同義語を追加 | 日本語で質問できるように |
| Agent の指示 | 英語 | 日本語で質問されたら日本語で回答する指示を追加 | 日本向け |
| Agent への権限 | Workshop 5章 Step 6 では MCP の GRANT が重複し、Agent への GRANT が欠落 | `GRANT USAGE ON AGENT` を明示 | 抜け漏れの修正 |
| 動作確認 | スキルの中で暗黙に実行 | 各ステップに確認セル（SHOW/DESCRIBE/テスト）を配置 | 処理を目で追えるように |
| 製品の結合 | 取引の `PRODUCT_SKU`（ENT-ANNUAL）と製品カタログの SKU（ENT-ANN-011）で結合 → **0件** | ティア×請求サイクル単位の `PRODUCT_PLAN_VIEW` で結合（200件） | 「ティア別売上」の検証済みクエリも0件になっていたため |
| 解約リスクの説明 | `Churn risk score (0-100)` | 「0〜1 ではなく 0〜100、30未満が低リスク」と明記 | Flow のプロンプト（`< 0.3`）で0件になる問題への対策 |
| OAuth のセカンダリロール | `IMPLICIT` | `NONE` | MCP の推奨設定。Quick 経由ではハンズオン用ロールの権限だけで動かす |
| ユーザー設定 | DEFAULT_ROLE のみ変更 | DEFAULT_ROLE・DEFAULT_WAREHOUSE を設定し、`ALLOWED_INTERFACES` を確認 | トライアルの初期ロール（ACCOUNTADMIN）は OAuth でブロックされるため。ALLOWED_INTERFACES が制限されていると Quick がログインを繰り返す |
| 前提アカウント | Workshop 配布のアカウント | トライアルアカウント | AI 機能の制限・既定コンピュートプールの注意を追加 |
| Flow のプロンプト | `CHURN_RISK_SCORE < 0.3`、製品カタログとの結合 | `< 30`、ティア単位のカタログ平均で結合、自然言語の質問1回＋Flow 側で計算 | 元のままではレポートが空・エラーになる |

## 確認ポイント（Stop ポイント）

スキルが「Stop」で止まる箇所は、Notebook でも確認セルとして残しています。

0. AI 機能が使えること（01 Step 0）
1. 6テーブルに200件ずつ入り、取引200件がプランビューに結合できること（01）
2. Agent のテスト質問3件が、Cortex Analyst が生成したSQLで回答されること（02）
3. OAuth の Client ID / Secret を控えたこと（03）
4. Quick 側の Redirect URL と `OAUTH_REDIRECT_URI` が完全一致していること（03 / Quick手順書）
5. DEFAULT_ROLE が `CORTEX_QUICK_HOL_ROLE`、ALLOWED_INTERFACES が `ALL` であること（03 Step 3・6）
