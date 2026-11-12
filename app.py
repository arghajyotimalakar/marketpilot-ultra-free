import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import feedparser
import io
import requests
import difflib

st.set_page_config(page_title="MarketPilot Ultra Free",page_icon="📈",layout="wide")
st.title("📈 MarketPilot Ultra • Free")
st.caption("Indian & global markets | Educational research | Data may be delayed or unavailable | No automatic trading")
page=st.sidebar.radio("Tools",["🌐 Market Pulse","🔎 Trade Scanner","📉 Chart & Trade Plan","🏦 Fundamentals","🧪 Backtest Lab","📰 Market News","💰 Risk Calculator","📁 CSV Data Lab","🏢 NSE Company Directory","📈 Broad Market Screener","🆕 IPO GMP Watch","📋 Daily Trading & Investment Brief","⏰ Scheduled Market Reports"])
st.sidebar.warning("Not exchange-grade live quotes. Check timestamps. No signal guarantees profit.")
@st.cache_data(ttl=300,show_spinner=False)
def history(sym,period="1y"):
    try:
        p=yf.download(sym,period=period,auto_adjust=True,threads=False,progress=False)
        if isinstance(p.columns,pd.MultiIndex):p.columns=p.columns.get_level_values(0)
        p=p.dropna(subset=["Close"])
        return p
    except Exception:return pd.DataFrame()
