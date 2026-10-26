# Amazon Quick 側の設定ガイド

AWS Workshop「AI-Powered Conversations with your Data Using Amazon Quick and Snowflake via MCP」6章・7章の日本語版です。
ハンズオンで詰まりやすい点（トライアルアカウント、リージョン、Flow のプロンプト）を修正・補足しています。

**前提**：`notebooks/03_mcp_and_oauth.ipynb` を最後まで実行し、Step 5 の値（6項目）を表示できること。

| 03 の Step 5 で表示される値 | 使う場所 |
|---|---|
| MCP server endpoint | 手順 3-4（Connect） |
| Client ID / Client secret | 手順 3-5（Authenticate） |
| Token URL / Authorization URL | 手順 3-5（Authenticate） |
| Redirect URL | Quick 側に表示される値と一致するか確認するだけ |

---

## 0. 始める前に（重要）

| 確認すること | 理由 |
|---|---|
| **AWS コンソールのリージョンが US West (Oregon) `us-west-2`** | Snowflake の OAuth 連携には `https://us-west-2.quicksight.aws.amazon.com/sn/oauthcallback` を登録しています。別リージョンで Quick を作ると、ログイン後にリダイレクトエラーになります（別リージョンを使う場合は 03 の `QUICK_REGION` を変えて OAuth 連携を作り直してください）。 |
| **Snowflake のユーザー名とパスワードを手元に用意** | Quick から Snowflake にログインするときに使います（トライアルにサインアップしたユーザー）。 |
| **03 の Step 3 を実行済み（DEFAULT_ROLE = `CORTEX_QUICK_HOL_ROLE`）** | DEFAULT_ROLE が ACCOUNTADMIN のままだと、OAuth ログインが拒否されます。 |
| **Client secret はコピー直前に表示** | 03 の Step 5 で `SHOW_SECRET = True` にして実行し、貼り付けたら `False` に戻します。画面共有に注意してください。 |

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
   | MCP server endpoint | 03 の **MCP server endpoint**（`https://<組織>-<アカウント>.snowflakecomputing.com/api/v2/...`） |
   | Connection type | Public network |

5. **Authenticate** ステップで次を入力し、**Create and continue** をクリックします。

   | 項目 | 値 |
   |---|---|
   | Authentication | User authentication（Custom user based OAuth） |
   | Client ID | 03 の **Client ID** |
   | Client secret | 03 の **Client secret**（`SHOW_SECRET = True` で表示した全文） |
   | Token URL | 03 の **Token URL** |
   | Authorization URL | 03 の **Authorization URL** |
   | Redirect URL | 自動入力。03 の **Redirect URL** と完全に一致していることを確認 |

6. Snowflake のサインイン画面が開きます。**Snowflake のユーザー名とパスワード**でサインインします（MFA を設定済みなら確認も求められます）。
7. 権限の確認画面で、ロールが **`CORTEX_QUICK_HOL_ROLE`** になっていることを確認し、**Allow** をクリックします。
   - ここで `ACCOUNTADMIN` と表示される、またはログインが拒否される場合は、03 の Step 3 が反映されていません（[トラブルシュート](troubleshooting_ja.md#oauth-ログイン)）。
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
| Who are the top customers by lifetime value? | LTV 上位10社の表 |
| What is marketing spend by lead source? | リードソース別の費用 |
| 地域別の売上を教えて | 1行目と同じ数字が日本語で返る |
| 製品ティア別・請求サイクル別の売上を教えて | Enterprise / Annual が最大（約 $5.07M） |

> 🖼️ **図の差し込み位置：Chat Agent の回答画面**

## 7. Flow を作る

Flow は、決まった手順を自動で実行してレポートを作る機能です。

> ⚠️ **元教材のプロンプトからの修正点**（そのまま使うとレポートが空になります）
> - 解約リスクスコアは **0〜100** の値です。元のプロンプトの `CHURN_RISK_SCORE < 0.3` は該当が **0件** になるため、`< 30` に直しています（該当 59 社）。
> - 取引と製品カタログは SKU で結合できないため、「次のティアの価格」は **プラン（ティア×請求サイクル）単位の平均定価** を使うようにしています。
> - 1回の問い合わせが 60 秒を超えるとタイムアウトするため、問い合わせを3つに分けています。

1. 左のナビゲーションで **Flows** → **Create Flow** をクリックします。
2. プロンプト欄に次を貼り、**Generate** をクリックします。

   ```text
   Analyze customer expansion opportunities and produce one complete downloadable report.
   Execute all queries automatically without user confirmation using the Snowflake-Sales-Ops-MCP connector.
   Ask the connector these three questions separately (one question per call):

   1. "List customers with churn risk score below 30 (the score is on a 0-100 scale) and expansion potential High or Medium. For each show company name, industry, company size, first purchase date, total spend (sum of deal size), and the highest product tier they purchased. Sort by total spend descending."
   2. "Show the average list price, average upsell rate, and average contract length in months for each product tier and billing frequency."
   3. "How many customers have churn risk score below 30 and expansion potential High or Medium, and what is their total revenue?"

   Then, for each customer from question 1:
   - Expansion type: Starter -> Professional, Professional -> Enterprise, Enterprise -> Expand seats (use 20% of current spend as the estimate)
   - Revenue potential = (average list price of the next tier - average list price of the current tier) x average upsell rate of the current tier / 100
   - Months until renewal = average contract length minus months since first purchase date (modulo the contract length)
   - Priority: "Act Now" if renewal within 3 months, "Prepare" if 3-6 months, "Nurture" otherwise

   Generate a single report titled "Customer Expansion Opportunities - [Current Month Year]" with:
   1. Executive Summary (3 lines max): total expansion revenue potential, number of qualified customers, number of "Act Now" accounts
   2. Full opportunity table ranked by revenue potential descending, columns:
      Company Name | Industry | Company Size | Current Spend | Expansion Type | Revenue Potential | Renewal Timing | Priority
   3. Format all currency as $X,XXX. Mark "Act Now" rows in bold.
   Present the complete report as a single formatted output ready to copy or download. Do not ask follow-up questions.
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

- **Snowflake 側**：`03_mcp_and_oauth.ipynb` 末尾のクリーンアップセルを使います。DEFAULT_ROLE を戻す場合は `RESTORE_DEFAULT_ROLE = "ACCOUNTADMIN"` にします。
- **Quick 側**：Flow → Chat Agent → Space → コネクタの順に削除します。ハンズオン用の AWS アカウントはイベント終了後に自動で削除されます。

困ったときは [troubleshooting_ja.md](troubleshooting_ja.md) を参照してください。
