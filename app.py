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
page=st.sidebar.radio("Tools",["🌐 Market Pulse","🔎 Trade Scanner","📉 Chart & Trade Plan","🏦 Fundamentals","🧪 Backtest Lab","📰 Market News","💰 Risk Calculator","📁 CSV Data Lab","🏢 NSE Company Directory","📈 Broad Market Screener","🆕 IPO GMP Watch"])
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
    query=st.text_input("Search company name or ticker (e.g. Relaxo, RELAXO, AAPL)","RELAXO")
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
    st.header("Indian financial news")
    feeds={"Economic Times markets":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms","Mint markets":"https://www.livemint.com/rss/markets"}
    pos=["growth","beat","rally","profit","gain","upgrade"];neg=["fall","loss","cuts","crash","downgrade"]
    for name,url in feeds.items():
        st.subheader(name)
        try:
            f=feedparser.parse(url)
            if not f.entries:st.warning("RSS feed currently unavailable or restricted.")
            for item in f.entries[:8]:
                h=item.get("title","Untitled");v=sum(w in h.lower() for w in pos)-sum(w in h.lower() for w in neg)
                st.markdown(f"- [{h}]({item.get('link',url)}) · {'positive wording' if v>0 else 'negative wording' if v<0 else 'neutral wording'}")
        except Exception:st.warning("Cannot retrieve feed.")
    st.markdown("[RBI official announcements](https://www.rbi.org.in/)")
    st.info("News labels are simple word-count sentiment. A predictive historical news-impact model requires a genuine dated news archive and aligned price data. It has NOT been trained by this page.")
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
        term=st.text_input("Company name, e.g. Relaxo Footwear", "")
        matching=directory[directory.Company.str.contains(term,case=False,regex=False)|directory.Symbol.str.contains(term,case=False,regex=False)].copy() if term else directory
        st.write(f"{len(matching):,} results")
        st.dataframe(matching.head(1000),hide_index=True,use_container_width=True)
        st.download_button("Export directory CSV",directory.to_csv(index=False),"nse_company_directory.csv",mime="text/csv")
        st.info("For a chart, select the ticker (e.g. RELAXO.NS) in Chart & Trade Plan.")
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

st.divider()
st.caption("MarketPilot Ultra Free • Research only; no investment advice, no assured predictions, no paid APIs, no broker-connected trade execution.")
