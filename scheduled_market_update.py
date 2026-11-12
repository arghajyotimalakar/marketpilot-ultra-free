"""Free scheduled snapshots for MarketPilot. Runs on GitHub Actions; no paid APIs.
Daily observations are NOT licensed real-time exchange quotes.
"""
import json, os, time, io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import feedparser

ROOT=Path(__file__).parent
DATA=ROOT/"data"
DATA.mkdir(exist_ok=True)
NOW=datetime.now(ZoneInfo("Asia/Kolkata"))
DATE=NOW.strftime("%Y-%m-%d")
STAMP=NOW.isoformat(timespec="seconds")
PREVIOUS=DATA/"latest.json"
HEADERS={"User-Agent":"Mozilla/5.0 MarketPilot educational market research"}
SOURCE="Yahoo Finance unofficial feed; may be delayed, rate-limited or unavailable"
def finite(x):
    try:
        v=float(x)
        return round(v,4) if np.isfinite(v) else None
    except Exception:return None
def download_batch(tickers,period="3mo"):
    try:
        return yf.download(tickers,period=period,interval="1d",auto_adjust=True,group_by="ticker",threads=True,progress=False,timeout=20)
    except Exception:return pd.DataFrame()
def series(data,symbol):
    try:
        a=data[symbol] if isinstance(data.columns,pd.MultiIndex) else data
        return a.dropna(subset=["Close"])
    except Exception:return pd.DataFrame()
def directory():
    paths=["https://archives.nseindia.com/content/equities/EQUITY_L.csv",
           "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"]
    for url in paths:
        try:
            req=requests.get(url,headers=HEADERS,timeout=18);req.raise_for_status()
            df=pd.read_csv(io.BytesIO(req.content));df.columns=[str(x).strip().lower() for x in df.columns]
            symbol=next((x for x in ("symbol","nse symbol") if x in df.columns),None)
            company=next((x for x in ("name of company","company name","company") if x in df.columns),None)
            if not symbol or not company:continue
            df=df[[symbol,company]].dropna().astype(str)
            df.columns=["symbol","company"]
            df["symbol"]=df.symbol.str.strip().str.upper()
            df=df[df.symbol.str.fullmatch(r"[A-Z0-9&._-]{1,30}",na=False)].drop_duplicates("symbol")
            if len(df)>=300:return dict(zip(df.symbol,df.company)),url
        except Exception:continue
    if PREVIOUS.exists():
        try:
            old=json.loads(PREVIOUS.read_text())
            return {x["symbol"]:x["company"] for x in old.get("stocks",[]) if x.get("company")},"previous snapshot symbols (NSE download unavailable)"
        except Exception:pass
    return {},"unavailable"
def news():
    feeds={
      "Economic Times Markets":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
      "Mint Markets":"https://www.livemint.com/rss/markets"
    }
    out=[]
    for source,url in feeds.items():
        try:
            feed=feedparser.parse(url)
            for x in feed.entries[:40]:
                h=str(x.get("title","")).strip()
                if h:out.append({"title":h,"url":str(x.get("link",url)),"published":str(x.get("published","unknown")),"source":source})
        except Exception:pass
    return out[:70]
def matched_news(symbol,company,items):
    terms=[symbol.lower()]
    clean=str(company).lower()
    if len(clean)>8:terms.append(clean)
    words=[w for w in clean.replace(" limited","").replace(" ltd","").split() if len(w)>=5 and w not in ("industries","international","company","india","corporation")]
    terms+=words[:1]
    return [item for item in items if any(t in item["title"].lower() for t in terms)][:3]
