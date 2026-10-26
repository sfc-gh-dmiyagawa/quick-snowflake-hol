-- ============================================================================
-- Amazon Quick × Snowflake ハンズオン  Git 連携セットアップ（load.sql）
--   GitHub の公開リポジトリから Snowsight の Workspace を作るための準備です。
--   実行方法: Snowsight の SQL ワークシートに貼り付けて「すべて実行」（約1分）
--   公開リポジトリのため、GitHub の認証情報（シークレット）は不要です。
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- Git リポジトリオブジェクトの置き場所
CREATE DATABASE IF NOT EXISTS QUICK_HOL_GIT_DB;
CREATE SCHEMA   IF NOT EXISTS QUICK_HOL_GIT_DB.GIT;
USE SCHEMA QUICK_HOL_GIT_DB.GIT;

-- GitHub への接続を許可する API 統合（このリポジトリのオーナー配下だけを許可）
CREATE OR REPLACE API INTEGRATION QUICK_HOL_GIT_INTEGRATION
  API_PROVIDER         = GIT_HTTPS_API
  API_ALLOWED_PREFIXES = ('https://github.com/sfc-gh-dmiyagawa/')
  ENABLED              = TRUE;

-- リポジトリを Snowflake に登録して最新を取得
CREATE OR REPLACE GIT REPOSITORY QUICK_HOL_GIT_REPO
  API_INTEGRATION = QUICK_HOL_GIT_INTEGRATION
  ORIGIN          = 'https://github.com/sfc-gh-dmiyagawa/quick-snowflake-hol.git';

ALTER GIT REPOSITORY QUICK_HOL_GIT_REPO FETCH;

-- 確認：notebooks/ に 3 本の .ipynb が見えれば OK
LS @QUICK_HOL_GIT_REPO/branches/main/notebooks/;

-- ----------------------------------------------------------------------------
-- 次の手順（Snowsight の画面操作）
--   1. Projects » Workspaces » 左上のワークスペース名 » 「From Git repository」
--   2. Repository URL : https://github.com/sfc-gh-dmiyagawa/quick-snowflake-hol
--      API integration: QUICK_HOL_GIT_INTEGRATION
--      認証            : Public repository（認証なし）
--   3. 作成されたワークスペースで notebooks/01_data_setup.ipynb を開いて実行
-- ----------------------------------------------------------------------------
