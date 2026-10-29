# Amazon Quick × Snowflake ハンズオン（Notebook 版）

Snowflake の **Cortex Analyst・Cortex Search・Cortex Agent** を一から組み立て、最後に **Amazon Quick** から自然言語で使えるようにするハンズオンです。


Quick 側の手順は日本語のガイドにしています。

```
6テーブル（S3）→ Semantic View → Cortex Analyst ┐
PDF レポート（S3）→ Cortex Search ──────────────┴→ Cortex Agent → Managed MCP Server → OAuth → Amazon Quick
```

## 構成

| ファイル | 役割 |
|---|---|
| [`load.sql`](load.sql) | **API 統合の仕組み**：GitHub からワークスペースを作るための API 統合・Git リポジトリ |
| [`setup.sql`](setup.sql) | **データの準備と権限**：WH・DB・ロール、S3 から6テーブルと PDF 2本、取引と製品をつなぐビュー |
| [`notebooks/01_explore_data.ipynb`](notebooks/01_explore_data.ipynb) | 取り込んだデータの確認。どんなデータがあり、何を作るのか |
| [`notebooks/02_cortex_analyst.ipynb`](notebooks/02_cortex_analyst.ipynb) | **Cortex Analyst**：Semantic View を最小構成で作る → 改善版を作る → 同じ9問で**正答率を比較**（GUI / SQL の両方の作り方を記載） |
| [`notebooks/03_cortex_search.ipynb`](notebooks/03_cortex_search.ipynb) | **Cortex Search**：PDF のテキスト抽出・チャンク分割・検索サービス作成（GUI / SQL） |
| [`notebooks/04_cortex_agent.ipynb`](notebooks/04_cortex_agent.ipynb) | **Cortex Agent**：Analyst と Search を使い分ける Agent（GUI / SQL） |
| [`data/pdfs/`](data/pdfs/) | 03 で検索対象にする PDF レポート 2 本（[Sales Performance Analysis](data/pdfs/Sales%20Performance%20Analysis.pdf) / [Customer Intelligence & Pipeline](data/pdfs/Customer%20Intelligence%20%26%20Pipeline.pdf)）。`setup.sql` が S3 から取り込むものと同じ |
| [`semantic_views/sales_ops_semantic_view.yaml`](semantic_views/sales_ops_semantic_view.yaml) | 02 の v2 を GUI（Autopilot）で作るときにアップロードする YAML |
| [`notebooks/05_mcp_and_oauth.ipynb`](notebooks/05_mcp_and_oauth.ipynb) | MCP Server・OAuth の作成、Quick 用のユーザー設定、Quick に入力する値の表示 |
| [`docs/02_quick_setup_guide_ja.md`](docs/02_quick_setup_guide_ja.md) | Amazon Quick 側：コネクタ・Space・Chat Agent・Flow |

## 必要なもの

- **Snowflake アカウント**
- **AWS アカウント**

## 進め方

1. **API 統合を作る**：Snowsight の SQL ワークシートに [`load.sql`](load.sql) を貼り付けて「すべて実行」します。公開リポジトリなので、GitHub の認証情報は要りません。
2. **データを準備する**：同じように [`setup.sql`](setup.sql) を「すべて実行」します。最後の確認で、テーブル各200件・プラン結合200件・PDF 2件と出れば OK です。
3. **ワークスペースを作る**：**Projects » Workspaces** » 左上のワークスペース名 » **From Git repository** を選び、次を入力します。

   | 項目 | 値 |
   |---|---|
   | Repository URL | `https://github.com/sfc-gh-dmiyagawa/quick-snowflake-hol` |
   | API integration | `QUICK_HOL_GIT_INTEGRATION` |
   | 認証 | Public repository |

   > Git 連携を使わない場合は、`notebooks/` のファイルをダウンロードしてワークスペースにアップロードしても構いません。
4. `notebooks/01_explore_data.ipynb` を開きます。接続先は **Run on container**、コンピュートプールは **`SYSTEM_COMPUTE_POOL_CPU`** にして、**Run all** で上から実行します。
5. `02` → `03` → `04` → `05` の順に、同じように実行します。05 の Step 5 に、Quick に入力する値が表示されます。
6. [`docs/02_quick_setup_guide_ja.md`](docs/02_quick_setup_guide_ja.md) に沿って、Quick 側を設定します。

> 💡 05 の Step 3 で、実行ユーザーの **DEFAULT_ROLE をハンズオン用ロールに変更**します。Quick からの OAuth ログインでは、ユーザーの DEFAULT_ROLE でセッションが作られます（ログイン時の同意画面に表示されるロールです）。ACCOUNTADMIN などの管理者ロールは OAuth では使えない（既定でブロック）ため、DEFAULT_ROLE が ACCOUNTADMIN のままだとログインが拒否されます。変更しても、Snowsight では今までどおり `USE ROLE ACCOUNTADMIN` で管理者作業ができます。元に戻す方法は 05 の末尾にあります。

