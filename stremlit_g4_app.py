import pandas as pd  # ensure imported
import streamlit as st
import re
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Initialize Sentiment Intensity Analyzer
sia = SentimentIntensityAnalyzer()

def categorize_severity(score):
    """Categorize sentiment into AML severity levels."""
    if score <= -0.5:
        return "High"
    elif -0.5 < score <= -0.2:
        return "Medium"
    elif -0.2 < score < 0:
        return "Low"
    else:
        return "Not Negative"


def fetch_from_newsdata(query, from_date, to_date):
    # Placeholder for newsdata.io fetching logic
    # Replace with actual API call
    print("Fetching from newsdata.io (placeholder)...")
    return []

def fetch_from_newsapi(query, from_date, to_date):
    # Placeholder for NewsAPI fetching logic
    # Replace with actual API call
    print("Fetching from NewsAPI (placeholder)...")
    return []

def fetch_from_gnews(query, from_date, to_date):
    # Placeholder for Google News fetching logic
    # Replace with actual API call
    print("Fetching from Google News (placeholder)...")
    return []

def search_sanctions(name):
    # Placeholder for sanctions search logic
    # Replace with actual API call or data source
    print(f"Searching sanctions for {name} (placeholder)...")
    return []


def search_all(name, keywords, from_date, to_date, high_severity=False):
    # === Predefined negative keywords ===
    default_negative_keywords = [
        "fraud", "scam", "scandal", "ponzi", "laundering", "money laundering",
        "terrorist", "terrorism", "bribery", "corruption", "embezzlement",
        "sanction", "tax evasion", "tax fraud", "illegal", "crime", "criminal",
        "kickback", "smuggling", "forgery", "fake", "theft", "stolen",
        "misconduct", "collusion", "cartel", "black money", "suspicious",
        "investigation", "probe", "raid", "arrested", "charges", "indicted",
        "convicted", "lawsuit", "fine", "penalty", "regulatory action",
        "OFAC", "FATF", "FCPA", "terror financing", "shell company",
        "Iran", "Syria", "North Korea", "Cuba"
    ]

    all_keywords = list(set(keywords + default_negative_keywords))
    query = " ".join(([name] if name else []) + all_keywords)

    articles = []
    articles += fetch_from_newsdata(query, from_date, to_date)
    articles += fetch_from_newsapi(query, from_date, to_date)
    articles += fetch_from_gnews(query, from_date, to_date)

    # === Highlighter ===
    def color_highlight_terms(text, name, keywords):
        if name:
            text = re.sub(
                fr"(?i)\b({re.escape(name)})\b",
                r"<span style='background-color: #fff176; font-weight:bold;'>\1</span>",
                text
            )
        for kw in sorted(set(keywords), key=lambda s: -len(s)):
            text = re.sub(
                fr"(?i)\b({re.escape(kw)})\b",
                r"<span style='background-color: #ef9a9a; font-weight:bold;'>\1</span>",
                text
            )
        return text

    results = []
    for art in articles:
        if not isinstance(art, dict):
            continue
        text = f"{art.get('title', '')} {art.get('desc', '')}"
        name_match = name.lower() in text.lower() if name else False
        keywords_match = any(kw.lower() in text.lower() for kw in all_keywords)
        score = sia.polarity_scores(text)["compound"]
        severity = categorize_severity(score)

        # Skip positives
        if severity == "Not Negative":
            continue

        # Filter when toggle is ON
        if high_severity and severity != "High":
            continue

        snippet_html = color_highlight_terms(text, name, all_keywords)
        results.append({
            "title": art.get("title", ""),
            "source": art.get("source", ""),
            "date": art.get("date", ""),
            "snippet_html": snippet_html,
            "url": art.get("url", ""),
            "score": score,
            "severity": severity
        })

    return results


# === STREAMLIT UI ===

st.title("📰 Adverse News + Sanctions Search")

name = st.text_input("Enter Name")
keywords_input = st.text_input("Enter Additional Keywords (optional, comma separated)")
keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

st.markdown("""
> **ℹ️ Note:** This tool automatically includes negative keywords like
> *fraud, scam, laundering, corruption, sanctions, terrorism, Iran, Syria, North Korea, Cuba,* etc.
> You may add your own keywords if required.
""")

col1, col2 = st.columns([2, 1])
with col1:
    sort_option = st.selectbox(
        "Sort results by:",
        ["Newest First", "Oldest First", "Source (A-Z)"],
        index=0
    )
with col2:
    high_severity = st.toggle("Show only high-severity (🔴) results", value=False)

if st.button("Search"):
    to_date = datetime.today().strftime("%Y-%m-%d")
    from_date = (datetime.today() - timedelta(days=365 * 7)).strftime("%Y-%m-%d")

    st.subheader("🔎 Negative News Matches")
    results = search_all(name, keywords, from_date, to_date, high_severity)

    if results:
        # Sorting
        if sort_option == "Newest First":
            results.sort(key=lambda x: x.get("date", ""), reverse=True)
        elif sort_option == "Oldest First":
            results.sort(key=lambda x: x.get("date", ""))
        elif sort_option == "Source (A-Z)":
            results.sort(key=lambda x: x.get("source", "").lower())

        # Prepare DataFrame for export
        df = pd.DataFrame([{
            "Title": r["title"],
            "Source": r["source"],
            "Date": r["date"],
            "Severity": r["severity"],
            "Sentiment Score": r["score"],
            "URL": r["url"]
        } for r in results])

        # Display results
        severity_colors = {"High": "red", "Medium": "orange", "Low": "#ffcc00"}
        for r in results:
            color = severity_colors.get(r["severity"], "gray")
            badge = f"<span style='color:{color}; font-weight:bold;'>({r['severity']} Severity)</span>"
            st.markdown(
                f"**{r['title']}** {badge}  \n"
                f"_Source: {r['source']} | Date: {r['date']}_  \n"
                f"{r['snippet_html']}  \n"
                f"[Read more]({r['url']})",
                unsafe_allow_html=True
            )
            st.write('---')

        # Download results as CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name=f"adverse_news_{name or 'search'}_{datetime.today().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.write("✅ No negative news found.")

    # === Sanctions Section ===
    if name:
        st.subheader("⚠️ Sanctions List Matches")
        ofac_matches = search_sanctions(name)
        if ofac_matches:
            for m in ofac_matches:
                st.write(f"- {m['sanctioned_name']} (similarity: {m['similarity']})")
        else:
            st.write("✅ No sanctions matches found.")
