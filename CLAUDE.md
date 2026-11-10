# 玩真的 FOR REAL — 給接手的 Claude

使用者 PZ（痞子葳）沒有程式背景，所有回覆用繁體中文、白話。這個 repo 是他的個人遊戲與科技資訊 App（他有經營遊戲頻道）。App 裡稱呼他「痞子葳」（問候語、小真播報），不要寫成 PZ。

## 原則（不可違反）
- 不收巴哈姆特（含 GNN）的內容與連結。他嫌那裡多是廠商廣告與業配。
- 只收官方與可信媒體的 RSS／公開資料；不轉載全文，只放標題、短摘要與原文連結。社群、KOL、論壇不收，網友投票選連結的站（Hacker News 這類）也不收：連到的多半是個人部落格（2026-10-28 拿掉 Hacker News 熱門）。
- 濾網一律是寫在 `config/rules.json` 的固定規則，同樣的新聞永遠得到同樣的判斷；被擋下的內容要在「濾網」頁留下理由，不能默默消失。（依來源自己標的分類擋下的清單也在 `rules.json` 的 `block_cats`，`* movies` 代表結尾是「 movies」的分類。改規則前先用新舊規則跑一遍 state 分支的 `items.json.gz` 比對差異，確認沒有誤擋。）
- 「影視娛樂（非遊戲）」`film_tv`：GamesRadar、Polygon、Kotaku 的 RSS 會混進大量電影、影集、漫畫新聞（DC、漫威、Glee…）。只有「來源標了影視分類（`block_cats.film_tv`）＋標題摘要完全沒有遊戲跡象（`game_words`、`game_signal`：遊戲字眼、主機、遊戲作品名）」才擋；改編自遊戲的電影影集（Edgerunners、快打旋風電影、質量效應影集、《決勝時刻》電影、《槍彈辯駁》影集）照常收錄：改編名單就是 `game_signal` 的作品名，新的改編作品要記得加進去（只會讓「不擋」變多，不會誤擋）。只用在遊戲區，科技區的 Netflix、Spotify 商業新聞不受影響。
- 成人內容（`rules.json` 的 `adult`）：R18／18 禁、hentai、成人平台限免這類新聞擋下；標題摘要提到法規、下架、金流、銀行、營收的產業新聞不擋。規則裡用 `(?P<hit>…)` 包住關鍵字，濾網頁就只顯示命中的字（`rules._first`）。
- 遊戲為主、科技 AI 為輔。手機遊戲只要買斷制／獨立遊戲，課金手遊宣傳一律擋下。
- 特價只用官方商店價格（Steam 台灣區、Epic），不放分潤導購連結。
- 不需要推播通知；特價、發售都是 App 內的分頁。
- 個人資料（稍後看、追蹤、已讀）只存在手機 localStorage。

