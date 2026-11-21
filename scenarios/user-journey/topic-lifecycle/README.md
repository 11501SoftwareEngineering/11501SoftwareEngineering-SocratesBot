# Topic Lifecycle

正面 journey，涵蓋題目從建立到學生進入 Session。**會呼叫模型**，後端需要可用的 LLM 設定：伺服器的 `OPENAI_API_KEY`，或呼叫者自己的 key。

| Case | 檔案 | 驗證內容 |
| --- | --- | --- |
| Topic Setup And Publish | `01-topic-setup-and-publish.http` | 具 `edit_topics` 的助教建題（只驗八欄的形狀）；助教讀取並儲存設定，再讀回比對；發布前學生看不到該題；老師發布；學生看到題目、讀背景說明、進入 Session，再次進入取得同一個 Session；老師與助教的題目列表帶人數；刪除課程 |

模型產出的內容每次不同，所以建題後先以 PUT 把八欄設成已知值，之後的斷言才是確定的。

## 執行

```sh
cp .env.example .env   # 在本資料夾；老師帳密見 docs/測試資料.md

httpyac send scenarios/user-journey/topic-lifecycle/01-topic-setup-and-publish.http --name teacherCourseListAfterDelete
```

沒有可用的 LLM 時，建題那一步會失敗；不需要 AI 的 journey（例如 `user-lifecycle`）不受影響。
