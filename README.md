# Geo-News Dashboard

## Interactive News Dashboard with Auto Categorization and Summarization

### Project Overview

Today, news websites mostly show articles in a **long text format**, which makes it difficult to quickly understand what is happening and where it is happening.

This project builds an **interactive news dashboard** that automatically collects news articles, classifies them into categories, generates short summaries, and visualizes them on a **world map based on location mentioned in the news**.

Instead of reading long articles, users can quickly see:

* Latest news by category
* Short summaries of articles
* Geographic location of events
* Trending keywords in the news

The goal of this project is to **convert large text-based news data into simple and visual insights**.

---

## Features

### 1. News Collection

The application collects the latest news articles using **NewsAPI**.

For each article, the following information is extracted:

* Headline
* Article content
* Source
* Image
* Publication date

---

### 2. Automatic News Categorization

News articles are automatically classified into categories such as:

* Politics
* Sports
* Technology
* Entertainment
* Education
* Business
* Health

The classification is done using a **Machine Learning model built with TF-IDF and Naive Bayes**.

This allows the system to automatically categorize new articles.

---

### 3. News Summarization

Most news articles are long and take time to read.

To make them easier to understand, the project generates **short summaries (1–2 lines)** for each article using **NLP based extractive summarization**.

Example:

Original article → multiple paragraphs
Generated output → short bullet summary

---

### 4. Location Extraction from News

The project uses **Named Entity Recognition (NER)** to detect locations mentioned in news articles.

Example:

Article text:

> Heavy rainfall reported in Mumbai and nearby regions.

Extracted location:

* Mumbai

Libraries used:

* **spaCy**

---

### 5. Map Visualization

After extracting the locations, they are converted into **latitude and longitude coordinates using Geopy**.

The locations are displayed on an **interactive map using Folium**.

Each marker on the map represents a news event.

Clicking the marker shows:

* News headline
* Image
* Short summary
* Category

---

### 6. Trending Keywords

The system also shows **frequently occurring keywords** in news articles for each category.

This helps users quickly understand **what topics are trending**.

---

### 7. Optional Sentiment Analysis

Sentiment analysis can be applied to determine whether the news article has:

* Positive sentiment
* Neutral sentiment
* Negative sentiment

This helps understand the **overall tone of the news**.

---

## Tech Stack

**Programming Language**

Python

**Libraries**

* Flask / Streamlit
* Scikit-learn
* spaCy
* NLTK
* Newspaper3k
* Folium
* Geopy

**Tools**

* Docker
* NewsAPI

---

## Project Structure

```
geo-news-dashboard

app.py
requirements.txt
Dockerfile
README.md

data/
    dataset.csv

models/
    classifier.pkl

utils/
    fetch_news.py
    summarize.py
    classify.py
    location_extraction.py

templates/
    index.html

static/
    css/
    images/
```

---

## How to Run the Project

### 1. Clone the repository

```
git clone https://github.com/yourusername/geo-news-dashboard.git
cd geo-news-dashboard
```

---

### 2. Install dependencies

```
pip install -r requirements.txt
```

---

### 3. Download spaCy model

```
python -m spacy download en_core_web_sm
```

---

### 4. Add NewsAPI key

Create a `.env` file and add your API key:

```
NEWS_API_KEY=your_api_key
```

---

### 5. Run the application

```
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

## Docker Setup 

Build Docker image:

```
docker build -t geo-news-dashboard .
```

Run container:

```
docker run -p 5000:5000 geo-news-dashboard
```

Open:

```
http://localhost:5000
```

## Learning Outcomes
Through this project, I practiced:

* Building **NLP pipelines**
* Text classification using **machine learning**
* Extracting entities using **spaCy NER**
* Generating **automatic text summaries**
* Creating **interactive visualizations with maps**
* Deploying applications using **Docker**

## Future Improvements

Some improvements that can be added in the future:

* Transformer based summarization models
* Real-time news streaming
* Multi-language news support
* News topic clustering
* Bias comparison across news sources