## 怎麼運作
- GitHub Actions（`.github/workflows/forreal.yml`）每小時跑 `pipeline/build.py`：抓 `config/sources.json` 的新聞來源、Steam／Epic／App Store、Wikipedia 發售表 → 過濾、合併同一件事、排序 → 輸出 `public/data/*.json` 並部署 GitHub Pages。
- 每小時一輪靠「接力」：GitHub 的排程 2026/11/6 起常常 4～11 小時才來一次（新聞、特價跟著停更），所以每一輪結束後由 workflow 的 `next` 工作等到這一輪開始後約 58 分鐘，自己用 workflow_dispatch 發出下一輪 build（GITHUB_TOKEN 發的 workflow_dispatch 會觸發新的執行）。已經有比自己新的一輪（排程、推送、別的接力）就不發，所以同一時間只有最新的那條接力；`run` 工作才有 concurrency（state 只能一個人寫），`next` 在等的時候不會擋住推送。每小時第 23 分的排程留著當備援，接力斷掉時靠它接回來。做法和冷眼的盤中接力一樣。
- 跨輪次資料（新聞暫存、價格紀錄、評論快取、來源狀態）存在 `state` 分支，每次只保留一個 commit。`state` 分支的 `out/` 是最近一次輸出，`runs.json` 是執行紀錄。
- 推到 `main` 時執行 `control/job.json` 指定的工作：`build`（抓資料＋發布）／`deploy`（只改介面時用）／`probe`（實測候選來源，原始回應存到 `probe-results` 分支）。
- 雲端 Claude 工作環境連不到這些網站，要實測新來源就用 `probe`。
- 本機測試：先把 `probe-results` 分支解開到 scratchpad，`PROBE=<資料夾> python3 tests/local_news.py`（看濾網與合併）、`python3 tests/local_build.py <輸出資料夾> <state 資料夾>`（跑完整一輪）。這兩支測試的「現在」預設是 probe 抓資料的時間（`summary.json` 的 `started`），要換就設 `NOW=<ISO 時間>`；用真正的現在跑舊 probe，新聞超過 120 小時全被清掉，就什麼都測不到。
- 翻譯：PZ 要外文新聞「先翻成繁體中文再收錄」，並附摘要。每輪在 Actions 上用 llama.cpp 跑開源模型（`scripts/llm_setup.sh` 下載、`scripts/llm_start.sh` 啟動，第一次下載後存在 GitHub 快取 `forreal-llm-v2-qwen3-8b`；4B 模型會翻錯遊戲名、亂加「傳聞」，已改用 8B 加範例，並刪掉原文沒有的「傳聞／尚未證實」句子），`pipeline/translate.py` 依重要性先翻，結果快取在 state 分支 `zh.json`。來不及翻的標 `pend`，App 顯示「翻譯中」。不需要 API 金鑰、不花錢。每輪翻譯器都是剛啟動、沒有提示快取，第一批 4 則要從頭讀完整段提示（4 核心機器上 5 分多鐘），所以請求等待上限是 600 秒（`READ_TIMEOUT`）；以前設 300 秒，排最前面的重要新聞每輪逾時、卡在「翻譯中」好幾天。llama-server 的記錄尾段每輪存在 state 分支 `diag/llama.log`。簡體字偵測用 OpenCC 字典裡「只在簡體出現」的字（約 3,800 字，已剔除群、件、秘、硬這類台灣也用的字），出現就整句轉台灣正體；轉完一律把「臺」換成「台」。
- 翻譯檢查（`translate.check()`，固定規則）：8B 模型常把金額的「億」算錯（$25 billion 寫成 25 億美元，應為 250 億）、把美元寫成「元」、自己猜日本人名漢字（櫻井政博寫成坂井悠真）、抄範例答案。每則翻完都檢查：①標題裡有 `config/glossary.json` 的名稱，翻譯就要用指定譯名或照抄原文；②翻譯裡的每個金額與「萬／億」大數字都要對得上原文（幣別也要對；只抓寫錯或自己加的，省略不算錯）；③原標題講的是實體版，中文標題就要寫出「實體」（以前把「PS5 實體版 2027 年推出」翻成「2027 年發售」）；④不能出現範例答案才有的字句。不過就把錯在哪、正確寫法附在題目後重翻一次，再錯就算失敗、下輪再試（6 輪後顯示原文）。題目一開始就附上「譯名」與「金額」的正確中文寫法（`hints()`）。快取裡的舊翻譯每輪也重新檢查，過不了就重翻（`stats.recheck`）。固定譯名只放人名與非遊戲作品；遊戲名交給 `names.py`。《》以外的英文原名翻完會換成譯名。小修提示詞不用加 `PROMPT_VERSION`（加一會讓三百多則全部重翻）。
- 遊戲中文名（`pipeline/names.py`）：翻譯裡的《英文遊戲名》換成台灣官方中文名，發售日曆也加中文名。先查 Steam 台灣商店（英文名完全相同、100 則評論以上或即將推出），再查維基百科中文版台灣正體（必須是電子遊戲條目；轉址到段落、別的作品、數字對不上都不收）。短名稱兩邊不一致時以維基百科為準（防撞名）。寧可保留英文也不要換錯；規則改了就把 `VERSION` 加一，快取（state 分支 `names.json`）會重查。比對前先去掉變音符號（新聞寫 Ghost of Yotei、維基百科是 Ghost of Yōtei），鍵的算法改了會在載入時自動換成新鍵（查到的優先），不用重查。查到的中英文名對照每輪放進 meta.json 的 `alias`，App 的搜尋與追蹤用它（見「介面」）。
- Steam 評價（特價、新作口碑）：用 `IStoreBrowseService/GetItems` 的 `reviews.summary_filtered`（全球所有語言、過濾掉洗評；一次 40 款，評價文字是中文，例如「極度好評」），`stores.steam_reviews`，快取 72 小時（state 分支 `reviews.json`）。舊的 `appreviews/<appid>?json=1` 2026/11 起改回 Steam 首頁的 HTML，特價頁因此整個變空（2026-11-10 修好），只留作備援。
- 展示素材（`pipeline/media.py` → `data/media.json`，2026/11 超級大更新）：App 看得到的 Steam 遊戲（活動、限時免費、特價前 40、新作、期待榜前 40、願望清單、對到 Steam 的發售日曆大作、每日特惠、發行商特賣）用 GetItems 加 `include_screenshots`／`include_trailers` 查：寬幅主視覺 `hero`（library_hero 1920×620）、直式封面 `box`（library_capsule 600×900，有台灣中文版就用中文版）、`wide`（616×353）、截圖 `shots`（全年齡，最多 6 張；App 用 `.600x338.jpg`／`.1920x1080.jpg` 取尺寸）、預告短片 `vid`（microtrailer，mp4／webm 各約 2.4MB、無聲）、完整預告 `tr`（HLS `hls_264_master.m3u8`，聲音是另一條音軌；封面在圖片主機），加上 `norm_item` 的價格、評價、標籤、簡介。影片主機 `video.akamai.steamstatic.com/store_trailers/`＋`trailer_url_format`；所有主機都回 `Access-Control-Allow-Origin: *`（2026-11-10 probe 實測）。每款快取 3 天（state 分支 `media.json`），每輪最多重查 240 款、輸出最多 260 款，成人內容不收。英文簡介和「活動」頁共用翻譯快取（`extra_zh.json`，每輪最多 100 秒）。發售日曆用 Steam 期待榜名稱或 names.py 在 Steam 對到的遊戲記下 `appid`（`link_steam_ranks`、`link_calendar_appids`）。
- 手動補充（選用）：若有 `ai/zh.json`（`{"items": {新聞id: {"t": 中文標題, "s": 中文摘要}}}`），build 也會合併。
- 「活動」分頁（`pipeline/events.py` → `events.json`，PZ 要的「Steam 平台的各項活動與內容」）：
  - 官方時程：Steamworks 文件 Upcoming Steam Events。日期用英文版（`?language=english`，中文版會落後），中文名稱與說明取中文版表格（用報名網址 `optin/sale/<代號>` 對應）。英文版會拿掉已結束的活動，所以和上次的時程合併、保留結束 21 天內的。
  - Steam 活動一律太平洋時間上午 10 點開始／結束（台灣隔天凌晨 1 或 2 點，看夏令時間）。
  - 正在進行的主題節、季節特賣：Steam 商店「內容中心」帳號（clan 41316928）的活動清單 `events/ajaxgetpartnereventspageable`，活動的 jsondata 有確切時間、`source_content_hub`、報名標籤 `optin_tagid`。季節特賣是全站特賣，參加遊戲直接用特價頁的好價。
  - 新品節：時程顯示進行中時，抓 `store.steampowered.com/sale/nextfest` 活動頁（`data-partnereventstore`），排行榜用 `saleaction/ajaxgetsaledynamicappquery`（clanAnnouncementGID 要用 announcement_body.gid，不是活動 gid；flavor：dailyactiveuserdemo／topwishlisted／trendingwishlisted），榜上的試玩版換成正式遊戲（related_items.parent_appid）。
  - 參加遊戲：任何 Steam 特賣活動都可以用 `actions/ajaxgetdynamicsaleitems?tagids_featured=<標籤>` 依熱門程度列出（主題節用 optin_tagid，新品節與發行商特賣用 featured_app_tagid）。
  - 發行商／系列作特賣、展會：`saleaction/ajaxgetlivesaleevents` → `events/ajaxgetbatchedpartnerevent` → 上面的參加遊戲清單；依參加遊戲的評論數排序。每日特惠與首頁焦點：`api/featuredcategories`。
  - 遊戲資料：`IStoreBrowseService/GetItems`（tchinese、TW）：台灣區價格、折扣與截止時間、評價、標籤（`GetTagList` 中文名）、繁中／簡中支援、試玩版、發售日。英文簡介先找開發商的簡中簡介（OpenCC 轉台灣正體），沒有才交給翻譯器（快取 state 分支 `extra_zh.json`，每輪最多 4 分鐘，重要的先翻；App 在機器翻譯的簡介前標「機翻」）。發行商特賣的活動名稱不翻（專有名詞常被翻錯，保留原文）。成人限定（content descriptor 3、4）與標了色情內容／Hentai 的小眾作品（評論 2 萬則以下）不收。
  - 限時免費（`build_free`）：免費領取（領了就永久留在收藏庫）用 Steam 搜尋 `search/results/?maxprice=free&specials=1`（會混到 DLC，DLC 也收、排在遊戲後面），再用 GetItems 的 `best_purchase_option.is_free_to_keep`、`free_to_keep_ends` 確認與取截止時間。免費週末只看 GetItems 的 `free_weekend` 欄位和行銷訊息 type 14（`is_free_temporarily` 在免費領取時也是 true，不能拿來判斷免費週末）。
  - Steam 用戶端行銷訊息 `IMarketingMessagesService/GetActiveMarketingMessages/v1/?country=TW&anonymous_user=true`：週末特價（2）、週中特價（11）、每日特惠（12）、免費週末（14）、特賣頁（15）的確切起訖，用來補「今日特惠與首頁焦點」的截止時間。抓不到時只記警告，免費領取照做。
  - 離線測試：`python3 tests/local_events.py [模擬時間 ISO] [輸出 events.json]`（`PROBES` 指向解開的 probe 資料夾）。
