================================================================================
                    ケアハウス・ライブコネクト - システム説明書
================================================================================
バージョン: 1.3
更新日: 2026年6月
対象読者: 施設スタッフ、一般管理者、システム運用担当者
ファイル形式: プレーンテキスト（Readme仕様）

--------------------------------------------------------------------------------
1. システム概要と開発の目的
--------------------------------------------------------------------------------
『ケアハウス・ライブコネクト』は、シニア向け住宅や介護施設向けに開発された、専門
知識がなくても直感的に使えるデジタル見守りシステムです。

入居者様のプライバシーに配慮しながら「目に見えない安全の盾」として機能し、部屋の
安全環境や健康状態の自動見守りを行います。同時に、施設事務所とお部屋（入居者様）
の間をペーパーレスでダイレクトにつなぐ、簡単な連絡・アンケート機能を備えています。

--------------------------------------------------------------------------------
2. 各機能の詳細解説
--------------------------------------------------------------------------------

[A] プライバシーに配慮した「自動見守り機能」（センサー連携）
    - 目的：入居者様の私生活を邪魔することなく、部屋の安全と健康状態を記録します。
    - 仕組み：センサーが感知したデータを以下の名前のCSVファイルとして自動で読み込みます。
         * 「temp_hum.csv」  ：お部屋の温度と湿度を記録。
         * 「heart_rate.csv」：入居者様の心拍数（BPM）を記録。
    - 専門用語抜きの解説：
      壁のセンサーや身につける機器が、数秒ごとにお部屋の環境や心拍数を自動チェック
      します。もし「部屋が暑すぎる」「乾燥しすぎている」「心拍数が急上昇した」など
      の異常を検知すると、管理画面の色が変わり、スタッフへひと目で危険を知らせます。

[B] 事務所の司令塔（スタッフ用管理画面）
    - 目的：施設全体の「今」の状況を、ひとつの画面でまとめて管理します。
    - 主な機能：
         * お部屋状況一覧（マップ）：全室の入居状況やリアルタイムのセンサー数値を
           格子状のパネルで一覧表示します。
         * 入居者名簿管理：新しい入居者様を空き部屋へ割り当てたり、退去日の記録手続き
           をボタンひとつで行えます。
         * グラフ履歴：過去の体調や部屋の環境変化をきれいな折れ線グラフで表示。往診の
           お医者様やご家族へこれまでの推移を説明する際にも役立ちます。

[C] らくらく回覧板・アンケート（通信・連絡管理）
    - 目的：紙のプリント配りや、手書きのアンケート回収の手間を無くします。
    - 主な機能：
         * ターゲット配信：お知らせを入力し、名簿のチェックボックスにチェックを入れる
           だけで「特定の人」「いくつかの部屋」「全員」へ自由に送り分けることができます。
         * かんたん回答ボタン：調査（例：「明日の予防接種を希望しますか？」）の際、
           入居者様が画面をポンと叩くだけで答えられる「選択肢ボタン」を設置できます。
         * 誤送信防止機能：送信ボタンを押した際、「本当に送信しますか？」という確認の
           ポップアップが出るため、押し間違いによる誤配信を未然に防ぎます。

[D] AIおしゃべりパートナー（入居者様専用スペース）
    - 目的：孤独感の解消、お話し相手、日常のちょっとしたサポートを提供します。
    - 専門用語抜きの解説：
      お部屋のタッチパネルからいつでも呼び出せる、画面の中の「優しいお友達（AI）」
      です。寂しいときやお話ししたいときにメッセージを入力すると、AIが温かい言葉で
      相槌を打ったり、お部屋での快適な過ごし方をアドバイスしてくれるなど、いつでも
      入居者様に寄り添う会話の相手になります。

--------------------------------------------------------------------------------
3. 実際の業務の流れ（操作・動作フロー）
--------------------------------------------------------------------------------

流れ1：センサーデータが画面に表示されるまで
手順 1 -> お部屋のセンサーや機器が数値を計測します。
手順 2 -> 機器が「incoming_csv」フォルダへ生のデータを書き込みます。
          例（temp_hum.csvの場合）: "2026-06-05 15:50:11,26.8,54.6"
手順 3 -> システムがこのデータを3秒以内に自動で読み取って記録し、フォルダ内の
          古いファイルを消去して常にクリーンな状態を保ちます。
手順 4 -> お部屋の確認画面に、最新の数値（26.8°C / 54.6%）が即座に反映されます。

流れ2：アンケートの一斉配信から回収まで
手順 1 -> スタッフが管理画面の「通信・連絡管理」を開きます。
手順 2 -> 対象者のチェックボックスにチェックを入れ、質問内容と、入居者様が選ぶ
          「はい」「いいえ」などのボタン項目を入力します。
手順 3 -> 送信ボタンを押し、確認画面で許可すると、スタッフ画面に「送信完了」の
          緑色の案内メッセージが表示されます。
手順 4 -> 対象のお部屋の画面に、ピコピコと点滅する赤い丸（🔴）の合図が現れます。
手順 5 -> 入居者様が合図をタップして内容を読み、ボタンをポンと押して回答します。
手順 6 -> 回答すると画面が自動で「送信済み」にロックされ（押し間違いや二重送信を防ぐ）、
          事務所の管理画面へリアルタイムに回答結果（ステータス）が届きます。

--------------------------------------------------------------------------------
4. デザインのこだわり（使いやすさへの配慮）
--------------------------------------------------------------------------------
- 見やすい文字と大きなボタン：高齢の入居者様でも読みやすいよう文字を大きくし、
  操作するボタンは指でタップしやすいよう大きくて押しやすい形にしています。
