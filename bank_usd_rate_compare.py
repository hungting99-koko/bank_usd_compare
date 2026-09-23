# 比較中國信託/兆豐/永豐/台新/富邦銀行的美金即時買入匯率
import datetime
import json
import re

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="美金匯率比較", layout="wide")

FINDRATE_URL = "https://www.findrate.tw/USD/"

# 顯示名稱 -> 比對關鍵字（用於在牌告匯率表中找出對應銀行）及官網查詢連結（供資料缺漏時使用）
BANKS = {
    "中國信託 CTBC": {
        "keywords": ["中國信託"],
        "official_url": "https://www.ctbcbank.com/twrbo/zh_tw/dep_index/dep_ratequery/dep_foreign_rates.html",
    },
    "兆豐銀行 Mega Bank": {
        "keywords": ["兆豐"],
        "official_url": "https://www.megabank.com.tw/",
    },
    "永豐銀行 SinoPac": {
        "keywords": ["永豐"],
        "official_url": "https://bank.sinopac.com/",
    },
    "台新銀行 Taishin": {
        "keywords": ["台新銀行"],
        "official_url": "https://www.taishinbank.com.tw/",
    },
    "富邦銀行 Fubon": {
        "keywords": ["富邦"],
        "official_url": "https://www.fubon.com/banking/",
    },
    "LINE Bank 連線銀行": {
        "keywords": ["LINE Bank", "連線銀行"],
        "official_url": "https://www.linebank.com.tw/board-rate/exchange-rate",
    },
    "將來銀行 Next Bank": {
        "keywords": ["將來銀行"],
        "official_url": "https://www.nextbank.com.tw/exchange-rates",
    },
}

# 銀行提供的「讓分」優惠，單位為分（1分 = 0.01元），會從牌告賣出價中扣除
DEFAULT_DISCOUNT_POINTS = {
    "中國信託 CTBC": 4.0,
    "富邦銀行 Fubon": 3.0,
    "兆豐銀行 Mega Bank": 3.0,
    "台新銀行 Taishin": 3.1,
}

