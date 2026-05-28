import streamlit as st
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import base64
import html as html_lib
import time

st.set_page_config(
    page_title="Citation & Brand Mention Checker",
    page_icon="🔍",
    layout="wide"
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1100px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
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
    return "..." + snippet + "..."


def check_url(url, brand_variants, client_domain, scraper_key):
    try:
        resp = requests.get(
            "http://api.scraperapi.com",
            params={"api_key": scraper_key, "url": url},
            timeout=30
        )

        # Catch bad API key or access errors before parsing
        if resp.status_code == 401:
            raise ValueError("Invalid ScraperAPI key")
        elif resp.status_code == 403:
            raise ValueError("Access blocked by target site")
        elif resp.status_code == 429:
            raise ValueError("Rate limit reached")
        elif resp.status_code >= 500:
            raise ValueError(f"ScraperAPI server error ({resp.status_code})")

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" "))

        # Brand check — longest variant first, replace matched text with spaces
        # so shorter variants don't double-count within already-matched strings
        variants_sorted = sorted(brand_variants, key=len, reverse=True)
        working_text = text.lower()
        brand_count = 0
        brand_context = ""

        for variant in variants_sorted:
            v = variant.lower()
            count = working_text.count(v)
            if count:
                brand_count += count
                if not brand_context:
                    brand_context = get_context(text, variant)
                working_text = working_text.replace(v, " " * len(v))

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
            "Brand Mentioned": "TRUE" if brand_count else "FALSE",
            "Mention Count": brand_count,
            "Domain Cited": "TRUE" if domain_count else "FALSE",
            "Citation Count": domain_count,
            "Context Snippet": brand_context or domain_context or "",
        }

    except Exception as e:
        err_str = str(e).lower()
        if "timed out" in err_str:
            err_msg = "Request timed out"
        elif "invalid scraperapi key" in err_str:
            err_msg = "Invalid API key"
        elif "rate limit" in err_str:
            err_msg = "Rate limit reached"
        elif "blocked" in err_str:
            err_msg = "Access blocked by target site"
        else:
            err_msg = "Could not fetch page"
        return {
            "URL": url,
            "Brand Mentioned": "Error",
            "Mention Count": 0,
            "Domain Cited": "Error",
            "Citation Count": 0,
            "Context Snippet": err_msg,
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

    # Build table rows with all values HTML-escaped
    headers_html = "".join(f"<th>{html_lib.escape(col)}</th>" for col in df.columns)
    rows_html = ""
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html_lib.escape(str(v))}</td>" for v in row)
        rows_html += f"<tr>{cells}</tr>"

    tsv_b64 = base64.b64encode(df.to_csv(sep="\t", index=False).encode("utf-8")).decode("ascii")
    row_height_est = 80
    iframe_height = 55 + (len(df) * row_height_est) + 60

    components.html(f"""<!DOCTYPE html>
<html>
<head><style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Source Sans Pro", sans-serif; font-size: 13px; padding: 4px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
th {{
    background: #f0f2f6; padding: 10px 12px; text-align: left;
    font-weight: 600; border-bottom: 2px solid #dde; color: #333;
}}
td {{
    padding: 10px 12px; border-bottom: 1px solid #e6e6e6;
    vertical-align: top; word-break: break-all;
    overflow-wrap: break-word; line-height: 1.5; color: #333;
}}
tr:hover td {{ background: #f9f9fb; }}
/* Column widths */
th:nth-child(1), td:nth-child(1) {{ width: 24%; }}
th:nth-child(2), td:nth-child(2) {{ width: 11%; }}
th:nth-child(3), td:nth-child(3) {{ width: 7%; }}
th:nth-child(4), td:nth-child(4) {{ width: 11%; }}
th:nth-child(5), td:nth-child(5) {{ width: 7%; }}
th:nth-child(6), td:nth-child(6) {{ width: 40%; }}
#copyBtn {{
    margin-top: 12px; background: #ff4b4b; color: white;
    border: none; padding: 7px 16px; border-radius: 6px;
    cursor: pointer; font-size: 13px; font-family: inherit;
}}
.hint {{ color: #888; font-size: 12px; margin-left: 8px; }}
</style></head>
<body>
<table>
  <thead><tr>{headers_html}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<button id="copyBtn">Copy table</button>
<span class="hint">Paste directly into Google Sheets</span>
<script>
var data = atob("{tsv_b64}");
document.getElementById('copyBtn').addEventListener('click', function() {{
    var btn = this;
    var ta = document.createElement('textarea');
    ta.value = data;
    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    var ok = false;
    try {{ ok = document.execCommand('copy'); }} catch(e) {{}}
    document.body.removeChild(ta);
    btn.textContent = ok ? 'Copied!' : 'Press Ctrl+C';
    setTimeout(function() {{ btn.textContent = 'Copy table'; }}, 2000);
}});
</script>
</body></html>""", height=iframe_height, scrolling=False)

# --- FAQ ---
st.divider()
st.markdown("### FAQs")

with st.expander("What is this tool for?"):
    st.markdown(
        "It's a quick way to spot-check whether a client's brand or link is actually on a webpage. "
        "It helps speed up your workflow by letting you verify URLs in bulk instead of opening them "
        "one by one during citation audits."
    )

with st.expander("What problem does it solve?"):
    st.markdown(
        "The *pageMentioned* metrics in WorkDuo citation reports looks for text mentions via a general "
        "crawl, but it doesn't verify if the actual domain is cited. This tool bridges that gap so you "
        "can double-check the details and choose the best strategy for your clients.\n\n"
        "It prevents two scenarios:\n\n"
        "**1. The brand is mentioned on the page, but the citation analysis report returned FALSE** — "
        "You can skip planning outreach for a site that already features the client.\n\n"
        "**2. The report says the brand is listed, but the website isn't actually cited** — "
        "You can identify a quick-win opportunity to reach out and request a direct link."
    )

with st.expander("How do I use this tool?"):
    st.markdown(
        "Drop in your URLs, the client's brand name, and their domain. It returns a table showing "
        "whether the brand is mentioned or cited on each page.\n\n"
        "If a client uses a few different name variations, you can check them all at once by "
        "separating them with commas."
    )

with st.expander("How does it actually work, and is there anything to note?"):
    st.markdown(
        "It fetches pages using ScraperAPI, so keep in mind that some websites might occasionally "
        "block the request or time out — that's normal and down to the site, not the tool.\n\n"
        "The tool currently runs on a free account with 1,000 credits per month (1 credit per URL). "
        "If you're processing a large batch and need more volume, you can easily plug in your own "
        "API key under **Use your own ScraperAPI Key**."
    )
