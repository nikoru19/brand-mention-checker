import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time

st.set_page_config(
    page_title="Citation & Brand Mention Checker",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Citation & Brand Mention Checker")
st.caption("Check if your client's brand and website are mentioned across a list of URLs.")

st.info(
    "Hey! This tool is running on Nicole's free ScraperAPI credits, so feel free to test it out. "
    "If you're planning to use it regularly or with larger batches, I'd really appreciate if you grabbed "
    "your own free API key at [scraperapi.com](https://www.scraperapi.com/), it's free, takes 2 minutes, "
    "and gives you 1,000 requests/month. Just paste your key in the field below. Thanks for trying it out! 🙌",
    icon="💡"
)

# --- API Key ---
default_key = st.secrets.get("SCRAPERAPI_KEY", "")
with st.expander("⚙️ Use your own ScraperAPI Key (optional)", expanded=not bool(default_key)):
    custom_key = st.text_input(
        "Your ScraperAPI Key",
        value="",
        type="password",
        help="Leave blank to use the default key. Get your own free key at scraperapi.com, 1,000 requests/month."
    )
api_key = custom_key.strip() if custom_key.strip() else default_key

st.divider()

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    brand_input = st.text_input(
        "Client Brand Name(s)",
        placeholder="SMEG, SMEG Shop, SMEG Shop Singapore"
    )
with col2:
    domain_input = st.text_input(
        "Client Domain",
        placeholder="smegshop.sg"
    )

urls_input = st.text_area(
    "URLs to Check (one per line, recommended 7–10)",
    height=200,
    placeholder="https://example.com/article-1\nhttps://example.com/article-2"
)

run_btn = st.button("▶  Run Check", type="primary", use_container_width=True)

# --- Session state for persistent results ---
if "results_df" not in st.session_state:
    st.session_state.results_df = None


# --- Helpers ---
def get_context(text, keyword, window=100):
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end].replace("\n", " ").strip()
    return "…" + snippet + "…"


def check_url(url, brand_variants, client_domain, api_key):
    try:
        resp = requests.get(
            "http://api.scraperapi.com",
            params={"api_key": api_key, "url": url},
            timeout=30
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" "))

        # Brand check — longest variant first to avoid double-counting substrings
        variants_sorted = sorted(brand_variants, key=len, reverse=True)
        text_lower = text.lower()
        brand_count = 0
        brand_context = ""

        for variant in variants_sorted:
            count = text_lower.count(variant.lower())
            if count:
                brand_count += count
                if not brand_context:
                    brand_context = get_context(text, variant)

        # Domain check — search raw HTML so href links are caught
        domain_clean = (
            client_domain.lower()
            .replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .rstrip("/")
        )
        domain_count = resp.text.lower().count(domain_clean)
        domain_context = get_context(text, domain_clean) if domain_count else ""

        return {
            "URL": url,
            "Brand Mentioned": "✅ Yes" if brand_count else "❌ No",
            "Mention Count": brand_count if brand_count else "—",
            "Domain Cited": "✅ Yes" if domain_count else "❌ No",
            "Citation Count": domain_count if domain_count else "—",
            "Context Snippet": brand_context or domain_context or "—",
        }

    except Exception as e:
        return {
            "URL": url,
            "Brand Mentioned": "⚠️ Error",
            "Mention Count": "—",
            "Domain Cited": "⚠️ Error",
            "Citation Count": "—",
            "Context Snippet": str(e),
        }


# --- Run ---
if run_btn:
    errors = []
    if not api_key:
        errors.append("Please enter a ScraperAPI key.")
    if not brand_input.strip():
        errors.append("Please enter at least one brand name.")
    if not domain_input.strip():
        errors.append("Please enter the client domain.")
    if not urls_input.strip():
        errors.append("Please enter at least one URL.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
        brand_variants = [b.strip() for b in brand_input.split(",") if b.strip()]
        client_domain = domain_input.strip()

        st.info(f"Checking {len(urls)} URL{'s' if len(urls) > 1 else ''}…")
        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, url in enumerate(urls):
            status.text(f"Scraping {i + 1} of {len(urls)}: {url}")
            result = check_url(url, brand_variants, client_domain, api_key)
            results.append(result)
            progress.progress((i + 1) / len(urls))
            time.sleep(0.5)

        status.empty()
        progress.empty()

        st.session_state.results_df = pd.DataFrame(results)

# --- Display results (persists until new run) ---
if st.session_state.results_df is not None:
    df = st.session_state.results_df
    st.success(f"Results — {len(df)} URL{'s' if len(df) > 1 else ''} checked.")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Brand Mentioned": st.column_config.TextColumn("Brand Mentioned", width="small"),
            "Mention Count": st.column_config.TextColumn("Count", width="small"),
            "Domain Cited": st.column_config.TextColumn("Domain Cited", width="small"),
            "Citation Count": st.column_config.TextColumn("Citations", width="small"),
            "Context Snippet": st.column_config.TextColumn("Context Snippet", width="large"),
        }
    )

    st.caption("📋 Copy table for Google Sheets — click the copy icon in the top-right of the box below, then paste directly into Sheets.")
    tsv = df.to_csv(sep="\t", index=False)
    st.code(tsv, language=None)