- Steam 願望清單（`pipeline/wishlist.py` → deals.json 的 `wish`，PZ 2026/10 要的）：`config/steam.json` 的 `profile` 填 Steam 個人檔案網址（/id/xxx 或 /profiles/7656…）。個人檔案 `?xml=1` 換 SteamID64、拿顯示名稱與隱私狀態；`IWishlistService/GetWishlist` 拿清單（願望清單要公開，「遊戲詳細資料」設公開）；遊戲資料用 `events.get_items`／`norm_item`（台灣區價格、折扣截止、評價、發售日），另外查英文名對應發售日曆（`mark_calendar` 在發售表加 `wl`）。價格記錄和特價頁共用 `prices.json`。沒設定時 App 顯示「還沒有連結」。GetWishlist 對「沒公開」和「空的」都回 `{"response":{}}`，所以清單是空的時候再開商店願望清單頁（`?l=tchinese`）：沒公開會出現「無法載入使用者的願望清單」，App 依此顯示「沒有公開」或「目前是空的」（2026/10/22 實測：PZ 的清單已公開、目前是空的）。
- 訂閱片單（`pipeline/subs.py` → releases.json 的 `subs`，「上市」頁的「訂閱片單」）：
  - Game Pass：`catalog.gamepass.com/sigls/v2`（TW、zh-tw）的最近新增／即將加入／即將離開清單＋`displaycatalog.mp.microsoft.com`（台灣官方中文名、圖、台灣售價）。日期與方案（Ultimate／Premium／PC、首日加入）來自 Xbox Wire 每月兩次的「Coming to XBOX Game Pass」文章（從新聞暫存裡 xboxwire 的文章找，解析結果存在 cache `gp_wire`，保留 50 天）；文章有、清單還沒有的也列出（英文名）。
  - PS Plus：台灣官網 `playstation.com/zh-hant-tw/ps-plus/whats-new/`。頁面是好幾個區塊，各有 `data-on-time`／`data-off-time`（網頁用 JS 切換，HTML 裡會留著過期的舊區塊），只採用現在有效的：每月遊戲、遊戲目錄本月新增、經典遊戲目錄、遊戲試玩。日期來自 PlayStation Blog 繁中版的 PS Plus 分類 RSS（`blog.zh-hant.playstation.com/category/ps-plus/feed/`）：每月遊戲公告寫「10月6日星期二至11月2日星期一」、遊戲目錄公告寫「將於10月20日起開放遊玩」；公告標題要提到目前片單裡的遊戲才套用（避免月份錯配）。小真在換新片單的那一週提一次、截止前 3 天提醒；行事曆有每月遊戲最後一天與 Game Pass 離開日。