## Semantic View の精度向上（02）

テーブルを並べただけの Semantic View（v1）と、次の4つを加えた改善版（v2）に、同じ9問を投げて自動採点します。
- 説明・同義語（日本語を含む）
- リレーションの修正
- 社内 KPI のメトリクス
- 検証済みクエリ

Agent が生成した SQL を実行し、結果に正解の値が含まれるかで採点します。

| | v1（最小構成） | v2（改善版） |
|---|---|---|
| 正答数（検証時） | **4 / 9** | **9 / 9** |

v1 が間違えた理由は、次の3種類です。どれも Semantic View にビジネスの定義を書くことで解決しています。

| 間違えた理由 | 例 |
|---|---|
| データのつながり | 製品の結合が0件になる |
| 社内用語 | 停滞商談・失注リスク・勝率 |
| PDF にだけ書かれた基準 | 推奨パイプラインカバレッジ 1.6 倍 |

## 元教材からの主な修正点

| 項目 | 修正内容 |
|---|---|
| 構成 | Cortex Search（PDF）と、Semantic View の精度比較を追加。Agent は Analyst と Search の2つのツールを持つ |
| データ | 取引の SKU と製品カタログの SKU が一致せず、製品の結合が0件 → ティア×請求サイクル単位の `PRODUCT_PLAN_VIEW` で結合 |
| 権限 | テーブル作成前の `GRANT SELECT ON ALL TABLES`、Agent への GRANT 漏れを修正 |
| Quick 接続 | OAuth のセカンダリロールを `NONE`（推奨設定）、DEFAULT_ROLE・DEFAULT_WAREHOUSE の設定、`ALLOWED_INTERFACES` の確認 |
| Flow | `CHURN_RISK_SCORE < 0.3`（スコアは0〜100のため0件）を修正、自然言語の質問1回＋Flow 側で計算する形に変更（[Quick ガイド 7章](docs/02_quick_setup_guide_ja.md#7-flow-を作る)） |
| 日本語化 | 日本語の同義語・検証済みクエリ、日本語で回答する Agent の指示、多言語の埋め込みモデル（英語の PDF を日本語で検索） |


## 作成されるオブジェクト

| 種類 | 名前 |
|---|---|
| ウェアハウス | `CORTEX_QUICK_HOL_WH`（XSMALL、60秒で自動停止） |
| データベース / スキーマ | `CORTEX_QUICK_HOL_DB.CORTEX_QUICK_HOL_SCHEMA` |
| ロール | `CORTEX_QUICK_HOL_ROLE` |
| テーブル / ビュー | 6テーブル、`PRODUCT_PLAN_VIEW`、`DOCS_PARSED`、`DOCS_CHUNKS` |
| ステージ | `HOL_S3_PDF_STAGE`（公開 S3）、`DOCS_STAGE`（PDF のコピー先） |
| Semantic View | `SALES_OPS_SV_BASIC`（v1）、`SALES_OPS_SEMANTIC_VIEW`（v2） |
| Cortex Search Service | `SALES_DOCS_SEARCH` |
| Cortex Agent | `SALES_OPS_AGENT` |
| MCP Server | `SALES_OPS_MCP_SERVER` |
| セキュリティ統合 | `SALES_OPS_QUICK_SUITE_OAUTH` |
| Git 連携（load.sql） | `QUICK_HOL_GIT_DB`、`QUICK_HOL_GIT_INTEGRATION` |

あわせて、アカウント設定 `CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'` と、実行ユーザーの `DEFAULT_ROLE` / `DEFAULT_WAREHOUSE` も変更します。

## 開発者向け

- `tools/build_notebooks.py`：Notebook を生成するスクリプトです。Notebook は直接編集せず、こちらを編集して再生成します。
- `tools/semantic_view_basic.sql` / `tools/semantic_view_source.sql`：Semantic View v1 の DDL と、v2 の元になる YAML です。
- `tools/run_notebooks.py`：手元から実アカウントに対して全セルを実行する検証スクリプトです。`snow` CLI の接続名を使います（環境変数 `SNOWFLAKE_CONNECTION` で指定）。

```bash
python tools/build_notebooks.py
python tools/run_notebooks.py notebooks/0*.ipynb
```

## 参考

- [Build Conversational Analytics with Amazon Quick and Snowflake MCP（Snowflake Developers）](https://www.snowflake.com/en/developers/guides/build-conversational-analytics-with-amazon-quick-and-snowflake-mcp/)
- [Snowflake-managed MCP server（Snowflake Documentation）](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)
- [Cortex Search（Snowflake Documentation）](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Notebooks in Workspaces（Snowflake Documentation）](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-edit-run)
