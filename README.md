# 偏旁組字輪盤

遊戲會顯示中央部件，只有一個方向的偏旁輪盤會亮起。亮起的方向就是偏旁在成字後的相對位置，例如「十 + 口」只能是口在下方的「古」，不會被出成右方。題庫包含橋、樹、媽、雷等複雜組字。轉動滑鼠滾輪選擇偏旁後按「確認答案」；答對即開啟教育部《重編國語辭典修訂本》的精確詞條。

## 產生題庫（爬蟲）

最簡單的方式是在 PowerShell 執行下列檔案；它會詢問要建立幾題：

```powershell
.\run_crawler.ps1
```

也可以直接指定數量：

```powershell
cd C:\Users\tonyl\Documents\Codex\2026-06-21\new-chat\outputs\hanzi-radical-wheel
python -m pip install -r requirements.txt
python scrape_dictionary.py --limit 80
```

爬蟲沒有固定題庫。它會實際爬取教育部辭典的「部首索引」取得候選單字，並逐一搜尋官方詞條取得精確網址。接著會下載 IDS 漢字構形資料，自動判讀字形最外層的左右或上下關係，再輸出 `questions.json`。

```powershell
# 從各筆畫的官方部首中抽樣 24 個索引，建立至少三構件的 60 題
python scrape_dictionary.py

# 完整掃描所有部首索引（耗時較久，請只在必要時使用）
python scrape_dictionary.py --max-radicals 0 --limit 300
```

每次對教育部網站的請求至少間隔 1.2 秒；請以少量、教育用途執行，勿移除限速或批量高頻抓取。IDS 資料僅用於判斷字形的相對位置；題目目標字與跳轉詞條均由教育部網站本次爬得。

預設會略過生僻字：答案必須同時存在於教育部《國語辭典簡編本》、總筆畫不超過 18，且中央部件與偏旁也必須是常見字或常用部首。若希望題庫也包含較生僻、但存在於《重編國語辭典修訂本》的字，使用：

```powershell
python scrape_dictionary.py --limit 80 --allow-rare
```

互動式的 `run_crawler.ps1` 也會直接詢問是否接受生僻字。

## 啟動

遊戲沒有內建題庫；請先產生 `questions.json`，然後在此資料夾啟動本機伺服器讓瀏覽器讀取題庫：

```powershell
python -m http.server 8000
```

然後開啟 `http://localhost:8000`。
