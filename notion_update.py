import yfinance as yf
import time
from notion_client import Client
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os

load_dotenv()


class NotionSync:
    """Lightweight Notion helper for common DB operations.

    Usage:
      client = NotionSync()  # reads NOTION_TOKEN from env
      client.create_page(database_id, properties)
    """

    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("NOTION_TOKEN")
        if not token:
            raise ValueError("Missing NOTION_TOKEN environment variable")
        self.client = Client(auth=token)

    def query_database(self, datasource_id: str, **kwargs) -> Dict[str, Any]:
        return self.client.data_sources.query(data_source_id=datasource_id, **kwargs)

    def update_price(self, page_id, new_price):
        """更新 Current price 欄位"""
        self.client.pages.update(
            page_id=page_id,
            properties={"Current price": {"number": new_price}},
        )
        print(f"✅ 更新成功: ${new_price}")


def main():
    # 初始化
    syncer = NotionSync(NOTION_TOKEN)

    print("正在讀取 Notion 資料...")
    pages = syncer.query_database(DATASOURCE_ID)["results"]

    for page in pages:
        props = page["properties"]
        page_id = page["id"]

        # ---------------------------------------------------------
        # 1. 解析股票代號
        # 優先用 Ticker (title) — 通常存代號 (NVDA, GOOGL...)
        # fallback 才用 Stock name (rich_text) — 可能是公司全名
        # ---------------------------------------------------------
        stock_symbol = None
        try:
            title_list = props.get("Ticker", {}).get("title", [])
            if title_list:
                stock_symbol = title_list[0]["plain_text"].strip()

            if not stock_symbol:
                rich_text_list = props.get("Stock name", {}).get("rich_text", [])
                if rich_text_list:
                    stock_symbol = rich_text_list[0]["plain_text"].strip()

        except Exception as e:
            print(f"⚠️ 解析欄位錯誤: {e}")
            continue

        if not stock_symbol:
            print(f"⚠️ 跳過: 頁面 ID {page_id} 沒有股票代號")
            continue

        # ---------------------------------------------------------
        # 2. 用 yfinance 抓取股價
        # ---------------------------------------------------------
        print(f"🔍 正在查詢: {stock_symbol} ...", end=" ")

        try:
            ticker = yf.Ticker(stock_symbol)
            # 抓取最新收盤價
            hist = ticker.history(period="1d")

            if not hist.empty:
                current_price = round(hist["Close"].iloc[-1], 2)

                # -----------------------------------------------------
                # 3. 更新回 Notion (Current price)
                # -----------------------------------------------------
                syncer.update_price(page_id, current_price)
            else:
                print("❌ 找不到股價資料")

        except Exception as e:
            print(f"❌ {stock_symbol} 錯誤: {e}")

        # 避免請求過於頻繁
        time.sleep(0.5)


if __name__ == "__main__":
    # --- 設定區 ---
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    DATASOURCE_ID = os.getenv("DATASOURCE_ID")
    if not NOTION_TOKEN or not DATASOURCE_ID:
        # 如果變數沒有讀到，會提前報錯
        print(f"致命錯誤：無法讀取  環境變數。{NOTION_TOKEN} {DATASOURCE_ID}")
        exit(1)
    main()
