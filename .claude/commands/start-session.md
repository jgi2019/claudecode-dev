# /start-session

セッション開始時に、作業対象・正本の版・許可範囲・再開地点を確定する。
共通契約の正本は `jgi2019/jgi-brain/foundation/WORKFLOW.md`。採用済みcommitが未指定の場合、Draftを現行ルールとして扱わない。

## 手順

1. **案件を特定**
   - `/pj <PJラベル>` の引数、現在の作業ディレクトリ、HEYの指示から対象PJを特定する。
   - PJレジストリDB（Notion: `dd705d5de8fe4252a4c8036fb6a8a19a`）で行を取得し、`project_id`（PJ行のpage ID）と正位置を記録する。
   - 特定できない場合は、書込みや実装に進まず候補と不足情報を示す。

2. **受信**
   - Slack `#taro-jiro`（Channel ID: `C0BGKGN721X`）を読み、対象PJ宛＋`[PJ:ソロプレナーOS]` 宛の申し送りだけを読む。
   - Notion ハンドオフDB（data source: `27e1a509-0fb5-4a07-824e-799985d70a3f`）から対象PJの進行中・最新handoffを取得する。
   - SlackとNotionが食い違う場合、Slackの議論だけで正本を上書きしない。HEYの明示指示は対象範囲を確認し、handoffへ記録する。

3. **正本と版を読む**
   - 採用済みAgent Brief、案件のNotion正本、対象repoの現在状態、最新handoff、今回のタスク指示を読む。
   - 各資料についてURL/IDと版（Git commit SHAまたはNotion `last_edited_time`）を `read_versions` として記録する。
   - 読めなかった資料を確認済みにしない。未取得・古い複製・Draftは明示する。

4. **実行境界を確定**
   - `session_id` と、同じ意図の再試行で変えない `operation_id` を決める。
   - HEYの指示から今回の `approval.scope` と根拠を記録する。
   - 同時更新の兆候を確認する。初期運用では同じ対象への複数Agent同時書込みを避ける。

5. **当日の文脈**
   - Morning Vision DB（`fb00fe5b8a494a5e83f17fad847a3445`）の当日エントリを確認する。
   - 最新handoffの次アクションと現在の指示を突き合わせる。

6. **開始カードをチャットに表示**
   ```yaml
   project_id: "<PJ registry page id>"
   session_id: "<session id>"
   operation_id: "<operation id>"
   source_agent: "Claude Code / JIRO"
   execution_environment:
     type: "<local_registered | remote_ephemeral>"
     path: "<pwd>"
     origin: "<git remote URL>"
     head_sha: "<verified SHA>"
   goal: "<今回の目的>"
   handoff_url: "<latest valid handoff URL or none>"
   read_versions:
     - source: "<URL/ID>"
       revision: "<SHA/last_edited_time>"
   approval:
     scope: "<許可範囲>"
     evidence: "<指示の根拠>"
   unresolved_before_start: []
   ```

7. **開始判断**
   - 明示された次アクションが許可範囲内なら、そのまま開始する。
   - 目的・対象・権限のいずれかが曖昧で結果が変わる場合のみ、HEYへ確認する。

## 注意

- ローカル正位置とリモート一時環境を混同しない。リモートはパスではなくorigin・HEAD・clean状態で同一性を確認する。
- ハンドオフの判断理由・制約・未決事項を割愛しすぎない。
- 過去のAgent記憶より、取得した正本と版を優先する。
- `operation_id` はラベルであり、一意制約そのものではない。自動化されるまでは再取得・照合して重複を避ける。
