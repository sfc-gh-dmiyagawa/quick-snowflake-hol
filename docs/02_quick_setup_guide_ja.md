# Amazon Quick 側の設定ガイド

AWS Workshop「AI-Powered Conversations with your Data Using Amazon Quick and Snowflake via MCP」6章・7章の日本語版です。
ハンズオンで詰まりやすい点（トライアルアカウント、リージョン、Flow のプロンプト）を修正・補足しています。

**前提**：`notebooks/05_mcp_and_oauth.ipynb` を最後まで実行し、Step 5 の値（6項目）を表示できること。

| 05 の Step 5 で表示される値 | 使う場所 |
|---|---|
| MCP server endpoint | 手順 3-4（Connect） |
| Client ID / Client secret | 手順 3-5（Authenticate） |
| Token URL / Authorization URL | 手順 3-5（Authenticate） |
| Redirect URL | Quick 側に表示される値と一致するか確認するだけ |

---

## 0. 始める前に（重要）

| 確認すること | 理由 |
|---|---|
| **AWS コンソールのリージョンが US West (Oregon) `us-west-2`** | Snowflake の OAuth 連携には `https://us-west-2.quicksight.aws.amazon.com/sn/oauthcallback` を登録しています。別リージョンで Quick を作ると、ログイン後にリダイレクトエラーになります（別リージョンを使う場合は 05 の `QUICK_REGION` を変えて OAuth 連携を作り直してください）。 |
| **Snowflake のユーザー名とパスワードを手元に用意** | Quick から Snowflake にログインするときに使います（トライアルにサインアップしたユーザー）。 |
| **05 の Step 3 を実行済み（DEFAULT_ROLE = `CORTEX_QUICK_HOL_ROLE`）** | DEFAULT_ROLE が ACCOUNTADMIN のままだと、OAuth ログインが拒否されます。 |
| **Client secret はコピー直前に表示** | 05 の Step 5 で `SHOW_SECRET = True` にして実行し、貼り付けたら `False` に戻します。画面共有に注意してください。 |

---

## 1. Amazon Quick を開く

1. AWS マネジメントコンソールにサインインします（ハンズオンでは配布された AWS アカウントを使います）。
2. 画面上部の検索バーに **Amazon Quick** と入力し、検索結果の **Amazon Quick** をクリックします。
3. アカウント選択画面が出たら、**Other active AWS console sessions** の中から、ハンズオン用 AWS アカウントのセッション（例：`WSParticipantRole/Participant`）を選びます。既存の Quick アカウントが表示されても無視してください。

> 🖼️ **図の差し込み位置：Quick の検索とアカウント選択**

## 2. Amazon Quick にサインアップする（初回のみ）

1. **Let's get started** 画面で AWS アカウント ID が表示されていることを確認し、**Sign up for Amazon Quick** をクリックします。
2. 次のように入力します。

   | 項目 | 値 |
   |---|---|
   | Account name | `HOL-LAB`（任意。世界で一意である必要があるため、使われている場合は `HOL-LAB-<名前>` など） |
   | Email for account notifications | 自分のメールアドレス |
   | Region | **US West (Oregon)** |
   | Authentication method | Password-based または Single Sign-On |
   | Encryption | Use AWS-managed key（既定） |

3. **Create account** をクリックし、作成完了（緑のチェック）を待ちます。
4. **Go to Amazon Quick** をクリックし、アカウント選択画面で再びハンズオン用のセッションを選ぶと、Quick のホーム画面が開きます。

> 🖼️ **図の差し込み位置：サインアップ画面（入力例）**

## 3. MCP コネクタを作る

1. 左のナビゲーションで **Connectors** をクリックします。
2. 検索バーの下の **Create for your team** タブを選びます。
3. **Model Context Protocol** のタイルを探してクリックします。
4. **Connect** ステップで次を入力し、**Next** をクリックします。

   | 項目 | 値 |
   |---|---|
   | Name | `Snowflake-Sales-Ops-MCP` |
   | Description | `Snowflake-Sales-Ops-MCP` |
   | MCP server endpoint | 05 の **MCP server endpoint**（`https://<組織>-<アカウント>.snowflakecomputing.com/api/v2/...`） |
   | Connection type | Public network |

