# 峻爸 KTV 多文字軌核對器 v1.0

這是一支**完全獨立**的 Windows 10/11 桌面程式，和「峻爸 AI Transcriber」分開維護、分開 GitHub 封裝；不修改原轉錄程式，也不依賴原程式才能使用。

## 用途

把「錄音檔 + 一份或多份文字/字幕」變成可播放、可核對、可學習的 KTV 式多文字軌介面。

### 可讀文字來源
- SRT / VTT：保留原始時間碼，核對最準。
- TXT：可讀 `[00:00:10]` 或 `00:00:10 --> 00:00:15`；純文字則做估算對齊。
- JSON：支援 `segments/start/end/text/speaker` 常見結構。
- CSV：支援 start/end/speaker/text 常見欄位。
- DOCX：可讀「時間｜講者｜逐字內容」表格，也能讀一般 Word 純文字。
- HTML：可重新讀入本程式匯出的 HTML；一般 HTML 則當純文字處理。

### KTV 核對
- 上方「完整全文」會跟錄音同步反白。
- 有精準時間碼時依 segment 同步。
- 沒有時間碼的翻譯/整理稿可依基準時間軸估算對齊，畫面會標示「估算」。
- 下方時間軸可同時顯示兩個文字軌，例如「原始逐字稿 + 中文翻譯」。
- 雙擊時間軸任一列，可直接跳到錄音位置。
- 支援 ±5 秒、0.75x～2.0x 播放速度。

### 外部使用
- 可把本程式或其他軟體產生的逐字稿/翻譯稿載入。
- 可匯出目前文字軌成 SRT / VTT。
- 可輸出「離線 KTV 網頁包」：HTML + 音訊 + VTT，拿到別台電腦也能用瀏覽器核對。
- 可儲存 `.jktv` 專案，保留多文字軌及對齊結果。

## 重要說明
這支程式的定位是「**轉錄結果核對 / 多文字軌學習 / 字幕校對**」，不是語音辨識引擎。因此不會動到原本峻爸 AI Transcriber 的 Whisper / Gemini / NPU / GPU 規劃。

## GitHub 封裝
Workflow：`.github/workflows/build-windows-v1.0.yml`

成功後會得到：
- `Junba-KTV-MultiTrack-v1.0-Portable-Windows-x64`
- `Junba-KTV-MultiTrack-v1.0-Single-EXE-Windows-x64`
