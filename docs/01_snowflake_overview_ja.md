# スキル版 ↔ Notebook版 対応表

元教材（Snowflakeクイックスタート / AWS Workshop Studio f2443d19）では、Snowflake側の構築を
Cortex Code スキル `sales-ops-cortex-agent-mcp-quick`（SKILL.md）が自動実行します。
本リポジトリではその処理を分解し、Notebook を上から実行して「何が起きているか」を確認できるようにしています。
あわせて **Cortex Search** と **Semantic View の精度向上** を追加しています。

## 全体対応

| 元教材 | 処理内容 | 本リポジトリ |
|---|---|---|
| （追加） | Git から Workspace を作るための API 統合・Git リポジトリ | `load.sql` |
| Workshop 4章（SQLワークシート） | WH / DB / スキーマ / ロール作成、権限付与、6テーブル作成、S3 から COPY INTO | `setup.sql` |
| （データ修正として追加） | 取引と製品をつなぐ `PRODUCT_PLAN_VIEW`、PDF 2本のステージへのコピー | `setup.sql` |
| スキル Step 1 | ACCOUNT_HOST 取得、6テーブルの存在確認 | `01_explore_data.ipynb`（データの確認・AI 機能のチェック）/ `05` 冒頭 |
| スキル Step 2 | `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` で SALES_OPS_SEMANTIC_VIEW 作成 | `02_cortex_analyst.ipynb` Step 3（v2） |
| （追加） | 最小構成の Semantic View（v1）と、同じ9問での正答率比較 | `02_cortex_analyst.ipynb` Step 2・4 |
| （追加） | PDF のテキスト抽出・チャンク分割・Cortex Search Service 作成 | `03_cortex_search.ipynb` |
| スキル Step 3 | `CREATE AGENT` で SALES_OPS_AGENT 作成（Cortex Analyst ツール） | `04_cortex_agent.ipynb` Step 1（Analyst ＋ Search の2ツール） |
| スキル Step 4 | `DATA_AGENT_RUN` で3つのテスト質問 | `04` Step 2（データと文書をまたぐ質問を追加） |
| （追加） | Agent Studio・Snowflake Intelligence での確認 | `04` Step 3 |
| スキル Step 5 / Workshop 5章 Step 6 | `CREATE MCP SERVER`（CORTEX_AGENT_RUN）、権限付与 | `05_mcp_and_oauth.ipynb` Step 1〜2 |
| スキル Step 6 / Workshop 5章 Step 7 | ACCOUNTADMINで `SECURITY INTEGRATION`（OAuth）作成、Client Secret取得 | `05` Step 3〜5 |
| スキル Step 7 | Quickに入力する値の表示と手順 | `05` Step 5 → `docs/02_quick_setup_guide_ja.md` |
| スキル Troubleshooting | SHOW/DESCRIBE/直接テスト | `05` Step 6・`docs/troubleshooting_ja.md` |
| スキル Cleanup / Workshop 9章 | DROP 一式 | `05` 末尾（既定は実行しない） |

## 元教材から変えている点

| 項目 | 元教材 | 本リポジトリ | 理由 |
|---|---|---|---|
| ユーザー名 | `SNOWFLAKE_USER` を手で書き換え | `CURRENT_USER()` を使用 | 書き換えミス防止 |
| テーブルへのSELECT付与 | テーブル作成前に `GRANT SELECT ON ALL TABLES` | ロード後に付与（＋FUTURE GRANTS） | 作成前の付与は後から作ったテーブルに効かない |
| Semantic View | 英語の同義語のみ | 日本語の同義語・検証済みクエリ、社内 KPI のメトリクスを追加 | 日本語の質問と社内用語に答えられるように |
| 精度の確認 | なし | v1（最小構成）と v2 の正答率を同じ9問で自動採点（検証時 4/9 → 9/9） | 改善の効果を数字で示す |
| 非構造化データ | S3 に PDF はあるが未使用 | Cortex Search で検索、Agent のツールに追加 | 数字と社内の基準をまたいで答える |
| Agent の指示 | 英語 | ツールの使い分けと、日本語で回答する指示を追加 | 日本向け・2ツールの使い分け |
| Agent への権限 | Workshop 5章 Step 6 では MCP の GRANT が重複し、Agent への GRANT が欠落 | `GRANT USAGE ON AGENT` を明示 | 抜け漏れの修正 |
| 製品の結合 | 取引の `PRODUCT_SKU`（ENT-ANNUAL）と製品カタログの SKU（ENT-ANN-011）で結合 → **0件** | ティア×請求サイクル単位の `PRODUCT_PLAN_VIEW` で結合（200件） | 「ティア別売上」が答えられなかったため |
| 解約リスクの説明 | `Churn risk score (0-100)` | 「0〜1 ではなく 0〜100、30未満が低リスク」と明記 | Flow のプロンプト（`< 0.3`）で0件になる問題への対策 |
| OAuth のセカンダリロール | `IMPLICIT` | `NONE` | MCP の推奨設定。Quick 経由ではハンズオン用ロールの権限だけで動かす |
| ユーザー設定 | DEFAULT_ROLE のみ変更 | DEFAULT_ROLE・DEFAULT_WAREHOUSE を設定し、`ALLOWED_INTERFACES` を確認 | トライアルの初期ロール（ACCOUNTADMIN）は OAuth でブロックされる。ALLOWED_INTERFACES が制限されていると Quick がログインを繰り返す |
| 前提アカウント | Workshop 配布のアカウント | トライアルアカウント | AI 機能の制限・既定コンピュートプールの注意を追加 |
| Flow のプロンプト | `CHURN_RISK_SCORE < 0.3`、製品カタログとの結合 | `< 30`、ティア単位のカタログ平均で結合、自然言語の質問1回＋Flow 側で計算 | 元のままではレポートが空・エラーになる |

## 確認ポイント

1. `setup.sql` の最後の確認で、テーブル各200件・プラン結合200件・PDF 2件（setup.sql）
2. AI 機能が使えること（01 Step 0）
3. 正答率が v1 より v2 で上がること（02 Step 4）
4. 日本語の質問で PDF の該当段落が返ること（03 Step 4）
5. Agent が質問に応じて Analyst と Search を使い分けること（04 Step 2）
6. OAuth の Client ID / Secret を控えたこと（05）
7. Quick 側の Redirect URL と `OAUTH_REDIRECT_URI` が完全一致していること（05 / Quick手順書）
8. DEFAULT_ROLE が `CORTEX_QUICK_HOL_ROLE`、ALLOWED_INTERFACES が `ALL` であること（05 Step 3・6）
