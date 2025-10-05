import streamlit as st
import requests, re, difflib
from datetime import datetime, timedelta
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

nltk.download('vader_lexicon')

# === API KEYS (replace with yours) ===
NEWSDATA_API_KEY = "pub_6f6a5665efae4a90823bc0195a8343f5"
NEWSAPI_API_KEY = "5b9afc75540c42a187ac83c8b61a165b"
GNEWS_API_KEY = "ee87c2b5d536c77dcbac6474f06497e8"

# === API Endpoints ===
NEWSDATA_ENDPOINT = "https://newsdata.io/api/1/news"
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"
GNEWS_ENDPOINT = "https://gnews.io/api/v4/search"

# Sanctions Sources
OFAC_URL = "https://sanctionslistservice.ofac.treas.gov/api/Publication"
UK_URL = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1159796/UK_Sanctions_List.json"
OPENSANCTIONS_URL = "https://api.opensanctions.org/datasets/default/entities/"

sia = SentimentIntensityAnalyzer()

def highlight_terms(text, terms):
    for term in sorted(set(terms), key=lambda s: -len(s)):
        text = re.sub(re.escape(term), f"**{term}**", text, flags=re.IGNORECASE)
    return text

def is_negative(text):
    if not text: return False
    score = sia.polarity_scores(text)
    return score["compound"] < -0.1

def fetch_ofac_list():
    try:
        resp = requests.get(OFAC_URL, timeout=30).json()
        names = []
        for entry in resp.get("SDNList", {}).get("SDNEntries", []):
            if entry.get("lastName"): names.append(entry["lastName"])
            if entry.get("firstName"): names.append(entry["firstName"])
            for aka in entry.get("akaList", {}).get("aka", []):
                if aka.get("akaName"): names.append(aka["akaName"])
        return list(set(names))
    except Exception as e:
        st.error(f"Error fetching OFAC list: {e}")
        return []

def fetch_opensanctions():
    try:
        resp = requests.get(OPENSANCTIONS_URL, timeout=30).json()
        return [e.get("properties", {}).get("name") for e in resp.get("results", []) if e.get("properties", {}).get("name")]
    except Exception as e:
        st.error(f"Error fetching OpenSanctions list: {e}")
        return []


def fetch_uk_list():
    try:
        resp = requests.get(UK_URL, timeout=30).json()
        return [x.get("Name") for x in resp if x.get("Name")]
    except Exception as e:
        st.error(f"Error fetching UK sanctions list: {e}")
        return []

def search_sanctions(name_query):
    sanctioned = fetch_ofac_list() + fetch_opensanctions() + fetch_uk_list()
    sanctioned = [s for s in sanctioned if s]
    matches = []
    for sname in sanctioned:
        ratio = difflib.SequenceMatcher(None, name_query.lower(), sname.lower()).ratio()
        if ratio >= 0.8:
            matches.append({"sanctioned_name": sname, "similarity": round(ratio,2)})
    return sorted(matches, key=lambda x: -x["similarity"])

def fetch_from_newsdata(query, from_date, to_date):
    try:
        params = {"apikey": NEWSDATA_API_KEY, "q": query, "from_date": from_date, "to_date": to_date, "language": "en"}
        r = requests.get(NEWSDATA_ENDPOINT, params=params).json()
        articles = []
        if r and r.get("results"):
            for a in r.get("results"):
                if isinstance(a, dict): # Ensure 'a' is a dictionary
                    articles.append({
                        "title": a.get("title",""),
                        "desc": a.get("description",""),
                        "date": a.get("pubDate",""),
                        "url": a.get("link",""),
                        "source":"NewsData"
                    })
        return articles
    except Exception as e:
        st.error(f"Error fetching from NewsData: {e}")
        return []

def fetch_from_newsapi(query, from_date, to_date):
    try:
        params = {"apiKey": NEWSAPI_API_KEY, "q": query, "from": from_date, "to": to_date, "language": "en"}
        r = requests.get(NEWSAPI_ENDPOINT, params=params).json()
        articles = []
        if r and r.get("articles"):
             for a in r.get("articles"):
                if isinstance(a, dict): # Ensure 'a' is a dictionary
                    articles.append({
                        "title": a.get("title",""),
                        "desc": a.get("description",""),
                        "date": a.get("publishedAt",""),
                        "url": a.get("url",""),
                        "source":"NewsAPI"
                    })
        return articles
    except Exception as e:
        st.error(f"Error fetching from NewsAPI: {e}")
        return []

def fetch_from_gnews(query, from_date, to_date):
    try:
        params = {"token": GNEWS_API_KEY, "q": query, "from": from_date, "to": to_date, "lang": "en"}
        r = requests.get(GNEWS_ENDPOINT, params=params).json()
        articles = []
        if r and r.get("articles"):
            for a in r.get("articles"):
                if isinstance(a, dict): # Ensure 'a' is a dictionary
                    articles.append({
                        "title": a.get("title",""),
                        "desc": a.get("description",""),
                        "date": a.get("publishedAt",""),
                        "url": a.get("url",""),
                        "source":"GNews"
                    })
        return articles
    except Exception as e:
        st.error(f"Error fetching from GNews: {e}")
        return []


def search_all(name, keywords, from_date, to_date):
    query = " ".join([name]+keywords if name else keywords)
    articles = []
    articles += fetch_from_newsdata(query, from_date, to_date)
    articles += fetch_from_newsapi(query, from_date, to_date)
    articles += fetch_from_gnews(query, from_date, to_date)

    results = []
    for art in articles:
        # Ensure 'art' is a dictionary before accessing keys
        if isinstance(art, dict):
            text = f"{art.get('title', '')} {art.get('desc', '')}"
            if not any(kw.lower() in text.lower() for kw in keywords): continue
            if not is_negative(text): continue
            results.append({
                "title": art.get("title", ""),
                "source": art.get("source", ""),
                "date": art.get("date", ""),
                "snippet": highlight_terms(text, keywords+[name]),
                "url": art.get("url", "")
            })
    return results

st.title("📰 Adverse News + Sanctions Search")

name = st.text_input("Enter Name")
keywords_input = st.text_input("Enter Keywords (comma separated)")
keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

if st.button("Search"):
    to_date = datetime.today().strftime("%Y-%m-%d")
    from_date = (datetime.today()-timedelta(days=365*7)).strftime("%Y-%m-%d")

    st.subheader("🔎 Negative News Matches")
    results = search_all(name, keywords, from_date, to_date)
    if results:
        for r in results:
            st.markdown(f"**{r.get('title', '')}**  \n_Source: {r.get('source', '')} | Date: {r.get('date', '')}_  \n{r.get('snippet', '')}  \n[Read more]({r.get('url', '')})")
            st.write('---')
    else:
        st.write("✅ No negative news found.")

    if name:
        st.subheader("⚠️ Sanctions List Matches")
        ofac_matches = search_sanctions(name)
        if ofac_matches:
            for m in ofac_matches:
                st.write(f"- {m.get('sanctioned_name', '')} (similarity: {m.get('similarity', '')})")
        else:
            st.write("✅ No sanctions matches found.")
