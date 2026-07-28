# Multi-Platform Customer Feedback Analytics Platform

An end-to-end, production-quality analytics application designed to extract actionable business insights from customer reviews. 

Built initially on the **Google Maps 800K Reviews** dataset, this platform features a modular architecture allowing seamless integration of additional sources like TripAdvisor, Yelp, Amazon, or the Play Store.

## 🚀 Business Objective
To help businesses automatically answer critical questions:
- Which branches perform the best?
- Which cities have the happiest customers?
- What are customers complaining about?
- Which businesses require immediate attention?
- How has customer satisfaction changed over time?

Rather than simple sentiment analysis, the platform provides an **Automated Recommendation Engine** that translates data into plain-English business directives.

## 🏗 Architecture
Follows a modular, decoupled design:
- **`config.py`**: Centralised configurations (paths, DB URI, thresholds, theme).
- **`src/preprocessing.py`**: Robust data cleaning pipeline (HTML stripping, encoding fixes, date parsing, city standardization).
- **`src/database.py`**: SQLAlchemy ORM and batch loading (SQLite for portability).
- **`src/analytics.py`**: SQL-first analytics engine with 20+ queries (CTEs, Window Functions).
- **`src/sentiment.py`**: NLP pipeline (NLTK VADER) and WordCloud generator.
- **`src/keyword_extraction.py`**: Rule-based complaint categorisation and TF-IDF theme extraction.
- **`src/recommendation_engine.py`**: Statistical insight generation.
- **`src/charts.py`**: Reusable Plotly component factory.
- **`dashboard/`**: Streamlit pages separated by domain (Executive, Ratings, Feedback, Trends, Geography, Comparison).

## 🛠 Tech Stack
- **Python 3.10+**
- **Streamlit** (UI / Dashboard)
- **SQLite + SQLAlchemy** (Data Storage & Modeling)
- **Pandas + NumPy** (Data Manipulation)
- **Plotly** (Interactive Visualizations)
- **NLTK + VADER + scikit-learn** (NLP & Sentiment)

## 📊 SQL Analytics
Includes over 30 queries utilizing advanced SQL features:
- **`GROUP BY` / `HAVING`**: Average ratings by city and category.
- **`JOINS`**: Combining 5 normalized tables.
- **Window Functions**: `LAG()` for month-over-month growth, `AVG() OVER()` for rolling averages, `NTILE()` for quartile ranking, and `DENSE_RANK()` for leaderboard positioning.
- **CTEs**: Isolating recent vs historical performance to identify declining businesses.

## 🧠 NLP Pipeline
1. **Sentiment Analysis**: VADER Lexicon scoring.
2. **Keyword Extraction**: Rule-based matching against defined complaint themes (Service, Food Quality, Waiting Time).
3. **TF-IDF**: Identifying statistically significant positive and negative terms per business.

## 💻 Installation & Usage

1. **Clone & Setup Environment**
   ```bash
   git clone <repo>
   cd CustomerFeedbackAnalytics
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Data Pipeline**
   Place your raw dataset in `data/raw/` (e.g. `google_maps_reviews.csv`).
   ```bash
   # Run the full pipeline in order
   python src/preprocessing.py
   python src/database.py
   python src/sentiment.py
   python src/keyword_extraction.py
   ```

3. **Run Dashboard**
   ```bash
   streamlit run app.py
   ```

## 📸 Dashboard Features
- **Executive Dashboard**: Top-level KPIs, overall rating gauge, and AI business insights.
- **Ratings Analytics**: Leaderboards and distribution metrics.
- **Customer Feedback**: Donut charts, complaint frequency bars, and sample review explorer.
- **Time-Series Trends**: Rolling averages, growth metrics, and sentiment shift tracking.
- **Geographic Analysis**: City performance treemaps and (optional) Mapbox scatter plotting.
- **Business Comparison**: Interactive radar charts comparing two competitors across 5 dimensions.

## 🌐 Deployment
Ready for deployment on **Streamlit Community Cloud** or **Render** via standard `requirements.txt`.

## 🔮 Future Enhancements
- Dockerization (`Dockerfile` / `docker-compose.yml`).
- Integration of `GeoPy` to reverse-geocode missing coordinates.
- Expansion of `PLATFORM_SOURCES` in `config.py` to ingest Yelp data.
- Implementation of a deep learning model (e.g., HuggingFace Transformers) to replace VADER.