5. **Authenticate** ステップで次を入力し、**Create and continue** をクリックします。

   | 項目 | 値 |
   |---|---|
   | Authentication | User authentication（Custom user based OAuth） |
   | Client ID | 05 の **Client ID** |
   | Client secret | 05 の **Client secret**（`SHOW_SECRET = True` で表示した全文） |
   | Token URL | 05 の **Token URL** |
   | Authorization URL | 05 の **Authorization URL** |
   | Redirect URL | 自動入力。05 の **Redirect URL** と完全に一致していることを確認 |

6. Snowflake のサインイン画面が開きます。**Snowflake のユーザー名とパスワード**でサインインします（MFA を設定済みなら確認も求められます）。
7. 権限の確認画面で、ロールが **`CORTEX_QUICK_HOL_ROLE`** になっていることを確認し、**Allow** をクリックします。
   - ここで `ACCOUNTADMIN` と表示される、またはログインが拒否される場合は、05 の Step 3 が反映されていません（[トラブルシュート](troubleshooting_ja.md#oauth-ログイン)）。
8. ツールの確認画面で `sales_ops_agent` が表示されていることを確認し、**Next** をクリックします。
9. 公開範囲の画面で **Publish** をクリックします。
10. コネクタ一覧で `Snowflake-Sales-Ops-MCP` が **Connected** になります。タイルを開くと Status が *Creation in progress* → 数分で **Ready**・**Signed in** に変わります。

> 🖼️ **図の差し込み位置：Connect / Authenticate の入力画面、Snowflake のサインイン・Allow 画面、Ready 状態**

## 4. コネクタをテストする

1. コネクタの Status が **Ready** かつ **Signed in** になったら、**Try it** をクリックします。
2. チャット欄に次を入力して送信します。

   ```
   Which sales reps have the highest quota attainment?
   ```

3. アクションの確認が表示されたら **Allow** をクリックします。
4. **Steven Moore（約 129.9%、North America - West）** がトップの表が返れば成功です。回答までは 20〜40 秒ほどかかります。

> ✅ チェックポイント：コネクタ `Snowflake-Sales-Ops-MCP` が Ready で、テストの質問に Snowflake のデータで回答できた。

---

## 5. Space を作る

Space は、コネクタ・エージェント・Flow とナレッジをまとめる入れ物です。

1. 左のナビゲーションで **Spaces** → **Create Space** をクリックします。
2. 名前を `Snowflake-Sales-Ops-MCP` にします。
3. 作成した Space で **Actions** → **Add actions** をクリックし、`Snowflake-Sales-Ops-MCP` コネクタを選んで **Add** をクリックします（「Successfully added 1 resource to space」と表示されます）。

> 🖼️ **図の差し込み位置：Space の作成とアクション追加**

## 6. Chat Agent を作る

1. 左のナビゲーションで **Chat Agents** → **+ Blank** をクリックします。
2. エージェントの設定欄に次のプロンプトを貼り、**Generate** をクリックします。

   > 💡 元教材の英語プロンプトに、日本語で答える指示と、このデータでは答えられない質問の扱いを追加しています。

   ```text
   You are a Sales Operations Analyst with deep expertise in revenue analytics, sales performance, and operational metrics. You help business users answer questions using the Snowflake-Sales-Ops-MCP connector.

   ## Your Capabilities
   - Answer questions about sales revenue, customers, product tiers (Starter / Professional / Enterprise), billing frequency, sales reps, pipeline, and marketing attribution
   - Answer questions about recommendations and benchmarks in the internal sales reports (e.g. pipeline coverage target, actions for stalled deals)
   - Provide data-driven insights with supporting numbers and trends
   - Present results in clear, actionable summaries with tables when appropriate

   ## Guidelines
   - Always query the Snowflake-Sales-Ops-MCP connector to get real data. Never fabricate numbers.
   - Send one focused question per tool call. Split complex requests into several simple questions.
   - Revenue can be broken down by product tier and billing frequency, but not by individual product or product category.
   - When a question is ambiguous, ask about time period, region, or product tier.
   - Format monetary values with currency symbols. When comparing, show absolute values and percentage changes.
   - If the data returned is empty or unexpected, explain possible reasons and suggest alternative questions.
   - Always reply in the same language as the user. If the user writes in Japanese, reply in Japanese.

   ## Response Format
   - Lead with a direct answer
   - Follow with supporting data in a table or bullet points
   - End with 1-2 suggested follow-up questions
   ```

3. Space のアクションとして `Snowflake-Sales-Ops-MCP` が付いていることを確認します（付いていなければ、エージェントの設定で手順 5 の Space を選びます）。
4. **Launch chat agent** をクリックします。
5. 次の質問を送信し、アクションの確認が出たら **Allow** をクリックします。

| 質問 | 期待される結果（目安） |
|---|---|
| What is total revenue by region? | North America 約 $5.95M、EMEA 約 $4.20M、APAC 約 $1.27M、LATAM 約 $0.94M |
| Which sales reps have the highest quota attainment? | Steven Moore（約 129.9%）がトップ |
| What is the pipeline value by stage? | 総額 約 $19.4M、Proposal が最大 |
| How does revenue break down by product tier? | Enterprise 約 $7.82M、Professional 約 $3.58M、Starter 約 $0.95M |
| 停滞している商談は何件？ | 43 件（社内定義：未クローズで滞留 40 日超） |
| 商談の勝率は？ | 約 69.7% |
| Who are the top customers by lifetime value? | LTV 上位10社の表 |
| What is marketing spend by lead source? | リードソース別の費用 |
| 地域別の売上を教えて | 1行目と同じ数字が日本語で返る |
| 製品ティア別・請求サイクル別の売上を教えて | Enterprise / Annual が最大（約 $5.07M） |
| レポートで推奨されているパイプラインカバレッジは？下回っている営業担当は何人？ | 1.6 倍（Sales Performance Analysis）、63 人（**PDF 検索とデータの両方**を使う） |
| 停滞商談への推奨アクションは？ | 役員スポンサーの関与、競合乗り換えキャンペーンなど（PDF 検索） |

> 🖼️ **図の差し込み位置：Chat Agent の回答画面**

## 7. Flow を作る

Flow は、決まった手順を自動で実行してレポートを作る機能です。

> ⚠️ **元教材のプロンプトからの修正点**（そのまま使うとレポートが空になる・エラーになります）
> - 解約リスクスコアは **0〜100** の値です。元の `CHURN_RISK_SCORE < 0.3` は該当が **0件** になるため `< 30` にしています。
> - 取引と製品カタログは SKU で結合できないため、SKU の先頭（STARTER / PRO / ENT）からティアを判定し、**ティア単位のカタログ平均値**で結合するよう Agent に指示しています。
> - Agent には **自然言語の質問を1回だけ** 送り、計算は Flow 側で行います（SQL を送るとエラーになるため）。

1. 左のナビゲーションで **Flows** → **Create Flow** をクリックします。
2. プロンプト欄に次を貼り、**Generate** をクリックします。

   ```text
   Analyze customer expansion opportunities and produce one complete downloadable report.

   DATA RETRIEVAL RULES (important):
   - Use the Snowflake-Sales-Ops-MCP connector tool "sales_ops_agent".
   - Send it a NATURAL-LANGUAGE question only. Do NOT write or send SQL.
   - Make ONE data request using exactly the question below, and run it automatically without user confirmation. If the agent offers a workaround or asks to re-run, accept it automatically and proceed — never stop for confirmation.

   "For every customer with churn risk score below 30 (scale 0-100) and expansion potential of High or Medium, return one row per customer.
   IMPORTANT DATA NOTE: transaction PRODUCT_SKU values (STARTER-ANNUAL, PRO-MONTHLY, ENT-ANNUAL, etc.) do NOT match catalog PRODUCT_SKU values (STA-ANN-001, PRO-MON-003, ENT-MLT-007, etc.). Do NOT join transactions to products on PRODUCT_SKU. Instead:
    1. Derive each transaction's tier from the SKU prefix: STARTER -> Starter, PRO -> Professional, ENT -> Enterprise.
    2. Compute tier-level averages from the product catalog grouped by PRODUCT_TIER: average LIST_PRICE_USD, average UPSELL_RATE_PCT, average AVERAGE_CONTRACT_LENGTH_MONTHS.
    3. Join on tier.
   Return: company name, industry, company size, churn risk score, expansion potential, first purchase date, total spend to date (sum of deal size USD; 0 if no transactions), current tier (tier of the customer's most recent transaction; null if no transactions), current tier average list price, next tier average list price (Starter -> Professional -> Enterprise; null if already Enterprise), current tier average upsell rate pct, and current tier average contract length in months."

   CALCULATIONS (do these in the Flow, on the returned rows):
   - Customers with no transactions (current tier is null): Expansion Type = "New Land (no purchase history)", Revenue Potential = 0, Renewal Timing = "N/A", Priority = "Nurture". Keep them in the table, ranked at the bottom.
   - Customers already on Enterprise: Expansion Type = "Retain / Cross-sell", Revenue Potential = 0.
   - Otherwise: Expansion Type = "Upgrade to <next tier>", Revenue Potential = (next tier avg list price - current tier avg list price) x (upsell rate pct / 100).
   - Months since first purchase = whole months between first purchase date and today.
   - Months until renewal = contract length - (months since first purchase MOD contract length). Days until renewal = months x 30.
   - Priority: "Act Now" if <= 90 days, "Prepare" if 91-180 days, "Nurture" if > 180 days.

   REPORT: title "Customer Expansion Opportunities — [Current Month Year]"
   1. Executive Summary (3 lines max): total expansion revenue potential, number of qualified customers (and how many lack purchase history), number of "Act Now" accounts.
   2. Full opportunity table with ALL qualified customers, ranked by Revenue Potential descending. Columns: Company Name | Industry | Company Size | Current Spend | Expansion Type | Revenue Potential | Renewal Timing | Priority
   3. Add one footnote line: "Product tier derived from transaction SKU prefix; pricing uses tier-level catalog averages."
   4. Format all currency as $X,XXX. Mark "Act Now" rows in bold.

   Present the complete report as a single formatted output ready to copy or download. Do not ask follow-up questions. Do not split into multiple messages.
   ```

   > 💡 日本語のレポートにしたい場合は、最後に `Write the report in Japanese.` を追加してください。

3. 生成された Flow で、コネクタ `Snowflake-Sales-Ops-MCP` が使われていることと、各ステップの内容を確認します。
4. **Share** をクリックし、**Share with all** をオンにします（「Successfully shared flow with all users」と表示されます）。
5. **Flow library** タブに作成した Flow が表示されます。タイルをクリックして **Start** → **Submit** をクリックします。
6. 3〜5分ほどでレポートが生成され、ダウンロードできます。

> 🖼️ **図の差し込み位置：Flow の生成画面、実行中の画面、完成したレポート**

### （任意）定期実行にする

Flow の画面でトリガーを作成し、名前とスケジュール（例：毎週月曜 9:00）を設定して **Create** をクリックすると、レポートが定期的に作られます。

> ✅ チェックポイント
> - Space `Snowflake-Sales-Ops-MCP` に MCP コネクタのアクションが付いている
> - Chat Agent が Snowflake のデータで質問に答える
> - Flow が顧客拡大機会のレポートを作る

---

## 8. 後片付け

- **Snowflake 側**：`05_mcp_and_oauth.ipynb` 末尾のクリーンアップセルを使います。DEFAULT_ROLE を戻す場合は `RESTORE_DEFAULT_ROLE = "ACCOUNTADMIN"` にします。
- **Quick 側**：Flow → Chat Agent → Space → コネクタの順に削除します。ハンズオン用の AWS アカウントはイベント終了後に自動で削除されます。

困ったときは [troubleshooting_ja.md](troubleshooting_ja.md) を参照してください。
