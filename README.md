# Amazon Quick × Snowflake ハンズオン（Notebook 版）

Amazon Quick から Snowflake Cortex Agent に自然言語で質問できる環境を、**Snowflake のトライアルアカウント**で一から作るハンズオンです。

元教材（Snowflake クイックスタート「Build Conversational Analytics with Amazon Quick and Snowflake MCP」/ AWS Workshop Studio）では Cortex Code のスキルが Snowflake 側をまとめて自動構築します。
このリポジトリでは、その処理を **3本の Notebook** に分け、上から実行しながら「何が作られているか」を確認できるようにしています。Quick 側の手順は日本語のガイドにしています。

```
6テーブル（S3） → Semantic View → Cortex Agent → Managed MCP Server → OAuth → Amazon Quick（Chat Agent / Flow）
```

## 構成

| ファイル | 内容 | 所要時間 |
|---|---|---|
| [`notebooks/01_data_setup.ipynb`](notebooks/01_data_setup.ipynb) | 事前チェック（AI 機能）、WH・DB・ロール作成、S3 から6テーブルをロード、取引と製品をつなぐビュー | 約10分 |
| [`notebooks/02_semantic_view_and_agent.ipynb`](notebooks/02_semantic_view_and_agent.ipynb) | Semantic View・Cortex Agent の作成と、英語・日本語での動作確認 | 約15分 |
| [`notebooks/03_mcp_and_oauth.ipynb`](notebooks/03_mcp_and_oauth.ipynb) | MCP Server・OAuth 連携の作成、Quick 用ユーザー設定、Quick に入力する値の表示 | 約10分 |
| [`docs/02_quick_setup_guide_ja.md`](docs/02_quick_setup_guide_ja.md) | Amazon Quick 側：コネクタ・Space・Chat Agent・Flow | 約40分 |
| [`docs/troubleshooting_ja.md`](docs/troubleshooting_ja.md) | よくあるエラーと対処 | － |
| [`docs/01_snowflake_overview_ja.md`](docs/01_snowflake_overview_ja.md) | 元教材のスキルとの対応表、変更点 | － |
| [`load.sql`](load.sql) | Git リポジトリからワークスペースを作るための API 統合・Git リポジトリ作成 | 約1分 |
| [`sql/00_setup.sql`](sql/00_setup.sql) | 01 と同じデータ準備を SQL ワークシートで一括実行する版 | 約3分 |

## 必要なもの

- **Snowflake トライアルアカウント**（Enterprise エディション、AWS リージョン推奨）
  - ⚠️ 通常のセルフサービストライアルでは Cortex Agent などの AI 機能が**既定で無効**です。イベント用のサインアップ URL で作ったアカウントを使うか、**Admin » Billing でクレジットカードを登録**してください（カードを登録しても残りの無償クレジットはそのまま使えます）。01 の最初のセルで確認できます。
- **AWS アカウント**（Amazon Quick を **us-west-2 / US West (Oregon)** で使えること）

## 進め方

1. **Git 連携の準備**：Snowsight の SQL ワークシートに [`load.sql`](load.sql) を貼り付けて「すべて実行」します（API 統合と Git リポジトリを作成。公開リポジトリなので認証情報は不要）。
2. **ワークスペースを作成**：**Projects » Workspaces** » 左上のワークスペース名 » **From Git repository** を選び、次を入力します。

   | 項目 | 値 |
   |---|---|
   | Repository URL | `https://github.com/sfc-gh-dmiyagawa/quick-snowflake-hol` |
   | API integration | `QUICK_HOL_GIT_INTEGRATION` |
   | 認証 | Public repository |

   > Git 連携を使わない場合は、`notebooks/` の3ファイルをダウンロードしてワークスペースにアップロードしても構いません。
3. `notebooks/01_data_setup.ipynb` を開き、接続先を **Run on container**・コンピュートプール **`SYSTEM_COMPUTE_POOL_CPU`** にして、**Run all** で上から実行します。
4. `02` → `03` の順に同じように実行します。03 の Step 5 に Quick で使う値が表示されます。
5. [`docs/02_quick_setup_guide_ja.md`](docs/02_quick_setup_guide_ja.md) に沿って Quick 側を設定します。

> 💡 03 の Step 3 で、実行ユーザーの **DEFAULT_ROLE をハンズオン用ロールに変更**します。トライアルの初期ロール ACCOUNTADMIN では Quick から OAuth でログインできないためです。変更後も `USE ROLE ACCOUNTADMIN` で管理者作業はできます。元に戻す方法は 03 の末尾にあります。

## 元教材からの主な修正点

| 項目 | 修正内容 |
|---|---|
| トライアル対応 | AI 機能の事前チェック、クロスリージョン推論の有効化、既定コンピュートプールの案内 |
| データ | 取引の SKU と製品カタログの SKU が一致せず製品の結合が0件 → ティア×請求サイクル単位の `PRODUCT_PLAN_VIEW` で結合 |
| 権限 | テーブル作成前の `GRANT SELECT ON ALL TABLES`、Agent への GRANT 漏れを修正 |
| Quick 接続 | OAuth のセカンダリロールを `NONE`（推奨設定）、DEFAULT_ROLE・DEFAULT_WAREHOUSE の設定、`ALLOWED_INTERFACES` の確認（制限されていると Quick がログインを繰り返す） |
| Flow | `CHURN_RISK_SCORE < 0.3`（スコアは0〜100のため0件）を `< 30` に修正、SKU 不一致を踏まえたティア単位の結合を指示、自然言語の質問1回＋Flow 側で計算する形に変更（[Quick ガイド 7章](docs/02_quick_setup_guide_ja.md#7-flow-を作る)） |
| 日本語化 | Semantic View の日本語同義語、日本語で回答する Agent の指示 |

詳細は [`docs/01_snowflake_overview_ja.md`](docs/01_snowflake_overview_ja.md) を参照してください。

## 作成されるオブジェクト

| 種類 | 名前 |
|---|---|
| ウェアハウス | `CORTEX_QUICK_HOL_WH`（XSMALL、60秒で自動停止） |
| データベース / スキーマ | `CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA` |
| ロール | `CORTEX_QUICK_HOL_ROLE` |
| テーブル / ビュー | 6テーブル、`PRODUCT_PLAN_VIEW` |
| Semantic View | `SALES_OPS_SEMANTIC_VIEW` |
| Cortex Agent | `SALES_OPS_AGENT` |
| MCP Server | `SALES_OPS_MCP_SERVER` |
| セキュリティ統合 | `SALES_OPS_QUICK_SUITE_OAUTH` |

アカウント設定 `CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'` と、実行ユーザーの `DEFAULT_ROLE` / `DEFAULT_WAREHOUSE` も変更します。

## 開発者向け

- `tools/build_notebooks.py`：Notebook を生成するスクリプト（Notebook を直接編集せず、こちらを編集して再生成します）
- `tools/run_notebooks.py`：手元から実アカウントに対して全セルを実行する検証スクリプト（`snow` CLI の接続名を使用）

```bash
python tools/build_notebooks.py
python tools/run_notebooks.py notebooks/01_data_setup.ipynb notebooks/02_semantic_view_and_agent.ipynb notebooks/03_mcp_and_oauth.ipynb
```

## 参考

- [Build Conversational Analytics with Amazon Quick and Snowflake MCP（Snowflake Developers）](https://www.snowflake.com/en/developers/guides/build-conversational-analytics-with-amazon-quick-and-snowflake-mcp/)
- [Snowflake-managed MCP server（Snowflake Documentation）](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)
- [Notebooks in Workspaces（Snowflake Documentation）](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-edit-run)
