# Python 與 PostgreSQL 學習專案

## 專案概述
開發一個簡易的命令列介面 (CLI) 應用程式，讓初學者能夠學習如何使用 Python 連接 PostgreSQL 資料庫並進行基本操作。

## 目標受眾
- 沒有 Python 程式設計基礎的初學者
- 對資料庫操作有興趣的學生

## 技術需求
1. **程式語言**: Python 3.x
2. **資料庫**: PostgreSQL
3. **連接庫**: psycopg2
4. **資料來源**:
   - 台鐵車站資訊表 (`台鐵車站資訊`)
   - 每日各站進出站人數表 (`每日各站進出站人數`)
5. **資料庫連接**: 使用 MCP 的 vscode_postgres server

## 功能需求
1. 建立一個命令列介面 (CLI) 程式
2. 實現基本的資料庫連接功能
3. 提供簡單的查詢功能，如:
   - 查詢特定地區的車站資訊
   - 查詢特定日期的進出站人數
   - 基本的資料統計和分析

## 教學設計
1. **分階段學習**: 將專案分解為多個漸進式學習步驟
2. **每個步驟包含**:
   - 明確的學習目標
   - 詳細的程式碼說明
   - 關鍵概念解釋
   - 實作練習
3. **文件格式**: 每個步驟建立獨立的 Markdown 文件，包含:
   - 步驟標題和學習重點
   - 程式碼片段及詳細註解
   - 執行結果示例
   - 練習題和延伸閱讀

## 複雜度控制
- 避免使用進階 Python 特性
- 簡化 SQL 查詢語句
- 提供清晰的程式碼註解
- 循序漸進增加功能複雜度

## 預期成果
學生能夠理解並實作一個簡單的 Python 應用程式，連接 PostgreSQL 資料庫並執行基本的資料查詢和分析操作。

