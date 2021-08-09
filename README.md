1. 元データ：https://cs50.jp/x/2021/week9/problem-set/finance/
1. APIキーを環境変数から取得するように変更する
    powershellの場合以下で一時的に環境変数を設定
    ```
    > $env:IEXAPIS_API_KEY = "<api_key>"
    ```
1. ローカル環境で起動できるようにする
1. ORM(SQLAlchemy)を導入する
    1. Session.executeで書き込み
    1. working with metadata
1. Herokuで稼働させる
1. HerokuのDBをPostgresSQLに切り替える
    1. postgressqlをherokuにデプロイ(アプリに紐づけてデプロイすると接続URLが自動でアプリの環境変数DATABASE＿URLに入る)
    ```
    heroku addons:create heroku-postgresql:hobby-dev -a <application_name>
    ```
    https://devcenter.heroku.com/ja/articles/heroku-postgresql
    
1. postgresSQLを利用できるようにアプリを書き換える

    1. DBを初期化する
    ```
    heroku run python -a <application_name>
    >>> from app import init_db
    >>> init_db()
    ```