def compute(p):
    p=p.copy();c=p["Close"]
    for n in (20,50,200):p[f"EMA{n}"]=c.ewm(span=n,adjust=False).mean()
    d=c.diff();g=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();l=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    p["RSI"]=100-100/(1+g/l.replace(0,np.nan))
    p["MACD"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    p["MACDs"]=p.MACD.ewm(span=9,adjust=False).mean()
    tr=pd.concat([p.High-p.Low,(p.High-c.shift()).abs(),(p.Low-c.shift()).abs()],axis=1).max(axis=1)
    p["ATR"]=tr.ewm(alpha=1/14,adjust=False).mean()
    ma=c.rolling(20).mean();sd=c.rolling(20).std()
    p["BBupper"]=ma+2*sd;p["BBlower"]=ma-2*sd;p["BBwidth"]=(4*sd)/ma
    p["RVOL"]=p.Volume/p.Volume.shift(1).rolling(20).mean()
    p["Turnover"]=c*p.Volume
    return p
def trade_plan(p,capital=100000,mode="Breakout"):
    if len(p)<220:return None
    q=p.iloc[-1];atr=float(q.ATR)
    if not np.isfinite(atr) or atr<=0:return None
    entry=float(q.High*1.002 if mode=="Breakout" else q.EMA20)
    stop=entry-1.5*atr
    if stop<=0:return None
    risk=entry-stop;qty=int(min(capital//entry,(capital*.01)//risk))
    return {"Entry trigger ₹":round(entry,2),"Stop loss ₹":round(stop,2),"Take 50% at ₹":round(entry+1.5*risk,2),"Final target ₹":round(entry+3*risk,2),"Target R:R":3.0,"Maximum shares":qty}
def candle(p):
    q=p.tail(150);fig=go.Figure([go.Candlestick(x=q.index,open=q.Open,high=q.High,low=q.Low,close=q.Close,name="Candles")])
    for k in ["EMA20","EMA50","EMA200"]:
        if k in q:fig.add_trace(go.Scatter(x=q.index,y=q[k],mode="lines",name=k))
    fig.update_layout(height=500,template="plotly_dark",xaxis_rangeslider_visible=False,margin=dict(l=5,r=5,t=20,b=5))
    st.plotly_chart(fig,use_container_width=True)

@st.cache_data(ttl=86400,show_spinner=False)
def company_directory():
    """Only published directories, never fabricated listings."""
    sources=[
      ("NSE official equity listing","https://archives.nseindia.com/content/equities/EQUITY_L.csv"),
      ("Nifty Indices official Nifty 500","https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv")
    ]
    for title,url in sources:
        try:
            r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (compatible; MarketPilotResearch/1.0)","Accept":"text/csv, */*"},timeout=15)
            r.raise_for_status()
            df=pd.read_csv(io.BytesIO(r.content))
            df.columns=[str(c).strip().lower() for c in df.columns]
            symbol_col=next((c for c in df.columns if c in ("symbol","ticker","nse symbol")),None)
            name_col=next((c for c in df.columns if c in ("name of company","company name","company","name")),None)
            if symbol_col is None or name_col is None:continue
            df=df[[symbol_col,name_col]].rename(columns={symbol_col:"Symbol",name_col:"Company"})
            df=df.dropna().astype(str)
            df["Symbol"]=df.Symbol.str.strip().str.upper()
            df["Company"]=df.Company.str.strip()
            df=df[df.Symbol.str.fullmatch(r"[A-Z0-9&._-]{1,30}",na=False)]
            df=df.drop_duplicates("Symbol").reset_index(drop=True)
            if len(df)>200:return df,title
        except Exception:pass
    return pd.DataFrame(columns=["Symbol","Company"]),"No online company list currently available"

def resolve_ticker(term, directory):
    value=term.strip()
    if value.upper().endswith(".NS"):return value.upper()
    if not value:return ""
    aliases={"relaxo footwear":"RELAXO.NS","relaxo footware":"RELAXO.NS","relaxo foot wears":"RELAXO.NS","relaxo":"RELAXO.NS","tata motors":"TATAMOTORS.NS","reliance industries":"RELIANCE.NS","hdfc bank":"HDFCBANK.NS","infosys":"INFY.NS"}
    if value.casefold() in aliases:return aliases[value.casefold()]
    if value.startswith("^") or value.upper().endswith((".NS",".BO")) or value.upper() in ("AAPL","MSFT","GOOGL","TSLA","AMZN","NVDA","SPY"):return value.upper()
    if not directory.empty:
        exact=directory[(directory.Symbol.str.casefold()==value.casefold())|(directory.Company.str.casefold()==value.casefold())]
        if not exact.empty:return exact.Symbol.iloc[0]+".NS"
        match=directory[directory.Company.str.contains(value,case=False,regex=False)]
        if len(match)==1:return match.Symbol.iloc[0]+".NS"
    return value.upper()+".NS" if " " not in value else ""

@st.cache_data(ttl=900,show_spinner=False)
def batch_daily_changes(symbols):
    """Batch prices at daily resolution; never present them as live quotes."""
    results=[]
    for start in range(0,len(symbols),40):
        part=symbols[start:start+40]
        tickers=[x+".NS" for x in part]
        try:
            raw=yf.download(tickers,period="7d",interval="1d",auto_adjust=True,progress=False,threads=True,group_by="ticker")
            for symbol,ticker in zip(part,tickers):
                try:
                    x=raw[ticker] if isinstance(raw.columns,pd.MultiIndex) else raw
                    cl=x["Close"].dropna()
                    if len(cl)<2:continue
                    ch=float((cl.iloc[-1]/cl.iloc[-2]-1)*100)
                    results.append({"Symbol":symbol,"Last daily close ₹":round(float(cl.iloc[-1]),2),"Previous close ₹":round(float(cl.iloc[-2]),2),"1D gain %":round(ch,2),"As of":str(cl.index[-1])[:10]})
                except Exception:continue
        except Exception:continue
    return pd.DataFrame(results)

@st.cache_data(ttl=900,show_spinner=False)
def collect_market_headlines():
    feeds={
        "Economic Times Markets":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "Mint Markets":"https://www.livemint.com/rss/markets"
    }
    items=[]
    for name,url in feeds.items():
        try:
            feed=feedparser.parse(url)
            for e in feed.entries[:20]:
                title=str(e.get("title","")).strip()
                if title:
                    items.append({"Headline":title,"Source":name,"Published":str(e.get("published","Unknown")),"Link":str(e.get("link",url))})
        except Exception:
            continue
    return items

def news_context(symbol,company,headlines):
    parts=[v for v in [str(symbol).lower(),str(company).lower()] if v and v!="nan"]
    words=[w for w in str(company).lower().replace(" ltd","").replace(" limited","").split() if len(w)>=5 and w not in ("industries","company","corporation","private")]
    found=[]
    for item in headlines:
        h=item["Headline"].lower()
        if any(p in h for p in parts) or any(w in h for w in words[:2]):
            found.append(item)
    return found[:3]

@st.cache_data(ttl=3600,show_spinner=False)
def daily_research_universe(symbols):
    """Download a transparent sample of prices in smaller batches; failures omitted."""
    rows=[]
    for start in range(0,len(symbols),30):
        batch=symbols[start:start+30]
        tickers=[s+".NS" for s in batch]
        try:
            data=yf.download(tickers,period="1y",interval="1d",auto_adjust=True,progress=False,threads=True,group_by="ticker",timeout=25)
            for symbol,ticker in zip(batch,tickers):
                try:
                    p=data[ticker].dropna(subset=["Close"]) if isinstance(data.columns,pd.MultiIndex) else data.dropna(subset=["Close"])
                    if len(p)<210:continue
                    if not all(k in p.columns for k in ("Open","High","Low","Close","Volume")):continue
                    p=compute(p)
                    q=p.iloc[-1];prior=p.iloc[-2]
                    if any(not np.isfinite(float(q[k])) for k in ["Close","ATR","EMA20","EMA50","EMA200","RSI","MACD","MACDs"]):continue
                    avg=float(p.Turnover.tail(20).mean())/1e7
                    if not np.isfinite(avg):continue
                    mom=sum([q.Close>q.EMA20,q.EMA20>q.EMA50,q.EMA50>q.EMA200,q.MACD>q.MACDs,q.RSI>52, q.Close>prior.High])
                    rev=sum([q.RSI<42,q.Close<q.EMA20,q.MACD>q.MACDs,q.Close>q.EMA200])
                    risk=float(q.ATR)*1.5
                    if risk<=0:continue
                    trigger=float(q.High)*1.002
                    rows.append({"Symbol":symbol,"Close ₹":round(float(q.Close),2),"1D %":round((q.Close/prior.Close-1)*100,2),"20D %":round((q.Close/p.Close.iloc[-21]-1)*100,2),"Turnover ₹cr":round(avg,1),"RSI14":round(float(q.RSI),1),"RVOL":round(float(q.RVOL),2) if np.isfinite(q.RVOL) else None,"ATR14":round(float(q.ATR),2),"Trade score / 100":round(mom/6*100),"Investment trend / 100":round((int(q.Close>q.EMA200)+int(q.EMA50>q.EMA200)+int(q.Close>q.EMA50)+int(p.Close.iloc[-1]>p.Close.iloc[-63]))/4*100),"Mean reversion / 100":round(rev/4*100),"Entry trigger ₹":round(trigger,2),"Stop ₹":round(trigger-risk,2),"Take half ₹":round(trigger+1.5*risk,2),"Final target ₹":round(trigger+3*risk,2),"As of":str(p.index[-1])[:10]})
                except Exception:continue
        except Exception:continue
    return pd.DataFrame(rows)


if page=="🌐 Market Pulse":
    st.header("Overnight and India market pulse")
    symbols={"Nifty 50":"^NSEI","Sensex":"^BSESN","Bank Nifty":"^NSEBANK","India VIX":"^INDIAVIX","S&P 500":"^GSPC","Nasdaq":"^IXIC","Nikkei 225":"^N225","US 10-year yield":"^TNX","USD/INR":"INR=X","Brent crude":"BZ=F","WTI crude":"CL=F","Gold":"GC=F"}
    rows=[]
    for name,sym in symbols.items():
        p=history(sym,"3mo")
        if len(p)>21:
            c=p.Close;rows.append({"Market":name,"Symbol":sym,"Last":round(float(c.iloc[-1]),3),"1D %":round(float((c.iloc[-1]/c.iloc[-2]-1)*100),2),"5D %":round(float((c.iloc[-1]/c.iloc[-6]-1)*100),2),"20D %":round(float((c.iloc[-1]/c.iloc[-21]-1)*100),2),"As of":str(p.index[-1])[:16]})
        else:rows.append({"Market":name,"Symbol":sym,"Last":None,"1D %":None,"5D %":None,"20D %":None,"As of":"Unavailable"})
    f=pd.DataFrame(rows);st.dataframe(f,use_container_width=True,hide_index=True)
    d=f.set_index("Market");ups=sum(pd.notna(d.loc[k,"20D %"]) and d.loc[k,"20D %"]>0 for k in ["Nifty 50","S&P 500","Nasdaq"])
    v=d.loc["India VIX","5D %"];regime="Risk-On" if ups>=2 and pd.notna(v) and v<=5 else "Risk-Off" if ups<=1 and pd.notna(v) and v>5 else "Neutral/insufficient data"
    st.info(f"**Indicative regime: {regime}.** Rule: positive 20-session returns for 2/3 core indices and India VIX 5D change ≤5% = Risk-On; <=1/3 positive and VIX change >5% = Risk-Off. This heuristic is not a forecast.")
elif page=="🔎 Trade Scanner":
    st.header("NSE large-cap setup scanner")
    st.caption("Liquid-stock sampling list (not a guaranteed current Nifty 50 + Nifty Next 50 full universe).")
    syms="RELIANCE TCS HDFCBANK ICICIBANK INFY ITC BHARTIARTL SBIN LT AXISBANK KOTAKBANK HINDUNILVR BAJFINANCE MARUTI TITAN SUNPHARMA TATAMOTORS NTPC POWERGRID ONGC WIPRO ULTRACEMCO ASIANPAINT BAJAJFINSV HCLTECH ADANIENT ADANIPORTS BEL TRENT COALINDIA NESTLEIND JSWSTEEL TATASTEEL EICHERMOT GRASIM CIPLA DRREDDY".split()
    capital=st.number_input("Paper trading capital ₹",1000,100000000,100000)
    mincr=st.number_input("Minimum average daily ₹ crore turnover",0.,10000.,20.,10.)
    if st.button("Run scanner",type="primary"):
        rows=[];bar=st.progress(0)
        for i,s in enumerate(syms):
            p=history(s+".NS","2y");bar.progress((i+1)/len(syms))
            if len(p)<220:continue
            p=compute(p);q=p.iloc[-1]
            if p.Turnover.tail(20).mean()<mincr*1e7:continue
            breakout=sum([q.Close>q.EMA20,q.EMA20>q.EMA50,q.EMA50>q.EMA200,q.MACD>q.MACDs,q.RSI>55,q.RVOL>1.2])
            revert=sum([q.RSI<40,q.Close<q.BBlower,q.MACD>q.MACDs,q.Close>q.EMA200])
            mode="Breakout" if breakout/6>=revert/4 else "Mean Reversion"
            plan=trade_plan(p,capital,mode)
            if not plan:continue
            rows.append({"Symbol":s,"Setup":mode,"Rank score":round(max(breakout/6,revert/4)*100),"Close":round(float(q.Close),2),"RSI14":round(float(q.RSI),1),"RVOL":round(float(q.RVOL),2) if np.isfinite(q.RVOL) else None,"ATR":round(float(q.ATR),2),**plan,"Last candle":str(p.index[-1])[:10]})
        bar.empty()
        if rows:
            out=pd.DataFrame(rows).sort_values("Rank score",ascending=False);st.dataframe(out,use_container_width=True)
            st.download_button("Download scanner CSV",out.to_csv(index=False),"daily_scanner.csv")
        else:st.warning("No qualifying stocks, or free data is unavailable. Try again later.")
    st.caption("Entry triggers and stops are derived from the last retrieved historical daily bars; NOT instructions to execute immediately.")
elif page=="📉 Chart & Trade Plan":
    st.header("Chart, indicators and trade plan")
    directory, directory_source=company_directory()
    query=st.text_input("Search company name or ticker (e.g. Relaxo Footwear, RELAXO.NS, AAPL)","Relaxo")
    if not directory.empty and query.strip() and len(query.strip())>=2:
        hits=directory[directory.Company.str.contains(query.strip(),case=False,regex=False)|directory.Symbol.str.contains(query.strip(),case=False,regex=False)].head(25)
        if len(hits):
            opts=[f"{r.Company} — {r.Symbol}" for r in hits.itertuples(index=False)]
            selected=st.selectbox("Select matching company",["Auto-detect"]+opts)
            sym=(selected.rsplit(" — ",1)[-1]+".NS") if selected!="Auto-detect" else resolve_ticker(query,directory)
        else:sym=resolve_ticker(query,directory)
    else:sym=resolve_ticker(query,directory)
    if not sym:st.warning("No exact match found. Type its NSE symbol, e.g. RELAXO or RELAXO.NS.")
    else:st.caption(f"Resolved ticker: {sym} | Company directory: {directory_source}")
    per=st.selectbox("Price history",["6mo","1y","2y","5y"],index=2)
    p=history(sym,per) if sym else pd.DataFrame()
    if len(p)>30:
        p=compute(p);q=p.iloc[-1];a,b,c=st.columns(3)
        a.metric("Last recorded close",f"{q.Close:,.2f}");b.metric("RSI14",f"{q.RSI:.1f}");c.metric("ATR14",f"{q.ATR:.2f}")
        st.caption(f"Yahoo Finance price history; last candle {p.index[-1]}. Quote may be delayed.")
        candle(p)
        mode=st.radio("Setup",["Breakout","Mean Reversion"],horizontal=True)
        cap=st.number_input("Paper capital ₹",1000,100000000,100000)
        pl=trade_plan(p,cap,mode)
        if pl:st.dataframe(pd.DataFrame([pl]),use_container_width=True,hide_index=True)
        else:st.warning("At least 220 candles needed for the EMA200 setup.")
        st.info("Review swing trades after 5–15 trading sessions or sooner if invalidated. Partial profit at first target is a possible plan, not a predicted price/time.")
    else:st.error("Feed unavailable or insufficient candles. You can analyze imported CSV data in Data Lab.")
elif page=="🏦 Fundamentals":
    st.header("Quality + value stock research")
    tickers=st.text_input("Comma-separated stock symbols","RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS")
    if st.button("Rank fundamentals"):
        rows=[]
        for symbol in [x.strip().upper() for x in tickers.split(",") if x.strip()][:15]:
            try:
                info=yf.Ticker(symbol).info
                pe=info.get("trailingPE");fpe=info.get("forwardPE");pb=info.get("priceToBook");roe=info.get("returnOnEquity");de=info.get("debtToEquity");fcf=info.get("freeCashflow");growth=info.get("revenueGrowth");beta=info.get("beta")
                rules=[(pe,15,lambda x:100 if 0<x<15 else 65 if 0<x<25 else 20),(fpe,10,lambda x:100 if 0<x<15 else 65 if 0<x<25 else 20),(pb,10,lambda x:100 if 0<x<2 else 65 if 0<x<4 else 20),(roe,20,lambda x:100 if x>.2 else 65 if x>.12 else 20),(de,10,lambda x:100 if x<30 else 65 if x<80 else 20),(fcf,15,lambda x:100 if x>0 else 0),(growth,15,lambda x:100 if x>.15 else 65 if x>0 else 10),(beta,5,lambda x:90 if 0<x<1.2 else 45)]
                valid=[(w,fn(float(v))) for v,w,fn in rules if isinstance(v,(int,float)) and np.isfinite(v)]
                cover=sum(w for w,_ in valid)
                score=round(sum(w*s for w,s in valid)/cover,1) if cover>=55 else None
                rows.append({"Ticker":symbol,"Quality/value score":score,"Weighted coverage %":cover,"P/E":pe,"Forward P/E":fpe,"P/B":pb,"ROE":roe,"Debt/equity":de,"Free cash flow":fcf,"Revenue growth":growth,"Beta":beta})
            except Exception:rows.append({"Ticker":symbol,"Quality/value score":None,"Weighted coverage %":0})
        df=pd.DataFrame(rows).sort_values("Quality/value score",ascending=False,na_position="last")
        st.dataframe(df,use_container_width=True)
        st.download_button("Export research",df.to_csv(index=False),"fundamentals.csv")
    st.caption("Missing factors excluded and scores normalized only if coverage ≥55%. This score is a simple heuristic and does not adjust for sector differences. Investment reviews may be quarterly over 6–24 months, not guaranteed holds.")
elif page=="🧪 Backtest Lab":
    st.header("EMA trend-following historical backtest")
    symbol=st.text_input("Test symbol","RELIANCE.NS")
    capital=st.number_input("Starting capital ₹",1000,100000000,100000)
    cost=st.slider("One-way commission/slippage %",0.,2.,0.15,0.05)/100
    p=history(symbol,"3y")
    if len(p)>=220:
        p=compute(p);cash=float(capital);shares=0;buy=0;eq=[];trades=[]
        for i in range(201,len(p)):
            prev=p.iloc[i-1];today=p.iloc[i]
            desired=bool(prev.EMA20>prev.EMA50 and prev.EMA50>prev.EMA200 and prev.MACD>prev.MACDs)
            op=float(today.Open)
            if not np.isfinite(op) or op<=0:continue
            if desired and not shares:
                n=int(cash/(op*(1+cost)))
                if n:shares=n;buy=op*(1+cost);cash-=shares*buy
            elif not desired and shares:
                sell=op*(1-cost);cash+=shares*sell
                trades.append({"Closed":str(p.index[i])[:10],"PnL ₹":shares*(sell-buy),"Return %":(sell/buy-1)*100});shares=0
            eq.append((p.index[i],cash+shares*float(today.Close)))
        if eq:
            curve=pd.DataFrame(eq,columns=["Date","Equity"]).set_index("Date");rets=curve.Equity.pct_change().dropna()
            yrs=max((curve.index[-1]-curve.index[0]).days/365.25,0.01)
            cagr=(curve.Equity.iloc[-1]/capital)**(1/yrs)-1 if curve.Equity.iloc[-1]>0 else -1
            dd=(curve.Equity/curve.Equity.cummax()-1).min()
            winners=[x["PnL ₹"] for x in trades if x["PnL ₹"]>0];losers=[x["PnL ₹"] for x in trades if x["PnL ₹"]<0]
            a,b,c,d,e=st.columns(5);a.metric("CAGR",f"{cagr:.1%}");b.metric("Max DD",f"{dd:.1%}")
            c.metric("Sharpe",f"{rets.mean()/rets.std()*np.sqrt(252):.2f}" if rets.std()>0 else "N/A")
            d.metric("Win rate",f"{len(winners)/len(trades):.1%}" if trades else "N/A")
            e.metric("Profit factor",f"{sum(winners)/abs(sum(losers)):.2f}" if losers else "N/A")
            st.line_chart(curve);st.dataframe(pd.DataFrame(trades),use_container_width=True)
    else:st.warning("Need about 220+ historical daily bars; source may be unavailable.")
    st.caption("Signals calculated from yesterday close; filled at today's open. Includes cost, but no survivorship correction, tax, impact cost or overnight gap control. Backtest is not a prediction.")
elif page=="📰 Market News":
    st.header("📰 News → Commodities → Indian market impact")
    st.caption("Today's headlines and historical asset-price moves, with transparent economic explanations. Impact directions are HYPOTHESES, not forecast probabilities or trade signals.")
    asset_map={
        "Brent crude (USD/bbl)":"BZ=F",
        "WTI crude (USD/bbl)":"CL=F",
        "Gold futures (USD/oz)":"GC=F",
        "Silver futures (USD/oz)":"SI=F",
        "Copper futures (USD/lb)":"HG=F",
        "USD/INR":"INR=X",
        "India VIX":"^INDIAVIX",
        "Nifty 50":"^NSEI",
        "Bank Nifty":"^NSEBANK",
        "S&P 500":"^GSPC",
        "US 10Y yield":"^TNX"
    }
    tab_quotes,tab_news,tab_guide=st.tabs(["Commodity & market moves","News impact explorer","Understand sector sensitivity"])
    with tab_quotes:
        st.subheader("Latest available commodity and market reference prices")
        st.caption("Source: Yahoo Finance daily candles via yfinance. Values are not official MCX spot prices or licensed live NSE quotes. Market holidays and provider delays apply.")
        quote_rows=[]
        for asset,ticker in asset_map.items():
            bars=history(ticker,"3mo")
            if len(bars)>=22:
                c=bars["Close"]
                quote_rows.append({
                    "Asset / market":asset,"Source symbol":ticker,
                    "Last reference":round(float(c.iloc[-1]),3),
                    "1D %":round(float((c.iloc[-1]/c.iloc[-2]-1)*100),2),
                    "5D %":round(float((c.iloc[-1]/c.iloc[-6]-1)*100),2),
                    "20D %":round(float((c.iloc[-1]/c.iloc[-21]-1)*100),2),
                    "Last bar":str(bars.index[-1])[:16],"Source":"Yahoo Finance (possibly delayed)"
                })
            else:
                quote_rows.append({"Asset / market":asset,"Source symbol":ticker,"Last reference":None,"1D %":None,"5D %":None,"20D %":None,"Last bar":"Unavailable","Source":"Yahoo Finance (no data)"})
        st.dataframe(pd.DataFrame(quote_rows),hide_index=True,use_container_width=True)
        st.caption("To study a commodity in Chart & Trade Plan, use BZ=F (Brent), GC=F (gold), SI=F (silver), or CL=F (WTI). Futures prices and percentage changes do not establish that today's headlines caused the move.")
    impact_categories={
        "Crude oil / energy": {
            "terms":["crude","brent","wti","opec","oil price","oil output","oil supply","petroleum","refinery","refining","fuel price","iran oil","russian oil"],
            "drivers":"Supply cuts or geopolitical disruptions may raise crude prices; weak demand or extra production may lower them.",
            "beneficiaries":"Upstream producers may benefit when realized crude prices rise (e.g. ONGC, Oil India), subject to taxes and company specifics.",
            "pressured":"Oil marketing, aviation, paints, chemicals, tyres and logistics can face higher input costs if crude prices rise; pass-through matters.",
            "watch":"Brent BZ=F, WTI CL=F, USD/INR, ONGC, OIL, IOC, BPCL, HPCL, INDIGO, ASIANPAINT",
            "markets":"Indian energy, aviation, paints, chemicals, transport; inflation, INR and bond yields"
        },
        "Gold / safe-haven": {
            "terms":["gold","bullion","central bank buying","safe haven","safe-haven","gold reserves","gold import"],
            "drivers":"Falling real yields, weaker USD, central-bank buying and uncertainty may support gold; rising real yields can pressure it.",
            "beneficiaries":"Gold-linked investors may benefit from rising prices, but jewellery company profit depends on demand, volumes and margins.",
            "pressured":"Higher gold prices can reduce discretionary jewellery volumes and increase working-capital needs.",
            "watch":"Gold GC=F, USD/INR, US 10Y ^TNX, TITAN, KALYANKJIL",
            "markets":"Precious metals, jewellery, gold imports, INR, inflation and gold-linked savings"
        },
        "Silver / industrial metals": {
            "terms":["silver","photovoltaic","solar panel","industrial metal","silver demand","silver supply"],
            "drivers":"Silver combines precious-metal sensitivity with industrial demand from solar, electronics and manufacturing; volatility can exceed gold.",
            "beneficiaries":"Silver-linked holdings may gain when price rises; mining and downstream manufacturing effects depend on exposures.",
            "pressured":"Solar and electronics inputs may become more expensive if silver rises sharply; hedging and pass-through matter.",
            "watch":"Silver SI=F, Copper HG=F, Gold GC=F",
            "markets":"Silver, solar, electronics, electrical equipment, industrial metals"
        },
        "Interest rates / currency": {
            "terms":["rbi","repo rate","fed","federal reserve","interest rate","rate cut","rate hike","inflation","cpi","bond yield","rupee","dollar"],
            "drivers":"Rate decisions change bond yields and discount rates; currency moves affect imports, exporters and global commodity prices in rupees.",
            "beneficiaries":"Lower funding costs may help rate-sensitive sectors; a weaker INR can help some exporters, depending on hedges and imports.",
            "pressured":"A weaker INR raises imported energy and commodity costs; rising yields can pressure long-duration equities and borrowers.",
            "watch":"USD/INR, US 10Y ^TNX, Gold GC=F, Bank Nifty ^NSEBANK, Brent BZ=F",
            "markets":"Banks, NBFCs, real estate, IT exporters, imported energy, metals, bonds and INR"
        },
        "Geopolitics / shipping": {
            "terms":["war","missile","sanction","tariff","red sea","shipping","strait of hormuz","geopolitical","trade war","supply chain"],
            "drivers":"Shipping disruptions and sanctions can increase freight costs and risk premia in energy and metals; equity impact is scenario-dependent.",
            "beneficiaries":"Shipping/freight firms may benefit from higher rates in some situations, but their costs and routes can worsen.",
            "pressured":"Import-dependent sectors, aviation and logistics can be negatively affected by higher freight or fuel costs.",
            "watch":"Brent BZ=F, Gold GC=F, USD/INR, Nifty 50 ^NSEI",
            "markets":"Crude, safe-haven assets, transport, shipping, aviation, importers and broad equity risk sentiment"
        }
    }
    with tab_news:
        st.subheader("Current accessible financial headlines")
        headlines=collect_market_headlines()
        if not headlines:
            st.warning("Free RSS feeds did not return headlines. No news inference is possible until a source responds.")
        else:
            category_filter=st.selectbox("Focus on impact",["All"]+list(impact_categories),key="news_impact_filter")
            enriched=[]
            for item in headlines:
                title=item["Headline"].lower()
                matches=[name for name,cfg in impact_categories.items() if any(term in title for term in cfg["terms"])]
                if category_filter!="All" and category_filter not in matches:continue
                enriched.append({**item,"Impact topics":", ".join(matches) if matches else "Unclassified"})
            st.caption(f"Showing {len(enriched)} accessible headlines. Categories are keyword matching, not trained AI sentiment.")
            if enriched:
                labels=[f"{i+1}. {x['Headline'][:100]}" for i,x in enumerate(enriched)]
                idx=st.selectbox("Select a headline for impact analysis",range(len(labels)),format_func=lambda i:labels[i],key="impact_news_index")
                chosen=enriched[idx]
                st.markdown(f"**[{chosen['Headline']}]({chosen['Link']})**")
                st.caption(f"{chosen['Source']} • Published: {chosen['Published']} • Tagged: {chosen['Impact topics']}")
                matches=[name for name,cfg in impact_categories.items() if name in chosen["Impact topics"]]
                if matches:
                    for name in matches:
                        cfg=impact_categories[name]
                        with st.expander(f"Potential impact: {name}",expanded=True):
                            st.write("**Possible price mechanism:** "+cfg["drivers"])
                            st.write("**Potential beneficiaries:** "+cfg["beneficiaries"])
                            st.write("**Potential risks:** "+cfg["pressured"])
                            st.write("**Which markets/sectors:** "+cfg["markets"])
                            st.write("**Tickers to verify:** "+cfg["watch"])
                else:
                    st.info("No reliable commodity-specific keyword match. A generic headline alone is not enough to assign a positive or negative market impact.")
                st.warning("The selected news item has NOT been causally linked to the price moves above. Confirm its original timestamp, whether markets already priced it in, and relevant company filings.")
            else:st.info("No current accessible headlines matched the chosen impact topic.")
        st.markdown("**Primary-source verification:** [RBI announcements](https://www.rbi.org.in/) · [NSE corporate announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) · [EIA oil market data](https://www.eia.gov/petroleum/) · [IEA](https://www.iea.org/)")
    with tab_guide:
        st.subheader("How commodities affect Indian stocks and sectors")
        for name,cfg in impact_categories.items():
            with st.expander(name):
                st.write("**Economic link:** "+cfg["drivers"])
                st.write("**Potentially helped:** "+cfg["beneficiaries"])
                st.write("**Potentially hurt:** "+cfg["pressured"])
                st.write("**Market exposures:** "+cfg["markets"])
                st.write("**Track:** "+cfg["watch"])
        st.markdown("**Example:** A surprise OPEC supply cut can increase Brent prices. This may support upstream oil producers but create cost pressure for airlines and paint makers. The actual stock reaction depends on expectations, hedging, currency, valuations and company-specific news.")
        st.info("A genuine historical news-impact model would need timestamped event archives, careful event classification, price benchmarks, and out-of-sample testing. This version provides transparent scenario mapping and observed price returns, not a trained predictive model.")
elif page=="💰 Risk Calculator":
    st.header("1% position sizing")
    cap=st.number_input("Capital ₹",1000.,1000000000.,100000.,1000.)
    riskpct=st.slider("Account risk per trade %",0.1,2.,1.,0.1)
    entry=st.number_input("Entry ₹",0.01,10000000.,1000.)
    stop=st.number_input("Stop ₹",0.01,10000000.,970.)
    if stop>=entry:st.error("Long trade stop must be lower than entry.")
    else:
        qty=int(min(cap//entry,(cap*riskpct/100)//(entry-stop)))
        st.metric("Maximum shares",qty);st.metric("Planned stop loss risk",f"₹{qty*(entry-stop):,.2f}")
        st.write(f"Partial take-profit: **₹{entry+1.5*(entry-stop):,.2f}**; final target: **₹{entry+3*(entry-stop):,.2f}**")
        st.caption("Actual losses may exceed planned stop because of gaps/slippage.")
elif page=="📁 CSV Data Lab":
    st.header("Analyze your own candles")
    f=st.file_uploader("CSV columns: Date, Open, High, Low, Close, Volume",type="csv")
    if f is not None:
        try:
            p=pd.read_csv(f);p.columns=[c.strip().title() for c in p.columns]
            needed={"Date","Open","High","Low","Close","Volume"}
            if not needed.issubset(p.columns):st.error(f"Missing columns: {needed-set(p.columns)}")
            else:
                p.Date=pd.to_datetime(p.Date,errors="coerce")
                for c in ["Open","High","Low","Close","Volume"]:p[c]=pd.to_numeric(p[c],errors="coerce")
                p=p.dropna(subset=list(needed)).sort_values("Date").set_index("Date")
                p=compute(p);st.dataframe(p.tail(20),use_container_width=True);candle(p)
                plan=trade_plan(p)
                if plan:st.dataframe(pd.DataFrame([plan]),use_container_width=True)
        except Exception as ex:st.error(f"Could not parse CSV: {ex}")

elif page=="🏢 NSE Company Directory":
    st.header("Company-name search across published NSE lists")
    st.caption("This is a *company directory*, not a claim that all companies have reliable live price feeds.")
    directory,src=company_directory()
    st.write(f"**Source:** {src} • **Successfully retrieved symbols:** {len(directory):,}")
    if directory.empty:
        st.warning("The free server could not retrieve official listings. Upload your own NSE company list (CSV columns Symbol, Company / NAME OF COMPANY).")
        uploaded=st.file_uploader("Upload NSE company directory",type="csv")
        if uploaded:
            try:
                df=pd.read_csv(uploaded);df.columns=[c.strip().lower() for c in df.columns]
                symbol=next((c for c in df if c=="symbol"),None);name=next((c for c in df if c in ("company","company name","name of company")),None)
                if symbol and name:directory=df[[symbol,name]].rename(columns={symbol:"Symbol",name:"Company"})
                else:st.error("CSV must contain Symbol and Company or NAME OF COMPANY.")
            except Exception as e:st.error(str(e))
    if not directory.empty:
        term=st.text_input("Type any company name OR ticker — e.g. Relaxo, RELAXO, RELAXO.NS", "",key="directory_query")
        normalized=term.strip().upper().removesuffix(".NS").removesuffix(".BO")
        matching=directory[directory.Company.str.contains(normalized,case=False,regex=False)|directory.Symbol.str.contains(normalized,case=False,regex=False)].copy() if normalized else directory
        st.write(f"**{len(matching):,} matching companies**")
        if len(matching):
            matching["Choose company"]=matching["Company"]+" ("+matching["Symbol"]+".NS)"
            options=matching["Choose company"].head(100).tolist()
            choice=st.selectbox("Suggestions — select the correct company",options,key="company_suggestion")
            selected=choice.rsplit("(",1)[-1].rstrip(")")
            st.success(f"Selected ticker: {selected}")
            st.link_button("Search ticker on NSE",f"https://www.nseindia.com/get-quotes/equity?symbol={selected.removesuffix('.NS')}")
            st.caption("To view a chart, open Chart & Trade Plan and paste the selected ticker.")
        else:
            st.warning("No matching company. Try a shorter name without .NS, or search using the official NSE link below.")
            st.link_button("Open official NSE site","https://www.nseindia.com/market-data/securities-available-for-trading")
        st.dataframe(matching[["Symbol","Company"]].head(1000),hide_index=True,use_container_width=True)
        st.download_button("Export full NSE directory",directory.to_csv(index=False),"nse_company_directory.csv",mime="text/csv")
        st.caption("Directory entries identify listed companies, not verified live trading prices. ")
elif page=="📈 Broad Market Screener":
    st.header("Broad NSE universe — daily gain and liquidity research")
    directory,src=company_directory()
    st.caption(f"Listing source: {src}. Free quote feeds can reject bulk requests. This scanner DOES NOT use IPO GMP.")
    symbols=directory.Symbol.tolist()
    up=st.file_uploader("Optional: use your NSE symbol list CSV instead (Symbol column)",type="csv",key="broad_symbols")
    if up:
        try:
            z=pd.read_csv(up);z.columns=[x.strip().lower() for x in z.columns]
            symbols=z["symbol"].dropna().astype(str).str.upper().str.replace(".NS","",regex=False).unique().tolist()
        except Exception as e:st.error(f"CSV error: {e}")
    st.write(f"Universe contains **{len(symbols):,} companies**. No guarantee that all have usable price history.")
    maxn=st.slider("Symbols to fetch per scan (larger scans can be slow or rate-limited)",25,1000,100,25)
    min_gain=st.number_input("Minimum daily gain (%)",value=0.0,step=1.0)
    max_gain=st.number_input("Maximum daily gain (%)",value=200.0,step=10.0)
    st.warning("150–200% daily returns are extremely unusual for ordinary listed shares. This percentage filter is separate from IPO grey-market premium in rupees.")
    if st.button("Scan selected symbols",type="primary",disabled=not symbols):
        sample=symbols[:maxn]
        with st.spinner(f"Checking {len(sample)} daily price histories..."):
            df=batch_daily_changes(sample)
        if df.empty:st.error("Public quote source returned no usable daily closes. Reduce scan size or try later.")
        else:
            out=df[df["1D gain %"].between(min_gain,max_gain)].sort_values("1D gain %",ascending=False)
            st.write(f"**Price data available:** {len(df)}/{len(sample)} symbols. **Matches:** {len(out)}. Unavailable symbols are excluded, not assumed to have no gain.")
            st.dataframe(out,use_container_width=True,hide_index=True)
            st.download_button("Export matches",out.to_csv(index=False),"nse_daily_gainers.csv",mime="text/csv")

elif page=="🆕 IPO GMP Watch":
    st.header("IPO Grey Market Premium (GMP) — separate watchlist")
    st.info("IPO GMP is an unofficial, unregulated prelisting premium, typically quoted in ₹ per share. It does **not** apply to 1,000 ordinary already-listed stocks. There is no reliable free official NSE GMP feed.")
    st.caption("To avoid inventing GMP values, use a dated CSV from a source you trust. Prices here are user-supplied, not independently verified.")
    file=st.file_uploader("Upload IPO GMP CSV: Company, Issue Price, GMP, As Of, Source",type="csv",key="ipo_gmp")
    threshold=st.radio("Show GMP at least",["₹150","₹200"],horizontal=True)
    if file:
        try:
            x=pd.read_csv(file);required=["Company","Issue Price","GMP","As Of","Source"]
            if not all(v in x.columns for v in required):st.error("Missing required columns: "+", ".join([v for v in required if v not in x.columns]))
            else:
                x["GMP"]=pd.to_numeric(x["GMP"],errors="coerce")
                x["Issue Price"]=pd.to_numeric(x["Issue Price"],errors="coerce")
                x["Implied premium %"]=((x["GMP"]/x["Issue Price"])*100).round(1)
                x=x[x["GMP"]>=int(threshold[1:])].sort_values("GMP",ascending=False)
                st.dataframe(x,hide_index=True,use_container_width=True)
        except Exception as ex:st.error(str(ex))
    st.markdown("Official [NSE IPO information](https://www.nseindia.com/market-data/all-upcoming-issues-ipo) can be checked separately from unverified GMP reports.")


elif page=="📋 Daily Trading & Investment Brief":
    st.header("Daily Trading & Investment Research Brief")
    st.caption("On-demand, cached one hour; research uses latest available *daily* candles, not guaranteed live prices. Refresh your browser or click Recalculate after cache expires.")
    directory,source=company_directory()
    st.write(f"NSE company directory: **{len(directory):,} listings** • Source: {source}")
    st.markdown("**Official verification:** [NSE listed securities](https://www.nseindia.com/static/market-data/securities-available-for-trading) · [NSE historical reports](https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives) · [NSE corporate announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements)")
    size=st.select_slider("Number of stocks to analyze (data providers may limit large batches)",options=[30,60,100,150,200,300,500],value=100)
    turn=st.number_input("Minimum average daily turnover (₹ crore)",min_value=0.0,max_value=10000.0,value=20.0,step=10.0,key="daily_turnover")
    budget=st.number_input("Paper trading capital (₹)",1000,100000000,100000,key="daily_capital")
    st.info("Investment trend score is **price trend only**, NOT fundamental quality. Use the Fundamentals page for P/E, profitability, valuation and debt. News headline relevance is keyword matching, NOT a predictive AI model.")
    if st.button("Generate today's latest available brief",type="primary",disabled=directory.empty):
        with st.spinner("Retrieving historical daily candles. Broad free scans can be rate-limited..."):
            base=directory.Symbol.tolist()
            df=daily_research_universe(base[:size])
        st.session_state["daily_df"]=df
        st.session_state["daily_requested"]=size
        st.session_state["daily_source"]=source
    if "daily_df" in st.session_state:
        df=st.session_state["daily_df"]
        if df.empty:
            st.error("No qualifying price histories were returned. Yahoo may be blocking large requests. Try 30 symbols or use official NSE data exports.")
        else:
            n=st.session_state.get("daily_requested",len(df))
            st.caption(f"Coverage: {len(df)}/{n} attempted symbols produced usable price histories. Missing stocks do not mean negative results. Last bars are shown in the table.")
            clean=df[df["Turnover ₹cr"]>=turn].copy()
            if clean.empty:st.warning("No stocks satisfy your minimum turnover filter.")
            else:
                st.subheader("A. Trading candidates — rules-based momentum")
                ranked=clean.sort_values(["Trade score / 100","Turnover ₹cr"],ascending=False).head(25)
                st.dataframe(ranked[["Symbol","Trade score / 100","Close ₹","1D %","RSI14","RVOL","Turnover ₹cr","Entry trigger ₹","Stop ₹","Take half ₹","Final target ₹","As of"]],use_container_width=True,hide_index=True)
                st.download_button("Download trading shortlist",ranked.to_csv(index=False),"trading_shortlist.csv",key="trading_dl")
                st.caption("For these hypothetical long setups, stop distance is 1.5× ATR. Maximum shares based on 1% capital risk = floor(min(capital/entry, 0.01×capital/(entry−stop))). Reject gaps, illiquidity and stale data. No automatic trades.")
                st.subheader("B. Longer-term observation — trend shortlist")
                invests=clean.sort_values(["Investment trend / 100","20D %","Turnover ₹cr"],ascending=False).head(25)
                st.dataframe(invests[["Symbol","Investment trend / 100","Close ₹","20D %","RSI14","Turnover ₹cr","As of"]],use_container_width=True,hide_index=True)
                st.caption("Price trend is NOT proof of good valuation or future returns. Analyze business quality, debt, cash flow and earnings, then review quarterly across 6–24 months.")
                st.download_button("Download investment observation list",invests.to_csv(index=False),"investment_watchlist.csv",key="invest_dl")
                st.subheader("C. What the latest news says about these symbols")
                headlines=collect_market_headlines()
                if not headlines:st.warning("No current headlines could be retrieved from free RSS feeds. Verify directly with RBI, NSE filings, ET and Mint.")
                else:
                    universe=directory.set_index("Symbol")["Company"].to_dict()
                    found=[]
                    for sym in ranked.Symbol.head(12).tolist():
                        for h in news_context(sym,universe.get(sym,""),headlines):
                            found.append({"Symbol":sym,"Headline":h["Headline"],"Published":h["Published"],"Source":h["Source"],"URL":h["Link"]})
                    if found:st.dataframe(pd.DataFrame(found),hide_index=True,use_container_width=True,column_config={"URL":st.column_config.LinkColumn("Source link")})
                    else:st.info("No clearly matching headlines in the retrieved RSS batch. This does not mean that no material company news exists.")
                st.subheader("D. Explain an individual setup")
                sym=st.selectbox("Choose ticker to understand its score and risk",ranked.Symbol.tolist())
                row=clean[clean.Symbol==sym].iloc[0]
                stopdist=row["Entry trigger ₹"]-row["Stop ₹"]
                qty=max(0,int(min(budget//row["Entry trigger ₹"],budget*.01//stopdist))) if stopdist>0 else 0
                st.write(f"**{sym}** • Trend {row['Trade score / 100']}/100 • RSI {row['RSI14']} • Relative volume {row['RVOL']} • Daily turnover ₹{row['Turnover ₹cr']} crore")
                st.write(f"**Conditional entry:** ₹{row['Entry trigger ₹']:,} only if the price triggers and conditions remain valid. **Stop:** ₹{row['Stop ₹']:,}. **Sell half:** ₹{row['Take half ₹']:,}. **Second target:** ₹{row['Final target ₹']:,}. **Maximum paper shares:** {qty} (1% planned account risk).")
                st.caption("Review the technical setup within 5–15 trading sessions; long-term investments require a separate fundamental thesis and quarterly review. Price gaps/slippage can exceed the planned stop.")


elif page=="⏰ Scheduled Market Reports":
    st.header("⏰ Scheduled Indian Market Intelligence — IST")
    st.caption("Automatic research snapshot slots: 07:00, 09:30, 10:00, 13:00, 14:00, 15:30 and 16:30 (market-close synthesis) on weekdays. GitHub Actions timing may be delayed or skipped. Market holidays are not excluded.")
    repo_data="https://raw.githubusercontent.com/arghajyotimalakar/marketpilot-ultra-free/main/data"
    @st.cache_data(ttl=120,show_spinner=False)
    def get_scheduled_report(url):
        try:
            response=requests.get(url,timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception:return None
    report=get_scheduled_report(repo_data+"/latest.json")
    if not report:
        st.warning("No scheduled report has been published yet. Scheduled jobs start after GitHub Actions is enabled and the first job completes.")
        st.markdown("[Open the scheduled workflow](https://github.com/arghajyotimalakar/marketpilot-ultra-free/actions/workflows/scheduled-market.yml) — select **Run workflow** if you want to test it manually.")
    else:
        st.success(f"Latest completed snapshot: **{report.get('generated_at_ist','unknown')}**")
        st.info(report.get("quote_freshness_note","Public prices may be delayed."))
        st.markdown(f"**Universe source:** {report.get('universe_source','unknown')}  |  **Listed symbols available:** {report.get('directory_count',0):,}  |  **Records accumulated:** {report.get('symbols_with_record',0):,}  |  **Attempted this run:** {report.get('run_symbol_count',0)}")
        summary=report.get("summary",{})
        k1,k2,k3=st.columns(3)
        k1.metric("Green in latest completed batch",summary.get("fresh_green","n/a"))
        k2.metric("Red in latest completed batch",summary.get("fresh_red","n/a"))
        k3.metric("Uptrend in latest batch",summary.get("uptrend_count","n/a"))
        st.subheader("Next-session outlook (conditional)")
        st.info(summary.get("next_session_scenario","Not enough data to establish a scenario."))
        st.caption(summary.get("warning","This is not a forecast probability."))
        indices=report.get("indices",{})
        if indices:
            st.subheader("Indices & commodity reference moves")
            idx_rows=[{"Asset":symbol,**r} for symbol,r in indices.items()]
            st.dataframe(pd.DataFrame(idx_rows),hide_index=True,use_container_width=True)
        stocks=report.get("stocks",[])
        if stocks:
            st.subheader("Green and red NSE stocks")
            df=pd.DataFrame(stocks)
            select=st.radio("Price direction",["All","Green","Red"],horizontal=True)
            if select!="All":df=df[df.get("direction","").str.lower()==select.lower()]
            minturn=st.number_input("Minimum traded value (₹ crore)",0.0,100000.0,20.0,10.0,key="scheduled_turnover")
            if "turnover_crore" in df:df=df[pd.to_numeric(df.turnover_crore,errors="coerce").fillna(-1)>=minturn]
            if len(df):
                cols=[x for x in ["symbol","company","direction","close","daily_change_pct","alpha_20d_pct","rsi14","relative_volume","turnover_crore","trend_score","last_price_bar","last_checked_at_ist"] if x in df]
                st.dataframe(df[cols].head(500),hide_index=True,use_container_width=True)
                st.download_button("Export this stock screen",df.to_csv(index=False),"scheduled_stock_screen.csv",key="scheduled_export")
            st.caption("Green/red is daily price change only. 'Alpha 20D' here means a simple 20-session return minus the Nifty 50's 20-session return, NOT regression alpha. All stocks can have different last-updated times.")
            st.subheader("Fundamentals — real values only where source available")
            available=[]
            for x in stocks:
                fundamentals=x.get("fundamentals") or {}
                if any(v is not None for v in fundamentals.values()):
                    available.append({"symbol":x.get("symbol"),"company":x.get("company"),**fundamentals,"financials_asof":x.get("fundamentals_asof")})
            if available:
                st.dataframe(pd.DataFrame(available).head(250),hide_index=True,use_container_width=True)
                st.caption("P/E, forward P/E, P/B, ROE, debt/equity, growth, free cash flow and vendor beta are sampled slowly from Yahoo. Data can be missing or stale; company valuation measures are not synchronized to the last candle.")
            else:st.info("No company fundamental ratios available yet. These are collected slowly due to free-provider limits.")
            st.subheader("Company-related financial headlines")
            related=report.get("matched_news",{})
            if related:
                tickers=sorted(related)
                sym=st.selectbox("Company news search",tickers,key="scheduled_news")
                for h in related.get(sym,[]):
                    st.markdown(f"- [{h.get('title','Headline')}]({h.get('url','#')}) · {h.get('source','')} · {h.get('published','unknown time')}")
                st.caption("Headlines are keyword-matched; a headline does not by itself prove any stock's future reaction.")
            else:st.info("No clearly matched company headlines in the retrieved RSS batch.")
        timeline=report.get("intraday_timeline",[])
        if timeline:
            st.subheader("Today's scheduled update timeline")
            compact=[{"Time IST":x.get("snapshot_at_ist",""),"Green (batch)":x.get("fresh_green"),
                      "Red (batch)":x.get("fresh_red"),"Uptrend (batch)":x.get("uptrend_count"),
                      "Nifty reference":(x.get("indices") or {}).get("^NSEI")} for x in timeline]
            st.dataframe(pd.DataFrame(compact),hide_index=True,use_container_width=True)
            st.caption("Each scheduled batch rotates across different stocks, so green/red totals are NOT directly comparable across time slots.")
        review=report.get("day_review",{})
        if review:
            st.subheader("Combined day review")
            st.write("**First snapshot:** "+str(review.get("first_observation_ist","Unknown")))
            st.write("**Most recent snapshot:** "+str(review.get("last_observation_ist","Unknown")))
            move=review.get("nifty_change_since_first_snapshot_pct")
            if move is not None:st.metric("Nifty change since first available snapshot",f"{move:+.2f}%")
            st.write(review.get("interpretation","No scenario available."))
            st.caption(review.get("warning","Daily scenario is not a forecast."))
        st.subheader("End-of-day consolidated reports")
        today=report.get("market_date_ist","")
        if today:
            close_url=repo_data+"/reports/"+today+"/1630.json"
            close=get_scheduled_report(close_url)
            if close:
                st.success("16:30 IST end-of-day snapshot is available")
                st.write(close.get("summary",{}).get("next_session_scenario","Outlook unavailable"))
                st.caption("This is an end-of-day synthesis of observed price breadth; it is NOT a trained future-market prediction.")
            else:
                st.caption("No 16:30 IST close snapshot is available for the recorded date (yet).")
        st.subheader("Unclassified broader headlines")
        for n in report.get("news",[])[:12]:
            st.markdown(f"- [{n.get('title','Headline')}]({n.get('url','#')}) · {n.get('source','')} · {n.get('published','unknown')}")
        st.caption("All values are provided for educational research. This dashboard cannot guarantee live 1-minute data or 100% coverage of listed stocks.")

st.divider()
st.caption("MarketPilot Ultra Free • Research only; no investment advice, no assured predictions, no paid APIs, no broker-connected trade execution.")