# 賣出美金時的「讓分」優惠，單位為分，會加到牌告買入價上
DEFAULT_SELL_DISCOUNT_POINTS = {
    "中國信託 CTBC": 0.0,
    "富邦銀行 Fubon": 3.0,
    "兆豐銀行 Mega Bank": 3.0,
    "台新銀行 Taishin": 0.0,
}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usd_rate_table() -> pd.DataFrame:
    """向「比率網 findrate.tw」抓取各銀行美金牌告匯率彙整表。"""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(FINDRATE_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for tr in soup.select("table tr"):
        bank_cell = tr.select_one("td.bank")
        if not bank_cell:
            continue
        cells = tr.select("td.WordB")
        if len(cells) < 6:
            continue
        rows.append(
            {
                "銀行": bank_cell.get_text(strip=True),
                "即期買入": cells[2].get_text(strip=True),
                "即期賣出": cells[3].get_text(strip=True),
                "更新時間": cells[4].get_text(strip=True),
            }
        )
    return pd.DataFrame(rows)


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_linebank_rate():
    """LINE Bank 匯率查詢頁為伺服器端渲染，直接爬取表格即可取得即期匯率。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    resp = requests.get("https://www.linebank.com.tw/board-rate/exchange-rate", headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) == 3 and "美元" in cells[0].get_text():
            buy = to_float(cells[1].get_text(strip=True))
            sell = to_float(cells[2].get_text(strip=True))
            if buy is not None and sell is not None:
                return {"即期買入": buy, "即期賣出": sell}
    return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_nextbank_rate():
    """呼叫將來銀行牌告匯率頁背後所使用的公開匯率 API（路徑本身標示為 open，非登入會員限定）。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nextbank.com.tw/",
    }
    resp = requests.post(
        "https://api.nextbank.com.tw/ap6/open/forex/v1.0/GetFXRate", headers=headers, timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("data", {}).get("currencyList", []):
        if item.get("currency") == "USD":
            rates = [to_float(item.get("buyRate")), to_float(item.get("sellRate"))]
            rates = [r for r in rates if r is not None]
            if len(rates) == 2:
                # API 的 buyRate/sellRate 命名與畫面欄位相反，以數值大小對應「賣出恆高於買入」還原
                return {"即期買入": min(rates), "即期賣出": max(rates)}
    return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_megabank_rate():
    """兆豐銀行官網匯率頁背後所使用的公開 REST API，直接回傳各幣別即期買賣價。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    resp = requests.get(
        "https://www.megabank.com.tw/api/client/ExchangeRate/GetRateData",
        params={"sc_lang": "zh-TW", "sc_site": "bank-zh-tw", "dic_lang": "zh-TW"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("rates", []):
        if item.get("currKey", "").split("|")[0] == "USD":
            spot = item.get("spot", {})
            buy = to_float(spot.get("bid"))
            sell = to_float(spot.get("ask"))
            if buy is not None and sell is not None:
                return {"即期買入": buy, "即期賣出": sell}
    return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_sinopac_rate():
    """永豐銀行官網即期匯率查詢所使用的公開 JSONP API（回應包在 genREMITResult(...) 中）。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    resp = requests.get(
        "https://mma.sinopac.com/ws/share/rate/ws_exchange.ashx",
        params={"exchangeType": "REMIT", "Cross": "genREMITResult", "callback": "genREMITResult"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    match = re.search(r"genREMITResult\((.*)\);?\s*$", resp.text.strip(), re.S)
    if not match:
        return None
    data = json.loads(match.group(1))
    for item in data[0].get("SubInfo", []):
        if item.get("DataValue4") == "USD":
            buy = to_float(item.get("DataValue2"))
            sell = to_float(item.get("DataValue3"))
            if buy is not None and sell is not None:
                return {"即期買入": buy, "即期賣出": sell}
    return None


# 銀行顯示名稱 -> 直接抓取官網/公開 API 的函式（優先於 findrate.tw 彙整表使用）
DIRECT_FETCHERS = {
    "LINE Bank 連線銀行": fetch_linebank_rate,
    "將來銀行 Next Bank": fetch_nextbank_rate,
    "兆豐銀行 Mega Bank": fetch_megabank_rate,
    "永豐銀行 SinoPac": fetch_sinopac_rate,
}


def build_bank_table(all_rates: pd.DataFrame) -> pd.DataFrame:
    records = []
    for display_name, meta in BANKS.items():
        fetcher = DIRECT_FETCHERS.get(display_name)
        if fetcher:
            try:
                fetched = fetcher()
            except Exception:
                fetched = None
            if fetched:
                records.append(
                    {
                        "銀行": display_name,
                        "即期買入": fetched["即期買入"],
                        "即期賣出": fetched["即期賣出"],
                        "更新時間": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "資料狀態": "✅ 即時",
                        "官網連結": meta["official_url"],
                    }
                )
                continue

        match = all_rates[
            all_rates["銀行"].apply(lambda name: any(kw in name for kw in meta["keywords"]))
        ]
        if not match.empty:
            row = match.iloc[0]
            records.append(
                {
                    "銀行": display_name,
                    "即期買入": to_float(row["即期買入"]),
                    "即期賣出": to_float(row["即期賣出"]),
                    "更新時間": row["更新時間"],
                    "資料狀態": "✅ 即時",
                    "官網連結": meta["official_url"],
                }
            )
        else:
            records.append(
                {
                    "銀行": display_name,
                    "即期買入": None,
                    "即期賣出": None,
                    "更新時間": "-",
                    "資料狀態": "⚠️ 暫無資料",
                    "官網連結": meta["official_url"],
                }
            )
    return pd.DataFrame(records)


def main():
    st.title("💵 各銀行美金買賣匯率比較")
    st.caption(
        "資料來源：比率網 findrate.tw（彙整各銀行牌告匯率），僅供參考，實際交易匯率請以各銀行當下公告為準。"
    )

    if st.button("🔄 重新整理即時匯率"):
        fetch_usd_rate_table.clear()

    try:
        all_rates = fetch_usd_rate_table()
    except Exception as e:
        st.error(f"無法取得即時匯率資料：{e}")
        return

    df = build_bank_table(all_rates)

    missing_banks = df.loc[df["資料狀態"] != "✅ 即時", "銀行"].tolist()
    if missing_banks:
        st.markdown("### ✍️ 手動輸入匯率（自動抓取失敗的銀行）")
        st.caption("這些銀行的網站有防自動爬蟲保護，請點選下方連結至官網查詢後，手動填入匯率。")
        for display_name in missing_banks:
            official_url = BANKS[display_name]["official_url"]
            col_link, col1, col2 = st.columns([2, 1, 1])
            col_link.markdown(f"**{display_name}**  \n[🔗 前往官網查詢即時匯率]({official_url})")
            spot_buy = col1.number_input(
                "即期買入", min_value=0.0, step=0.001, format="%.4f", key=f"manual_{display_name}_spot_buy"
            )
            spot_sell = col2.number_input(
                "即期賣出", min_value=0.0, step=0.001, format="%.4f", key=f"manual_{display_name}_spot_sell"
            )
            manual_values = {
                "即期買入": spot_buy or None,
                "即期賣出": spot_sell or None,
            }
            if any(manual_values.values()):
                idx = df.index[df["銀行"] == display_name][0]
                for col_name, val in manual_values.items():
                    if val:
                        df.at[idx, col_name] = val
                df.at[idx, "資料狀態"] = "✍️ 手動輸入"

    with st.expander("⚙️ 讓分設定（銀行從賣出價再折讓的優惠，單位：分，1分=0.01元）", expanded=True):
        discount_points = {}
        cols = st.columns(len(BANKS))
        for col, display_name in zip(cols, BANKS):
            default = DEFAULT_DISCOUNT_POINTS.get(display_name, 0.0)
            discount_points[display_name] = col.number_input(
                display_name, min_value=0.0, step=0.1, value=default, key=f"discount_{display_name}"
            )

    df["讓分(分)"] = df["銀行"].map(discount_points).fillna(0.0)
    df["我們的買入成本"] = df.apply(
        lambda r: r["即期賣出"] - r["讓分(分)"] / 100 if pd.notna(r["即期賣出"]) else None, axis=1
    )

    st.subheader("🛒 我們買美金（換匯支出）")
    st.markdown("我們買入美金時適用即期賣出價，扣除讓分後的我們的買入成本數字越低表示換匯越划算。")

    buy_display_df = df[
        ["銀行", "即期賣出", "讓分(分)", "我們的買入成本", "更新時間", "資料狀態", "官網連結"]
    ]
    buy_sorted_df = buy_display_df.sort_values("我們的買入成本", na_position="last")
    buy_price_cols = ["即期賣出", "我們的買入成本"]

    st.caption("網站資料可能有延遲，建議點選「官網連結」欄位以官網當下公告的匯率為準。")
    st.dataframe(
        buy_sorted_df.style.format({col: "{:.4f}" for col in buy_price_cols}, na_rep="-").highlight_min(
            subset=["我們的買入成本"], color="#c6f6c6"
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "官網連結": st.column_config.LinkColumn("官網連結", display_text="🔗 前往查詢"),
        },
    )

    st.subheader("💰 我們賣美金（換匯收入）")
    st.markdown("我們賣出美金時適用即期買入價，加上讓分後的我們的賣出收入數字越高表示拿到的台幣越多。")

    with st.expander("⚙️ 賣出讓分設定（銀行在牌告買入價上加碼的優惠，單位：分，1分=0.01元）", expanded=True):
        sell_discount_points = {}
        sell_cols = st.columns(len(BANKS))
        for col, display_name in zip(sell_cols, BANKS):
            default = DEFAULT_SELL_DISCOUNT_POINTS.get(display_name, 0.0)
            sell_discount_points[display_name] = col.number_input(
                display_name, min_value=0.0, step=0.1, value=default, key=f"sell_discount_{display_name}"
            )

    df["賣出讓分(分)"] = df["銀行"].map(sell_discount_points).fillna(0.0)
    df["我們的賣出收入"] = df.apply(
        lambda r: r["即期買入"] + r["賣出讓分(分)"] / 100 if pd.notna(r["即期買入"]) else None, axis=1
    )

    sell_display_df = df[
        ["銀行", "即期買入", "賣出讓分(分)", "我們的賣出收入", "更新時間", "資料狀態", "官網連結"]
    ]
    sell_sorted_df = sell_display_df.sort_values("我們的賣出收入", ascending=False, na_position="last")
    sell_price_cols = ["即期買入", "我們的賣出收入"]

    st.dataframe(
        sell_sorted_df.style.format({col: "{:.4f}" for col in sell_price_cols}, na_rep="-").highlight_max(
            subset=["我們的賣出收入"], color="#c6f6c6"
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "官網連結": st.column_config.LinkColumn("官網連結", display_text="🔗 前往查詢"),
        },
    )

    st.caption(f"頁面產生時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