def indicators(p,ref):
    close=p["Close"].astype(float)
    if len(close)<55:return {}
    c=float(close.iloc[-1]);prev=float(close.iloc[-2])
    e20=close.ewm(span=20,adjust=False).mean().iloc[-1]
    e50=close.ewm(span=50,adjust=False).mean().iloc[-1]
    e200=close.ewm(span=200,adjust=False).mean().iloc[-1] if len(close)>=200 else np.nan
    diff=close.diff()
    g=diff.clip(lower=0).ewm(alpha=1/14,adjust=False).mean().iloc[-1]
    loss=(-diff.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean().iloc[-1]
    rsi=100 if loss==0 and g>0 else (100-100/(1+g/loss) if loss else np.nan)
    tr=pd.concat([p.High-p.Low,(p.High-close.shift()).abs(),(p.Low-close.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.ewm(alpha=1/14,adjust=False).mean().iloc[-1])
    vol=float(p.Volume.iloc[-1]);refvol=float(p.Volume.iloc[-21:-1].mean()) if len(close)>21 else np.nan
    rvol=vol/refvol if refvol>0 else np.nan
    ret20=c/float(close.iloc[-21])-1
    benchmark=ref.get("returns",[])
    alpha20=None
    if len(benchmark)>=21:
        alpha20=finite((ret20-(benchmark[-1]/benchmark[-21]-1))*100)
    score=sum([c>e20,e20>e50,c>e50, rsi>50,ret20>0,rvol>1.1])
    change=(c/prev-1)*100
    return {"close":finite(c),"daily_change_pct":finite(change),"return_20d_pct":finite(ret20*100),
            "alpha_20d_pct":alpha20,"rsi14":finite(rsi),"atr14":finite(atr),
            "ema20":finite(e20),"ema50":finite(e50),"ema200":finite(e200),
            "relative_volume":finite(rvol),"turnover_crore":finite(c*vol/1e7),
            "trend_score":int(score/6*100),"direction":"green" if change>0 else "red" if change<0 else "flat",
            "last_price_bar":str(p.index[-1]),"entry_reference":finite(float(p.High.iloc[-1])*1.002),
            "stop_reference":finite(float(p.High.iloc[-1])*1.002-1.5*atr),
            "target_1_reference":finite(float(p.High.iloc[-1])*1.002+2.25*atr)}
def fundamentals(ticker):
    try:
        info=yf.Ticker(ticker).info
        return {
            "pe":finite(info.get("trailingPE")),"forward_pe":finite(info.get("forwardPE")),
            "pb":finite(info.get("priceToBook")),"roe":finite(info.get("returnOnEquity")),
            "debt_to_equity":finite(info.get("debtToEquity")),
            "revenue_growth":finite(info.get("revenueGrowth")),
            "free_cashflow":finite(info.get("freeCashflow")),
            "beta":finite(info.get("beta"))
        }
    except Exception:return {}
def run():
    old={}
    if PREVIOUS.exists():
        try:old=json.loads(PREVIOUS.read_text())
        except Exception:pass
    universe,universe_source=directory()
    existing={x["symbol"]:x for x in old.get("stocks",[]) if isinstance(x,dict) and x.get("symbol")}
    stocks=dict(existing)
    all_symbols=list(universe)
    max_symbols=min(int(os.environ.get("MAX_SYMBOLS_PER_RUN","125")),200)
    slots=[all_symbols[i:i+max_symbols] for i in range(0,len(all_symbols),max_symbols)]
    # Rotates batches between snapshots to limit rate limiting; updated quote ages are displayed.
    slot=(int(NOW.strftime("%j"))*7+int(NOW.hour)*3+int(NOW.minute)//30)%len(slots) if slots else 0
    selection=slots[slot] if slots else []
    benchmark=download_batch(["^NSEI","^GSPC","BZ=F","GC=F","SI=F","INR=X"],"3mo")
    indices={}
    for ticker in ["^NSEI","^GSPC","BZ=F","GC=F","SI=F","INR=X"]:
        p=series(benchmark,ticker)
        if len(p)>1:
            vals=p.Close.astype(float)
            indices[ticker]={"close":finite(vals.iloc[-1]),"daily_change_pct":finite((vals.iloc[-1]/vals.iloc[-2]-1)*100),
                             "last_price_bar":str(vals.index[-1])}
    nifty=series(benchmark,"^NSEI")
    ref={"returns":nifty.Close.astype(float).tolist() if len(nifty)>21 else []}
    for offset in range(0,len(selection),25):
        part=selection[offset:offset+25]
        batch=download_batch([x+".NS" for x in part],"1y")
        for sym in part:
            p=series(batch,sym+".NS")
            if len(p)<55:continue
            computed=indicators(p,ref)
            if not computed:continue
            prior=stocks.get(sym,{})
            stocks[sym]={"symbol":sym,"company":universe.get(sym,prior.get("company",sym)),
                         **computed,"last_checked_at_ist":STAMP,
                         "fundamentals":prior.get("fundamentals",{}),
                         "fundamentals_asof":prior.get("fundamentals_asof")}
        time.sleep(1.0)
    # Fundamental info is very often unavailable on free endpoints. Only refresh a small rotating sample.
    candidates=[x for x in selection if x in stocks and stocks[x].get("turnover_crore") is not None]
    candidates.sort(key=lambda x:stocks[x].get("turnover_crore") or 0,reverse=True)
    for sym in candidates[:min(6,len(candidates))]:
        details=fundamentals(sym+".NS")
        if any(v is not None for v in details.values()):
            stocks[sym]["fundamentals"]=details
            stocks[sym]["fundamentals_asof"]=STAMP
        time.sleep(0.35)
    headlines=news()
    news_by_symbol={}
    sorted_stocks=sorted(stocks.values(),key=lambda x:x.get("turnover_crore") or 0,reverse=True)
    for row in sorted_stocks[:250]:
        matches=matched_news(row["symbol"],row.get("company",""),headlines)
        if matches:news_by_symbol[row["symbol"]]=matches
    green=sum(1 for r in stocks.values() if r.get("direction")=="green" and r.get("last_checked_at_ist")==STAMP)
    red=sum(1 for r in stocks.values() if r.get("direction")=="red" and r.get("last_checked_at_ist")==STAMP)
    trend_pos=sum(1 for r in stocks.values() if r.get("trend_score",0)>=66 and r.get("last_checked_at_ist")==STAMP)
    total=green+red
    outlook="Uncertain: insufficient fresh breadth data."
    if total>=15:
        outlook=("Conditional bullish bias: more fresh stocks rising than falling. Watch for confirmation next session." if green/total>.6 and trend_pos/total>.4 else
                 "Conditional defensive bias: more fresh stocks falling than rising. Watch for volatility next session." if red/total>.6 else
                 "Mixed breadth: look for confirmation rather than a directional bet.")
    record={
        "generated_at_ist":STAMP,"market_date_ist":DATE,"source":SOURCE,
        "universe_source":universe_source,"directory_count":len(universe),
        "run_symbol_count":len(selection),"symbols_with_record":len(stocks),
        "quote_freshness_note":"Daily candle bar may be partial during market hours; no guaranteed 1-minute or live update.",
        "indices":indices,"summary":{"fresh_green":green,"fresh_red":red,"fresh_flat_or_unavailable":len(selection)-total,
        "uptrend_count":trend_pos,"next_session_scenario":outlook,
        "warning":"Scenario derived from available daily returns, not trained news prediction."},
        "news":headlines,"matched_news":news_by_symbol,"stocks":sorted_stocks
    }
    PREVIOUS.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    day_dir=DATA/"reports"/DATE
    day_dir.mkdir(parents=True,exist_ok=True)
    snapshot=day_dir/(NOW.strftime("%H%M")+".json")
    snapshot.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    daily=DATA/"reports"/f"{DATE}.json"
    daily.parent.mkdir(exist_ok=True)
    daily.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    print(f"{STAMP} saved. {len(selection)} attempted; {len(stocks)} total stored; {green} green/{red} red. News {len(headlines)}.")
if __name__=="__main__":run()