- 主機特價（`pipeline/console.py` → deals.json 的 `ps`，「特價」頁的「主機」）：PlayStation Store 台灣區。用網頁自己的 GraphQL（persisted query，一定要帶 `content-type: application/json` 標頭，不然會被當成跨站請求擋掉）：`getExperience`（alias deals）找出這週的促銷分類，`categoryStrandRetrieve` 取商品（原價、優惠價、折扣、是否 PS Plus 會員價）。同款遊戲只留一個版本（標準版優先），不收追加內容；名稱去掉結尾的「PS4 & PS5」「(PS5)」這類平台字樣（平台另外顯示），名稱有 Hentai 的成人向小品不收（和 Steam 那邊一致）；每個促銷最多取 300 款（「所有優惠」有兩千多款），照 Sony 頁面的順序排。Store 沒有公開優惠截止時間。查詢的 sha256Hash 寫在 `HASH`；Sony 改版後如果壞掉（濾網頁的來源狀態會顯示錯誤），用 probe_browser 打開 store.playstation.com/zh-hant-tw/pages/deals 抓新的 hash。任天堂：台灣 eShop 有台灣價格（`api.ec.nintendo.com/v1/price?country=TW&ids=<nsuid>` 回新台幣），但沒有公開的特價清單（ec.nintendo.com 的 search/sales 都 404、香港商店網頁擋程式），只做得出不完整的清單，所以沒做。
- 行事曆（`pipeline/ical.py`）：`data/ics/<id>.ics` 是單一遊戲（發售表每筆有 `ics` 代號，App 的行事曆按鈕連過去，發售當天早上 9 點提醒）；`data/cal/releases.ics`（大廠、Steam 期待榜、願望清單的發售日）與 `data/cal/deals.ics`（Steam 官方活動起訖、Steam／Epic 限時免費截止）給手機訂閱，每小時更新。iPhone 用 webcal:// 訂閱；Google 日曆要在電腦版「加入日曆網址」。.ics 不存 state 分支，deploy 模式用上一輪的 JSON 重新產生。
- 離線測試新功能：`PROBE=<probe 資料夾> python3 tests/local_extras.py <預覽站 data 資料夾> <state 資料夾> [模擬時間]`（願望清單用假資料）；展示素材 `PROBE=<probe 資料夾> python3 tests/local_media.py`（要有 include_assets／screenshots／trailers 的 GetItems 回應）。雲端環境連不到 Steam 的圖片與影片主機，介面截圖要把外部圖片換成本機佔位圖才看得出版面。

