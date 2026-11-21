# User Lifecycle

正面 journey，涵蓋帳號生命週期與課程角色流程。沒有任何模型呼叫，後端不需要 LLM 設定。

| Case | 檔案 | 驗證內容 |
| --- | --- | --- |
| Account Lifecycle | `01-account.http` | 註冊、登入、取得目前使用者、更新語言、修改密碼並以新密碼登入、登出並確認 refresh session 已撤銷 |
| Course And Roles | `02-course-and-roles.http` | 老師建課；兩位學生以邀請碼加入；指派助教（先預檢再正式）並更新權限；各角色的課程列表與課程資訊；依角色的成員名單；學生退出、老師移除學生與撤銷助教；刪除課程 |

## 執行

```sh
cp .env.example .env   # 在本資料夾；老師帳密見 docs/測試資料.md

httpyac send scenarios/user-journey/user-lifecycle/01-account.http --name verifyLogoutRevokedSession
httpyac send scenarios/user-journey/user-lifecycle/02-course-and-roles.http --name teacherCourseListAfterDelete
```

兩個 case 都自成一體：自己建帳號與課程，結束時課程已刪除；註冊的帳號會留在資料庫。