- 間違いを防ぐ安心ロック：アンケートに一度回答すると、選択ボタンは消えて「事務所へ
  送信しました」という緑色のチェックマークに変わります。これにより、「本当に送れた
  かしら？」という不安や、何度も同じボタンを押してしまう混乱をなくします。
- 消えるまで残るお知らせ：スタッフ画面の「送信完了」などの案内メッセージは、右端の
  （×）ボタンを押すまで画面の上部に残り続けるため、重要なステータス通知を見逃す
  心配がありません。
================================================================================




================================================================================
                    CAREHOUSE LIVE CONNECT - SYSTEM DOCUMENTATION
================================================================================
Version: 1.3
Date: June 2026
Target Audience: Facility Staff, General Operators, and System Managers
File Format: Plain Text Readme Specification

--------------------------------------------------------------------------------
1. SYSTEM OVERVIEW & CORE PURPOSE
--------------------------------------------------------------------------------
Carehouse Live Connect is a non-technical, user-friendly digital ecosystem 
designed for assisted living facilities and senior housing. The platform acts 
as an invisible protective shield—monitoring resident vitals and room safety—
while opening up a direct, simplified paperless communication matrix between 
the facility front office, physical rooms, and residents.

--------------------------------------------------------------------------------
2. COMPREHENSIVE COMPONENT BREAKDOWN
--------------------------------------------------------------------------------

[A] AUTOMATED PRIVACY-FIRST見守り (SAFETY MONITORING)
    - Purpose: Tracks critical safety metrics without invading resident privacy.
    - Raw Inputs: Reads simple, headerless text logs directly from hardware.
         * "temp_hum.csv" tracks ambient room temperatures and humidity percentages.
         * "heart_rate.csv" tracks resident cardiovascular vitals (BPM).
    - Non-IT Explanation: The system automatically samples data from subtle wall 
      sensors and smart wearables every few seconds. If an entry records a room 
      that is dangerously hot, too dry, or a heart rate that spikes too high, 
      the interface visually shifts to highlight the risk immediately.

[B] STAFF COMMAND CENTER (ADMIN DASHBOARD)
    - Purpose: Provides a centralized management portal for facility staff.
    - Key Sub-Features:
         * Room Directory Grid: A single-screen visual map showing occupancy 
           and live sensor readings across all rooms.
         * Resident Roster Manager: Simplifies checking new residents into empty 
           rooms and logging discharge dates cleanly.
         * Trend Log History: Draws clear historical line charts over past days, 
           making it easy to print or show medical professionals health trends.

[C] THE COMMUNICATION MATRIX (DIGITAL NOTICE BOARD & SURVEYS)
    - Purpose: Replaces paper handouts, clipboards, and manual surveys.
    - Key Sub-Features:
         * Targeted Broadcast: Staff can write one announcement and check custom 
           boxes to send it to 1 person, a specific group of rooms, or everyone.
         * Interactive Choice Buttons: For survey queries (e.g., "Do you want 
           tomorrow's vaccine?"), staff can install dynamic touch buttons.
         * Action Confirmation: Features built-in safety prompts ("Are you sure 
           you want to send?") to completely prevent accidental mass-clicks.

[D] AI COMPANION PARTNER (RESIDENT INTERACTIVE SPACE)
    - Purpose: Provides companionship, chat capabilities, and lifestyle support.
    - Non-IT Explanation: A friendly, virtual companion space accessible right 
      from the resident's touch screen. It provides a warm conversational outlet 
      to combat social isolation. Residents can type messages, chat naturally, 
      and receive immediate empathetic conversation or practical environmental 
      comfort advice.

--------------------------------------------------------------------------------
3. OPERATIONAL WORKFLOWS (HOW IT WORKS IN PRACTICE)
--------------------------------------------------------------------------------

WORKFLOW 1: BIOMETRIC & CLIMATE DATA INGESTION
Step 1 -> Wireless room hardware registers a reading.
Step 2 -> The hardware writes a basic raw line to the 'incoming_csv' folder.
          Example (temp_hum.csv): "2026-06-05 15:50:11,26.8,54.6"
Step 3 -> The app background thread reads the line, records it, and deletes the 
          temporary file within 3 seconds to keep things clean.
Step 4 -> The room dashboard page instantly displays the fresh information.

WORKFLOW 2: RELEASING A GROUP SURVEY & TRACKING RESPONSES
Step 1 -> Staff navigate to the Communication Center in the administration panel.
Step 2 -> Staff check specific names from a list of checkboxes and choose a response 
          type (e.g., creating tap buttons for "Yes, Please" or "No, Thank you").
Step 3 -> Staff click send, confirm the popup warning, and a floating success 
          confirmation banner appears on their dashboard.
Step 4 -> A blinking red dot alert (🔴) appears instantly on the target residents' 
          screens to guide their attention.
Step 5 -> The resident clicks the notification, reads the note, and taps their choice.
Step 6 -> The system immediately locks the page (preventing duplicates or errors) and 
          transfers the answer live back to the staff's administrative status tracker.

--------------------------------------------------------------------------------
4. DESIGN PHILOSOPHY
--------------------------------------------------------------------------------
- High Contrast Text & Large Interactive Elements: Built to accommodate older 
  adults, text inputs use large typography, and actionable elements are designed 
  as large, easy-to-tap touch blocks.
- One-Way Input Locking: Once a resident submits a response, the options hide 
  and turn into a green confirmation token. This layout naturally prevents 
  accidental double-submitting or confusion over whether a response went through.
- Closeable Flash Banners: Administrative warning banners stay anchored on-screen 
  until explicitly closed by clicking the (X) icon, ensuring critical status 
  updates are never missed.
================================================================================