## 介面
- 主題：遊戲情報中樞（2026/11 超級大更新，延續 2026/10 的防偽情報中樞）。深藍墨色底，用鈔票、護照的防偽印刷當視覺語言：扭索紋花飾（`fx.js` 的 `rosette()`）、全像箔、紫外線掃描光、凹版紅色「攔截」印章、切角的「保全文件」卡片（`.doc`）；再加上遊戲主機的語彙：開場「輕觸開始」、全幅焦點舞台、遊戲盒貨架、寶箱稀有度、魔王血條、成就解鎖。標題用 Noto Serif TC 900，數字用 Saira（窄體），內文用系統字。只有深色模式。
- 全像箔只用在：「真」印、選中的分頁、小真的核心。「真」印只給「官方來源」或「三家以上獨立報導」的消息（傳聞、爆料就算很多家在傳也不給，「已證實」篩選同一套規則，`app.js` 的 `isVerified`）、特價頁的「好價」，以及「活動」頁的 Steam 官方活動（發行商自己辦的特賣不給）。不要拿來裝飾。
- 稀有度（`stage.js` 的 `rarity()`，只用在特價）：傳說＝好價（金框＋「真」印，`DEAL_RULES.great`）、史詩＝推薦（紫框，`DEAL_RULES.good`）、稀有＝觀測新低或六折以下（藍框）、其他普通。沒有 `verdict` 的遊戲（活動頁、願望清單）用同一套門檻算。每次打開 App 第一次進特價頁「開寶箱」（卡片依序掉落，有傳說就閃金光＋金色粒子＋`legend` 音效）。
- 開場畫面（`fx.js` 的 `title()`）：每次打開 App（sessionStorage `fr.booted`）先出現「輕觸開始」，背景是這一輪特價、新作封面排成的斜放遊戲牆，下面逐行出現系統狀態。按下去那一下喚醒 Web Audio、播 `start` 音效、開背景音樂（瀏覽器規定要有觸碰才能出聲）。設定可關（`fx.boot`），關掉時第一次觸碰畫面才開始放音樂。
- 焦點舞台（`stage.js`，簡報頁最上面）：全幅輪播，用固定規則挑 3～6 張（`buildSlides`）：進行中的 Steam 官方活動（附血條）→ 限時免費 → 傳說級好價 → 頭號消息（有圖的）→ 7 天內發售（Steam 期待榜有確切日期的）→ 熱銷新作。圖用 `media.json` 的 `hero`，沒有就用截圖、再沒有用商店橫幅加模糊底。7 秒換一張、Ken Burns 慢推、文字滑入；左右滑、點進度條、鍵盤左右鍵都能換；有暫停鈕；滑出畫面、打開情報卡、App 切到背景就暫停；減少動態效果時不自動換。停留 1.2 秒以上的那張才載預告短片（無聲循環）。
- 首頁貨架（`shelvesHTML`）：「寶箱：本週好價」「倒數發售」（3 週內、Steam 期待榜）「熱銷新作」，直式遊戲盒（`box` 封面，沒有就橫幅加模糊底），左右滑。
- 遊戲情報卡（`game.js`）：任何有 Steam appid 的地方（舞台、貨架、特價、願望清單、活動榜單、發行商特賣、期待榜、新作口碑、發售日曆、搜尋結果）點了都開這張卡，`gameModel()` 收集 App 裡關於它的一切：預告短片（自動、無聲）、完整預告（點了才播，有聲；iPhone 原生 HLS，其他瀏覽器載入 `site/vendor/hls.min.mjs`（hls.js 1.7.3，Apache-2.0）；播放時背景音樂停）、截圖（點了全螢幕左右滑）、台灣區價格與稀有度、全球評價環、繁中支援、正在出現在哪（活動、特賣、限免、願望清單、熱銷／期待榜）、發售日、開發發行、相關新聞（用搜尋的中英文名對照）、追蹤、加入行事曆、在 Steam 打開。沒有 appid 的（PS Store、Game Pass、App Store、對不到 Steam 的發售日曆）照舊直接連到來源。
- 魔王血條（「活動」頁進行中的官方活動）：血條＝活動剩下的時間比例（剛開始滿血、快結束見底），進場時從滿血掉到現在的血量；背景是參加遊戲的封面牆。第一次進活動頁播 `boss` 音效。季節特賣是金色血條。
- 小真：痞子葳的情報秘書，「簡報」分頁焦點舞台下面的簡報。內容用固定規則從當輪資料組出來（`brief.js` 的 `buildBrief`，不是 AI 生成）：頭號消息、Steam 活動、限時免費、好價、7 天內大作、追蹤關鍵字、濾網統計。可以用手機內建語音（speechSynthesis、zh-TW）播報，唸到哪一行就亮哪一行，播報時背景音樂自動壓低（`duck`）。
- 聲光：`sfx.js` 用 Web Audio 即時合成音效（不載音檔，有大廳殘響）並搭配震動（使用者碰過畫面後才震，`userActivation`）；`music.js` 是生成式背景音樂（Fmaj7–G6–Em7–Am9，墊音＋琶音＋貝斯＋閃光音，隔一輪出現主旋律），每個分頁有自己的氣氛（`setMood`：濾波器亮暗、琶音疏密），App 切到背景就暫停整個音效引擎。右上角喇叭三段：音效＋音樂／只有音效／靜音（`fr.sfx` 的 `on`、`music`）。`fx.js`：開場畫面、背景全像光塵（canvas，30fps）、爆閃粒子（`burst`）、白光、分頁左右滑入、全像光影、紫外線掃描、數字滾動、提示框（成就解鎖用 `achv` 樣式）。全部都能在「設定」關掉或切省電（省電＝不畫光塵粒子、不播影片、不做 Ken Burns 與轉場）；系統開了「減少動態效果」時一律不播；手機開了省數據不自動播影片。設定存在 localStorage（`fr.sfx`、`fr.fx`）。
- 共用小工具在 `site/kit.js`（時間格式、金額、圖示、`shot()` 取截圖尺寸、`bigImg()` 把 WordPress 縮圖換大圖），新模組都從這裡拿。新增 .js 模組要加進 `sw.js` 的 `SHELL_FILES`。
- 搜尋（右上放大鏡）：同時搜新聞、特價、Steam 活動、發售表，可以把關鍵字直接加到追蹤。中文名、英文名都找得到：`brief.js` 用 meta.json 的 `alias`（names.py 查到的官方中文名）＋發售日曆、Game Pass、願望清單自己的中英文名做對照，打「惡靈古堡」也會找到寫英文的 Resident Evil（系列名去掉結尾的代數也記一組）；英文名要整個字對上（CoD 不會對到 CODE VEIN）。小真簡報的「追蹤關鍵字」也是用同一個搜尋。
- 名稱整理（`build.py` 的 `clean_names`，輸出前統一做）：拿掉 ™ ® ©（MotoGP™23 → MotoGP 23），整個名稱被《》包住的去掉書名號。
- 更新紀錄（`site/updates.js`，最新的放最前面，id 用日期＋字母）：App 打開時有沒看過的更新就跳出來一次（`fr.updseen`），「設定」最下面可以看全部。有改東西才加一筆，寫給痞子葳看、白話、不寫技術細節。
- 「活動」頁：進行中的官方活動放最上面（魔王血條、時間、剩幾天、參加遊戲榜單），沒有進行中的就顯示下一場（倒數圓環）；再來是限時免費、今日特惠與首頁焦點、發行商／系列作特賣、官方活動時程（依月份）。時間一律顯示台灣時間。
- 被擋下的內容用紅色印章標理由。
- 手機常把 App 放在背景好幾小時：切回來超過 10 分鐘就當成新的一次查看（問候語、簡報、「新進」標記重算），資料超過 65 分鐘沒更新就自動重抓。問候語的時間一律用台灣時間，從 `formatToParts` 取「時」（中文格式會輸出「17時」，不能直接轉數字）。
- `app.js` 用 `?v=__BUILD__` 匯入其他模組；`build.py` 的 `copy_site` 會把所有 .js、.html 裡的 `__BUILD__` 換成這輪的 build id（`sw.js` 也是），改版後手機不會卡在舊檔。
